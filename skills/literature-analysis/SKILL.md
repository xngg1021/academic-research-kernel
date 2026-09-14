---
name: literature-analysis
description: "文献分析:相似论文检索、查重比对、矛盾与反证、作者档案、模拟审稿、谬误标注."
version: 1.2.0
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
required_environment_variables:
  - name: OPENALEX_API_KEY
    prompt: "OpenAlex API key（可跳过，使用匿名查询）"
    help: "在 OpenAlex 官方账户中获取免费 key；不要把 key 写进技能或聊天。"
    required_for: "Authenticated OpenAlex requests; anonymous queries remain available."
metadata:
  hermes:
    tags: [research, literature, similarity, plagiarism, peer-review, fallacy, openalex]
    related_skills: [academic-source-verification, arxiv, grounded-citations]
---

# 文献分析 Skill

围绕一篇论文或一个概念做六类分析：相似论文检索、查重比对、矛盾与反证查找、作者档案、模拟审稿、逻辑谬误标注。与 `academic-source-verification` 互补：那个 skill 负责"这篇论文是否真实、是否被撤稿、全文在哪"，本 skill 负责"围绕它做研究分析"。

核心原则：每一步结论都给出数据来源（哪个 API、哪个字段、哪段原文），能自动化的自动化，不能自动化的（审稿、谬误判断）交给模型按模板执行并保留可核对引文。

## When to Use

- 用户发一个概念/研究问题，要求"找相似题材的论文"
- 用户发论文链接或 PDF 文件，要求"找同款研究""查重""看有没有人做过"
- 用户要求"查找这篇论文的反证""有没有论文反对这个结论"
- 用户要求"模拟审稿""假装是审稿人审一下这篇"
- 用户要求"标注这篇文章的逻辑谬误"
- 用户给出作者姓名，要求查其学术档案
- 用户要求批量文献综述（对比矩阵）、按主题反查候选期刊、生成 BibTeX 条目
- 用户要求双语对照精读英文论文、分析研究空白、找论文官方代码与数据集复现

## Prerequisites（渠道分层）

按三类渠道聚合，默认只用免费层，白嫖层与付费层由用户自行接入（key 写进环境变量，禁止写进技能文件）。

免费/公开渠道（有配额及配置要求）：OpenAlex（匿名 $0.10/日、免费 key $1/日预算，超过预算或 100 req/s 返回 429）、Crossref（无 key，含多语言元数据查询）、Unpaywall（带 email 参数）、arXiv、Europe PMC（api.europepmc.org，无 key）、PubMed E-utilities（无 key，生物医学）、DOAJ。母语文献补充渠道：中文走知网/万方网页检索（无公开 API）；日文走 CiNii（按当前具体 API 核实 appid 要求）；俄文与东欧文献经 Crossref 收录。

可选账户渠道（访问条件须核对）：Semantic Scholar（key 有独立配额（初始 1 req/s）；contexts 可用性按当前端点授权/数据判断，不保证 key 解锁或内容齐全）、Scite（试用/访问条件以当前账户为准，查询引用立场）、Dimensions 免费版（仅网页无 API）、CiNii API（日本文献，按当前端点要求配置）。

付费层（自备 key，自行接入）：Scopus API、Web of Science API、Dimensions API、Scite Pro。AI 生成成分检测的免费/付费渠道在 `academic-writing` 技能的工作流 D。

所有请求带 `User-Agent`（含 mailto）。URL 一律用 `https://api.openalex.org/works/...`（注意 api 域名；实体 id 形如 `https://openalex.org/W...` 是实体标识；机器请求使用 API 域名，不保证网页地址的 HTTP 状态）。


### OpenAlex 当前查询约定（2026-09-06 核查）

所有 URL 示例均为请求模板，实际用 urllib.parse.urlencode 编码参数；免费 key 用 OPENALEX_API_KEY 环境变量构造 Authorization: Bearer 头。匿名可技术调用但预算较低，按查询类型计费，不能把预算换成固定无限请求数。官方当前每页最多 100；采用 per_page 与 group_by，未证实旧连字符别名有确定移除日期。

