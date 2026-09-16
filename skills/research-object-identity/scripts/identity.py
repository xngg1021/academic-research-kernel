"""Research Object 身份归一、聚合判定与谱系建边。纯标准库，无网络依赖。

三个确定性核心：
- normalize(kind, value)：把各类标识符归一为可比较字符串；
- resolve(records)：聚合同一对象的若干候选记录，输出五态判定；
- link(a, b, kind, evidence)：在两个对象之间建 relations/lineage 边并双向回填。

五态判定（EXACT / STRONG_MATCH / CANDIDATE / CONFLICT / UNRESOLVED）全部
依据离散字段比较：本模块禁止任何置信分数与模糊评分。判定规则集中在
judge(facts)，可独立测试。

向后兼容：from_canonical_work 接受 literature-analysis 的 CanonicalWork
（鸭子类型，不 import），产出 Work 型 ResearchObject 草案。
consume_receipt 消费 schemas/evidence-receipt.schema.json 1.0 回执，
产出 source_observations 与 uncertainty。
"""
from __future__ import annotations

import copy
import re
from typing import Any

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

__all__ = [
    'VERDICTS',
    'RELATION_KINDS',
    'LINEAGE_KINDS',
    'EVIDENCE_KEYS',
    'normalize',
    'normalize_title',
    'normalize_author',
    'title_similarity',
    'judge',
    'resolve',
    'link',
    'from_canonical_work',
    'consume_receipt',
]

VERDICTS = ('EXACT', 'STRONG_MATCH', 'CANDIDATE', 'CONFLICT', 'UNRESOLVED')
RELATION_KINDS = ('cites', 'contradicts', 'replicates', 'derived_from')
LINEAGE_KINDS = ('preprint_to_vor', 'correction', 'retraction', 'version_chain')
EVIDENCE_KEYS = ('source', 'queried_at', 'match_fields', 'conflict_fields', 'human_confirmed')

# CANDIDATE 判定的标题相似度阈值：token 集合 Jaccard，离散阈值比较。
_TITLE_SIMILARITY_THRESHOLD = 0.5


def normalize(kind: str, value: Any) -> str:
    """归一单个标识符。空值返回 ''；未知 kind 原样返回去空白后的文本。"""
    text = str(value or '').strip()
    if not text:
        return ''
    if kind == 'doi':
        text = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*|doi\.org/)', '', text, flags=re.I)
        return text.strip().lower()
    if kind == 'arxiv_id':
        text = re.sub(r'^https?://arxiv\.org/(?:abs|pdf)/', '', text, flags=re.I)
        text = re.sub(r'^arxiv:\s*', '', text, flags=re.I)
        text = re.sub(r'\.pdf$', '', text, flags=re.I)
        text = re.sub(r'v\d+$', '', text, flags=re.I)
        return text.strip().lower()
    if kind == 'pmid':
        return re.sub(r'\D', '', text)
    if kind == 'pmcid':
        text = re.sub(r'^PMC\s*', '', text, flags=re.I)
        return re.sub(r'\s', '', text).upper()
    if kind == 'openalex_id':
        text = text.rstrip('/')
        if '/' in text:
            text = text.rsplit('/', 1)[-1]
        return text.strip().upper()
    if kind == 'orcid':
        text = re.sub(r'^https?://orcid\.org/', '', text, flags=re.I)
        text = re.sub(r'[^0-9Xx]', '', text)
        return text.strip().upper()
    if kind in ('isbn', 'issn'):
        return re.sub(r'[^0-9Xx]', '', text).upper()
    if kind == 'handle':
        text = re.sub(r'^https?://(?:hdl\.)?handle\.net/', '', text, flags=re.I).strip()
        return text
    if kind == 'url':
        text = text.rstrip('/').strip()
        m = re.match(r'^(https?)://([^/]+)(.*)$', text, flags=re.I)
        if m:
            text = f'{m.group(1).lower()}://{m.group(2).lower()}{m.group(3)}'
        return text
    return text


def normalize_title(text: Any) -> str:
    """标题规范文本:小写折叠、去标点(保留中日韩字符)、压缩空白。"""
    text = str(text or '').casefold()
    text = re.sub(r'[^a-z0-9\u4e00-\u9fff\uac00-\ud7af]+', ' ', text)
    return ' '.join(text.split())


