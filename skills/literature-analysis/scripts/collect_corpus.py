"""多路候选合并：文本检索 + 算法推荐 + 主题交叉（工作流 A 的确定性合并层）。

merge_candidates 为纯离线合并：按 DOI/OpenAlex ID/标题归一合并，保留全部来源层次；
live_* 函数明确标记，实际发起网络请求（OpenAlex，可匿名或用 OPENALEX_API_KEY）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

USER_AGENT = 'hermes-academic-skills/1.2'
KNOWN_LAYERS = ('text-search', 'algorithmic-related', 'topic-cross', 'citation-pool')


def normalize_doi(doi) -> str:
    return (doi or '').strip().lower().removeprefix('https://doi.org/').removeprefix(
        'http://doi.org/').removeprefix('doi:')


def normalize_title(title) -> str:
    return ' '.join(re.findall(r'[a-z0-9]+|[一-鿿]', (title or '').lower()))


def _work_key(work: dict):
    doi = normalize_doi(work.get('doi'))
    if doi:
        return 'doi:' + doi
    openalex_id = (work.get('id') or work.get('openalex_id') or '')
    if openalex_id:
        return 'openalex:' + str(openalex_id).split('/')[-1]
    title = normalize_title(work.get('title'))
    return 'title:' + title if title else None


def merge_candidates(layers: dict) -> dict:
    """合并 {来源层次: [work, ...]}，同一候选只保留一条并累计 source_layers。

    排序：有 relevance_score 的按得分降序（概念检索命中），其余按被引数降序。
    """
    merged = {}
    order = []
    skipped = 0
    for layer, works in layers.items():
        if not isinstance(layer, str) or not layer:
            raise ValueError('layer names must be non-empty strings')
        for work in works or []:
            key = _work_key(work)
            if key is None:
                skipped += 1
                continue
            entry = merged.get(key)
            if entry is None:
                entry = {
                    'key': key,
                    'title': work.get('title'),
                    'year': work.get('publication_year') or work.get('year'),
                    'doi': normalize_doi(work.get('doi')) or None,
                    'openalex_id': str(work.get('id') or work.get('openalex_id') or '') or None,
                    'cited_by_count': work.get('cited_by_count'),
                    'relevance_score': work.get('relevance_score'),
                    'source_layers': [],
                }
                merged[key] = entry
                order.append(key)
            else:
                for field, value in (('title', work.get('title')),
                                     ('year', work.get('publication_year') or work.get('year')),
                                     ('cited_by_count', work.get('cited_by_count')),
                                     ('relevance_score', work.get('relevance_score'))):
                    if entry.get(field) is None and value is not None:
                        entry[field] = value
            if layer not in entry['source_layers']:
                entry['source_layers'].append(layer)
    candidates = [merged[key] for key in order]
    candidates.sort(key=lambda c: (c['relevance_score'] is not None,
                                   c['relevance_score'] or 0,
                                   c['cited_by_count'] or 0), reverse=True)
    return {'candidates': candidates, 'count': len(candidates), 'skipped_unidentifiable': skipped}


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


def live_search(query: str, per_page: int = 10) -> list:
    """LIVE: OpenAlex 概念搜索，按 relevance_score 降序。"""
    params = {'search': query, 'per_page': per_page, 'sort': 'relevance_score:desc',
              'select': 'id,title,publication_year,cited_by_count,doi,relevance_score'}
    return live_get('https://api.openalex.org/works?' + urlencode(params)).get('results') or []


def live_work(doi: str) -> dict:
    """LIVE: 查论文本体（related_works/topics 供算法推荐与主题交叉层使用）。"""
    select = 'id,title,publication_year,cited_by_count,doi,related_works,topics,primary_topic'
    return live_get('https://api.openalex.org/works/https://doi.org/' + quote(doi, safe='')
                    + '?' + urlencode({'select': select}))


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='离线合并：--input JSON，形如 {"text-search": [...], "algorithmic-related": [...]}；'
               '在线：--query 概念搜索（text-search 层），--related-of DOI 查本体（其 related_works '
               '为 algorithmic-related 层候选 id）。已知层次: ' + ', '.join(KNOWN_LAYERS))
    parser.add_argument('--input', help='多路候选 JSON 文件（按来源层次分组）')
    parser.add_argument('--query', help='LIVE：OpenAlex 概念搜索词')
    parser.add_argument('--per-page', type=int, default=10, help='LIVE：搜索每页数量（默认 10）')
    parser.add_argument('--related-of', help='LIVE：目标论文 DOI，取 related_works 作为算法推荐层')
    args = parser.parse_args(argv)
    _utf8_stdio()

    layers = {}
    if args.input:
        try:
            with open(args.input, encoding='utf-8') as handle:
                layers = json.load(handle)
            if not isinstance(layers, dict):
                raise ValueError('input JSON must be an object mapping layer name to work list')
        except (OSError, ValueError) as error:
            print(json.dumps({'status': 'failed', 'error': f'{type(error).__name__}: {error}'},
                             ensure_ascii=False, indent=2))
            return 1
    try:
        if args.query:
            layers['text-search'] = live_search(args.query, per_page=args.per_page)
        if args.related_of:
            work = live_work(normalize_doi(args.related_of))
            related = [{'id': rid} for rid in work.get('related_works') or []]
            layers['algorithmic-related'] = related
            layers.setdefault('target-work', [work])
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as error:
        print(json.dumps({'status': 'failed', 'error': f'{type(error).__name__}: {error}',
                          'note': '网络请求失败不等于无结果'}, ensure_ascii=False, indent=2))
        return 1
    if not layers:
        parser.error('给 --input 或 --query/--related-of 之一')

    result = merge_candidates(layers)
    result['status'] = 'ok'
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
