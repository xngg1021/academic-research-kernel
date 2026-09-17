"""核对单篇文献在 OpenAlex 与 Crossref 的身份信息（三库交叉核对的前两库）。

离线函数解析已获取的记录并给出字段级对照；live_* 函数明确标记，实际发起网络请求。
被引数存在来源口径差异，仅记录，不用于判定文献身份。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

USER_AGENT = 'hermes-academic-skills/1.2'


def _norm_title(title) -> str:
    r"""小写、去标点、折叠空白;保留 Unicode 字母数字 (AV-03):
    西里尔、假名、重音字符等不丢失, 规则 [^\W_]+ 覆盖全部文字系统。"""
    return ' '.join(re.findall(r'[^\W_]+', (title or '').lower()))


def _norm_doi(doi) -> str:
    return (doi or '').lower().removeprefix('https://doi.org/').removeprefix('http://doi.org/')


def parse_openalex_work(record: dict) -> dict:
    """从 OpenAlex work 记录提取身份字段。"""
    source = ((record.get('primary_location') or {}).get('source') or {})
    authors = [a.get('author', {}).get('display_name') for a in record.get('authorships') or []]
    return {
        'source': 'openalex',
        'doi': _norm_doi(record.get('doi')),
        'title': record.get('title'),
        'year': record.get('publication_year'),
        'venue': source.get('display_name'),
        'authors': [a for a in authors if a],
        'cited_by_count': record.get('cited_by_count'),
        'is_retracted': record.get('is_retracted'),
        'oa_status': (record.get('open_access') or {}).get('oa_status'),
    }


def parse_crossref_work(message: dict) -> dict:
    """从 Crossref message 记录提取身份字段。"""
    year = None
    for key in ('published-print', 'published-online', 'issued'):
        parts = (message.get(key) or {}).get('date-parts')
        if parts and parts[0] and parts[0][0]:
            year = parts[0][0]
            break
    authors = []
    for author in message.get('author') or []:
        name = ' '.join(p for p in (author.get('given'), author.get('family')) if p)
        authors.append(name or author.get('name'))
    container = message.get('container-title') or []
    return {
        'source': 'crossref',
        'doi': _norm_doi(message.get('DOI')),
        'title': ' '.join(message.get('title') or []) or None,
        'year': year,
        'venue': container[0] if container else None,
        'authors': [a for a in authors if a],
        'cited_by_count': message.get('is-referenced-by-count'),
    }


def compare_works(works: list, target_doi: str = None) -> dict:
    """字段级对照两份以上已解析记录；被引数仅记录不比对。

    target_doi 提供时先做身份绑定校验: 每份记录的 DOI 必须与请求 DOI 归一
    一致, 不一致的记入 identity_binding_mismatch (AV-01: 来源互证不得在
    目标身份冲突未被拦住时通过)。
    """
    fields = {}
    for name in ('doi', 'title', 'year'):
        values = {}
        for work in works:
            value = work.get(name)
            if name == 'doi':
                value = _norm_doi(value)
            elif name == 'title':
                value = _norm_title(value)
            values[work['source']] = value
        present = [v for v in values.values() if v not in (None, '')]
        fields[name] = {
            'values': values,
            'match': len(set(present)) == 1 if len(present) > 1 else None,
        }
    binding = []
    if target_doi is not None:
        expected = _norm_doi(target_doi)
        for work in works:
            found = _norm_doi(work.get('doi'))
            if found and found != expected:
                binding.append({'source': work['source'], 'expected': expected, 'found': found})
    return {
        'fields': fields,
        'identity_binding_mismatch': binding,
        'citation_counts': {w['source']: w.get('cited_by_count') for w in works},
        'note': '被引数存在来源口径差异（收录范围不同），仅记录并标注来源，不用于判定文献身份。'
                'identity_binding_mismatch 非空表示来源记录与请求 DOI 不一致, 字段比对结果不可作为身份证据。',
    }


def live_get(url: str):
    """LIVE: 网络访问。OpenAlex 可匿名或用 OPENALEX_API_KEY；429/5xx 有界退避，不循环耗尽。"""
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


def fetch_openalex(doi: str) -> dict:
    """LIVE: 查询 OpenAlex work 记录。"""
    return live_get('https://api.openalex.org/works/https://doi.org/' + quote(doi, safe=''))


def fetch_crossref(doi: str) -> dict:
    """LIVE: 查询 Crossref message 记录。非 Crossref 注册 DOI（如 DataCite 的 arXiv DOI）可能 404。"""
    return live_get('https://api.crossref.org/works/' + quote(doi, safe=''))['message']


def _load_json_file(path: str) -> dict:
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='默认在线查询；--openalex-json/--crossref-json 用已保存记录离线核对；'
               '--offline 禁用网络（无文件的来源标记为 skipped，不推断）。')
    parser.add_argument('--doi', required=True, help='目标 DOI（裸 DOI 或 doi.org URL）')
    parser.add_argument('--openalex-json', help='已保存的 OpenAlex work JSON 文件')
    parser.add_argument('--crossref-json', help='已保存的 Crossref message JSON 文件')
    parser.add_argument('--offline', action='store_true', help='禁用一切网络请求')
    args = parser.parse_args(argv)
    _utf8_stdio()

    doi = _norm_doi(args.doi)
    sources = {}
    parsed = []
    plans = [
        ('openalex', args.openalex_json, fetch_openalex, parse_openalex_work),
        ('crossref', args.crossref_json, fetch_crossref, parse_crossref_work),
    ]
    for name, json_path, live_fetch, parser_fn in plans:
        if json_path:
            try:
                work = parser_fn(_load_json_file(json_path))
                sources[name] = {'status': 'ok', 'mode': 'offline-file', 'work': work}
                parsed.append(work)
            except (OSError, ValueError, KeyError) as error:
                sources[name] = {'status': 'failed', 'error': f'{type(error).__name__}: {error}'}
        elif args.offline:
            sources[name] = {'status': 'skipped', 'reason': 'offline mode; no input file; no result inferred'}
        else:
            try:
                work = parser_fn(live_fetch(doi))
                sources[name] = {'status': 'ok', 'mode': 'live', 'work': work}
                parsed.append(work)
            except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as error:
                sources[name] = {'status': 'failed', 'error': f'{type(error).__name__}: {error}'}

    report = {'target_doi': doi, 'sources': sources,
              'comparison': compare_works(parsed, target_doi=doi) if parsed else None}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    ok = sum(1 for s in sources.values() if s['status'] == 'ok')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