def normalize_author(name: Any) -> str:
    """作者姓名规范文本：小写折叠、去标点、压缩空白。"""
    return normalize_title(name)


def _title_tokens(text: Any) -> set:
    return set(normalize_title(text).split())


def title_similarity(a: Any, b: Any) -> float:
    """两个标题的 token 集合 Jaccard 相似度。任一侧无 token 返回 0.0。"""
    ta, tb = _title_tokens(a), _title_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def judge(facts: dict) -> str:
    """五态判定，全部输入为离散布尔事实，规则按优先级排列：

    1. id_conflicts      -> CONFLICT    同一标识符类型出现两个不同值；
    2. shared_identifier -> EXACT       至少一个规范标识符跨记录一致；
    3. single_record     -> EXACT/UNRESOLVED  单记录有标识符则自洽 EXACT；
    4. title+authors 全部一致 -> STRONG_MATCH；
    5. 标题部分相似或作者重叠 -> CANDIDATE；
    6. 其余              -> UNRESOLVED  信息不足，无法判断。
    """
    if facts.get('id_conflicts'):
        return 'CONFLICT'
    if facts.get('shared_identifier'):
        return 'EXACT'
    if facts.get('single_record'):
        return 'EXACT' if facts.get('has_identifier') else 'UNRESOLVED'
    if facts.get('title_all_equal') and facts.get('authors_all_equal'):
        return 'STRONG_MATCH'
    if facts.get('title_similar') or facts.get('author_overlap'):
        return 'CANDIDATE'
    return 'UNRESOLVED'


def _record_identifiers(record: dict) -> list:
    """提取记录的 (kind, raw, normalized) 三元组;normalized 一律经 normalize 重算。"""
    out = []
    for item in record.get('identifiers') or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get('type') or '').strip()
        raw = str(item.get('value') or '').strip()
        if raw:
            norm = normalize(kind, raw)
        else:
            carried = str(item.get('normalized') or '').strip()
            norm = normalize(kind, carried)
        if kind and norm:
            out.append((kind, raw or norm, norm))
    return out


def _authors_of(record: dict) -> list:
    return [normalize_author(a) for a in record.get('authors') or [] if str(a).strip()]


