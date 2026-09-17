"""CanonicalWork 中间结构与 BibTeX/RIS/CSL-JSON/Crossref/OpenAlex 互转。

纯 Python 标准库，无网络依赖。用途：把不同来源的文献元数据先归一到
CanonicalWork，再导出为目标格式，避免 N×N 种两两转换。

CanonicalWork 字段（最小集）：
- work_type: 规范类型，取值 article / paper-conference / book / chapter /
  preprint / thesis / report / misc
- title: 标题
- authors: 作者列表，尽量规范为 "Family, Given"；来源只有显示名时保留原样
- year: 发表年份（int 或 None）
- container: 来源容器（期刊名、会议录名、书名等）
- doi: 裸 DOI（去掉 https://doi.org/ 前缀并小写化）
- url: 落地页 URL
另带 volume / issue / pages / publisher 四个常见可选字段与 extra 字典，
用于承载格式特有、规范结构未覆盖的信息。

已知边界（最小解析，不追求完整语法）：
- BibTeX 解析不支持字符串宏（@string）、字段值拼接（#）与括号定界条目；
  花括号/引号值的转义按字面保留。嵌套花括号会展开为最内层文本。
- OpenAlex 作者只有 display_name，无法可靠拆姓/名，原样保留。
- 年份只取公历年（4 位数字）；更早或不确定的年份记 None。
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

__all__ = [
    'CanonicalWork',
    'normalize_doi',
    'make_citekey',
    'from_bibtex',
    'from_ris',
    'from_csl_json',
    'from_crossref_json',
    'from_openalex_json',
    'to_bibtex',
    'to_ris',
    'to_csl_json',
]

CANONICAL_TYPES = (
    'article', 'paper-conference', 'book', 'chapter',
    'preprint', 'thesis', 'report', 'misc',
)

_BIBTEX_FROM = {
    'article': 'article',
    'inproceedings': 'paper-conference', 'conference': 'paper-conference',
    'proceedings': 'paper-conference',
    'book': 'book',
    'incollection': 'chapter', 'inbook': 'chapter',
    'phdthesis': 'thesis', 'mastersthesis': 'thesis',
    'techreport': 'report',
    'misc': 'misc', 'unpublished': 'preprint', 'manual': 'misc',
    'booklet': 'misc', 'online': 'misc',
}
_BIBTEX_TO = {
    'article': 'article',
    'paper-conference': 'inproceedings',
    'book': 'book',
    'chapter': 'incollection',
    'preprint': 'unpublished',
    'thesis': 'phdthesis',
    'report': 'techreport',
    'misc': 'misc',
}

_RIS_FROM = {
    'JOUR': 'article', 'CONF': 'paper-conference', 'CPAPER': 'paper-conference',
    'BOOK': 'book', 'CHAP': 'chapter', 'THES': 'thesis', 'RPRT': 'report',
    'GEN': 'misc', 'ELEC': 'misc', 'UNPB': 'preprint',
}
_RIS_TO = {
    'article': 'JOUR',
    'paper-conference': 'CONF',
    'book': 'BOOK',
    'chapter': 'CHAP',
    'preprint': 'UNPB',
    'thesis': 'THES',
    'report': 'RPRT',
    'misc': 'GEN',
}

_CSL_FROM = {
    'article-journal': 'article', 'article-magazine': 'article',
    'article-newspaper': 'article', 'review': 'article',
    'paper-conference': 'paper-conference', 'proceedings-article': 'paper-conference',
    'book': 'book', 'chapter': 'chapter',
    'preprint': 'preprint', 'manuscript': 'preprint', 'posted-content': 'preprint',
    'thesis': 'thesis', 'dissertation': 'thesis',
    'report': 'report',
}
_CSL_TO = {
    'article': 'article-journal',
    'paper-conference': 'paper-conference',
    'book': 'book',
    'chapter': 'chapter',
    'preprint': 'preprint',
    'thesis': 'thesis',
    'report': 'report',
    'misc': 'article',
}

_CROSSREF_TYPE_FROM = {
    'journal-article': 'article', 'proceedings-article': 'paper-conference',
    'book': 'book', 'book-chapter': 'chapter', 'monograph': 'book',
    'posted-content': 'preprint', 'preprint': 'preprint',
    'dissertation': 'thesis', 'report': 'report',
}

_OPENALEX_TYPE_FROM = {
    'article': 'article', 'proceedings-article': 'paper-conference',
    'book': 'book', 'book-chapter': 'chapter',
    'preprint': 'preprint', 'dissertation': 'thesis', 'report': 'report',
    'review': 'article', 'letter': 'article', 'editorial': 'article',
}


@dataclass
class CanonicalWork:
    """文献元数据的规范中间结构。"""

    work_type: str = 'misc'
    title: str = ''
    authors: list = field(default_factory=list)
    year: Optional[int] = None
    container: str = ''
    doi: str = ''
    url: str = ''
    volume: str = ''
    issue: str = ''
    pages: str = ''
    publisher: str = ''
    extra: dict = field(default_factory=dict)

    def key_fields(self) -> dict:
        """往返测试用的关键字段快照。"""
        return {
            'work_type': self.work_type,
            'title': self.title,
            'authors': list(self.authors),
            'year': self.year,
            'container': self.container,
            'doi': self.doi,
            'url': self.url,
        }

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CanonicalWork':
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def normalize_doi(value: Any) -> str:
    """归一 DOI：去前缀、去空白、小写。空值返回 ''。"""
    text = str(value or '').strip()
    text = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', text, flags=re.I)
    return text.strip().lower()


def _year_from(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    m = re.search(r'(\d{4})', str(value))
    return int(m.group(1)) if m else None


def _first(value: Any) -> str:
    """Crossref 的 title/container-title 是列表，取第一个非空字符串。"""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
        return ''
    return str(value).strip() if value else ''


def _family_given(family: Any, given: Any) -> str:
    family, given = str(family or '').strip(), str(given or '').strip()
    if family and given:
        return f'{family}, {given}'
    return family or given


def _split_author_name(name: str) -> dict:
    """把 "Family, Given" 拆成 CSL 的 family/given；无逗号按 literal 处理。"""
    name = name.strip()
    if ',' in name:
        family, _, given = name.partition(',')
        out = {'family': family.strip()}
        if given.strip():
            out['given'] = given.strip()
        return out
    return {'literal': name}


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------

_BIBTEX_ENTRY_HEAD = re.compile(r'@([A-Za-z]+)\s*\{', re.M)


def _balanced_entries(text: str) -> Iterable[tuple]:
    """产出 (entry_type, citekey, body)。只支持花括号定界条目。"""
    pos = 0
    while True:
        m = _BIBTEX_ENTRY_HEAD.search(text, pos)
        if not m:
            return
        depth, i = 1, m.end()
        while i < len(text) and depth:
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
            i += 1
        body = text[m.end():i - 1]
        citekey, _, rest = body.partition(',')
        yield m.group(1).lower(), citekey.strip(), rest
        pos = i


def _split_top_level(body: str, sep: str = ',') -> list:
    parts, depth, in_quote, cur = [], 0, False, []
    for ch in body:
        if ch == '"':
            in_quote = not in_quote
        if not in_quote:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            elif ch == sep and depth == 0:
                parts.append(''.join(cur))
                cur = []
                continue
        cur.append(ch)
    if ''.join(cur).strip():
        parts.append(''.join(cur))
    return parts


def _clean_bibtex_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
    while value.startswith('{') and value.endswith('}'):
        depth, balanced = 0, True
        for idx, ch in enumerate(value):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and idx != len(value) - 1:
                    balanced = False
                    break
        if not balanced or depth != 0:
            break
        value = value[1:-1].strip()
    return value.replace('\n', ' ').strip()


def _parse_bibtex_fields(rest: str) -> dict:
    fields = {}
    for part in _split_top_level(rest):
        name, eq, raw = part.partition('=')
        if not eq:
            continue
        fields[name.strip().lower()] = _clean_bibtex_value(raw)
    return fields


TEX_REPLACEMENTS = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}',
                    '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
                    '_': r'\_', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}


def tex_escape(text) -> str:
    """LaTeX 特殊字符转义 (LA-07): 与 export_bibtex.tex_escape 同表,
    保证 interop 与导出脚本产出的 BibTeX 语义一致、可编译。"""
    return ''.join(TEX_REPLACEMENTS.get(c, c) for c in str(text))


def _bibtex_authors(value: str) -> list:
    """拆分 BibTeX author 字段为姓名列表。

    LA-08: 花括号包裹的机构名 (如 '{Harvard and MIT}') 整体保留, 不被
    ' and ' 拆成多人; 无逗号的片段按字面姓名保留, 不丢。"""
    authors = []
    for piece in re.findall(r'\{[^{}]*\}|[^{}]+', value or ''):
        piece = piece.strip()
        if not piece:
            continue
        if piece.startswith('{'):
            name = piece.strip('{}').strip()
            if name:
                authors.append(name)
            continue
        for chunk in re.split(r'\s*\band\b\s*', piece):
            name = chunk.strip().strip('{}').strip()
            if not name:
                continue
            if ',' in name:
                family, _, given = name.partition(',')
                name = _family_given(family, given)
            authors.append(name)
    return authors


def from_bibtex(text: str) -> list:
    """解析 BibTeX 文本为 CanonicalWork 列表（每个 @entry 一条）。"""
    works = []
    for entry_type, citekey, rest in _balanced_entries(text):
        fields = _parse_bibtex_fields(rest)
        work = CanonicalWork(
            work_type=_BIBTEX_FROM.get(entry_type, 'misc'),
            title=fields.get('title', ''),
            authors=_bibtex_authors(fields.get('author', '')),
            year=_year_from(fields.get('year')),
            container=fields.get('journal') or fields.get('booktitle') or fields.get('series', ''),
            doi=normalize_doi(fields.get('doi', '')),
            url=fields.get('url', ''),
            volume=fields.get('volume', ''),
            issue=fields.get('number', ''),
            pages=fields.get('pages', '').replace('--', '-'),
            publisher=fields.get('publisher', ''),
        )
        work.extra['citekey'] = citekey
        work.extra['bibtex_type'] = entry_type
        works.append(work)
    return works


def make_citekey(work: CanonicalWork) -> str:
    family = ''
    if work.authors:
        family = re.split(r'[,\s]', work.authors[0].strip(), maxsplit=1)[0]
    family = re.sub(r'[^A-Za-z0-9]', '', family).lower() or 'anon'
    year = str(work.year or 'nd')
    stop = {'the', 'and', 'for', 'with', 'from', 'that', 'this', 'into', 'using'}
    words = [w.lower() for w in re.findall(r'[A-Za-z]{4,}', work.title)
             if w.lower() not in stop]
    return f"{family}{year}{words[0] if words else 'work'}"


def to_bibtex(work: CanonicalWork, citekey: Optional[str] = None) -> str:
    """导出单条 BibTeX。container 按类型落到 journal 或 booktitle。

    LA-07: 所有字段值经 tex_escape 转义, %、&、_、括号等不再破坏语义与编译。
    """
    key = citekey or work.extra.get('citekey') or make_citekey(work)
    entry_type = _BIBTEX_TO.get(work.work_type, 'misc')
    pairs = []
    if work.title:
        pairs.append(('title', tex_escape(work.title)))
    if work.authors:
        pairs.append(('author', ' and '.join(work.authors)))
    if work.year:
        pairs.append(('year', str(work.year)))
    if work.container:
        container_field = 'journal' if work.work_type == 'article' else 'booktitle'
        if work.work_type in ('article', 'paper-conference', 'chapter'):
            pairs.append((container_field, tex_escape(work.container)))
    for name, value in (('volume', work.volume), ('number', work.issue),
                        ('pages', work.pages.replace('-', '--') if work.pages else ''),
                        ('publisher', work.publisher),
                        ('doi', work.doi), ('url', work.url)):
        if value:
            pairs.append((name, tex_escape(value)))
    body = ',\n'.join(f'  {name} = {{{value}}}' for name, value in pairs)
    return f'@{entry_type}{{{key},\n{body}\n}}'


# ---------------------------------------------------------------------------
# RIS
# ---------------------------------------------------------------------------

_RIS_TAG = re.compile(r'^([A-Z][A-Z0-9])  - (.*)$')


def from_ris(text: str) -> list:
    """解析 RIS 文本（支持多条记录，TY 开始、ER 结束）。"""
    records, current, last_tag = [], None, None
    for raw in text.splitlines():
        line = raw.rstrip('\r\n')
        m = _RIS_TAG.match(line)
        if m:
            tag, value = m.group(1), m.group(2).strip()
            if tag == 'TY':
                current = {'_multi': {}}
                last_tag = 'TY'
                current['_multi'].setdefault('TY', []).append(value)
                continue
            if current is None:
                continue
            current['_multi'].setdefault(tag, []).append(value)
            last_tag = tag
            if tag == 'ER':
                records.append(current['_multi'])
                current, last_tag = None, None
        elif current is not None and last_tag and line.strip():
            current['_multi'][last_tag][-1] += ' ' + line.strip()
    if current is not None:
        records.append(current['_multi'])

    works = []
    for rec in records:
        get = lambda *tags: next((rec[t][0] for t in tags if rec.get(t)), '')
        start, end = get('SP'), get('EP')
        pages = f'{start}-{end}' if start and end else (start or end)
        work = CanonicalWork(
            work_type=_RIS_FROM.get(get('TY').upper(), 'misc'),
            title=get('TI', 'T1'),
            authors=[a for a in rec.get('AU', []) + rec.get('A1', []) if a],
            year=_year_from(get('PY', 'Y1', 'DA')),
            container=get('JO', 'JF', 'JA', 'T2', 'BT'),
            doi=normalize_doi(get('DO')),
            url=get('UR'),
            volume=get('VL'),
            issue=get('IS'),
            pages=pages,
            publisher=get('PB'),
        )
        works.append(work)
    return works


def to_ris(work: CanonicalWork) -> str:
    """导出单条 RIS 记录。"""
    lines = [f'TY  - {_RIS_TO.get(work.work_type, "GEN")}']
    if work.title:
        lines.append(f'TI  - {work.title}')
    for author in work.authors:
        lines.append(f'AU  - {author}')
    if work.year:
        lines.append(f'PY  - {work.year}')
    if work.container:
        lines.append(f'JO  - {work.container}')
    if work.volume:
        lines.append(f'VL  - {work.volume}')
    if work.issue:
        lines.append(f'IS  - {work.issue}')
    if work.pages:
        start, _, end = work.pages.partition('-')
        lines.append(f'SP  - {start.strip()}')
        if end.strip():
            lines.append(f'EP  - {end.strip()}')
    if work.doi:
        lines.append(f'DO  - {work.doi}')
    if work.url:
        lines.append(f'UR  - {work.url}')
    if work.publisher:
        lines.append(f'PB  - {work.publisher}')
    lines.append('ER  - ')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# CSL-JSON
# ---------------------------------------------------------------------------

def from_csl_json(obj: dict) -> CanonicalWork:
    """解析单条 CSL-JSON 记录。"""
    authors = []
    for a in obj.get('author') or []:
        if a.get('literal'):
            authors.append(str(a['literal']).strip())
        else:
            name = _family_given(a.get('family'), a.get('given'))
            if name:
                authors.append(name)
    issued = obj.get('issued') or {}
    date_parts = issued.get('date-parts') or [[None]]
    year = _year_from(date_parts[0][0] if date_parts and date_parts[0] else None)
    container = obj.get('container-title') or ''
    if isinstance(container, list):
        container = _first(container)
    return CanonicalWork(
        work_type=_CSL_FROM.get(str(obj.get('type', '')).lower(), 'misc'),
        title=str(obj.get('title') or '').strip(),
        authors=authors,
        year=year,
        container=str(container).strip(),
        doi=normalize_doi(obj.get('DOI', '')),
        url=str(obj.get('URL') or '').strip(),
        volume=str(obj.get('volume') or ''),
        issue=str(obj.get('issue') or ''),
        pages=str(obj.get('page') or ''),
        publisher=str(obj.get('publisher') or ''),
    )


def to_csl_json(work: CanonicalWork) -> dict:
    """导出 CSL-JSON 记录（dict，可直接 json.dumps）。"""
    out = {'type': _CSL_TO.get(work.work_type, 'article')}
    if work.title:
        out['title'] = work.title
    if work.authors:
        out['author'] = [_split_author_name(a) for a in work.authors]
    if work.year:
        out['issued'] = {'date-parts': [[work.year]]}
    if work.container:
        out['container-title'] = work.container
    if work.volume:
        out['volume'] = work.volume
    if work.issue:
        out['issue'] = work.issue
    if work.pages:
        out['page'] = work.pages
    if work.doi:
        out['DOI'] = work.doi
    if work.url:
        out['URL'] = work.url
    if work.publisher:
        out['publisher'] = work.publisher
    return out


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

def from_crossref_json(obj: dict) -> CanonicalWork:
    """解析 Crossref REST 返回。接受完整信封（含 message）或单条 message。

    LA-06: message 含 items 是列表响应, 不是单条文献, 受控拒绝;
    用 from_crossref_search_results 逐条解析。
    LA-08: 只有 name、没有 family/given 的作者按字面名保留, 不消失。
    LA-09: 发表年只取 issued/published 系列; created 只记入 extra.registered_at,
    不再冒充发表年。
    """
    msg = obj.get('message', obj) if isinstance(obj, dict) else {}
    if 'items' in msg:
        raise ValueError('Crossref list response (message.items): 请用 '
                         'from_crossref_search_results 逐条解析, 不要把列表当单条文献')
    authors = []
    for a in msg.get('author') or []:
        name = _family_given(a.get('family'), a.get('given'))
        if not name:
            name = str(a.get('name') or '').strip()
        if name:
            authors.append(name)
    year = None
    for key in ('issued', 'published', 'published-print', 'published-online'):
        parts = (msg.get(key) or {}).get('date-parts')
        if parts and parts[0]:
            year = _year_from(parts[0][0])
            if year:
                break
    work = CanonicalWork(
        work_type=_CROSSREF_TYPE_FROM.get(str(msg.get('type', '')).lower(), 'misc'),
        title=_first(msg.get('title')),
        authors=authors,
        year=year,
        container=_first(msg.get('container-title')),
        doi=normalize_doi(msg.get('DOI', '')),
        url=str(msg.get('URL') or '').strip(),
        volume=str(msg.get('volume') or ''),
        issue=str(msg.get('issue') or ''),
        pages=str(msg.get('page') or ''),
        publisher=str(msg.get('publisher') or ''),
    )
    created = (msg.get('created') or {}).get('date-parts')
    if created and created[0] and created[0][0]:
        work.extra['registered_at'] = str(created[0][0])
    return work


def from_crossref_search_results(obj: dict) -> list:
    """Crossref 列表响应 ({message:{items:[...]}}) → CanonicalWork 列表 (LA-06)。"""
    items = ((obj or {}).get('message') or {}).get('items') or []
    return [from_crossref_json(item) for item in items]


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

def from_openalex_json(obj: dict) -> CanonicalWork:
    """解析 OpenAlex work 对象（select 裁剪后的子集也可）。"""
    authors = []
    for a in obj.get('authorships') or []:
        name = ((a or {}).get('author') or {}).get('display_name')
        if name:
            authors.append(str(name).strip())
    source = ((obj.get('primary_location') or {}).get('source') or {})
    container = str(source.get('display_name') or '').strip()
    if not container:
        container = str((obj.get('host_venue') or {}).get('display_name') or '').strip()
    biblio = obj.get('biblio') or {}
    first_page, last_page = biblio.get('first_page'), biblio.get('last_page')
    pages = ''
    if first_page:
        pages = f'{first_page}-{last_page}' if last_page else str(first_page)
    url = str(obj.get('id') or '').strip()
    landing = (obj.get('primary_location') or {}).get('landing_page_url')
    if landing:
        url = str(landing).strip()
    return CanonicalWork(
        work_type=_OPENALEX_TYPE_FROM.get(str(obj.get('type', '')).lower(), 'misc'),
        title=str(obj.get('title') or obj.get('display_name') or '').strip(),
        authors=authors,
        year=_year_from(obj.get('publication_year')),
        container=container,
        doi=normalize_doi(obj.get('doi', '')),
        url=url,
        volume=str(biblio.get('volume') or ''),
        issue=str(biblio.get('issue') or ''),
        pages=pages,
    )


if __name__ == '__main__':
    # 离线自检：每种格式一条样本做往返，断言关键字段保持。
    _bib = ('@article{vaswani2017attention,\n'
            '  title = {Attention Is All You Need},\n'
            '  author = {Vaswani, Ashish and Shazeer, Noam},\n'
            '  year = {2017},\n'
            '  journal = {Advances in Neural Information Processing Systems},\n'
            '  volume = {30},\n'
            '  doi = {10.5555/3295222.3295349},\n'
            '  url = {https://arxiv.org/abs/1706.03762}\n'
            '}')
    w = from_bibtex(_bib)[0]
    again = from_bibtex(to_bibtex(w))[0]
    assert again.key_fields() == w.key_fields(), 'bibtex round-trip'
    again = from_ris(to_ris(w))[0]
    assert again.key_fields() == w.key_fields(), 'ris round-trip'
    again = from_csl_json(to_csl_json(w))
    assert again.key_fields() == w.key_fields(), 'csl round-trip'
    print('interop self-test PASS')
