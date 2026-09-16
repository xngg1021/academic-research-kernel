"""Unpaywall OA 全文定位（is_oa + best_oa_location）。

UNPAYWALL_EMAIL 未配置时明确 SKIP，不推断结果；is_oa=false 时不证明 OA 版本不存在。
live_unpaywall 明确标记，实际发起网络请求。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

USER_AGENT = 'hermes-academic-skills/1.2'
FALLBACK_ORDER = ['OpenAlex open_access.oa_url', 'Semantic Scholar openAccessPdf.url',
                  'archive.org（公版书/专著）']


def pick_oa_location(record: dict):
    """从 Unpaywall 记录提取最佳 OA 位置；is_oa 为假或缺位置时返回 None，不证明不存在。"""
    if not isinstance(record, dict) or not record.get('is_oa'):
        return None
    location = record.get('best_oa_location') or {}
    if not location:
        return None
    return {
        'url_for_pdf': location.get('url_for_pdf'),
        'url': location.get('url'),
        'version': location.get('version'),
        'host_type': location.get('host_type'),
        'license': location.get('license'),
    }


def live_unpaywall(doi: str, email: str) -> dict:
    """LIVE: 查询 Unpaywall。email 须为用户真实联系邮箱（服务可 422 拒绝示例邮箱）。"""
    headers = {'User-Agent': USER_AGENT}
    url = ('https://api.unpaywall.org/v2/' + quote(doi, safe='')
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


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='email 取 --email 或 UNPAYWALL_EMAIL 环境变量；'
               '未配置时输出 SKIP 并以 0 退出，不推断任何结果。')
    parser.add_argument('--doi', required=True, help='目标 DOI（裸 DOI 或 doi.org URL）')
    parser.add_argument('--email', help='Unpaywall 联系邮箱（默认读 UNPAYWALL_EMAIL）')
    parser.add_argument('--record', help='已保存的 Unpaywall 记录 JSON（离线模式，不发请求）')
    args = parser.parse_args(argv)
    _utf8_stdio()

    doi = args.doi.lower().removeprefix('https://doi.org/').strip().strip('/')
    if args.record:
        try:
            with open(args.record, encoding='utf-8') as handle:
                record = json.load(handle)
        except (OSError, ValueError) as error:
            print(json.dumps({'doi': doi, 'status': 'failed',
                              'error': f'{type(error).__name__}: {error}'}, ensure_ascii=False, indent=2))
            return 1
        mode = 'offline-file'
    else:
        email = args.email or os.environ.get('UNPAYWALL_EMAIL')
        if not email:
            print(json.dumps({'doi': doi, 'status': 'skipped',
                              'reason': 'SKIP Unpaywall: UNPAYWALL_EMAIL not configured; no result inferred'},
                             ensure_ascii=False, indent=2))
            return 0
        try:
            record = live_unpaywall(doi, email)
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            print(json.dumps({'doi': doi, 'status': 'failed',
                              'error': f'{type(error).__name__}: {error}',
                              'note': '网络请求失败不等于不存在 OA 版本'}, ensure_ascii=False, indent=2))
            return 1
        mode = 'live'

    location = pick_oa_location(record)
    report = {
        'doi': doi,
        'status': 'ok',
        'mode': mode,
        'is_oa': bool(record.get('is_oa')),
        'location': location,
        'fallback_order': FALLBACK_ORDER,
    }
    if not location:
        report['note'] = '此服务未定位到 OA 版本，不证明不存在；按 fallback_order 继续其他渠道。'
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
