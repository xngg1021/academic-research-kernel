---
name: academic-source-verification
description: "核查文献真实性:交叉核对被引数、撤稿状态、开放获取全文与原文内容."
version: 1.1.1
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
required_environment_variables:
  - name: OPENALEX_API_KEY
    prompt: "OpenAlex API key（可跳过，使用匿名查询）"
    help: "在 OpenAlex 官方账户中获取免费 key；不要把 key 写进技能或聊天。"
    required_for: "Authenticated OpenAlex requests; anonymous queries remain available."
  - name: UNPAYWALL_EMAIL
    prompt: "Unpaywall 联系邮箱（可跳过此服务）"
    help: "填写您自己的真实联系邮箱；跳过时继续其他来源检查。"
    required_for: "Unpaywall OA lookup only; other source checks remain available."
metadata:
  hermes:
    tags: [research, citations, open-access, crossref, openalex, semantic-scholar, unpaywall, retraction]
    related_skills: [arxiv, pdf, grounded-citations, literature-analysis]
---

# 学术来源核查 Skill

验证一篇论文/文献是否真实存在、交叉核对它的元数据与被引数、核查撤稿与更正状态、下载可获得的开放获取全文做内容验证。与 `arxiv` skill 互补：`arxiv` 负责"检索发现论文"，本 skill 负责"核查论文 + 拿全文"。

核心原则：引用一个科研结论前，先核对文献身份、已知撤稿信号、被引数口径和结论原文——而不是凭记忆或二手转述。

## When to Use

- 用户要求"下载论文交叉核查""验证这个文献是不是真的""核对被引数"
- 建模/论证里引用了文献，需要坐实它的标题/作者/年份/期刊/被引数
- 需要拿到论文全文（开放获取）并确认下载的是正确的那篇
- 核查一篇文献是否已被撤稿或发过更正（引用的底线检查）
- 查经典专著/公版书的原文（Ebbinghaus 遗忘曲线、Miller 1956 等）

Don't use for: 纯检索发现论文（用 `arxiv` skill）、OCR/解析已下载的 PDF 正文（用 `pdf`）。

## Prerequisites

网络请求使用 Python stdlib urllib；PDF 提取需单独检查 pymupdf。OpenAlex 可匿名小规模查询，建议免费 key；Unpaywall 要求用户真实联系邮箱。各服务均有限额，免费访问不保证无需配置：

| 服务 | 用途 | 限制 |
| --- | --- | --- |
| OpenAlex | 元数据、主题、OA 与撤稿标记 | 匿名 $0.10/日、免费 key $1/日预算；超过预算或 100 req/s 返回 429 |
| Crossref | Crossref 收录口径被引数 + **撤稿/更正记录** | 非 Crossref 注册 DOI 可返回 404（例如 DataCite 注册的 arXiv DOI） |
| Semantic Scholar | 另一数据库的被引数口径 | 匿名共享限额易 429；key 初始额度 1 req/s，按分配额度执行 |
| Unpaywall | OA 全文定位（is_oa + best_oa_location） | 需带 email 参数 |

## 核查四道关

### 第一关：三库交叉核对（真实性 + 被引数）

核对 DOI、标题、作者及版本，记录三个数据库的差异。数据库可能共享出版商/Crossref 数据，不能把一致性当作三个独立证明；被引数不用于判定身份。

| 库 | 端点 | 关键字段 |
| --- | --- | --- |
| OpenAlex | `https://api.openalex.org/works/https://doi.org/{DOI}` | `cited_by_count`、`publication_year`、`authorships`、`primary_location.source.display_name`、`open_access.oa_status` + `oa_url` |
| Crossref | `https://api.crossref.org/works/{DOI}` | `message.is-referenced-by-count` |
| Semantic Scholar | `https://api.semanticscholar.org/graph/v1/paper/DOI:{DOI}?fields=title,authors,year,venue,citationCount,influentialCitationCount,openAccessPdf`（或 `arXiv:{id}`） | `citationCount` |

请求要带 `User-Agent`（带 mailto 更礼貌），否则部分端点会拒。三库被引数必然不同（收录范围不同），分数量级差异也可来自版本合并/收录范围，须解释而不据此否定论文身份。

用 `execute_code` 批量查并打印对照表；按各服务实际配额控制调用速率；固定 sleep 不能保证避免共享限额的 429。

### 第二关：撤稿与更正核查（Crossref update 记录）

Crossref 于 2025-01 将 Retraction Watch 信号纳入 REST API（2023-09 是合作/收购时间）。记录原始 DOI、通知 DOI、类型、source 和查询时间。`update-to` 通常位于通知记录，指向被更新对象；不能把通知本身判成被撤稿论文。`message.type` 是文献类型，不是撤稿类型。

