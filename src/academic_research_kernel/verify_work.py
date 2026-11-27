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
from urllib.request import Request

from .research.sources import controlled_urlopen as urlopen, reject_link_or_reparse


from ._version import __version__

USER_AGENT = f'academic-research-kernel/{__version__}'


_INLINE_MARKUP_TAG_RE = re.compile(r'</?(?:i|b|em|strong|sub|sup|scp|span|mml:[a-z0-9_]+)\b[^>]*>', re.IGNORECASE)
_REL_OP_MAP = {'≤': '<=', '≥': '>=', '≠': '!=', '==': '='}
_TITLE_TOKEN_RE = re.compile(r'<=|>=|!=|==|[<>≤≥≠=]|[^\W_]+')


def _norm_title(title) -> str:
    r"""小写、去普通标点并保留比较关系符与 Unicode 字母数字 (AV-03):
    剥离常见内联排版标签后保留 <=/>=/!=/</>/= 语义区分，防止剂量/阈值不等号反转碰撞。"""
    cleaned = _INLINE_MARKUP_TAG_RE.sub(' ', (title or '').lower())
    return ' '.join(_REL_OP_MAP.get(tok, tok) for tok in _TITLE_TOKEN_RE.findall(cleaned))


def _norm_doi(doi) -> str:
    return (doi or '').lower().removeprefix('https://doi.org/').removeprefix('http://doi.org/')


def parse_openalex_work(record: dict) -> dict:
    """从 OpenAlex work 记录提取身份字段。"""
    source = ((record.get('primary_location') or {}).get('source') or {})
    authors = [a.get('author', {}).get('display_name') for a in record.get('authorships') or []]
    pub_year = record.get('publication_year')
    valid_years = [int(pub_year)] if isinstance(pub_year, int) and not isinstance(pub_year, bool) else []
    raw_ret = record.get('is_retracted')
    if raw_ret is not None and not isinstance(raw_ret, bool):
        raise ValueError(f'OpenAlex is_retracted must be a JSON boolean or null, got {raw_ret!r}')
    return {
        'source': 'openalex',
        'doi': _norm_doi(record.get('doi')),
        'title': record.get('title') or record.get('display_name'),
        'year': pub_year,
        'valid_years': valid_years,
        'venue': source.get('display_name'),
        'authors': [a for a in authors if a],
        'cited_by_count': record.get('cited_by_count'),
        'is_retracted': raw_ret,
        'oa_status': (record.get('open_access') or {}).get('oa_status'),
    }


def parse_crossref_work(message: dict) -> dict:
    """从 Crossref message 记录提取身份字段（保留印刷/线上多年份与方向正确的撤稿信号）。"""
    msg = (
        message.get('message')
        if isinstance(message, dict) and isinstance(message.get('message'), dict) and 'DOI' not in message
        else (message or {})
    )
    own_doi = _norm_doi(msg.get('DOI'))
    year_by_type: dict[str, int] = {}
    for key in ('published-print', 'published-online', 'issued', 'published'):
        parts = (msg.get(key) or {}).get('date-parts')
        if parts and parts[0] and isinstance(parts[0][0], int) and not isinstance(parts[0][0], bool):
            year_by_type[key] = int(parts[0][0])
    year = (
        year_by_type.get('published-print')
        or year_by_type.get('published-online')
        or year_by_type.get('issued')
        or year_by_type.get('published')
    )
    valid_years = sorted(set(year_by_type.values()))
    authors = []
    author_parts = []
    for author in msg.get('author') or []:
        given = str(author.get('given') or '').strip()
        family = str(author.get('family') or '').strip()
        name = ' '.join(p for p in (given, family) if p) or str(author.get('name') or '').strip()
        if name:
            authors.append(name)
            author_parts.append({'given': given, 'family': family, 'name': name})
    container = msg.get('container-title') or []

    ret_types = {'retraction', 'retracted', 'withdrawal', 'removal'}
    # Crossref `updated-by` sits on the retracted work itself; `update-to` sits on a notice pointing to target DOI
    updated_by = msg.get('updated-by') or []
    retracted_via_updated_by = any(
        isinstance(u, dict) and str(u.get('type') or '').strip().lower() in ret_types
        for u in updated_by
    )
    retraction_notices_for: list[str] = []
    self_retracted_via_update_to = False
    for u in msg.get('update-to') or []:
        if isinstance(u, dict) and str(u.get('type') or '').strip().lower() in ret_types:
            t_doi = _norm_doi(u.get('DOI'))
            if t_doi:
                retraction_notices_for.append(t_doi)
                if own_doi and t_doi == own_doi:
                    self_retracted_via_update_to = True
    rel = msg.get('relation') or {}
    retracted_via_rel = bool(isinstance(rel, dict) and rel.get('is-retracted-by'))
    is_retracted = bool(retracted_via_updated_by or self_retracted_via_update_to or retracted_via_rel)
    return {
        'source': 'crossref',
        'doi': own_doi,
        'title': ' '.join(msg.get('title') or []) or None,
        'year': year,
        'valid_years': valid_years,
        'year_by_date_type': year_by_type,
        'venue': container[0] if container else None,
        'authors': authors,
        'author_parts': author_parts,
        'cited_by_count': msg.get('is-referenced-by-count'),
        'is_retracted': is_retracted,
        'retraction_notices_for': sorted(set(retraction_notices_for)),
    }


