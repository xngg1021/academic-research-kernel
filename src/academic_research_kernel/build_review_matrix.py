"""综述矩阵骨架：摘要重建 + 五列对比表 + 覆盖声明（工作流 G 的确定性层）。

重建 abstract_inverted_index、生成表格骨架为纯离线确定性逻辑；
方法/样本/结论/局限四列是模型判断，脚本留空，由模型按 references/review-matrix.md 填。
"""
from __future__ import annotations

import argparse
import json
import sys


NEEDS_FULLTEXT = '【需全文】'
COLUMNS = ('论文(年份)', '方法', '样本/数据', '核心结论', '局限/适用边界')


def rebuild_abstract(inverted_index) -> str:
    """从 OpenAlex abstract_inverted_index 重建摘要；缺失或为空返回 None，不脑补。"""
    if not isinstance(inverted_index, dict) or not inverted_index:
        return None
    positions = []
    for word, indexes in inverted_index.items():
        for index in indexes or []:
            positions.append((index, word))
    if not positions:
        return None
    return ' '.join(word for _, word in sorted(positions))


def matrix_rows(works: list) -> list:
    """生成矩阵行：第一列（论文+年份+DOI）与摘要备查确定给出，四列判断留空。"""
    rows = []
    for work in works:
        title = work.get('title') or '(untitled)'
        year = work.get('publication_year') or work.get('year') or 'n.d.'
        abstract = rebuild_abstract(work.get('abstract_inverted_index'))
        if abstract is None:
            abstract = work.get('abstract') or NEEDS_FULLTEXT
        rows.append({
            'paper': f'{title} ({year})',
            'doi': (work.get('doi') or '').lower().removeprefix('https://doi.org/') or None,
            'abstract': abstract,
            'method': '', 'sample': '', 'conclusion': '', 'limits': '',
        })
    return rows


def _cell(text) -> str:
    return str(text or '').replace('|', '\\|').replace('\n', ' ')


def render_markdown(rows: list, coverage: dict = None) -> str:
    """渲染 markdown 矩阵骨架 + 摘要备查 + 覆盖声明。"""
    lines = ['| ' + ' | '.join(COLUMNS) + ' |', '| --- | --- | --- | --- | --- |']
    for row in rows:
        first = row['paper'] + (f"，DOI: {row['doi']}" if row['doi'] else '，DOI: 待核')
        lines.append('| ' + ' | '.join([_cell(first), '', '', '', '']) + ' |')
    lines.append('')
    lines.append('## 摘要备查')
    for index, row in enumerate(rows, 1):
        lines.append(f"{index}. {row['paper']}：{row['abstract']}")
    lines.append('')
    coverage = coverage or {}
    query = coverage.get('query') or '待填'
    date = coverage.get('date') or '待填'
    lines.append(f"覆盖声明：本次矩阵覆盖 {len(rows)} 篇；检索词：{query}；检索日期：{date}。"
                 '未覆盖范围（付费墙内文献、摘要缺失需全文的条目等）须如实写明。')
    return '\n'.join(lines)


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
