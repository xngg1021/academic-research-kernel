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
from urllib.request import Request, urlopen

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

USER_AGENT = 'hermes-academic-skills/1.2'

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
    """全大写缩写词（≥2 字符）加花括号，防止 LaTeX 转小写。"""
    protected = []
    for token in str(title or '').split(' '):
        core = token.strip('.,:;()[]')
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
    with open(path, encoding='utf-8') as handle:
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='离线：--input works.json --source crossref|openalex；在线：--doi 查 Crossref。'
               '生成后须过 biber --tool 或 Overleaf 编译检查，批量时抽查 3 条逐字段对照。')
    parser.add_argument('--input', help='元数据 JSON 文件（Crossref message 或 OpenAlex work 列表）')
    parser.add_argument('--source', choices=['crossref', 'openalex'], default='crossref',
                        help='--input 的元数据来源（默认 crossref）')
    parser.add_argument('--doi', help='LIVE：按 DOI 查 Crossref 并导出单条')
    args = parser.parse_args(argv)
    _utf8_stdio()

    if args.doi:
        doi = args.doi.lower().removeprefix('https://doi.org/').strip().strip('/')
        try:
            works, source = [live_crossref(doi)], 'crossref'
        except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as error:
            print(json.dumps({'status': 'failed', 'error': f'{type(error).__name__}: {error}'},
                             ensure_ascii=False, indent=2))
            return 1
    elif args.input:
        try:
            works, source = _load_works(args.input, args.source), args.source
        except (OSError, ValueError) as error:
            print(json.dumps({'status': 'failed', 'error': f'{type(error).__name__}: {error}'},
                             ensure_ascii=False, indent=2))
            return 1
    else:
        parser.error('给 --input 或 --doi 之一')

    converter = crossref_to_entry if source == 'crossref' else openalex_to_entry
    seen_keys = set()
    blocks = []
    for work in works:
        entry = converter(work)
        key = entry['key']
        if key in seen_keys:  # 同一 bib 内 key 不重复
            suffix = 2
            while f'{key}{suffix}' in seen_keys:
                suffix += 1
            entry['todo'].append(f'key deduplicated: {key} -> {key}{suffix}')
            key = f'{key}{suffix}'
            entry['key'] = key
        seen_keys.add(key)
        blocks.append(format_entry(entry))
    print('\n\n'.join(blocks))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
