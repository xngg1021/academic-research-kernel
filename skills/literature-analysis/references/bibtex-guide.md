# BibTeX 生成指南（BibTeX Export）

对应工作流 I。从 OpenAlex/Crossref 元数据生成 BibTeX 条目，与 Zotero、Overleaf 互通。

## 条目类型对照

| 文献类型 | BibTeX 类型 | 必填字段 |
| --- | --- | --- |
| 期刊论文 | @article | author, title, journal, year, volume, number, pages, doi |
| 会议论文 | @inproceedings | author, title, booktitle, year, pages, doi |
| 书籍 | @book | author/editor, title, publisher, year |
| 学位论文 | @phdthesis / @mastersthesis | author, title, school, year |
| 预印本 | @misc | author, title, year, eprint(arXiv ID), archivePrefix="arXiv" |
| 网页 | @misc | author, title, year, howpublished="\\url{...}", note=访问日期 |

## 生成规则

- 作者字段：`and` 连接；"姓, 名"形式（BibTeX 对姓前名后最稳）；中文作者写全名。
- 标题：保持原文大小写，易被 LaTeX 转为小写的缩写词（例如 IEEE、GPT 或 RAG）须使用花括号包裹：`title = {A Survey on {RAG}}`。
- DOI：有 DOI 就写 `doi` 字段，不带 URL 前缀。
- key 命名：`第一作者姓+年份+标题首词`，如 `vaswani2017attention`，同一 bib 内不重复。
- 优先取 Crossref 给出的 family/given 或机构 name；OpenAlex display_name 不包含可靠姓/名边界，不用 rsplit 猜复姓/文化命名规则。只有 display_name 时保留完整字面姓名并标待核，不能默默重排。
- 文献类型、作者姓名、卷期页码与 DOI 是否必需取决于具体条目类型与排版样式，上表是收集清单，并非所有格式都必填。OpenAlex primary_location/source 均可能为 null；先用 `(w.get('primary_location') or {}).get('source') or {}` 再取字段。完整作者表可能被截断，须核对原文。
- 以下可运行示例使用结构化 Crossref 元数据；生产输入替换 fixture，未知字段留待核，不输出假的年份/期刊：

```python
# smoke-test: true
def tex_escape(text):
    replacements = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}',
                    '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
                    '_': r'\_', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(replacements.get(c, c) for c in str(text))

def bibtex_name(author):
    family, given = author.get('family'), author.get('given')
    if family:
        return tex_escape(family) + (', ' + tex_escape(given) if given else '')
    literal = author.get('name') or author.get('display_name')
    if not literal:
        raise ValueError('author name missing; do not invent')
    return '{' + tex_escape(literal) + '}'  # literal name; flag personal display_name for review

authors = [{'family': 'LeCun', 'given': 'Yann'},
           {'family': 'de la Cruz', 'given': 'María'}, {'name': 'Research & Co.'}]
author_field = ' and '.join(map(bibtex_name, authors))
assert bibtex_name(authors[0]) == 'LeCun, Yann'
assert bibtex_name(authors[1]) == 'de la Cruz, María'
assert bibtex_name({'display_name': '王小明'}) == '{王小明}'
assert tex_escape('A_{B} & 5%') == r'A\_\{B\} \& 5\%'
title = tex_escape('Example {RAG} & Methods')  # plain-text title, not pre-escaped LaTeX
entry = '@misc{example,\n  author = {' + author_field + '},\n  title = {{' + title + '}}\n}'
print(entry)  # illustrative misc; no fabricated year/DOI/journal
```

## 中文文献

中文文献推荐用 biblatex 的 gb7714-2015 样式包（`biblatex-gb7714-2015`，对应旧版 GB/T 7714-2015；现行 2025 需先确认样式包版本支持，不能自动视为等价），普通 BibTeX 对中文排序与"等/et al."处理不佳。中文期刊文章条目字段与英文相同，author 写中文全名。

## 验证

生成的 .bib 文件必须过一遍 `biber --tool` 或 Overleaf 编译检查；批量生成时抽查 3 条与原始元数据逐字段对照。
