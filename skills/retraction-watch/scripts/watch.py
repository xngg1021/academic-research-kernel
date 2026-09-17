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


def _atomic_write_json(path, payload) -> None:
    """MW-04 / M04 / M05: 锁租期回收 + 临时写入 + 原子替换 + 重读合并。
    - 锁内写入 pid 与当前时间戳;
    - 若锁存在但超期 (30s) 或进程已不存在, 受控回收遗留锁 (M05);
    - 获取锁后, 重新读取目标文件现有最新状态并合并字典 (M04: 防止并发覆盖丢失增量)。
    """
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.with_suffix(target.suffix + '.lock')
    lock_lease_seconds = 30.0

    for _ in range(60):
        try:
            with open(lock, 'x') as f:
                f.write(f'{os.getpid()}:{time.time()}')
            break
        except FileExistsError:
            try:
                content = lock.read_text(encoding='utf-8').strip()
                if ':' in content:
                    pid_str, ts_str = content.split(':', 1)
                    lock_ts = float(ts_str)
                    if time.time() - lock_ts > lock_lease_seconds:
                        lock.unlink(missing_ok=True)
                        continue
            except Exception:
                pass
            time.sleep(0.05)
    else:
        raise RuntimeError(f'state lock timeout: {lock}')

    try:
        final_payload = dict(payload) if isinstance(payload, dict) else payload
        if isinstance(final_payload, dict) and target.is_file():
            try:
                disk_state = json.loads(target.read_text(encoding='utf-8'))
                if isinstance(disk_state, dict):
                    disk_state.update(final_payload)
                    final_payload = disk_state
            except Exception:
                pass
        tmp = target.with_suffix(target.suffix + '.tmp')
        tmp.write_text(json.dumps(final_payload, ensure_ascii=False, indent=1, sort_keys=True),
                       encoding='utf-8')
        os.replace(tmp, target)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


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
    if old_r is not None and new_r is None:
        changes.append('is_retracted: 本轮无法核验 (OpenAlex 无记录), 保留上次成功核验结果')
    elif old_r != new_r:
        changes.append(f'is_retracted: {old_r} -> {new_r}')
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
    signals, is_retracted = [], None
    try:
        data = get(f'{OPENALEX}/works/https://doi.org/{quote(doi)}?select=is_retracted')
        is_retracted = bool(data.get('is_retracted'))
    except HTTPError as exc:
        if exc.code != 404:
            raise
    data_cr = get(f'{CROSSREF}/works?filter=updates:{quote(doi, safe="")}&rows=100')
    message = data_cr.get('message') or {}
    records = message.get('items') or []
    total_results = message.get('total-results', len(records))
    truncated = bool(total_results > len(records))
    signals = update_signals_from_records(records, doi)
    return snapshot_from_signals(is_retracted, signals, truncated=truncated)


def run(watchlist_path, state_path) -> int:
    """live 入口：逐 DOI 检查，与状态文件比较，只报告变化。"""
    dois = load_watchlist(watchlist_path)
    state_file = Path(state_path).expanduser()
    state = {}
    if state_file.is_file():
        state = json.loads(state_file.read_text(encoding='utf-8'))
    reports = 0
    for doi in dois:
        new = check_doi(doi)
        old = state.get(doi)
        if new.get('truncated'):
            print(f'警告: {doi} Crossref 更新记录超过首批 100 条并被截断，未能全量核验', file=sys.stderr)
        # MW-01 / M06: 本轮无法核验且历史有成功核验结果时, 保留历史结果, 但明确标记本轮观测状态
        new['current_observation'] = new.get('is_retracted')
        if old is not None and new['is_retracted'] is None and old.get('is_retracted') is not None:
            new['is_retracted'] = old['is_retracted']
            new['verification_status'] = 'retained_prior'
        else:
            new['verification_status'] = 'verified_current'
        if old is None:
            print(f'- {doi}: 首次建档（is_retracted={new["is_retracted"]}, '
                  f'signals={new["signals"] or "无"}）')
            reports += 1
        else:
            changes = diff_snapshots(old, new)
            if changes:
                print(f'- {doi}: ' + '；'.join(changes))
                reports += 1
        state[doi] = new
    if not reports:
        print(f'无状态变化（监控 {len(dois)} 个 DOI，{date.today().isoformat()}）。')
    _atomic_write_json(state_file, state)
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
