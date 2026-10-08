"""retraction-watch：对 DOI watchlist 查撤稿/更动信号，只有状态变化才报告。

用法：
    python watch.py --self-test          # 离线自检，不触网；live 部分明确 SKIP
    python watch.py --run --watchlist <path> [--state <path>]

watchlist JSON 结构：
    {"dois": ["10.1038/nature12373", "10.1126/science.1234567"]}

信号来源（均为 live 函数，只在 --run 下发起真实 HTTPS 请求）：
- OpenAlex work 的 is_retracted 布尔字段；
- Crossref updates:<DOI> 反向查询：命中记录的 update-to 字段中指向目标 DOI 的
  撤稿/撤回/更正/表达关注条目（与 academic-source-verification/scripts/
  check_updates.py 的 update_signals 语义一致）。
状态文件记录每个 DOI 上次的状态快照；本次与上次一致则保持静默。
纯标准库，无第三方依赖。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import tempfile
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

OPENALEX = 'https://api.openalex.org'
CROSSREF = 'https://api.crossref.org/v1'


def normalize_doi(value) -> str:
    text = str(value or '').strip()
    text = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', text, flags=re.I)
    return text.strip().lower()


def load_watchlist(path) -> list:
    data = json.loads(Path(path).expanduser().read_text(encoding='utf-8'))
    dois = data.get('dois') if isinstance(data, dict) else None
    if not isinstance(dois, list):
        raise ValueError('watchlist 必须是含 dois 数组的 JSON 对象')
    return [normalize_doi(d) for d in dois if str(d).strip()]


def update_signals_from_records(records: list, target_doi: str) -> list:
    """从 Crossref 反向查询结果提取指向目标 DOI 的更新信号。

    语义与 check_updates.py 的 update_signals 一致:只看 update-to 中
    DOI 等于目标 DOI 的条目。MW-03 / M03: 信号身份优先绑定通知记录自身 DOI,
    同类型不同通知 DOI 的多次更正拥有独立身份。
    """
    target = normalize_doi(target_doi)
    found = []
    for record in records:
        notice_doi = normalize_doi(record.get('DOI') or '')
        for update in record.get('update-to') or []:
            if normalize_doi(update.get('DOI') or '') == target:
                kind = str(update.get('type') or 'update')
                source = str(update.get('source') or 'unknown')
                upd_doi = notice_doi or normalize_doi(update.get('DOI') or '') or '?'
                stamp = str(update.get('date') or update.get('timestamp') or '').strip()
                sig = f'{kind}({source}) update-doi={upd_doi}'
                if stamp:
                    sig += f' date={stamp}'
                found.append(sig)
    return sorted(set(found))


LOCK_LEASE_SECONDS = 30.0
LOCK_TIMEOUT_SECONDS = 3.0


@contextmanager
def _lock_guard(target):
    """OS lock serializes lease acquisition/recovery/release; never unlink it.

    A persistent guard inode avoids the unlink/reopen race. The OS releases its
    byte/flock ownership if a process dies, including during lease recovery.
    """
    guard = target.with_name(target.name + '.lock.guard')
    with guard.open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'\0')
            stream.flush()
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f'state guard timeout: {guard}')
                time.sleep(0.01)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _pid_is_alive(pid):
    if pid == os.getpid():
        return True
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            # Access denied is not proof of death. Invalid PID is ERROR_INVALID_PARAMETER.
            return ctypes.get_last_error() != 87
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _lease_info(lock):
    text = lock.read_text(encoding='utf-8').strip()
    try:
        data = json.loads(text)
        return int(data['pid']), float(data['created_at']), data.get('token')
    except (ValueError, TypeError, KeyError):
        try:  # v1 legacy pid:timestamp lock files remain recoverable.
            pid, stamp = text.split(':', 1)
            return int(pid), float(stamp), None
        except (ValueError, TypeError):
            return None, lock.stat().st_mtime, None


def _release_lease(target, token):
    lock = target.with_name(target.name + '.lock')
    with _lock_guard(target):
        if lock.exists() and _lease_info(lock)[2] == token:
            lock.unlink()


@contextmanager
def _state_lock(target):
    target = Path(target).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.with_name(target.name + '.lock')
    token = uuid.uuid4().hex
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        with _lock_guard(target):
            if lock.exists():
                pid, stamp, _ = _lease_info(lock)
                expired = time.time() - stamp > LOCK_LEASE_SECONDS
                # A long-lived active writer cannot be evicted by lease age.
                if expired and (pid is None or not _pid_is_alive(pid)):
                    lock.unlink()
            if not lock.exists():
                with lock.open('x', encoding='utf-8') as stream:
                    json.dump({'pid': os.getpid(), 'created_at': time.time(), 'token': token}, stream)
                break
        if time.monotonic() >= deadline:
            raise RuntimeError(f'state lock timeout: {lock}')
        time.sleep(0.01)
    try:
        yield
    finally:
        _release_lease(target, token)


def _read_json_object(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'),
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f'corrupt state file: {path}: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError(f'state file must contain an object: {path}')
    return data


def _read_state(target):
    state = _read_json_object(target)
    for doi, snapshot in state.items():
        if not isinstance(snapshot, dict):
            raise ValueError(f'invalid state snapshot for {doi}: {target}')
        for key in ('is_retracted', 'current_observation'):
            value = snapshot.get(key)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f'invalid state {key} for {doi}: {target}')
        version = snapshot.get('observation_version', 0)
        if type(version) is not int or version < 0:
            raise ValueError(f'invalid observation version for {doi}: {target}')
        confirmed = snapshot.get('confirmed_observation_version', 0)
        if type(confirmed) is not int or confirmed < 0 or confirmed > version:
            raise ValueError(f'invalid confirmed observation version for {doi}: {target}')
    return state


def _replace_json(target, payload):
    """Unique same-directory temporary file; a failed replace leaves old data intact."""
    text = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False)
    fd, temporary = tempfile.mkstemp(prefix=target.name + '.', suffix='.tmp', dir=target.parent)
    tmp = Path(temporary)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def _next_version(target, state):
    counter = target.with_name(target.name + '.sequence.json')
    reserved = _read_json_object(counter).get('last_reserved', 0)
    if type(reserved) is not int or reserved < 0:
        raise ValueError(f'invalid observation sequence: {counter}')
    version = max(reserved, max((s.get('observation_version', 0) for s in state.values()), default=0)) + 1
    _replace_json(counter, {'last_reserved': version})
    return version


def _reserve_observation(path):
    """Order observations before HTTP, under a short lock; commit order is irrelevant."""
    target = Path(path).expanduser()
    with _state_lock(target):
        return _next_version(target, _read_state(target))


def _prepare_observation(old, observed, version):
    new = dict(observed)
    current = new.get('is_retracted')
    if current is not None and not isinstance(current, bool):
        raise ValueError('is_retracted must be a boolean or None')
    new['current_observation'] = current
    new['observation_version'] = version
    new['confirmed_observation_version'] = _confirmed_version(old)
    if current is None:
        if old is not None and old.get('is_retracted') is not None:
            new['is_retracted'] = old['is_retracted']
            new['verification_status'] = 'retained_prior'
        else:
            new['verification_status'] = 'unverified'
    else:
        new['verification_status'] = 'verified_current'
        new['confirmed_observation_version'] = version
    # Unavailable Crossref is not evidence that its previous notices disappeared.
    if new.get('source_status', {}).get('crossref') not in (None, 'verified') and old:
        new['signals'] = list(old.get('signals', []))
    return new


def _confirmed_version(snapshot):
    if not snapshot or snapshot.get('is_retracted') is None:
        return 0
    if 'confirmed_observation_version' in snapshot:
        return snapshot['confirmed_observation_version']
    # Legacy verified records bind their known value to their observation.
    # Legacy retained values without an independent version are a baseline.
    if snapshot.get('current_observation', snapshot.get('is_retracted')) is not None:
        return snapshot.get('observation_version', 0)
    return 0


def _merge_observation(old, observed, version):
    current = observed.get('is_retracted')
    if current is not None and not isinstance(current, bool):
        raise ValueError('is_retracted must be a boolean or None')
    if old and version <= old.get('observation_version', 0):
        # A newer unknown observation orders the current status, but must not
        # erase valid evidence that arrives later from an earlier query. Its
        # confirmed version advances independently; current stays unknown.
        if current is not None and version > _confirmed_version(old):
            new = dict(old)
            new['is_retracted'] = current
            new['confirmed_observation_version'] = version
            if new.get('current_observation') is None:
                new['verification_status'] = 'retained_prior'
            return new, True, True
        return old, False, False
    return _prepare_observation(old, observed, version), True, False


def _commit_observation(path, doi, observed, version):
    if type(version) is not int or version < 1:
        raise ValueError('observation_version must be a positive integer')
    target = Path(path).expanduser()
    with _state_lock(target):
        state = _read_state(target)
        old = state.get(doi)
        new, applied, historical_only = _merge_observation(old, observed, version)
        if not applied:
            return {'applied': False, 'old': old, 'new': old, 'changes': []}
        changes = diff_snapshots(old, new) if old is not None else ['首次建档']
        if historical_only and changes:
            changes.append('迟到有效观测更新历史值；本轮观测仍无法核验')
        state[doi] = new
        _replace_json(target, state)
        return {'applied': True, 'historical_only': historical_only, 'old': old, 'new': new, 'changes': changes}


def _atomic_write_json(path, payload) -> None:
    """Compatibility writer accepts DOI deltas only, never a pre-query full snapshot.

    An explicit observation_version uses the same stale-write rejection as run().
    Legacy unversioned deltas are fresh writes ordered at this call's lock boundary.
    """
    if not isinstance(payload, dict):
        raise ValueError('state delta must be an object')
    target = Path(path).expanduser()
    with _state_lock(target):
        state = _read_state(target)
        for doi, observed in payload.items():
            if not isinstance(observed, dict):
                raise ValueError('state snapshot must be an object')
            version = observed.get('observation_version')
            if version is None:
                version = _next_version(target, state)
            if type(version) is not int or version < 1:
                raise ValueError('observation_version must be a positive integer')
            old = state.get(doi)
            new, applied, _ = _merge_observation(old, observed, version)
            if applied:
                state[doi] = new
        _replace_json(target, state)


def snapshot_from_signals(is_retracted, signals, truncated: bool = False) -> dict:
    """把两个来源的信号合并为可比较的状态快照。
    is_retracted 支持三态: True/False/None (None = 本轮无法核验, 不冒充阴性)。
    M02: truncated 标明是否达到上限截断。
    """
    if is_retracted is None:
        retracted = None
    elif isinstance(is_retracted, bool):
        retracted = is_retracted
    else:
        raise ValueError(f'is_retracted 必须是 JSON 布尔或 None, got {is_retracted!r}')
    res = {
        'is_retracted': retracted,
        'signals': sorted(set(signals)),
    }
    if truncated:
        res['truncated'] = True
    return res


def diff_snapshots(old: dict, new: dict) -> list:
    """逐项比较状态快照 (三态), 返回人类可读的变化列表；无变化返回空列表。"""
    changes = []
    old_r = old.get('is_retracted')
    new_r = new.get('is_retracted')
    old_current = old.get('current_observation', old_r)
    new_current = new.get('current_observation', new_r)
    if old_current is not None and new_current is None:
        suffix = '，保留上次成功核验结果' if old_r is not None else ''
        changes.append('is_retracted: 本轮无法核验' + suffix)
    elif old_current is None and new_current is not None and old_r == new_r:
        changes.append(f'is_retracted: 恢复本轮核验 ({new_current})')
    elif old_r != new_r:
        changes.append(f'is_retracted: {old_r} -> {new_r}')
    if old.get('source_status') != new.get('source_status') and new.get('source_status') is not None:
        changes.append('来源核验状态: ' + json.dumps(new['source_status'], ensure_ascii=False, sort_keys=True))
    added = sorted(set(new.get('signals', [])) - set(old.get('signals', [])))
    removed = sorted(set(old.get('signals', [])) - set(new.get('signals', [])))
    for sig in added:
        changes.append(f'新增 Crossref 更新信号: {sig}')
    for sig in removed:
        changes.append(f'消失 Crossref 更新信号: {sig}')
    return changes


def _headers() -> dict:
    headers = {'User-Agent': 'hermes-retraction-watch/1.0'}
    contact = os.environ.get('HERMES_MAILTO', '').strip()
    if contact:
        headers['User-Agent'] += f' (mailto:{contact})'
    return headers


def _parse_retry_after(value: str | None, default_delay: float) -> float:
    """支持 RFC 9110 秒数 (delta-seconds) 或 HTTP-date。"""
    if not value:
        return default_delay
    val = value.strip()
    try:
        return max(0.0, min(float(val), 30.0))
    except ValueError:
        pass
    try:
        import email.utils
        dt = email.utils.parsedate_to_datetime(val)
        now = datetime.now(timezone.utc)
        diff = (dt - now).total_seconds()
        return max(0.0, min(diff, 30.0))
    except Exception:
        return default_delay


RETRY_STATUSES = {429, 500, 502, 503, 504}


def get(url: str, timeout: int = 20) -> dict:
    """live: 真实 HTTPS GET，仅针对 429 与 5xx 有界重试；OpenAlex key 仅注入官方 HTTPS 域名。"""
    req = Request(url, headers=_headers())
    key = os.environ.get('OPENALEX_API_KEY', '').strip()
    parsed = urlsplit(url)
    if key and parsed.scheme == 'https' and (parsed.hostname or '').lower() == 'api.openalex.org':
        req.add_header('Authorization', f'Bearer {key}')
    attempts, delay = 0, 1.0
    while True:
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except HTTPError as exc:
            if exc.code not in RETRY_STATUSES or attempts >= 3:
                raise
            attempts += 1
            retry_after = exc.headers.get('Retry-After') if exc.headers else None
            wait = _parse_retry_after(retry_after, delay)
            time.sleep(wait)
            delay *= 2
        except URLError:
            attempts += 1
            if attempts >= 3:
                raise
            time.sleep(delay)
            delay *= 2


def check_doi(doi: str) -> dict:
    """live: 合并 OpenAlex is_retracted 与 Crossref updates:<DOI> 反向查询信号。

    MW-01: OpenAlex 404 (查不到记录) 时 is_retracted=None (未知三态),
    不得折叠成 False; 保留上次成功核验结果由 run 负责。
    """
    signals, is_retracted, truncated = [], None, False
    statuses, errors = {}, {}
    try:
        data = get(f'{OPENALEX}/works/https://doi.org/{quote(doi)}?select=is_retracted')
        value = data.get('is_retracted') if isinstance(data, dict) else None
        if isinstance(value, bool):
            is_retracted = value
            statuses['openalex'] = 'verified'
        else:
            statuses['openalex'] = 'invalid_response'
            errors['openalex'] = 'is_retracted missing or not a JSON boolean'
    except HTTPError as exc:
        statuses['openalex'] = 'not_found' if exc.code == 404 else 'unavailable'
        errors['openalex'] = f'HTTP {exc.code}'
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        statuses['openalex'] = 'unavailable'
        errors['openalex'] = type(exc).__name__
    try:
        data_cr = get(f'{CROSSREF}/works?filter=updates:{quote(doi, safe="")}&rows=100')
        message = data_cr.get('message') if isinstance(data_cr, dict) else None
        records = message.get('items') if isinstance(message, dict) else None
        if not isinstance(records, list):
            raise ValueError('Crossref message.items must be an array')
        total_results = message.get('total-results', len(records))
        if type(total_results) is not int or total_results < 0:
            raise ValueError('Crossref total-results must be a nonnegative integer')
        truncated = total_results > len(records)
        signals = update_signals_from_records(records, doi)
        statuses['crossref'] = 'verified'
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        statuses['crossref'] = 'unavailable'
        errors['crossref'] = f'HTTP {exc.code}' if isinstance(exc, HTTPError) else type(exc).__name__
    except (ValueError, TypeError, AttributeError) as exc:
        statuses['crossref'] = 'invalid_response'
        errors['crossref'] = type(exc).__name__
    snapshot = snapshot_from_signals(is_retracted, signals, truncated=truncated)
    snapshot['source_status'] = statuses
    if errors:
        snapshot['source_errors'] = errors
    return snapshot


def run(watchlist_path, state_path) -> int:
    """live 入口：逐 DOI 检查，与状态文件比较，只报告变化。"""
    dois = load_watchlist(watchlist_path)
    state_file = Path(state_path).expanduser()
    reports = 0
    for doi in dois:
        version = _reserve_observation(state_file)
        new = check_doi(doi)
        if new.get('truncated'):
            print(f'警告: {doi} Crossref 更新记录超过首批 100 条并被截断，未能全量核验', file=sys.stderr)
        event = _commit_observation(state_file, doi, new, version)
        if not event['applied']:
            print(f'- {doi}: 较早观测 {version} 已被新观测取代，未覆盖状态。')
            continue
        old, new = event['old'], event['new']
        if old is None:
            print(f'- {doi}: 首次建档（is_retracted={new["is_retracted"]}, '
                  f'current_observation={new["current_observation"]}, '
                  f'verification_status={new["verification_status"]}, '
                  f'signals={new["signals"] or "无"}）')
            reports += 1
        else:
            changes = event['changes']
            if changes:
                print(f'- {doi}: ' + '；'.join(changes))
                reports += 1
    if not reports:
        print(f'无状态变化（监控 {len(dois)} 个 DOI，{date.today().isoformat()}）。')
    return 0


def self_test() -> int:
    """离线自检：不触网，只验证信号合并与变化检测。"""
    fixture = Path(os.environ.get('TEMP', '/tmp')) / 'retraction-watch-fixture.json'
    fixture.write_text(json.dumps({'dois': ['HTTPS://DOI.ORG/10.1/ABC', ' 10.2/def ']}),
                       encoding='utf-8')
    assert load_watchlist(fixture) == ['10.1/abc', '10.2/def']
    fixture.unlink()
    records = [
        {'update-to': [{'DOI': '10.9/other', 'type': 'retraction', 'source': 'publisher'}]},
        {'update-to': [{'DOI': '10.1/abc', 'type': 'retraction', 'source': 'retraction-watch'}]},
        {'update-to': [{'DOI': '10.1/abc', 'type': 'correction', 'source': 'publisher'}]},
    ]
    assert update_signals_from_records(records, '10.1/abc') == [
        'correction(publisher) update-doi=10.1/abc',
        'retraction(retraction-watch) update-doi=10.1/abc']
    assert update_signals_from_records(records, '10.9/other') == [
        'retraction(publisher) update-doi=10.9/other']
    old = snapshot_from_signals(False, [])
    new = snapshot_from_signals(True, ['retraction(retraction-watch)'])
    changes = diff_snapshots(old, new)
    assert any('is_retracted' in c for c in changes), changes
    assert any('retraction(retraction-watch)' in c for c in changes), changes
    assert diff_snapshots(new, dict(new)) == [], '相同快照必须静默'
    print('SKIP live OpenAlex/Crossref checks (offline self-test)')
    print('retraction-watch self-test PASS')
    return 0


def main(argv) -> int:
    args = list(argv)
    if '--self-test' in args:
        return self_test()
    if '--run' not in args:
        print(__doc__)
        return 2
    def option(name, default=None):
        return args[args.index(name) + 1] if name in args else default
    watchlist = option('--watchlist', os.environ.get('RETRACTION_WATCHLIST'))
    if not watchlist:
        print('缺少 --watchlist <path> 或 RETRACTION_WATCHLIST 环境变量', file=sys.stderr)
        return 2
    state = option('--state', os.environ.get('RETRACTION_WATCH_STATE',
                                            str(Path(watchlist).with_suffix('.state.json'))))
    return run(watchlist, state)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
