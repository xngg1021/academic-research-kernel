"""候选文献去重：DOI 归一优先，标题归一兜底。纯离线、确定性，无网络访问。"""
from __future__ import annotations

import argparse
import json
import re
import sys


import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

def normalize_doi(doi) -> str:
    return (doi or '').strip().lower().removeprefix('https://doi.org/').removeprefix(
        'http://doi.org/').removeprefix('https://dx.doi.org/').removeprefix('doi:')


def normalize_title(title) -> str:
    """小写、去标点（保留字母/数字/CJK）、折叠空白。"""
    return ' '.join(re.findall(r'[a-z0-9]+|[一-鿿]', (title or '').lower()))


def work_key(work: dict):
    """DOI 存在用 doi: 键，否则用 title: 键；两者皆无返回 None（保留并计数，不猜）。"""
    doi = normalize_doi(work.get('doi'))
    if doi:
        return 'doi:' + doi
    title = normalize_title(work.get('title'))
    return 'title:' + title if title else None


def deduplicate_works(works: list) -> dict:
    """保留首见条目；重复条目记入 removed 并注明原因与首见标题。"""
    kept, removed = [], []
    seen = {}
    unidentified = 0
    for work in works:
        key = work_key(work)
        if key is None:
            unidentified += 1
            kept.append(work)
            continue
        if key in seen:
            removed.append({
                'work': work,
                'key': key,
                'reason': 'same-doi' if key.startswith('doi:') else 'same-title',
                'duplicate_of': seen[key].get('title'),
            })
        else:
            seen[key] = work
            kept.append(work)
    return {
        'kept': kept,
        'removed': removed,
        'summary': {
            'input': len(works),
            'kept': len(kept),
            'removed': len(removed),
            'unidentifiable_kept': unidentified,
        },
    }


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='输入为 work JSON 列表（每项至少含 doi 或 title）；--input - 读标准输入。')
    parser.add_argument('--input', required=True, help='work JSON 列表文件，或 - 读标准输入')
    args = parser.parse_args(argv)
    _utf8_stdio()

    try:
        if args.input == '-':
            works = json.load(sys.stdin)
        else:
            with open(args.input, encoding='utf-8') as handle:
                works = json.load(handle)
        if not isinstance(works, list):
            raise ValueError('input JSON must be a list of works')
    except (OSError, ValueError) as error:
        print(json.dumps({'status': 'failed', 'error': f'{type(error).__name__}: {error}'},
                         ensure_ascii=False, indent=2))
        return 1

    result = deduplicate_works(works)
    result['status'] = 'ok'
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