def resolve(records: list) -> dict:
    """聚合同一对象的若干候选记录，输出判定结果。

    每条记录是 dict：identifiers[{type,value}] 加可选 title/authors/year/
    source/queried_at/object_type。输出 dict 含 object_type、
    merged_identifiers、verdict（五态之一）、match_fields、conflict_fields、
    sources、human_confirmed（初始 False）。
    """
    records = [r for r in (records or []) if isinstance(r, dict)]
    result = {
        'object_type': 'Work',
        'merged_identifiers': [],
        'verdict': 'UNRESOLVED',
        'match_fields': [],
        'conflict_fields': [],
        'sources': [],
        'uncertainty': [],
        'human_confirmed': False,
    }
    for r in records:
        if r.get('source'):
            result['sources'].append({'source': r['source'], 'queried_at': r.get('queried_at'),
                                      'status': 'ok'})
    if not records:
        return result
    seen_types = {str(r.get('object_type') or '') for r in records}
    seen_types.discard('')
    if len(seen_types) > 1:
        result['conflict_fields'].append('object_type')
        result['uncertainty'].append({'item': 'object_type disagreement',
                                      'kind': 'object_type_conflict', 'needs_human': True})
        result['object_type'] = sorted(seen_types)[0]
    elif seen_types:
        result['object_type'] = sorted(seen_types)[0]

    by_kind: dict = {}
    per_record_pairs = []
    for r in records:
        pairs = _record_identifiers(r)
        per_record_pairs.append({(k, n) for k, _, n in pairs})
        for kind, raw, norm in pairs:
            by_kind.setdefault(kind, {}).setdefault(norm, set()).add(raw)

    conflict_fields = sorted(kind for kind, values in by_kind.items() if len(values) > 1)
    for kind in sorted(by_kind):
        for norm in sorted(by_kind[kind]):
            result['merged_identifiers'].append(
                {'type': kind, 'value': sorted(by_kind[kind][norm])[0], 'normalized': norm})

    pair_counts: dict = {}
    for pairs in per_record_pairs:
        for pair in pairs:
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
    shared_kinds = sorted({k for (k, _), c in pair_counts.items() if c >= 2})

    titles = [normalize_title(r.get('title')) for r in records]
    authors = [_authors_of(r) for r in records]
    years = [str(r.get('year') or '') for r in records]

    title_all = all(titles) and len(set(titles)) == 1
    authors_all = all(authors) and all(set(a) == set(authors[0]) for a in authors)
    year_all = all(years) and len(set(years)) == 1

    match_fields = list(shared_kinds)
    if title_all:
        match_fields.append('title')
    elif len([t for t in titles if t]) > 1 and len({t for t in titles if t}) > 1:
        conflict_fields.append('title')
    if authors_all:
        match_fields.append('authors')
    if year_all:
        match_fields.append('year')
    elif len([y for y in years if y]) > 1 and len({y for y in years if y}) > 1:
        conflict_fields.append('year')

    title_similar = any(
        title_similarity(titles[i], titles[j]) >= _TITLE_SIMILARITY_THRESHOLD
        for i in range(len(titles)) for j in range(i + 1, len(titles)))
    author_overlap = any(
        set(authors[i]) & set(authors[j])
        for i in range(len(authors)) for j in range(i + 1, len(authors)))

    facts = {
        'id_conflicts': bool(conflict_fields) and any(k in conflict_fields for k in by_kind),
        'shared_identifier': bool(shared_kinds),
        'single_record': len(records) == 1,
        'has_identifier': bool(per_record_pairs and per_record_pairs[0]),
        'title_all_equal': title_all,
        'authors_all_equal': authors_all,
        'title_similar': title_similar,
        'author_overlap': author_overlap,
    }
    result['verdict'] = judge(facts)
    result['match_fields'] = sorted(set(match_fields))
    result['conflict_fields'] = sorted(set(conflict_fields) | set(result['conflict_fields']))
    if result['verdict'] == 'EXACT' and result['conflict_fields']:
        result['uncertainty'].append({'item': 'metadata disagreement under shared identifier',
                                      'kind': 'metadata_conflict', 'needs_human': True})
    return result


def link(a: dict, b: dict, kind: str, evidence: dict) -> dict:
    """在 a 到 b 之间建有方向的边,返回所建的边。

    kind 属于 RELATION_KINDS 时只写入 a 的 relations(方向 a→b);
    反向断言不自动回填,需要反向关系时由调用者显式 link(b, a)。
    属于 LINEAGE_KINDS 时写入双方的 lineage(from=a,to=b,方向保留在边内)。
    a 与 b 的 object_id 相同则抛 ValueError。
    evidence 必须含 source、queried_at、match_fields、conflict_fields、
    human_confirmed 五个键,缺一抛 ValueError。
    """
    missing = [key for key in EVIDENCE_KEYS if key not in (evidence or {})]
    if missing:
        raise ValueError(f'evidence missing keys: {missing}')
    if not isinstance(a, dict) or not isinstance(b, dict):
        raise ValueError('link arguments must be dict objects')
    if (a or {}).get('object_id') == (b or {}).get('object_id'):
        raise ValueError('cannot link an object to itself')
    ev = {
        'source': evidence['source'],
        'queried_at': evidence['queried_at'],
        'match_fields': list(evidence['match_fields']),
        'conflict_fields': list(evidence['conflict_fields']),
        'human_confirmed': bool(evidence['human_confirmed']),
    }
    if kind in RELATION_KINDS:
        forward = {'target_object_id': b['object_id'], 'kind': kind, 'evidence': dict(ev)}
        a.setdefault('relations', []).append(forward)
        return forward
    if kind in LINEAGE_KINDS:
        edge = {'from_object_id': a['object_id'], 'to_object_id': b['object_id'],
                'kind': kind, 'evidence': dict(ev)}
        a.setdefault('lineage', []).append(edge)
        b.setdefault('lineage', []).append(copy.deepcopy(edge))
        return edge
    raise ValueError(f'unknown edge kind: {kind!r}')