1. 查原文 DOI 元数据；标题 `RETRACTED:` / `WITHDRAWN:` 前缀只作需核实信号，普通标题用词不是结论。
2. 反向查 `https://api.crossref.org/works?filter=updates:<DOI>&rows=100`，逐项核对 `update-to[].DOI` 是否是目标 DOI。超过一页则用 Crossref 自己的 cursor 规则继续，记录截断。
3. 区分 `retraction`、`withdrawal`、`correction`、`expression-of-concern`，记录 publisher / retraction-watch 来源；不同信号不合并成“撤稿”。
4. OpenAlex `is_retracted=true` 表示数据库记录的撤稿信号；false 不排除遗漏。arXiv 另查 abs 页及版本历史的 withdrawal 状态；有疑问核对出版社通知或 Retraction Watch 原记录。

以下离线逻辑只提取与目标关联的更新信号，输入须来自已成功查询的 Crossref 记录：

```python
# smoke-test: true
def update_signals(target_doi, records):
    target = target_doi.lower().removeprefix('https://doi.org/')
    signals = []
    for record in records:
        for update in record.get('update-to') or []:
            updated_doi = str(update.get('DOI') or '').lower().removeprefix('https://doi.org/')
            if updated_doi == target:
                signals.append({'type': update.get('type'), 'source': update.get('source'),
                                'record_doi': record.get('DOI'), 'target_doi': updated_doi})
    return signals
fixture = {'DOI': '10.1234/notice', 'update-to': [
    {'DOI': '10.1234/original', 'type': 'retraction', 'source': 'publisher'}]}
assert update_signals('10.1234/original', [fixture])[0]['type'] == 'retraction'
assert update_signals('10.1234/notice', [fixture]) == []
assert update_signals('10.1234/original', [{'DOI': '10.1234/original'}]) == []
```

查无信号时只报告“在已检查的数据源中未发现撤稿/撤回记录”，附来源、时间、失败/未查项。请求失败不算未发现记录。命中时说明“数据库标记/出版社通知确认”的证据层次；撤稿论文可作为撤稿事件研究对象，不能无说明地当作可靠结论依据。

