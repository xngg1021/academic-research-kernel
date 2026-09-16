"""构建语料内引文网络与引用者候选池（工作流 C 的确定性层）。

build_graph 为纯离线建图：语料内互相引用成边，语料外引用只计数；
live_citation_pool 明确标记，分页获取目标论文引用者（预算上限，记录截断）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

USER_AGENT = 'hermes-academic-skills/1.2'


def _node_id(work: dict):
    raw = work.get('id') or work.get('openalex_id')
    if raw:
        return str(raw).split('/')[-1]
    doi = (work.get('doi') or '').lower().removeprefix('https://doi.org/')
    return doi or None


def build_graph(works: list) -> dict:
    """从含 referenced_works 的 work 列表建语料内引文网络。"""
    nodes = {}
    for work in works:
        node = _node_id(work)
        if node:
            nodes[node] = {'id': node, 'title': work.get('title'),
                           'year': work.get('publication_year') or work.get('year')}
    edges = []
    external_counts = {}
    for work in works:
        src = _node_id(work)
        if not src:
            continue
        for ref in work.get('referenced_works') or []:
            rid = str(ref).split('/')[-1]
            if rid in nodes and rid != src:
                edges.append({'citing': src, 'cited': rid})
            else:
                external_counts[src] = external_counts.get(src, 0) + 1
    return {
        'nodes': list(nodes.values()),
        'edges': edges,
        'external_reference_counts': external_counts,
        'summary': {'node_count': len(nodes), 'internal_edge_count': len(edges)},
    }


def in_degrees(graph: dict) -> dict:
    """语料内被引次数（仅内部边，不等于数据库被引数）。"""
    degrees = {node['id']: 0 for node in graph['nodes']}
    for edge in graph['edges']:
        degrees[edge['cited']] = degrees.get(edge['cited'], 0) + 1
    return degrees


def live_get(url: str):
    """LIVE: 网络访问。OpenAlex 可匿名或用 OPENALEX_API_KEY；429/5xx 有界退避。"""
    headers = {'User-Agent': USER_AGENT}
    key = os.environ.get('OPENALEX_API_KEY')
    if urlsplit(url).netloc == 'api.openalex.org' and key:
        headers['Authorization'] = 'Bearer ' + key
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            retry = error.headers.get('Retry-After', '')
            delay = float(retry) if retry.isdigit() else 2 ** attempt
            if delay > 10:
                raise
            time.sleep(delay)
    return None


def live_citation_pool(wid: str, per_page: int = 25, max_pages: int = 4) -> dict:
    """LIVE: 分页获取 filter=cites:<WID> 的引用者候选池；达到预算上限标 truncated，不称全部引用者。"""
    works = []
    cursor = '*'
    truncated = False
    pages = 0
    for pages in range(1, max_pages + 1):
        params = {'filter': 'cites:' + wid, 'per_page': per_page, 'cursor': cursor,
                  'select': 'id,title,abstract_inverted_index,publication_year,doi'}
        message = live_get('https://api.openalex.org/works?' + urlencode(params))
        batch = message.get('results') or []
        works.extend(batch)
        cursor = (message.get('meta') or {}).get('next_cursor')
        if not batch or not cursor:
            break
    else:
        # 页数预算耗尽且每页均有结果：只能称部分样本。
        truncated = bool(works)
    return {'pool': works, 'fetched': len(works), 'pages_fetched': pages, 'truncated': truncated}


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='离线：--input works.json（含 referenced_works）建语料内网络；'
               '在线：--wid W... 分页获取引用者候选池（--pages 预算上限）。')
    parser.add_argument('--input', help='work JSON 列表文件（离线建图）')
    parser.add_argument('--wid', help='LIVE：目标论文 OpenAlex WID（如 W2741809807）')
    parser.add_argument('--per-page', type=int, default=25, help='LIVE：每页数量（默认 25）')
    parser.add_argument('--pages', type=int, default=4, help='LIVE：页数预算上限（默认 4）')
    args = parser.parse_args(argv)
    _utf8_stdio()

    if args.input:
        try:
            with open(args.input, encoding='utf-8') as handle:
                works = json.load(handle)
            if not isinstance(works, list):
                raise ValueError('input JSON must be a list of works')
        except (OSError, ValueError) as error:
            print(json.dumps({'status': 'failed', 'error': f'{type(error).__name__}: {error}'},
                             ensure_ascii=False, indent=2))
            return 1
        graph = build_graph(works)
        report = {'status': 'ok', 'mode': 'offline-file', 'graph': graph,
                  'in_corpus_in_degrees': in_degrees(graph),
                  'note': 'in_degrees 仅统计语料内互相引用，不等于数据库被引数'}
    elif args.wid:
        wid = args.wid.split('/')[-1]
        try:
            pool = live_citation_pool(wid, per_page=args.per_page, max_pages=args.pages)
        except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as error:
            print(json.dumps({'status': 'failed', 'error': f'{type(error).__name__}: {error}',
                              'note': '网络请求失败不等于无引用者'}, ensure_ascii=False, indent=2))
            return 1
        report = {'status': 'ok', 'mode': 'live', 'target': wid, **pool,
                  'queried_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        if report['truncated']:
            report['note'] = '达到页数预算上限，结果为部分样本，不能称全部引用者'
    else:
        parser.error('给 --input 或 --wid 之一')

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