def from_canonical_work(cw: Any) -> dict:
    """把 literature-analysis 的 CanonicalWork 转成 Work 型 ResearchObject 草案。

    鸭子类型：接受 CanonicalWork 实例或同名字段 dict，不 import interop。
    草案在 schema 八字段之外附带 title/authors/year/container 信息字段，
    供 resolve 聚合使用。
    """
    if isinstance(cw, dict):
        get = lambda key, default=None: cw.get(key, default)
    else:
        get = lambda key, default=None: getattr(cw, key, default)
    raw_doi = str(get('doi', '') or '')
    doi = normalize('doi', raw_doi)
    identifiers = []
    if doi:
        identifiers.append({'type': 'doi', 'value': raw_doi, 'normalized': doi})
    extra = get('extra', {}) or {}
    arxiv_raw = str(extra.get('arxiv_id', '') or '')
    arxiv = normalize('arxiv_id', arxiv_raw)
    if arxiv:
        identifiers.append({'type': 'arxiv_id', 'value': arxiv_raw, 'normalized': arxiv})
    title = str(get('title', '') or '')
    if doi:
        object_id = f'ro:work:{doi}'
    else:
        slug = '-'.join(normalize_title(title).split()[:6]) or 'untitled'
        object_id = f'ro:work:{slug}'
    return {
        'object_id': object_id,
        'object_type': 'Work',
        'identifiers': identifiers,
        'manifestations': [],
        'relations': [],
        'lineage': [],
        'source_observations': [],
        'uncertainty': [],
        'title': title,
        'authors': list(get('authors', []) or []),
        'year': get('year'),
        'container': str(get('container', '') or ''),
    }


def consume_receipt(receipt: dict) -> dict:
    """消费 Evidence Receipt 1.0,产出 source_observations 与 uncertainty。

    映射规则(离散、无评分):
    - schema_version 非 1.0 时:sources 照常保留为观察记录,其余语义
      内容(claims/conflicts/failures)一律不解读,统一进一条
      uncertainty(kind=unsupported_schema_version,needs_human=True);
    - sources -> source_observations(source/queried_at/status/coverage/
      raw_identifier 直传);
    - support_status=contradicted 的 claim -> uncertainty,needs_human=True;
    - support_status=unverifiable 的 claim -> uncertainty,needs_human=False;
    - support_status=out_of_scope 的 claim -> uncertainty,
      kind=out_of_scope_claim,needs_human=False(不静默丢弃);
    - conflicts 每条 -> uncertainty(kind=receipt_conflict),needs_human=True;
    - failures 每条 -> uncertainty(kind=query_failure),needs_human=False。
    """
    observations = []
    uncertainty = []
    if (receipt or {}).get('schema_version') != '1.0':
        for s in (receipt or {}).get('sources') or []:
            observations.append({
                'source': s.get('source', ''),
                'queried_at': s.get('queried_at', ''),
                'status': s.get('status', 'skipped'),
                'coverage': s.get('coverage'),
                'raw_identifier': s.get('raw_identifier'),
            })
        uncertainty.append({'item': 'unsupported schema_version',
                            'kind': 'unsupported_schema_version', 'needs_human': True})
        return {'source_observations': observations, 'uncertainty': uncertainty}
    for s in (receipt or {}).get('sources') or []:
        observations.append({
            'source': s.get('source', ''),
            'queried_at': s.get('queried_at', ''),
            'status': s.get('status', 'skipped'),
            'coverage': s.get('coverage'),
            'raw_identifier': s.get('raw_identifier'),
        })
    for c in (receipt or {}).get('claims') or []:
        status = c.get('support_status')
        if status == 'contradicted':
            uncertainty.append({'item': c.get('claim', ''),
                                'kind': 'contradicted_claim', 'needs_human': True})
        elif status == 'unverifiable':
            uncertainty.append({'item': c.get('claim', ''),
                                'kind': 'unverifiable_claim', 'needs_human': False})
        elif status == 'out_of_scope':
            uncertainty.append({'item': c.get('claim', ''),
                                'kind': 'out_of_scope_claim', 'needs_human': False})
    for text in (receipt or {}).get('conflicts') or []:
        uncertainty.append({'item': text, 'kind': 'receipt_conflict', 'needs_human': True})
    for text in (receipt or {}).get('failures') or []:
        uncertainty.append({'item': text, 'kind': 'query_failure', 'needs_human': False})
    return {'source_observations': observations, 'uncertainty': uncertainty}


