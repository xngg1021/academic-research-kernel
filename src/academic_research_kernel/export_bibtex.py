"""BibTeX 导出：Crossref/OpenAlex 元数据 → .bib 条目（工作流 I 的确定性层）。

tex_escape / bibtex_name / key 命名 / 类型对照为纯离线确定性逻辑；
未知字段留待核，不输出假的年份/期刊；live_crossref 明确标记，实际发起网络请求。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request

from .research.sources import controlled_urlopen as urlopen, reject_link_or_reparse


USER_AGENT = 'academic-research-kernel/1.2'

TEX_REPLACEMENTS = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}',
                    '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
                    '_': r'\_', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}

CROSSREF_TYPES = {
    'journal-article': 'article',
    'proceedings-article': 'inproceedings',
    'book': 'book',
    'monograph': 'book',
    'reference-book': 'book',
    'book-chapter': 'incollection',
    'dissertation': 'phdthesis',
    'posted-content': 'misc',
}
OPENALEX_TYPES = {
    'article': 'article',
    'book': 'book',
    'book-chapter': 'incollection',
    'dissertation': 'phdthesis',
    'preprint': 'misc',
}


def tex_escape(text) -> str:
    """LaTeX 特殊字符转义（输入为纯文本，非已转义 LaTeX）。"""
    return ''.join(TEX_REPLACEMENTS.get(c, c) for c in str(text))


def bibtex_name(author: dict) -> str:
    """优先 family/given；仅有字面姓名（name/display_name）时保留完整并置花括号待核。"""
    family, given = author.get('family'), author.get('given')
    if family:
        return tex_escape(family) + (', ' + tex_escape(given) if given else '')
    literal = author.get('name') or author.get('display_name')
    if not literal:
        raise ValueError('author name missing; do not invent')
    return '{' + tex_escape(literal) + '}'  # literal name; flag personal display_name for review


def protect_acronyms(title) -> str:
    """全大写缩写词（≥2 字符）加花括号，防止 LaTeX 转小写（幂等：已加花括号的词不重复包裹）。"""
    protected = []
    for token in str(title or '').split(' '):
        if (token.startswith('{') and token.endswith('}')) or (token.startswith(r'\{') and token.endswith(r'\}')):
            protected.append(token)
            continue
        core = token.strip('.,:;()[]')
        if (core.startswith('{') and core.endswith('}')) or (core.startswith(r'\{') and core.endswith(r'\}')):
            protected.append(token)
            continue
        if len(core) >= 2 and core.isupper() and any(c.isalpha() for c in core):
            protected.append('{' + token + '}')
        else:
            protected.append(token)
    return ' '.join(protected)


def entry_key(authors: list, year, title) -> str:
    """key 命名：第一作者姓 + 年份 + 标题首词，如 vaswani2017attention。"""
    family = 'anon'
    if authors:
        first = authors[0]
        family = first.get('family') or first.get('name') or first.get('display_name') or 'anon'
    family = re.sub(r'[^a-z0-9]', '', str(family).lower()) or 'anon'
    words = re.findall(r'[a-z0-9]+', (title or '').lower())
    first_word = words[0] if words else 'untitled'
    return f'{family}{year or "nd"}{first_word}'


def _crossref_year(message: dict):
    for key in ('published-print', 'published-online', 'issued'):
        parts = (message.get(key) or {}).get('date-parts')
        if parts and parts[0] and parts[0][0]:
            return parts[0][0]
    return None


def crossref_to_entry(message: dict) -> dict:
    """Crossref message → 条目 dict {'type', 'fields', 'todo'}；未知字段记入 todo。"""
    todo = []
    authors = [{'family': a.get('family'), 'given': a.get('given'), 'name': a.get('name')}
               for a in message.get('author') or []]
    if not authors:
        todo.append('author list missing; verify against original')
    title = ' '.join(message.get('title') or []) or None
    if not title:
        todo.append('title missing; verify against original')
    year = _crossref_year(message)
    if year is None:
        todo.append('year missing; verify against original')
    container = message.get('container-title') or []
    entry_type = CROSSREF_TYPES.get(message.get('type'), 'misc')
    doi = (message.get('DOI') or '').lower() or None
    fields = {}
    if authors:
        fields['author'] = ' and '.join(bibtex_name(a) for a in authors)
    if title:
        fields['title'] = protect_acronyms(tex_escape(title))
    if entry_type == 'inproceedings':
        if container:
            fields['booktitle'] = tex_escape(container[0])
        else:
            todo.append('booktitle missing; verify against original')
    elif entry_type == 'article':
        if container:
            fields['journal'] = tex_escape(container[0])
        else:
            todo.append('journal missing; verify against original')
    elif entry_type == 'book':
        if message.get('publisher'):
            fields['publisher'] = tex_escape(message['publisher'])
    elif entry_type == 'incollection':
        # LA-05: 书籍章节保留书级容器信息 (书名 + 出版社)
        if container:
            fields['booktitle'] = tex_escape(container[0])
        else:
            todo.append('booktitle missing; verify against original')
        if message.get('publisher'):
            fields['publisher'] = tex_escape(message['publisher'])
    elif entry_type == 'phdthesis':
        school = (message.get('institution') or {}).get('name') or message.get('publisher')
        if school:
            fields['school'] = tex_escape(school)
    if year:
        fields['year'] = str(year)
    for src, dst in (('volume', 'volume'), ('issue', 'number'), ('page', 'pages')):
        if message.get(src):
            fields[dst] = tex_escape(message[src])
    if doi:
        fields['doi'] = doi
        arxiv = re.match(r'^10\.48550/arxiv\.(\S+)$', doi)
        if arxiv:
            fields['eprint'] = arxiv.group(1)
            fields['archiveprefix'] = 'arXiv'
    return {'type': entry_type, 'key': entry_key(authors, year, title),
            'fields': fields, 'todo': todo}


def openalex_to_entry(work: dict) -> dict:
    """OpenAlex work → 条目 dict。display_name 不猜姓/名边界，按字面姓名置花括号待核。"""
    todo = []
    authors = [{'display_name': (a.get('author') or {}).get('display_name')}
               for a in work.get('authorships') or []]
    if not authors:
        todo.append('author list missing; verify against original')
    title = work.get('title')
    if not title:
        todo.append('title missing; verify against original')
    year = work.get('publication_year')
    if year is None:
        todo.append('year missing; verify against original')
    type_crossref = work.get('type_crossref')
    entry_type = CROSSREF_TYPES.get(type_crossref) or OPENALEX_TYPES.get(work.get('type'), 'misc')
    source = ((work.get('primary_location') or {}).get('source') or {})
    venue = source.get('display_name')
    biblio = work.get('biblio') or {}
    doi = (work.get('doi') or '').lower().removeprefix('https://doi.org/') or None
    fields = {}
    if authors:
        fields['author'] = ' and '.join(bibtex_name(a) for a in authors)
    if title:
        fields['title'] = protect_acronyms(tex_escape(title))
    if entry_type == 'inproceedings':
        if venue:
            fields['booktitle'] = tex_escape(venue)
        else:
            todo.append('booktitle missing; verify against original')
    elif entry_type == 'article':
        if venue:
            fields['journal'] = tex_escape(venue)
        else:
            todo.append('journal missing; verify against original')
    elif entry_type == 'incollection':
        # LA-05: 书籍章节保留书级容器信息 (书名 + 出版社)
        if venue:
            fields['booktitle'] = tex_escape(venue)
        else:
            todo.append('booktitle missing; verify against original')
        publisher = ((work.get('primary_location') or {}).get('source') or {}).get(
            'host_organization_name')
        if publisher:
            fields['publisher'] = tex_escape(publisher)
    if year:
        fields['year'] = str(year)
    for src, dst in (('volume', 'volume'), ('issue', 'number')):
        if biblio.get(src):
            fields[dst] = tex_escape(biblio[src])
    if biblio.get('first_page'):
        pages = biblio['first_page'] + ('--' + biblio['last_page'] if biblio.get('last_page') else '')
        fields['pages'] = tex_escape(pages)
    if doi:
        fields['doi'] = doi
    todo.append('OpenAlex display_name 无可靠姓/名边界，姓名字段按字面保留，须核对原文')
    return {'type': entry_type, 'key': entry_key(authors, year, title),
            'fields': fields, 'todo': todo}


FIELD_ORDER = ('author', 'title', 'journal', 'booktitle', 'publisher', 'school',
               'year', 'volume', 'number', 'pages', 'doi', 'eprint', 'archiveprefix', 'note')


def format_entry(entry: dict) -> str:
    """渲染单条 BibTeX；todo 项以 % 注释留在条目前，不伪造字段。"""
    lines = ['% TODO: ' + item for item in entry['todo']]
    ordered = [name for name in FIELD_ORDER if name in entry['fields']]
    ordered += [name for name in entry['fields'] if name not in FIELD_ORDER]
    lines.append('@' + entry['type'] + '{' + entry['key'] + ',')
    for index, name in enumerate(ordered):
        comma = ',' if index < len(ordered) - 1 else ''
        lines.append(f'  {name} = {{{entry["fields"][name]}}}{comma}')
    lines.append('}')
    return '\n'.join(lines)


def live_crossref(doi: str) -> dict:
    """LIVE: 查 Crossref message（无 key；带 User-Agent，429/5xx 有界退避）。"""
    headers = {'User-Agent': USER_AGENT}
    url = 'https://api.crossref.org/works/' + quote(doi, safe='')
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                return json.load(response)['message']
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            retry = error.headers.get('Retry-After', '')
            delay = float(retry) if retry.isdigit() else 2 ** attempt
            if delay > 10:
                raise
            time.sleep(delay)
    return None


def _load_works(path: str, source: str) -> list:
    p = reject_link_or_reparse(path)
    with p.open(encoding='utf-8') as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if source == 'crossref' and isinstance(data.get('message'), dict):
            msg = data['message']
            if isinstance(msg.get('items'), list):
                return msg['items']
            return [msg]
        if isinstance(data.get('results'), list):
            return data['results']
        if isinstance(data.get('items'), list):
            return data['items']
        return [data]
    raise ValueError('input JSON must be a work, a list of works, or an object with results/items')


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
