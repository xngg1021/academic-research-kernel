"""literature-watch：按 watchlist 查 OpenAlex/Crossref 新作品，去重后只报新增。

用法：
    python watch.py --self-test          # 离线自检，不触网；live 部分明确 SKIP
    python watch.py --run --watchlist <path> [--state <path>] [--days 7]

watchlist JSON 结构：
    {"topics": ["retrieval augmented generation"],
     "authors": ["A5023888391"],            # OpenAlex author id
     "dois": ["10.1038/nature12373"]}       # 追踪这些论文的新引用者

带 "live:" 注释的函数会发起真实 HTTPS 请求，只在 --run 下执行；
--self-test 全程离线。纯标准库，无第三方依赖。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

OPENALEX = 'https://api.openalex.org'
CROSSREF = 'https://api.crossref.org'
DEFAULT_DAYS = 7
SELECT = 'id,doi,title,publication_year,authorships,primary_location,type'


def normalize_doi(value) -> str:
    text = str(value or '').strip()
    text = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', text, flags=re.I)
    return text.strip().lower()


def load_watchlist(path) -> dict:
    data = json.loads(Path(path).expanduser().read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('watchlist 必须是 JSON 对象')
    out = {'topics': [], 'authors': [], 'dois': []}
    for key in out:
        values = data.get(key) or []
        if not isinstance(values, list):
            raise ValueError(f'watchlist.{key} 必须是数组')
        out[key] = [str(v).strip() for v in values if str(v).strip()]
    out['dois'] = [normalize_doi(d) for d in out['dois']]
    return out


def dedupe_key(item: dict) -> str:
    """去重键：优先 DOI，其次 OpenAlex id，最后归一化标题。"""
    doi = normalize_doi(item.get('doi', ''))
    if doi:
        return 'doi:' + doi
    oid = str(item.get('id') or '').strip()
    if oid:
        return 'id:' + oid
    title = re.sub(r'\s+', ' ', str(item.get('title') or '').strip().lower())
    return 'title:' + title


def filter_unseen(items, seen: set) -> list:
    fresh = []
    for item in items:
        key = dedupe_key(item)
        if key not in seen:
            fresh.append(item)
            seen.add(key)
    return fresh


def _headers() -> dict:
    headers = {'User-Agent': 'hermes-literature-watch/1.0'}
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


def _truncated(data: dict) -> bool:
    """MW-02: 首批结果条数小于 meta.count 时标记截断, 提示漏报风险。"""
    total = ((data.get('meta') or {}).get('count') or 0)
    return int(total) > len(data.get('results') or [])


def fetch_topic_works(topic: str, since: date):
    """live: OpenAlex 主题检索，from_publication_date 限定新增窗口。
    返回 (items, truncated); truncated=True 表示还有未取回的分页。"""
    params = urlencode({
        'search': topic,
        'filter': f'from_publication_date:{since.isoformat()}',
        'per_page': 100,
        'select': SELECT,
    })
    data = get(f'{OPENALEX}/works?{params}')
    return data.get('results') or [], _truncated(data)


def fetch_author_works(author_id: str, since: date):
    """live: OpenAlex 按 author id 过滤新作。返回 (items, truncated)。"""
    params = urlencode({
        'filter': f'authorships.author.id:{author_id},from_publication_date:{since.isoformat()}',
        'per_page': 100,
        'select': SELECT,
    })
    data = get(f'{OPENALEX}/works?{params}')
    return data.get('results') or [], _truncated(data)


def fetch_citing_works(doi: str, since: date):
    """live: 先取 watched DOI 的 OpenAlex id，再取窗口内的新引用者。
    返回 (items, truncated)。OpenAlex 查不到 id 时接通 Crossref 兜底
    (MW-05), 产出标记 crossref-fallback 的种子元数据记录。"""
    data = get(f'{OPENALEX}/works/https://doi.org/{quote(doi)}?select=id')
    wid = str(data.get('id') or '').rsplit('/', 1)[-1]
    if not wid:
        record = fetch_crossref_record(doi)
        if record:
            fallback = {
                'id': None,
                'doi': normalize_doi(doi),
                'title': ' '.join(record.get('title') or []) or None,
                'publication_year': _crossref_year(record),
                'source': 'crossref-fallback',
            }
            return [fallback], False
        return [], False
    params = urlencode({
        'filter': f'cites:{wid},from_publication_date:{since.isoformat()}',
        'per_page': 100,
        'select': SELECT,
    })
    data = get(f'{OPENALEX}/works?{params}')
    return data.get('results') or [], _truncated(data)


def _crossref_year(record: dict):
    """从 Crossref message 提取发表年 (MW-05 兜底转写用)。"""
    for key in ('published-print', 'published-online', 'issued'):
        parts = (record.get(key) or {}).get('date-parts')
        if parts and parts[0] and parts[0][0]:
            return parts[0][0]
    return None


def fetch_crossref_record(doi: str) -> dict:
    """live: Crossref 单条元数据，作为 OpenAlex 缺失时的兜底。"""
    data = get(f'{CROSSREF}/works/{quote(doi, safe="")}')
    return data.get('message') or {}


def collect(watchlist: dict, since: date):
    """live: 聚合三个来源的候选新作并预去重。
    返回 (items, truncations); truncations 非空表示对应来源达到首批上限。
    """
    items, seen, truncations = [], set(), []
    for topic in watchlist['topics']:
        its, tr = fetch_topic_works(topic, since)
        items.extend(its)
        if tr:
            truncations.append(f'topic={topic!r}')
    for author_id in watchlist['authors']:
        its, tr = fetch_author_works(author_id, since)
        items.extend(its)
        if tr:
            truncations.append(f'author={author_id!r}')
    for doi in watchlist['dois']:
        its, tr = fetch_citing_works(doi, since)
        # M01: 排除被监控论文自身 Crossref 兜底记录, 仅保留真实引用者
        citing_items = [it for it in its if it.get('source') != 'crossref-fallback']
        items.extend(citing_items)
        if tr:
            truncations.append(f'citing-doi={doi!r}')
    return filter_unseen(items, seen), truncations


def summarize(item: dict) -> str:
    title = str(item.get('title') or '(无标题)').strip()
    year = item.get('publication_year') or '?'
    doi = normalize_doi(item.get('doi', '')) or '无 DOI'
    return f'- [{year}] {title} ({doi})'


def _atomic_write_json(path, payload) -> None:
    """MW-04: 锁文件互斥 + 临时写入 + 原子替换, 中断/并发不留下损坏状态。"""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.with_suffix(target.suffix + '.lock')
    for _ in range(40):
        try:
            with open(lock, 'x'):
                pass
            break
        except FileExistsError:
            time.sleep(0.05)
    else:
        raise RuntimeError(f'state lock timeout: {lock}')
    try:
        tmp = target.with_suffix(target.suffix + '.tmp')
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                       encoding='utf-8')
        os.replace(tmp, target)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def run(watchlist_path, state_path, days: int) -> int:
    """live 入口：查新、跨周去重、只输出新增。"""
    watchlist = load_watchlist(watchlist_path)
    state_file = Path(state_path).expanduser()
    seen = set()
    if state_file.is_file():
        seen = set(json.loads(state_file.read_text(encoding='utf-8')))
    since = date.today() - timedelta(days=days)
    collected, truncations = collect(watchlist, since)
    if truncations:
        print(f'⚠ 完整性警告: 以下来源达到首批上限, 存在漏报风险: {truncations}')
    fresh = filter_unseen(collected, seen)
    if fresh:
        print(f'## 新增 {len(fresh)} 条（窗口 {since.isoformat()} 起）')
        for item in fresh:
            print(summarize(item))
    else:
        print(f'无新增（窗口 {since.isoformat()} 起，已见 {len(seen)} 条）。')
    _atomic_write_json(state_file, sorted(seen))
    return 0


def self_test() -> int:
    """离线自检：不触网，只验证去重、归一化与 watchlist 解析。"""
    fixture = Path(os.environ.get('TEMP', '/tmp')) / 'literature-watch-fixture.json'
    fixture.write_text(json.dumps({
        'topics': ['topic a'], 'authors': ['A1'],
        'dois': ['HTTPS://DOI.ORG/10.1/ABC']}), encoding='utf-8')
    wl = load_watchlist(fixture)
    assert wl['dois'] == ['10.1/abc'], wl
    fixture.unlink()
    items = [
        {'id': 'W1', 'doi': 'https://doi.org/10.1/x', 'title': 'Paper X'},
        {'id': 'W2', 'doi': '10.1/x', 'title': 'Paper X duplicate'},
        {'doi': '', 'title': 'No DOI paper'},
        {'doi': '', 'title': 'no  doi  paper'},
    ]
    seen = set()
    fresh = filter_unseen(items, seen)
    assert [i['title'] for i in fresh] == ['Paper X', 'No DOI paper'], fresh
    assert filter_unseen(items, seen) == [], '二次运行必须零新增'
    print('SKIP live OpenAlex/Crossref checks (offline self-test)')
    print('literature-watch self-test PASS')
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
    watchlist = option('--watchlist', os.environ.get('LITERATURE_WATCHLIST'))
    if not watchlist:
        print('缺少 --watchlist <path> 或 LITERATURE_WATCHLIST 环境变量', file=sys.stderr)
        return 2
    state = option('--state', os.environ.get('LITERATURE_WATCH_STATE',
                                            str(Path(watchlist).with_suffix('.seen.json'))))
    return run(watchlist, state, int(option('--days', DEFAULT_DAYS)))


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