if __name__ == '__main__':
    # 离线自检：归一、五态判定、双向建边、回执消费各跑一次。
    assert normalize('doi', 'https://doi.org/10.1038/Nature12373') == '10.1038/nature12373'
    assert normalize('arxiv_id', 'arXiv:2310.15264v2') == '2310.15264'
    assert normalize('pmid', 'PMID: 38123654') == '38123654'
    assert normalize('openalex_id', 'https://openalex.org/W2123456789') == 'W2123456789'
    assert normalize('orcid', 'https://orcid.org/0000-0002-1825-0097') == '0000000218250097'

    _rec_a = {'identifiers': [{'type': 'doi', 'value': '10.1038/nature12373'}],
              'title': 'Attention Is All You Need', 'authors': ['Vaswani, Ashish'],
              'year': 2017, 'source': 'Crossref', 'queried_at': '2026-09-17T00:00:00Z'}
    _rec_b = {'identifiers': [{'type': 'arxiv_id', 'value': '1706.03762v5'},
                              {'type': 'doi', 'value': 'https://doi.org/10.1038/nature12373'}],
              'title': 'Attention Is All You Need', 'authors': ['Vaswani, Ashish'],
              'year': 2017, 'source': 'arXiv', 'queried_at': '2026-09-17T00:01:00Z'}
    _agg = resolve([_rec_a, _rec_b])
    assert _agg['verdict'] == 'EXACT' and 'doi' in _agg['match_fields'], _agg
    assert resolve([{'identifiers': [{'type': 'doi', 'value': '10.1/a'}]},
                    {'identifiers': [{'type': 'doi', 'value': '10.1/b'}]}])['verdict'] == 'CONFLICT'
    assert resolve([])['verdict'] == 'UNRESOLVED'

    _obj_a = from_canonical_work({'doi': '10.1038/nature12373', 'title': 'Attention Is All You Need',
                                  'authors': ['Vaswani, Ashish'], 'year': 2017})
    _obj_b = from_canonical_work({'doi': '10.48550/arXiv.1706.03762', 'title': 'Attention Is All You Need',
                                  'authors': ['Vaswani, Ashish'], 'year': 2017})
    _edge = link(_obj_a, _obj_b, 'preprint_to_vor', {
        'source': 'Crossref', 'queried_at': '2026-09-17T00:02:00Z',
        'match_fields': ['title'], 'conflict_fields': [], 'human_confirmed': False})
    assert _obj_a['lineage'] and _obj_b['lineage'], 'lineage 双向回填'
    assert _edge['from_object_id'] == _obj_a['object_id']
    _cite = link(_obj_a, _obj_b, 'cites', {
        'source': 'Crossref', 'queried_at': '2026-09-17T00:02:01Z',
        'match_fields': [], 'conflict_fields': [], 'human_confirmed': False})
    assert _cite['target_object_id'] == _obj_b['object_id']
    assert all(e['target_object_id'] != _obj_a['object_id'] or e['kind'] != 'cites'
               for e in _obj_b['relations']), 'relations 不得反向回填'
    try:
        link(_obj_a, _obj_a, 'cites', {'source': 'x', 'queried_at': 't',
                                       'match_fields': [], 'conflict_fields': [],
                                       'human_confirmed': False})
        raise AssertionError('self-link must raise')
    except ValueError:
        pass

    _out = consume_receipt({'sources': [{'source': 'OpenAlex', 'queried_at': '2026-09-17T00:03:00Z',
                                         'status': 'ok', 'raw_identifier': None}],
                            'claims': [], 'conflicts': ['citation count differs'], 'failures': []})
    assert _out['source_observations'] and _out['uncertainty'][0]['needs_human'] is True
    print('identity self-test PASS')