取多页从 cursor=* 开始，把 meta.next_cursor 原样编码带回；直到 null、空结果或显式预算上限。达到上限必须标“部分样本”，不能称全部引用者。计数/趋势比较统一 corpus=core（如需扩展则各查询同时用 corpus=all）、日期窗口与文献类型，记录查询时间。

Concepts 已弃用且不再维护，不作为主要路径；旧数据回顾只能显式标 legacy。真正 bibliographic coupling 需比较两文 referenced_works 的交集/并集；co-citation 则需引用者同时引用两篇的计数，两者均不可由 related_works 代替。

官方依据：[认证与限额](https://help.openalex.org/api/authentication/)、[当前查询速查](https://help.openalex.org/api/llm-quick-reference/)、[字段语义](https://help.openalex.org/data/works/attributes/)、[分页](https://help.openalex.org/api/paging/)。

## 工作流 A：相似论文查找

输入有三种形态，先归一化为 DOI 或概念文本：

1. **概念文本**（如"检索增强生成中的幻觉抑制"）→ OpenAlex 概念搜索：
   `GET https://api.openalex.org/works?search=<概念>&per_page=10&sort=relevance_score:desc&select=title,publication_year,cited_by_count,doi`
2. **论文链接/DOI** → 先查该论文本体，再取三层相似：
   - `related_works`（算法推荐：与目标共享较多 topics 的近期论文，不是引用耦合）
   - `topics` ID 交叉（用 topics[].id 比较，primary_topic 表示主主题；score 为分类得分，不是论文相似概率）
   - 标题词组合搜索（用论文标题关键词再跑一次概念搜索）
3. **PDF 文件** → pymupdf 提首页标题与摘要文本，用标题/摘要作概念搜索。

输出格式：每个候选论文一行（标题、年份、被引数、DOI、相似依据），标注相似依据是哪一层（文本检索/算法推荐/主题交叉），并按依据强度排序。概念检索命中按 `relevance_score` 排序即可。

## 工作流 B：查重比对（本地句级）

诚实边界先说明：真正的全网查重需要商业服务（iThenticate/Turnitin），本 skill 做的是"目标论文 vs 候选相似论文集合"的本地句子级比对，用于发现与指定集合的逐字/近似重叠，不声称覆盖全网。

步骤：

1. 用工作流 A 拿到候选相似论文列表（10~20 篇），能下 OA 全文的尽量下。
2. 目标论文提全文：`doc = pymupdf.open(path); text = " ".join(p.get_text() for p in doc)`。
3. 句子切分与规范化：按句号/换行切句，去掉空白、页码、参考文献段，全小写，长度 20 字符以下的句子丢弃。
4. 对每篇候选论文做同样的句子集合。
5. 比对：完全相同的句子（逐字重复）与高度相似句子（difflib 的 `SequenceMatcher.ratio() > 0.85`）。
6. 报告：重叠句对数、占目标论文总句数的比例、重叠句子原文与出处段落。

```python
# fragment: API reference; supply the named input variables and required imports.
from difflib import SequenceMatcher
def overlap_ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()
```

判定参考：单篇候选与目标的重叠率 >5% 或存在连续 3 句以上逐字相同 → 标黄；>15% → 标红。同时报告版本与发表时间、引号/引用和公共方法文本；这些阈值仅作本地筛查提示，时间先后与句子重叠不能单独证明抄袭或方向。目标句子每句只计一次，避免重复匹配使比例超过 100%。

## 工作流 C：矛盾与反证查找

两层方法，顺序执行：

1. **引用池甄别**（主路径）：分页获取目标论文引用者作为候选池，设定预算/页数上限并报告已取数量：
   `GET https://api.openalex.org/works?filter=cites:<OpenAlex-WID>&per_page=25&select=id,title,abstract_inverted_index,publication_year,doi`
   摘要三层兜底（缺失率依领域/时间而异，不能从三篇抽样外推）：第一层 `abstract_inverted_index` 重建；第二层缺失时查 Crossref `works/{DOI}` 的 `message.abstract`；第三层仍缺则标“证据不足”，尝试 OA 全文（academic-source-verification）；标题仅用于召回排序，不能据此确定支持/批评/无法复现。兜底后由模型逐篇判断引用性质（支持/中立/批评/无法复现），只保留批评与无法复现类，并标注每篇的判断依据（摘要/全文；仅标题者列待核）。
2. **否定词搜索**（辅助）：用否定句式搜同主题论文：
   `search=fail to replicate <主题>`、`search=challenges <主题> findings`、`search=<主题> irreproducible`
   这类召回偏调查综述，需要从命中里人工筛选真正构成反证的研究。

输出：反证论文列表，每篇附"反证类型"（方法质疑/结论矛盾/无法复现/边界反驳）与证据句（引用原文或摘要句）。诚实声明：反证查找的召回率受摘要可获取性限制，付费墙内的批评可能漏掉；有 Semantic Scholar key 时加查 `citations?fields=contexts` 用引用上下文提高召回。

## 工作流 D：作者档案

从论文的 `authorships` 拿到 `author.id`（如 `A5023888391`），然后：

1. 档案本体：`GET https://api.openalex.org/authors/<A-ID>` → `display_name`、`works_count`、`cited_by_count`、`h_index`（在 `summary_stats` 里）、`last_known_institutions`。
2. 代表作品：`GET https://api.openalex.org/works?filter=authorships.author.id:<A-ID>&sort=cited_by_count:desc&per_page=10&select=title,cited_by_count,publication_year`
3. 合作网络（可选）：`filter=authorships.author.id:<A-ID>` 加 `select=authorships`，统计共同作者出现频次。

## 工作流 E：模拟审稿

模板与评分表见 `references/peer-review-template.md`。要点：先声明这是模拟审稿、不替代真实同行评审；按模板逐节给出"优点/问题/建议"；终评给 1~5 分（强拒/拒/大修/小修/接收）并列出决定性的三条理由；每一条批评必须定位到论文段落（引原文）。

## 工作流 F：逻辑谬误标注

清单见 `references/fallacy-checklist.md`。要点：逐段扫描论证结构；标注格式为"段落定位 + 谬误类型 + 为什么成立 + 改写建议"；统计谬误类型分布；只标注确定成立的，疑似但拿不准的列"存疑"区，不强行定罪。

## 工作流 G：批量综述矩阵

20~50 篇论文压成五列对比表（方法/样本/核心结论/局限），按主题聚类分组。执行细节与输出规范见 `references/review-matrix.md`。

## 工作流 H：期刊匹配推荐

用论文 topics ID 筛选 works，再按 primary_location.source.id 聚合候选刊源，输出候选期刊与命中理由。分区与影响因子不在数据内，必须声明需另行核对。见 `references/journal-matching.md`。

## 工作流 I：BibTeX 导出

从 OpenAlex 元数据生成 BibTeX 条目（含中文文献的 biblatex-gb7714 建议）。见 `references/bibtex-guide.md`。

## 工作流 J：双语对照精读

外文论文分节要点翻译 + 关键句原文 + 全文统一术语表，支持任意语对（默认译为中文，用户可指定目标语言）。见 `references/bilingual-reading.md`。

## 工作流 K：研究空白分析

主题组合的论文密度与时间趋势对比，输出交叉区冷热度。措辞只许说"密度低"，禁止断言"存在空白"。见 `references/research-gap.md`。

## 工作流 L：复现辅助

找官方代码与数据集。旧 Papers with Code v1 API 不作可靠依赖，先核查当前服务状态，走 GitHub 搜索 + HuggingFace + 网页检索。见 `references/reproduction.md`。

## Procedure

1. 识别输入形态：概念文本 / 链接 / PDF / 作者名 / 明确指令（审稿、谬误、查重）。
2. 归一化：链接→DOI（`https://api.openalex.org/works/https://doi.org/{DOI}`），PDF→标题与摘要文本。
3. 选择工作流（A~L），组合任务按 A→B→C 顺序推进（找相似→查重→反证）。
4. 每个结论附数据来源与证据句；无法自动化的判断（批评甄别、谬误认定、审稿意见）附论文原文位置。
5. 结果用纯文本回报：清单式、可核对、区分"数据事实"与"模型判断"。
6. 输出语言：默认跟随用户输入语言（用户用什么语言问就用什么语言答），用户明确指定时按指定语言；论文标题与引文一律保留原文，译名首次出现时附原文。

## Pitfalls

1. **OpenAlex 请求格式**：API 域名是 `api.openalex.org`；work 实体 id（`https://openalex.org/W...`）只能当 id 用，直接请求会 403。filter 值用 id 尾段（如 `cites:W2919115771`、`author.id:A5023888391`）。
2. **Semantic Scholar 的可用性依限额与配置而异**。匿名可尝试公开端点，持续 429 时报告未查到而非空结果；key 不保证 contexts 字段存在。
3. **查重的诚实边界**：本地比对只能覆盖你下载到全文的候选集合，不能声称全网查重。报告里必须写明覆盖范围。
4. **反证召回有限**：引用论文的摘要经常拿不到——OpenAlex 的 `abstract_inverted_index` 可缺失，三篇抽测不能估计总体缺失率，Crossref 的 `abstract` 也可能为空（Nature 2015 论文实测为空）。拿不到摘要则取全文或标证据不足，标题只作候选召回，并在报告里标注每篇反证的判断依据。报"未发现反证"时措辞为"在可获取的 N 篇引用文献中未发现批评性引用"。
5. **相似度不等于抄袭**：主题算法推荐（related_works）是正常的学术邻近关系，不能当成抄袭信号。工作流 B 也只提供文本重叠证据，抄袭结论需要语境、引用与版本证据。
6. **审稿与谬误判断是模型判断，不是数据事实**：输出必须分栏标注"API 数据"与"模型判断"，后者保留可核对引文，让用户自行复核。
7. **速率礼貌**：OpenAlex 有日预算和 100 req/s 上限，使用 OPENALEX_API_KEY 环境变量；限制总页数并对 429 有界退避，检查剩余额度；同一会话内结果可复用，不要重复请求相同端点。

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

wid = 'W2741809807'
w = get('https://api.openalex.org/works/' + wid + '?' + urlencode({
    'select': 'id,title,doi,topics,primary_topic,related_works,authorships,is_retracted'}))
assert w['id'].endswith('/' + wid) and w['authorships'] and w['topics']
assert all(t['id'].split('/')[-1].startswith('T') for t in w['topics'])
assert isinstance(w['related_works'], list)
query = {'filter': 'topics.id:' + w['topics'][0]['id'].split('/')[-1],
         'per_page': 1, 'cursor': '*', 'select': 'id,topics', 'corpus': 'core'}
first = get('https://api.openalex.org/works?' + urlencode(query))
assert first['results'] and first['meta']['next_cursor']
query['cursor'] = first['meta']['next_cursor']
second = get('https://api.openalex.org/works?' + urlencode(query))
assert second['results'] and first['results'][0]['id'] != second['results'][0]['id']
assert all(any(t['id'] == w['topics'][0]['id'] for t in r['topics']) for r in first['results'] + second['results'])
topic_ids = [t['id'].split('/')[-1] for t in w['topics'][:2]]
both = get('https://api.openalex.org/works?' + urlencode({
    'filter': ','.join('topics.id:' + t for t in topic_ids), 'per_page': 1,
    'select': 'id,topics', 'corpus': 'core'}))
assert both['results'] and all(set(topic_ids) <= {t['id'].split('/')[-1] for t in r['topics']} for r in both['results'])
groups = get('https://api.openalex.org/works?' + urlencode({
    'filter': 'topics.id:' + topic_ids[0], 'group_by': 'primary_location.source.id',
    'per_page': 5, 'corpus': 'core'}))
assert groups['group_by'] and all(isinstance(g['count'], int) for g in groups['group_by'])
search = get('https://api.openalex.org/works?' + urlencode({
    'search': 'attention is all you need', 'per_page': 1, 'select': 'id,title', 'sort': 'relevance_score:desc'}))
assert search['results'] and search['results'][0]['title']
author_id = w['authorships'][0]['author']['id'].split('/')[-1]
author_works = get('https://api.openalex.org/works?' + urlencode({
    'filter': 'authorships.author.id:' + author_id, 'per_page': 1, 'select': 'id,authorships'}))
assert author_works['results'] and any(a['author']['id'].endswith('/'+author_id) for a in author_works['results'][0]['authorships'])
print('literature-analysis topics, cursor, topic AND, source grouping, search and author filter passed')
```