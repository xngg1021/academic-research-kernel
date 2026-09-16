"""retraction-watch：对 DOI watchlist 查撤稿/更动信号，只有状态变化才报告。

用法：
    python watch.py --self-test          # 离线自检，不触网；live 部分明确 SKIP
    python watch.py --run --watchlist <path> [--state <path>]

watchlist JSON 结构：
    {"dois": ["10.1038/nature12373", "10.1126/science.1234567"]}

信号来源（均为 live 函数，只在 --run 下发起真实 HTTPS 请求）：
- OpenAlex work 的 is_retracted 布尔字段；
- Crossref message.relation 中含 retract 的关系（is-retraction-of 等）。
状态文件记录每个 DOI 上次的状态快照；本次与上次一致则保持静默。
纯标准库，无第三方依赖。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

OPENALEX = 'https://api.openalex.org'
CROSSREF = 'https://api.crossref.org'


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


def retraction_relations(relation: dict) -> list:
    """从 Crossref relation 字典提取撤稿相关关系名。"""
    found = []
    for key in relation or {}:
        if 'retract' in str(key).lower():
            found.append(str(key))
    return sorted(found)


def snapshot_from_signals(is_retracted, relations) -> dict:
    """把两个来源的信号合并为可比较的状态快照。"""
    return {
        'is_retracted': bool(is_retracted),
        'relations': sorted(set(relations)),
    }


def diff_snapshots(old: dict, new: dict) -> list:
    """逐项比较状态快照，返回人类可读的变化列表；无变化返回空列表。"""
    changes = []
    old_r, new_r = bool(old.get('is_retracted')), bool(new.get('is_retracted'))
    if old_r != new_r:
        changes.append(f'is_retracted: {old_r} -> {new_r}')
    added = sorted(set(new.get('relations', [])) - set(old.get('relations', [])))
    removed = sorted(set(old.get('relations', [])) - set(new.get('relations', [])))
    for rel in added:
        changes.append(f'新增 Crossref 关系: {rel}')
    for rel in removed:
        changes.append(f'消失 Crossref 关系: {rel}')
    return changes


def _headers() -> dict:
    headers = {'User-Agent': 'hermes-retraction-watch/1.0'}
    contact = os.environ.get('HERMES_MAILTO', '').strip()
    if contact:
        headers['User-Agent'] += f' (mailto:{contact})'
    return headers


def get(url: str, timeout: int = 20) -> dict:
    """live: 真实 HTTPS GET，带 429/5xx 有界重试；OpenAlex key 只发给 OpenAlex。"""
    req = Request(url, headers=_headers())
    key = os.environ.get('OPENALEX_API_KEY', '').strip()
    if key and url.startswith(OPENALEX):
        req.add_header('Authorization', f'Bearer {key}')
    attempts, delay = 0, 1.0
    while True:
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except HTTPError as exc:
            attempts += 1
            if exc.code == 401 or attempts >= 3:
                raise
            retry_after = exc.headers.get('Retry-After') if exc.headers else None
            wait = min(float(retry_after), 30.0) if retry_after else delay
            time.sleep(wait)
            delay *= 2
        except URLError:
            attempts += 1
            if attempts >= 3:
                raise
            time.sleep(delay)
            delay *= 2


def check_doi(doi: str) -> dict:
    """live: 合并 OpenAlex is_retracted 与 Crossref relation 两个信号。"""
    relations, is_retracted = [], False
    try:
        data = get(f'{OPENALEX}/works/https://doi.org/{quote(doi)}?select=is_retracted')
        is_retracted = bool(data.get('is_retracted'))
    except HTTPError as exc:
        if exc.code != 404:
            raise
    data = get(f'{CROSSREF}/works/{quote(doi, safe="")}?select=relation,type')
    msg = data.get('message') or {}
    relations = retraction_relations(msg.get('relation') or {})
    return snapshot_from_signals(is_retracted, relations)


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
        if old is None:
            print(f'- {doi}: 首次建档（is_retracted={new["is_retracted"]}, '
                  f'relations={new["relations"] or "无"}）')
            reports += 1
        else:
            changes = diff_snapshots(old, new)
            if changes:
                print(f'- {doi}: ' + '；'.join(changes))
                reports += 1
        state[doi] = new
    if not reports:
        print(f'无状态变化（监控 {len(dois)} 个 DOI，{date.today().isoformat()}）。')
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True),
                          encoding='utf-8')
    return 0


def self_test() -> int:
    """离线自检：不触网，只验证信号合并与变化检测。"""
    fixture = Path(os.environ.get('TEMP', '/tmp')) / 'retraction-watch-fixture.json'
    fixture.write_text(json.dumps({'dois': ['HTTPS://DOI.ORG/10.1/ABC', ' 10.2/def ']}),
                       encoding='utf-8')
    assert load_watchlist(fixture) == ['10.1/abc', '10.2/def']
    fixture.unlink()
    rel = {'is-retraction-of': [{'id': '10.9/x'}], 'cites': [{'id': '10.9/y'}],
           'has-preprint': [{'id': '10.9/z'}]}
    assert retraction_relations(rel) == ['is-retraction-of']
    old = snapshot_from_signals(False, [])
    new = snapshot_from_signals(True, ['is-retraction-of'])
    changes = diff_snapshots(old, new)
    assert any('is_retracted' in c for c in changes), changes
    assert any('is-retraction-of' in c for c in changes), changes
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
