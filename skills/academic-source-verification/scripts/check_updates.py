"""Crossref update-to 反向查询：撤稿/撤回/更正/表达关注信号的提取与分类记录。

update_signals 为纯离线判定（输入须来自已成功查询的 Crossref 记录）；
live_reverse_lookup 明确标记，实际发起网络请求。不同信号类型分别记录，不合并归为撤稿。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

USER_AGENT = 'hermes-academic-skills/1.2'


def update_signals(target_doi: str, records: list) -> list:
    """只提取与目标 DOI 关联的更新信号；通知记录本身不是被撤稿对象。"""
    target = target_doi.lower().removeprefix('https://doi.org/')
    signals = []
    for record in records:
        for update in record.get('update-to') or []:
            updated_doi = str(update.get('DOI') or '').lower().removeprefix('https://doi.org/')
            if updated_doi == target:
                signals.append({'type': update.get('type'), 'source': update.get('source'),
                                'record_doi': record.get('DOI'), 'target_doi': updated_doi})
    return signals


def summarize_signals(signals: list) -> dict:
    """按类型分别计数（retraction/withdrawal/correction/expression-of-concern 不合并）。"""
    counts = {}
    for signal in signals:
        key = signal.get('type') or 'unknown'
        counts[key] = counts.get(key, 0) + 1
    return counts


def live_get(url: str):
    """LIVE: 网络访问。429/5xx 有界退避；长预算封锁交给调用者报告，不循环耗尽。"""
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


def live_reverse_lookup(doi: str, rows: int = 100, max_pages: int = 10) -> dict:
    """LIVE: 反向查询 filter=updates:<DOI>，按 Crossref cursor 规则翻页，记录截断。"""
    items = []
    cursor = '*'
    truncated = False
    pages = 0
    for done in range(max_pages):
        params = {'filter': 'updates:' + doi, 'rows': rows, 'cursor': cursor}
        message = live_get('https://api.crossref.org/works?' + urlencode(params))['message']
        batch = message.get('items') or []
        items.extend(batch)
        pages = done + 1
        cursor = message.get('next-cursor')
        if not batch or not cursor:
            break
    else:
        # 页数预算耗尽且每页均有结果：记录截断。
        truncated = bool(items)
    return {'items': items, 'truncated': truncated, 'pages_fetched': pages}


def _load_records(path: str) -> list:
    with open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get('items'), list):
            return data['items']
        message = data.get('message')
        if isinstance(message, dict) and isinstance(message.get('items'), list):
            return message['items']
    raise ValueError('records file must be a JSON list, or an object with items / message.items')


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='默认在线反向查询；--records 用已保存的 Crossref 记录离线提取信号。'
               '查无信号时仅报告"在已检查的数据源中未发现撤稿或撤回记录"。')
    parser.add_argument('--doi', required=True, help='目标 DOI（原始论文 DOI，非通知 DOI）')
    parser.add_argument('--records', help='已保存的 Crossref 记录 JSON（list 或含 items 的对象）')
    parser.add_argument('--rows', type=int, default=100, help='在线查询每页行数（默认 100）')
    parser.add_argument('--max-pages', type=int, default=10, help='在线查询页数预算上限（默认 10）')
    args = parser.parse_args(argv)
    _utf8_stdio()

    target = args.doi.lower().removeprefix('https://doi.org/')
    if args.records:
        try:
            records = _load_records(args.records)
        except (OSError, ValueError) as error:
            print(json.dumps({'target_doi': target, 'status': 'failed',
                              'error': f'{type(error).__name__}: {error}'}, ensure_ascii=False, indent=2))
            return 1
        meta = {'mode': 'offline-file', 'records_examined': len(records)}
    else:
        try:
            result = live_reverse_lookup(target, rows=args.rows, max_pages=args.max_pages)
        except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as error:
            print(json.dumps({'target_doi': target, 'status': 'failed',
                              'error': f'{type(error).__name__}: {error}',
                              'note': '网络请求失败不等于未发现记录'}, ensure_ascii=False, indent=2))
            return 1
        records = result['items']
        meta = {'mode': 'live', 'records_examined': len(records), 'truncated': result['truncated'],
                'queried_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}

    signals = update_signals(target, records)
    report = {
        'target_doi': target,
        'status': 'ok',
        **meta,
        'signals': signals,
        'signal_counts': summarize_signals(signals),
    }
    if not signals:
        report['note'] = '在已检查的数据源中未发现撤稿或撤回记录；请注明数据来源、查询时间与未查项目。'
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
