"""候选文献去重：DOI 归一优先，标题归一为候选关系兜底。纯离线、确定性，无网络访问。

LA-01: 无 DOI 的文献不得仅凭标题直接判重移除。同标题条目先比对作者与年份：
作者交集非空且年份一致（或任一方缺年份）才判重复；否则双方都保留，并记入
title_candidates 供人工核对。
"""
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


def _norm_authors(work) -> set:
    """作者名归一集合（个人姓名或机构名统一小写去标点）。"""
    names = set()
    for author in work.get('authors') or []:
        if isinstance(author, dict):
            raw = ' '.join(str(author.get(k) or '') for k in ('family', 'given', 'name'))
        else:
            raw = str(author)
        norm = ' '.join(re.findall(r'[a-z0-9]+|[一-鿿]', raw.lower()))
        if norm:
            names.add(norm)
    return names


def deduplicate_works(works: list) -> dict:
    """保留首见条目；DOI 确定的重复记入 removed；无 DOI 同标题仅在同作者同年份
    证据下判重，其余降级为 title_candidates 候选关系（双方保留）。"""
    kept, removed, candidates = [], [], []
    seen = {}
    title_index = {}
    unidentified = 0
    for work in works:
        doi = normalize_doi(work.get('doi'))
        if doi:
            key = 'doi:' + doi
            if key in seen:
                removed.append({
                    'work': work,
                    'key': key,
                    'reason': 'same-doi',
                    'duplicate_of': seen[key].get('title'),
                })
            else:
                seen[key] = work
                kept.append(work)
            continue
        title = normalize_title(work.get('title'))
        if not title:
            unidentified += 1
            kept.append(work)
            continue
        matches = title_index.get(title)
        if not matches:
            title_index[title] = [work]
            kept.append(work)
            continue
        # LA-01: 同标题候选判断 —— 作者交集非空且年份一致（或任一方缺年份）才判重
        duplicate = None
        for earlier in matches:
            author_overlap = bool(_norm_authors(work) & _norm_authors(earlier))
            work_year = str(work.get('year') or '').strip()
            earlier_year = str(earlier.get('year') or '').strip()
            year_ok = (work_year == earlier_year) or not (work_year and earlier_year)
            if author_overlap and year_ok:
                duplicate = earlier
                break
        if duplicate is not None:
            removed.append({
                'work': work,
                'key': 'title:' + title,
                'reason': 'same-title',
                'duplicate_of': duplicate.get('title'),
            })
        else:
            candidates.append({
                'title': title,
                'note': '同标题但作者/年份证据不一致，双方均保留，待人工核对',
                'works': [earlier.get('title') for earlier in matches] + [work.get('title')],
            })
            title_index[title].append(work)
            kept.append(work)
    return {
        'kept': kept,
        'removed': removed,
        'title_candidates': candidates,
        'summary': {
            'input': len(works),
            'kept': len(kept),
            'removed': len(removed),
            'unidentifiable_kept': unidentified,
            'title_candidates': len(candidates),
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