_SURNAME_PARTICLES = frozenset({'van', 'von', 'de', 'del', 'della', 'di', 'da', 'du', 'la', 'le', 'st', 'al', 'bin', 'ibn'})
_VENUE_STOPWORDS = frozenset({'of', 'the', 'in', 'on', 'for', 'and', 'to', 'a', 'an'})


def _split_given_family(name: str, structured: dict | None = None) -> tuple[list[str], list[str]]:
    if isinstance(structured, dict) and structured.get('family'):
        g_toks = re.findall(r'[^\W_]+', str(structured.get('given') or '').lower())
        f_toks = re.findall(r'[^\W_]+', str(structured.get('family') or '').lower())
        if f_toks:
            return g_toks, f_toks
    raw = str(name or '').strip()
    if ',' in raw:
        parts = [p.strip() for p in raw.split(',') if p.strip()]
        if len(parts) == 2:
            f_toks = re.findall(r'[^\W_]+', parts[0].lower())
            g_toks = re.findall(r'[^\W_]+', parts[1].lower())
            return g_toks, f_toks
    toks = re.findall(r'[^\W_]+', raw.lower())
    if len(toks) <= 1:
        return [], toks
    # Group trailing surname particles with surname (e.g. ' Laurens van der Maaten ' -> family=['van', 'der', 'maaten'])
    idx = len(toks) - 1
    while idx > 1 and toks[idx - 1] in (_SURNAME_PARTICLES | {'der', 'den', 'ten', 'ter'}):
        idx -= 1
    return toks[:idx], toks[idx:]


def _given_tokens_compatible(cg: list[str], rg: list[str]) -> bool:
    if not cg and not rg:
        return True
    if not cg or not rg:
        return False
    if cg == rg:
        return True
    # First given token must match by full token or initial
    if not (cg[0] == rg[0] or (len(cg[0]) == 1 and rg[0].startswith(cg[0])) or (len(rg[0]) == 1 and cg[0].startswith(rg[0]))):
        return False
    # Any additional middle tokens supplied on BOTH sides must agree by token or initial
    common_extra = min(len(cg), len(rg)) - 1
    for i in range(1, 1 + common_extra):
        a, b = cg[i], rg[i]
        if not (a == b or (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b))):
            return False
    return True


def _author_name_compatible(cited_name: str, registry_name: str, registry_struct: dict | None = None) -> bool:
    cg, cf = _split_given_family(cited_name)
    rg, rf = _split_given_family(registry_name, registry_struct)
    if not cf or not rf or cf != rf:
        return False
    return _given_tokens_compatible(cg, rg)