官方依据：[Crossref 集成说明](https://www.crossref.org/blog/retraction-watch-retractions-now-in-the-crossref-api/)、[更新查询过滤器](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)。

### 第三关：OA 全文定位（Unpaywall 首选）

Unpaywall 是 OA 定位渠道之一，覆盖率和更新延迟与其他来源不同，未作普遍优劣保证。以下片段依赖 Verification 的 get() 与待查 doi：

```python
# fragment: 需 get、doi；UNPAYWALL_EMAIL 为用户真实联系邮箱。
import os
from urllib.parse import quote, urlencode
email = os.environ['UNPAYWALL_EMAIL']
r = get('https://api.unpaywall.org/v2/' + quote(doi, safe='') + '?' + urlencode({'email': email}))
if r.get("is_oa"):
    loc = r.get("best_oa_location")  # url_for_pdf / url，版本 published/accepted/submitted
else:
    loc = None  # 此服务未定位到 OA 版本，不证明不存在
```

顺序：Unpaywall `best_oa_location` → OpenAlex `oa_url` → Semantic Scholar `openAccessPdf.url` → archive.org（公版书/专著）。付费墙 403 不要死磕。

### 第四关：下载与内容核对

- **arXiv（绿 OA）**：`https://arxiv.org/pdf/{id}`；可因限流、撤回或网络限制失败。
- **公版书/专著（如 Ebbinghaus 1885）**：走 `archive.org` —— 先用 `https://archive.org/advancedsearch.php?q=<标题>&fl[]=identifier,title,year,mediatype&rows=3&output=json` 搜 identifier，再查 `https://archive.org/metadata/{identifier}` 的 files 选择实际 PDF 文件名；不假定文件名与 identifier 相同，并核对访问状态。

```python
# fragment: API reference; supply the named input variables and required imports.
import pymupdf
doc = pymupdf.open(path)
print(" ".join(doc[0].get_text().split())[:400])  # 首页文字，核对标题/作者
print(doc.page_count)
doc.close()
```

下载统一存到稳定目录（例如 `Path("~/papers").expanduser()` 并 `mkdir(parents=True, exist_ok=True)`，路径保证 UTF-8 可用），回报绝对路径 + 字节数 + 页数。

## Procedure

1. 确定论文的 DOI/arXiv ID/标题。期刊论文用 DOI，arXiv 预印本用 arXiv ID。
2. `execute_code` 批量查 OpenAlex + Crossref（+ Semantic Scholar），打印三库标题/作者/年份/期刊/被引数对照表。
3. 按第二关核查双向更新关系、OpenAlex 标记及出版社/arXiv 状态，分类记录，避免把通知记录判成被撤稿对象。
4. 判断真实性：DOI、元数据与版本匹配 → 报告身份已核对。不一致 → 记下差异，如实报告。
5. 能下 OA 就下（Unpaywall/arXiv/archive.org），下完用 pymupdf 提首页文字核对内容。
6. 付费墙 403 的，报告已完成的实际检查与“全文访问受限”；403 也可能是反爬/访问策略，不据此断定付费墙或撤稿状态，不反复尝试。

## Pitfalls

1. **被引数有来源口径**。预印本与正式版本的合并、重复记录及数据库覆盖都会影响计数，标明来源和查询日；不把某库数值称为真实影响或严格下限。
2. **Crossref 与 OpenAlex 查 arXiv 的 data-DOI 可能 404/滞后**。`10.48550/arXiv.<id>` 是 DataCite 注册的，Crossref 常返回 404，OpenAlex 偶有收录延迟。遇此情况直接调用 arXiv 官方 API（`http://export.arxiv.org/api/query?id_list=<id>` 或 `search_query=ti:<标题>`）核实标题、摘要、版本历史及撤回（withdrawn）状态。
3. **经典奠基文献标题易与后继综述撞车**。以简短通用标题（如 "Working Memory"）检索时，极易命中作者多年后的同名回顾篇。核查奠基作须限定出版年份（Crossref `filter=from-pub-date:YYYY-01-01,until-pub-date:YYYY-12-31`）并核对作者序列表。
4. **Semantic Scholar 无 key 极易 429**。请求间隔 ≥1.1s，失败退避重试；持续 429 就退回 OpenAlex + Crossref 两个来源，并如实说明。
4. **update-to 非空 ≠ 撤稿**。还须核对更新方向、目标 DOI 与 update.type；更正和表达关注分别记录，不能见 update-to 就报撤稿。
5. **出版商 PDF 付费墙，脚本下载 403**。OpenAlex 的 `oa_status: "bronze"` 只表示"在出版商网站免费可读"，不代表能脚本下载（Wiley 的 pdfdirect 就是 403）。403 后报告访问受限，不循环重试。
6. **下载成功 ≠ 内容正确**。必须提取 PDF 首页文字核对标题/作者，防止下到同名错误文件。
7. **Unpaywall 的 email 参数有硬校验**。使用自己的真实联系邮箱；服务可用 422 拒绝缺失/示例邮箱，不推断邮箱域名的 DNS 行为。`is_oa=false` 时 `best_oa_location` 为 null，先判再取。

输出语言：默认跟随用户输入语言（用户用什么语言问就用什么语言答）；论文标题与引文保留原文，译名首次出现时附原文。

## Verification

```python
# external-test: true
import json, os, time
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, urlencode, quote
from urllib.error import HTTPError

def get(url):
    headers = {'User-Agent': 'hermes-academic-skills/1.2'}
    if urlsplit(url).netloc == 'api.openalex.org' and os.environ.get('OPENALEX_API_KEY'):
        headers['Authorization'] = 'Bearer ' + os.environ['OPENALEX_API_KEY']
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            # 有界退避；长预算封锁交给调用者报告，不循环耗尽免费服务。
            retry = error.headers.get('Retry-After', '')
            delay = float(retry) if retry.isdigit() else 2**attempt
            if delay > 10:
                raise
            time.sleep(delay)

doi = '10.1038/nature14539'
oa = get('https://api.openalex.org/works/https://doi.org/' + quote(doi, safe=''))
assert oa.get('doi', '').lower() == 'https://doi.org/' + doi
assert 'deep learning' in oa['title'].lower()
assert isinstance(oa.get('is_retracted'), bool)
cr = get('https://api.crossref.org/works/' + quote(doi, safe=''))['message']
assert cr['DOI'].lower() == doi and 'deep learning' in ' '.join(cr['title']).lower()
original = '10.1177/1758835920922055'
updates = get('https://api.crossref.org/works?' + urlencode({'filter': 'updates:' + original, 'rows': 5}))['message']
assert any(u.get('DOI', '').lower() == original and u.get('type') == 'retraction'
           for item in updates['items'] for u in item.get('update-to', []))
print('OpenAlex/Crossref identity + reverse retraction lookup passed')
email = os.environ.get('UNPAYWALL_EMAIL')
if email:
    up = get('https://api.unpaywall.org/v2/' + quote(doi, safe='') + '?' + urlencode({'email': email}))
    assert isinstance(up.get('is_oa'), bool) and up['doi'].lower() == doi
    print('Unpaywall passed')
else:
    print('SKIP Unpaywall: UNPAYWALL_EMAIL not configured; no result inferred')
```

无 key 时 OpenAlex 自检会实际走匿名路径；带 key 路径仅在配置 OPENALEX_API_KEY 后运行。未配置服务应明确 SKIP，不当作通过。Semantic Scholar 按任务与可用额度另行核对。