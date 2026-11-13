"""Unpaywall 与 OpenAlex 机构库 OA 全文定位（is_oa + best_oa_location + 机构知识库回退链）。

UNPAYWALL_EMAIL 未配置且未启用 --fallback-openalex / --openalex-record 时明确 SKIP，不推断结果；
启用 --fallback-openalex 或提供 --openalex-record 时自动回退查询 OpenAlex 开放获取与高校机构知识库直链。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request

from .research.sources import controlled_urlopen as urlopen, reject_link_or_reparse

USER_AGENT = 'academic-research-kernel/3.0.0'
FALLBACK_ORDER = [
    'OpenAlex open_access.oa_url',
    'Semantic Scholar openAccessPdf.url',
    'Europe PMC fullTextUrlList',
    'archive.org（公版书/专著）',
]


def _normalize_doi(raw: str) -> str:
    s = str(raw or '').strip().lower()
    s = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', s, flags=re.I)
    return s.strip().strip('/')


def _valid_http_url(val) -> str | None:
    if isinstance(val, str):
        u = val.strip()
        if u.startswith(('http://', 'https://')):
            return u
    return None


def pick_oa_location(record: dict):
    """从 Unpaywall 记录提取最佳 OA 位置；is_oa 为假或缺位置时返回 None，不证明不存在。"""
    if not isinstance(record, dict) or not record.get('is_oa'):
        return None
    location = record.get('best_oa_location') or {}
    if not isinstance(location, dict) or not location:
        return None
    pdf_u = _valid_http_url(location.get('url_for_pdf'))
    land_u = _valid_http_url(location.get('url'))
    if not pdf_u and not land_u:
        return None
    return {
        'url_for_pdf': pdf_u,
        'url': land_u or pdf_u,
        'version': location.get('version'),
        'host_type': location.get('host_type'),
        'license': location.get('license'),
    }


def pick_openalex_oa_locations(work: dict) -> list[dict]:
    """从 OpenAlex work 记录提取已确认为开放获取(is_oa=True)的最佳 OA 与机构知识库位置列表。"""
    if not isinstance(work, dict):
        return []
    candidates = []
    seen = set()

    def _add(pdf_url, landing_url, version=None, host_type=None, lic=None, source_name=None):
        p_u = _valid_http_url(pdf_url)
        l_u = _valid_http_url(landing_url)
        key = p_u or l_u
        if not key or key in seen:
            return
        seen.add(key)
        candidates.append({
            'url_for_pdf': p_u,
            'url': l_u or p_u,
            'version': version,
            'host_type': host_type,
            'license': lic,
            'source': source_name,
        })

    # 1. 优先提取明确标记 is_oa=True 且具备直接 pdf_url 的高校/学科机构知识库 (repository)，绕过出版商主站 403 WAF
    for loc in work.get('locations') or []:
        if not isinstance(loc, dict) or not loc.get('is_oa'):
            continue
        src = loc.get('source') or {}
        stype = src.get('type') if isinstance(src, dict) else None
        sname = src.get('display_name') if isinstance(src, dict) else None
        if stype == 'repository' and _valid_http_url(loc.get('pdf_url')):
            _add(loc.get('pdf_url'), loc.get('landing_page_url'), loc.get('version'),
                 'repository', loc.get('license'), sname)

    # 2. 提取 best_oa_location（须明确为开放获取，且不得标记为 is_oa=False）
    oa = work.get('open_access') if isinstance(work.get('open_access'), dict) else {}
    work_is_oa = bool(oa.get('is_oa'))
    best = work.get('best_oa_location')
    if isinstance(best, dict) and best.get('is_oa') is not False and (best.get('is_oa') or work_is_oa):
        src = best.get('source') if isinstance(best.get('source'), dict) else {}
        _add(best.get('pdf_url'), best.get('landing_page_url'), best.get('version'),
             src.get('type'), best.get('license'), src.get('display_name'))

    # 3. 提取 open_access.oa_url（仅当 work_is_oa 为真时）
    if work_is_oa and _valid_http_url(oa.get('oa_url')):
        oa_u = _valid_http_url(oa.get('oa_url'))
        _add(oa_u if oa_u.lower().endswith('.pdf') else None,
             oa_u, None, oa.get('oa_status'), None, 'openalex.open_access')

    # 4. 其余标记为 is_oa=True 的 locations
    for loc in work.get('locations') or []:
        if not isinstance(loc, dict) or not loc.get('is_oa'):
            continue
        src = loc.get('source') if isinstance(loc.get('source'), dict) else {}
        _add(loc.get('pdf_url'), loc.get('landing_page_url'), loc.get('version'),
             src.get('type'), loc.get('license'), src.get('display_name'))

    return candidates


def live_unpaywall(doi: str, email: str) -> dict:
    """LIVE: 查询 Unpaywall。email 须为用户真实联系邮箱（服务可 422 拒绝示例邮箱）。"""
    clean_doi = _normalize_doi(doi)
    headers = {'User-Agent': USER_AGENT}
    url = ('https://api.unpaywall.org/v2/' + quote(clean_doi, safe='')
           + '?' + urlencode({'email': email}))
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


def live_openalex_oa(doi: str) -> dict:
    """LIVE: 查询 OpenAlex 获取 OA 与高校机构库(repository)全文位置（无需邮箱配置）。"""
    clean_doi = _normalize_doi(doi)
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    url = 'https://api.openalex.org/works/https://doi.org/' + quote(clean_doi, safe='')
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


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def _build_openalex_report(doi: str, oa_work: dict, mode: str) -> tuple[int, dict]:
    if not isinstance(oa_work, dict):
        return 1, {'doi': doi, 'status': 'failed', 'error': 'ValueError: OpenAlex record must be a JSON object'}
    rec_doi = _normalize_doi(oa_work.get('doi') or '')
    if rec_doi and rec_doi != doi:
        return 1, {
            'doi': doi,
            'status': 'failed',
            'error': f'record DOI mismatch: requested {doi}, got {rec_doi}',
            'mismatch': True,
        }
    locations = pick_openalex_oa_locations(oa_work)
    oa_meta = oa_work.get('open_access') if isinstance(oa_work.get('open_access'), dict) else {}
    is_oa = bool(oa_meta.get('is_oa') or locations)
    loc0 = locations[0] if locations else None
    report = {
        'doi': doi,
        'identifier': {'type': 'doi', 'value': doi, 'normalized': doi},
        'status': 'ok',
        'mode': mode,
        'is_oa': is_oa,
        'oa_url': (loc0.get('url_for_pdf') or loc0.get('url')) if loc0 else oa_meta.get('oa_url'),
        'location': loc0,
        'alternate_locations': locations,
        'fallback_order': FALLBACK_ORDER,
    }
    if not locations:
        report['note'] = 'OpenAlex 未定位到直链 OA 版本，不证明不存在。'
    return 0, report


def live_semantic_scholar_oa(doi: str) -> dict | None:
    """LIVE: Query Semantic Scholar Graph API for openAccessPdf URL."""
    clean_doi = _normalize_doi(doi)
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    api_key = os.environ.get('S2_API_KEY', '').strip()
    if api_key:
        headers['x-api-key'] = api_key
    url = (
        'https://api.semanticscholar.org/graph/v1/paper/DOI:'
        + quote(clean_doi, safe='')
        + '?fields=isOpenAccess,openAccessPdf,url'
    )
    with urlopen(Request(url, headers=headers), timeout=20) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        return None
    oa_pdf = data.get('openAccessPdf') if isinstance(data.get('openAccessPdf'), dict) else {}
    pdf_u = _valid_http_url(oa_pdf.get('url'))
    if not pdf_u:
        return None
    return {
        'url_for_pdf': pdf_u,
        'url': _valid_http_url(data.get('url')) or pdf_u,
        'version': oa_pdf.get('status'),
        'host_type': 'repository',
        'license': oa_pdf.get('license'),
        'source': 'Semantic Scholar',
    }


def live_europe_pmc_oa(doi: str) -> dict | None:
    """LIVE: Query Europe PMC REST API for open-access fullTextUrlList."""
    clean_doi = _normalize_doi(doi)
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    q = f'DOI:"{clean_doi}"'
    url = (
        'https://www.ebi.ac.uk/europepmc/webservices/rest/search?'
        + urlencode({'query': q, 'format': 'json', 'resultType': 'core'})
    )
    with urlopen(Request(url, headers=headers), timeout=20) as response:
        data = json.load(response)
    results = ((data.get('resultList') or {}).get('result') or []) if isinstance(data, dict) else []
    for item in results:
        if not isinstance(item, dict) or str(item.get('isOpenAccess') or '').upper() != 'Y':
            continue
        ft_list = ((item.get('fullTextUrlList') or {}).get('fullTextUrl') or [])
        pdf_u = None
        land_u = None
        for ft in ft_list:
            if not isinstance(ft, dict):
                continue
            avail = str(ft.get('availabilityCode') or '').upper()
            if avail not in ('OA', 'F', ''):
                continue
            style = str(ft.get('documentStyle') or '').lower()
            u = _valid_http_url(ft.get('url'))
            if not u:
                continue
            if style == 'pdf' and not pdf_u:
                pdf_u = u
            elif not land_u:
                land_u = u
        if pdf_u or land_u:
            return {
                'url_for_pdf': pdf_u,
                'url': land_u or pdf_u,
                'version': 'publishedVersion',
                'host_type': 'repository',
                'license': item.get('license'),
                'source': 'Europe PMC',
            }
    return None


def _try_extra_oa_sources(doi: str, identifier_norm: dict) -> tuple[int, dict] | None:
    for mode_name, fn in (
        ('semantic-scholar-fallback', live_semantic_scholar_oa),
        ('europe-pmc-fallback', live_europe_pmc_oa),
    ):
        try:
            loc = fn(doi)
        except Exception:
            loc = None
        if isinstance(loc, dict):
            return 0, {
                'doi': doi,
                'identifier': identifier_norm,
                'status': 'ok',
                'mode': mode_name,
                'is_oa': True,
                'oa_url': loc.get('url_for_pdf') or loc.get('url'),
                'location': loc,
                'fallback_order': FALLBACK_ORDER,
            }
    return None


def resolve_oa(
    identifier_norm: dict,
    email: str | None = None,
    *,
    fallback_openalex: bool = False,
    fallback_all: bool = False,
) -> tuple[int, dict]:
    """Normalized OA locator respecting explicit --email > UNPAYWALL_EMAIL env > OpenAlex / S2 / Europe PMC fallbacks."""
    if fallback_all:
        fallback_openalex = True
    id_type = identifier_norm.get('type')
    val = str(identifier_norm.get('value') or identifier_norm.get('normalized') or '')
    if id_type == 'arxiv':
        pdf_url = f'https://arxiv.org/pdf/{val}.pdf'
        abs_url = f'https://arxiv.org/abs/{val}'
        loc = {
            'url_for_pdf': pdf_url,
            'url': abs_url,
            'version': 'submittedVersion',
            'host_type': 'repository',
            'license': None,
            'source': 'arXiv',
        }
        return 0, {
            'identifier': identifier_norm,
            'status': 'ok',
            'mode': 'arxiv-direct',
            'is_oa': True,
            'oa_url': pdf_url,
            'location': loc,
        }
    if id_type != 'doi':
        return 1, {
            'identifier': identifier_norm,
            'status': 'unsupported',
            'mode': 'none',
            'is_oa': False,
            'oa_url': None,
            'location': None,
        }
    clean_doi = _normalize_doi(val)
    eff_email = (email.strip() if isinstance(email, str) and email.strip() else '') or os.environ.get('UNPAYWALL_EMAIL', '').strip()
    unpaywall_err: str | None = None
    if eff_email:
        try:
            rec = live_unpaywall(clean_doi, eff_email)
        except Exception as exc:
            unpaywall_err = f"{type(exc).__name__}: {exc}"
            rec = None
        if isinstance(rec, dict):
            loc = pick_oa_location(rec)
            is_oa = bool(rec.get('is_oa') and loc is not None)
            if not is_oa and fallback_openalex:
                try:
                    rc_fb, rep_fb = _build_openalex_report(clean_doi, live_openalex_oa(clean_doi), 'openalex-fallback')
                except Exception:
                    rc_fb, rep_fb = 1, {'is_oa': False}
                if rc_fb == 0 and rep_fb.get('is_oa') and rep_fb.get('oa_url'):
                    rep_fb['identifier'] = identifier_norm
                    return rc_fb, rep_fb
                if fallback_all:
                    extra_hit = _try_extra_oa_sources(clean_doi, identifier_norm)
                    if extra_hit is not None:
                        return extra_hit
                if rc_fb == 0:
                    rep_fb['identifier'] = identifier_norm
                    return rc_fb, rep_fb
            return 0, {
                'doi': clean_doi,
                'identifier': identifier_norm,
                'status': 'ok',
                'mode': 'unpaywall-live',
                'is_oa': is_oa,
                'oa_url': (loc.get('url_for_pdf') or loc.get('url')) if loc else None,
                'location': loc,
                'oa_status': rec.get('oa_status'),
            }
        if fallback_openalex:
            try:
                rc_fb, rep_fb = _build_openalex_report(clean_doi, live_openalex_oa(clean_doi), 'openalex-fallback')
            except Exception as oa_exc:
                rc_fb, rep_fb = 1, {'doi': clean_doi, 'status': 'failed', 'error': f'{type(oa_exc).__name__}: {oa_exc}'}
            if rc_fb == 0 and rep_fb.get('is_oa') and rep_fb.get('oa_url'):
                rep_fb['identifier'] = identifier_norm
                if unpaywall_err:
                    rep_fb['unpaywall_error'] = unpaywall_err
                return rc_fb, rep_fb
            if fallback_all:
                extra_hit = _try_extra_oa_sources(clean_doi, identifier_norm)
                if extra_hit is not None:
                    if unpaywall_err:
                        extra_hit[1]['unpaywall_error'] = unpaywall_err
                    return extra_hit
            rep_fb['identifier'] = identifier_norm
            if unpaywall_err:
                rep_fb['unpaywall_error'] = unpaywall_err
            return rc_fb, rep_fb
        return 1, {
            'doi': clean_doi,
            'identifier': identifier_norm,
            'status': 'failed',
            'mode': 'unpaywall-live',
            'is_oa': False,
            'oa_url': None,
            'location': None,
            'error': unpaywall_err or 'Unpaywall response was not a JSON object',
        }
    if fallback_openalex:
        try:
            rc_oa, rep_oa = _build_openalex_report(clean_doi, live_openalex_oa(clean_doi), 'openalex-live')
        except Exception as oa_exc:
            rc_oa, rep_oa = 1, {'doi': clean_doi, 'status': 'failed', 'error': f'{type(oa_exc).__name__}: {oa_exc}'}
        if rc_oa == 0 and rep_oa.get('is_oa') and rep_oa.get('oa_url'):
            rep_oa['identifier'] = identifier_norm
            return rc_oa, rep_oa
        if fallback_all:
            extra_hit = _try_extra_oa_sources(clean_doi, identifier_norm)
            if extra_hit is not None:
                return extra_hit
        rep_oa['identifier'] = identifier_norm
        return rc_oa, rep_oa
    return 2, {
        'doi': clean_doi,
        'identifier': identifier_norm,
        'status': 'skipped',
        'mode': 'offline-no-email',
        'is_oa': None,
        'oa_url': None,
        'location': None,
        'reason': 'UNPAYWALL_EMAIL is not configured and --email / --fallback-openalex / --fallback-all was not provided',
        'fallback_order': FALLBACK_ORDER,
    }