def _has_bijection(cited_list: list[str], reg_list: list[str], reg_structs: list[dict] | None) -> bool:
    if len(cited_list) != len(reg_list):
        return False
    n = len(cited_list)
    adj = [
        [
            j for j in range(n)
            if _author_name_compatible(
                cited_list[i],
                reg_list[j],
                reg_structs[j] if (reg_structs and j < len(reg_structs)) else None,
            )
        ]
        for i in range(n)
    ]
    match_r = [-1] * n

    def _dfs(u: int, seen: set[int]) -> bool:
        for v in adj[u]:
            if v in seen:
                continue
            seen.add(v)
            if match_r[v] == -1 or _dfs(match_r[v], seen):
                match_r[v] = u
                return True
        return False

    for i in range(n):
        if not _dfs(i, set()):
            return False
    return True


def _venue_compatible(cited_venue: str, registry_venue: str) -> bool:
    cv_toks = re.findall(r'[^\W_]+', (cited_venue or '').lower())
    rv_toks = re.findall(r'[^\W_]+', (registry_venue or '').lower())
    if not cv_toks or not rv_toks:
        return False
    if cv_toks == rv_toks:
        return True
    # Exact initialism match (e.g. 'CACM' <-> 'Communications of the ACM', 'CVPR' <-> '... Computer Vision and Pattern Recognition')
    cv_sig = [t for t in cv_toks if t not in _VENUE_STOPWORDS]
    rv_sig = [t for t in rv_toks if t not in _VENUE_STOPWORDS]
    if len(cv_toks) == 1 and len(rv_sig) >= 2 and cv_toks[0] == ''.join(t[0] for t in rv_sig):
        return True
    if len(rv_toks) == 1 and len(cv_sig) >= 2 and rv_toks[0] == ''.join(t[0] for t in cv_sig):
        return True
    return False


def compare_works(works: list, target_doi: str = None) -> dict:
    """字段级对照两份以上已解析记录；被引数仅记录不比对。

    target_doi 提供时强制正向身份绑定校验: 每份记录必须显式携带且匹配请求 DOI,
    缺失或不一致的均记入 identity_binding_mismatch 且不参与权威字段互证。
    """
    binding = []
    bound_works = list(works or [])
    retraction_notice_hits = []
    if target_doi is not None:
        expected = _norm_doi(target_doi)
        bound_works = []
        for work in works or []:
            found = _norm_doi(work.get('doi'))
            if expected and expected in (work.get('retraction_notices_for') or []):
                retraction_notice_hits.append(work['source'])
            if not found or found != expected:
                binding.append({'source': work.get('source'), 'expected': expected, 'found': found or None})
            else:
                bound_works.append(work)

    fields = {}
    for name in ('doi', 'title', 'year'):
        values = {}
        for work in bound_works:
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
    year_sets = []
    valid_years_by_src = {}
    for work in bound_works:
        vy = work.get('valid_years')
        yset = {int(y) for y in (vy if vy else ([work['year']] if work.get('year') is not None else []))}
        valid_years_by_src[work['source']] = sorted(yset)
        if yset:
            year_sets.append(yset)
    year_compatible = None
    if len(year_sets) > 1:
        common = set.intersection(*year_sets)
        year_compatible = len(common) > 0
    elif len(year_sets) == 1:
        year_compatible = True
    fields['year']['valid_years'] = valid_years_by_src
    fields['year']['year_compatible'] = year_compatible

    retracted_flags = {w['source']: w.get('is_retracted') for w in bound_works if w.get('is_retracted') is not None}
    is_retracted = any(v is True for v in retracted_flags.values()) or bool(retraction_notice_hits)
    return {
        'fields': fields,
        'positively_bound_sources': [w['source'] for w in bound_works],
        'identity_binding_mismatch': binding,
        'is_retracted': is_retracted,
        'retraction_by_source': retracted_flags,
        'citation_counts': {w['source']: w.get('cited_by_count') for w in bound_works},
        'note': '被引数存在来源口径差异（收录范围不同），仅记录并标注来源，不用于判定文献身份。'
                'identity_binding_mismatch 非空表示来源记录缺失或与请求 DOI 不一致, 字段比对结果不可作为身份证据。',
    }


def compare_cited_metadata(cited: dict, works: list, *, target_doi: str | None = None) -> dict:
    """按单条正向绑定注册表记录核对论文引文元数据（拒绝跨冲突源拼凑，区分失配与不可核查）。"""
    checked: list[str] = []
    has_title = isinstance(cited.get('cited_title'), str) and bool(cited['cited_title'].strip())
    raw_authors = [str(a).strip() for a in (cited.get('cited_authors') or []) if str(a).strip()]
    explicit_et_al = bool(cited.get('cited_authors_et_al', False))
    cleaned_authors: list[str] = []
    for tok in raw_authors:
        if re.sub(r'[^a-z]+', ' ', tok.lower()).strip() == 'et al':
            explicit_et_al = True
        else:
            cleaned_authors.append(tok)
    has_authors = len(cleaned_authors) > 0
    has_year = cited.get('cited_year') is not None and not isinstance(cited.get('cited_year'), bool)
    has_venue = isinstance(cited.get('cited_venue'), str) and bool(cited['cited_venue'].strip())

    if has_title:
        checked.append('title')
    if has_authors:
        checked.append('authors')
    if has_year:
        checked.append('year')
    if has_venue:
        checked.append('venue')

    if not checked:
        return {
            'checked_fields': [],
            'mismatched_fields': [],
            'uncheckable_fields': [],
            'field_checks': {},
            'per_source_evaluations': {},
            'citation_metadata_match': None,
        }

    expected_doi = _norm_doi(target_doi) if target_doi else None
    bound_works = [
        w for w in (works or [])
        if isinstance(w, dict) and (not expected_doi or (_norm_doi(w.get('doi')) == expected_doi and bool(expected_doi)))
    ]
    if not bound_works:
        return {
            'checked_fields': checked,
            'mismatched_fields': [],
            'uncheckable_fields': list(checked),
            'field_checks': {},
            'per_source_evaluations': {},
            'citation_metadata_match': None,
        }

    ct_norm = _norm_title(cited['cited_title']) if has_title else ''
    ct_tokens = set(ct_norm.split()) if has_title else set()
    cy = int(cited['cited_year']) if has_year else 0
    cv_raw = str(cited.get('cited_venue') or '').strip()

    per_source: dict[str, dict] = {}
    for idx_w, w in enumerate(bound_works):
        src_key = str(w.get('source') or f'source_{idx_w}')
        s_mismatch: list[str] = []
        s_uncheckable: list[str] = []
        s_details: dict[str, Any] = {}

        if has_title:
            w_title = _norm_title(w.get('title'))
            if not w_title:
                s_uncheckable.append('title')
                s_details['title'] = {'status': 'uncheckable'}
            else:
                wt_tokens = set(w_title.split())
                jacc = (len(ct_tokens & wt_tokens) / len(ct_tokens | wt_tokens)) if (ct_tokens and wt_tokens) else 0.0
                if ct_norm == w_title:
                    s_details['title'] = {'status': 'match', 'exact': True, 'jaccard': 1.0}
                elif jacc >= 0.85:
                    s_uncheckable.append('title')
                    s_details['title'] = {
                        'status': 'uncheckable',
                        'reason': 'non_exact_high_similarity',
                        'exact': False,
                        'jaccard': round(jacc, 4),
                    }
                else:
                    s_mismatch.append('title')
                    s_details['title'] = {'status': 'mismatch', 'exact': False, 'jaccard': round(jacc, 4)}

        if has_authors:
            ra_list = w.get('authors') or []
            ra_structs = w.get('author_parts') if isinstance(w.get('author_parts'), list) else None
            if not ra_list:
                s_uncheckable.append('authors')
                s_details['authors'] = {'status': 'uncheckable'}
            else:
                first_ok = _author_name_compatible(
                    cleaned_authors[0], ra_list[0], ra_structs[0] if ra_structs else None
                )
                if explicit_et_al:
                    ordered_ok = len(cleaned_authors) <= len(ra_list) and all(
                        _author_name_compatible(
                            cleaned_authors[i], ra_list[i], ra_structs[i] if (ra_structs and i < len(ra_structs)) else None
                        )
                        for i in range(len(cleaned_authors))
                    )
                else:
                    ordered_ok = len(cleaned_authors) == len(ra_list) and all(
                        _author_name_compatible(
                            cleaned_authors[i], ra_list[i], ra_structs[i] if (ra_structs and i < len(ra_structs)) else None
                        )
                        for i in range(len(cleaned_authors))
                    )
                order_only = (not ordered_ok) and (not explicit_et_al) and _has_bijection(cleaned_authors, ra_list, ra_structs)
                if not ordered_ok:
                    s_mismatch.append('authors')
                    if order_only:
                        s_mismatch.append('author_order')
                s_details['authors'] = {
                    'status': 'match' if ordered_ok else 'mismatch',
                    'first_author_match': first_ok,
                    'ordered_match': ordered_ok,
                    'unordered_bijection_only': order_only,
                    'explicit_et_al': explicit_et_al,
                }

        if has_year:
            vy = set(w.get('valid_years') or [])
            if isinstance(w.get('year'), int):
                vy.add(int(w['year']))
            if not vy:
                s_uncheckable.append('year')
                s_details['year'] = {'status': 'uncheckable'}
            else:
                y_ok = cy in vy
                if not y_ok:
                    s_mismatch.append('year')
                s_details['year'] = {'status': 'match' if y_ok else 'mismatch', 'valid_years': sorted(vy)}

        if has_venue:
            w_venue = w.get('venue')
            if not w_venue:
                s_uncheckable.append('venue')
                s_details['venue'] = {'status': 'uncheckable'}
            else:
                v_ok = _venue_compatible(cv_raw, str(w_venue))
                if not v_ok:
                    s_mismatch.append('venue')
                s_details['venue'] = {'status': 'match' if v_ok else 'mismatch', 'registry_venue': w_venue}

        per_source[src_key] = {
            'mismatched_fields': s_mismatch,
            'uncheckable_fields': s_uncheckable,
            'complete_match': (len(s_mismatch) == 0 and len(s_uncheckable) == 0),
            'details': s_details,
        }

    # Aggregate each field strictly over its non-uncheckable observations; any conflict or missing check blocks True:
    any_complete_match = any(ev['complete_match'] for ev in per_source.values())
    agg_mismatched: list[str] = []
    agg_uncheckable: list[str] = []
    agg_conflicts: list[str] = []
    field_checks: dict[str, dict] = {}

    for f in checked:
        statuses = [
            ev['details'][f]['status']
            for ev in per_source.values()
            if f in ev['details']
        ]
        known_statuses = [st for st in statuses if st != 'uncheckable']
        if not known_statuses:
            agg_uncheckable.append(f)
            field_checks[f] = {'status': 'uncheckable', 'match': None}
        elif all(st == 'mismatch' for st in known_statuses):
            agg_mismatched.append(f)
            if f == 'authors' and any(ev['details']['authors'].get('unordered_bijection_only') for ev in per_source.values() if 'authors' in ev['details']):
                agg_mismatched.append('author_order')
            field_checks[f] = {'status': 'mismatch', 'match': False}
        elif 'mismatch' in known_statuses and 'match' in known_statuses:
            agg_conflicts.append(f)
            field_checks[f] = {'status': 'registry_conflict', 'match': None}
        else:
            field_checks[f] = {'status': 'match', 'match': True}

    if agg_mismatched:
        overall_match: bool | None = False
    elif agg_conflicts or agg_uncheckable:
        overall_match = None
    elif any_complete_match:
        overall_match = True
    else:
        overall_match = None

    return {
        'checked_fields': checked,
        'mismatched_fields': agg_mismatched,
        'conflicting_fields': agg_conflicts,
        'uncheckable_fields': agg_uncheckable,
        'field_checks': field_checks,
        'per_source_evaluations': per_source,
        'citation_metadata_match': overall_match,
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
    p = reject_link_or_reparse(path)
    with p.open(encoding='utf-8') as handle:
        return json.load(handle)


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
