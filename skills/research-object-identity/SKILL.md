---
name: research-object-identity
description: "研究对象身份归一、聚合五态判定与谱系建边的确定性公共骨架."
version: 1.0.0
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [identity, lineage, dedup, research-object, deterministic]
    related_skills: [academic-source-verification, literature-analysis]
---

# research-object-identity

Research Object Identity & Lineage v0.1：研究对象身份与谱系的**确定性公共骨架**。本技能只做三件可测试的事——标识符归一（normalize）、候选记录聚合判定（resolve）、关系与谱系建边（link），全部由 [`scripts/identity.py`](scripts/identity.py) 实现，纯标准库、无网络依赖、无第三方库。

定位先说清：本层**不是**通用本体设计，也不是运行时服务。它产出符合 [`../../schemas/research-object.schema.json`](../../schemas/research-object.schema.json) 的对象草案，供后续 Claim-Evidence 层与 Method Miner 层消费；判定结论一律是离散字段值，**禁止任何置信分数与模糊评分**。

## When to Use

- 同一篇论文（或数据集、仓库）来自多个来源，需要判定是不是同一对象；
- 需要把 preprint、正式发表版、更正、撤稿串成谱系链；
- 需要把 academic-source-verification 的 Evidence Receipt 落成对象上的来源观察与不确定项；
- 下游技能需要一个不评分的、可复核的身份判定基座。

## 对象模型

五类对象：Work、Person、Dataset、CodeRepository、Artifact。每个对象八个顶层字段：object_id、object_type、identifiers、manifestations、relations、lineage、source_observations、uncertainty。完整定义见仓库根目录的 JSON Schema（draft 2020-12）。manifestations 允许空数组；relations 与 lineage 的每条边都携带 evidence。

## 工作流一：标识符归一（normalize）

`normalize(kind, value) -> str`，每类标识符一套确定性规则：

| kind | 规则 | 示例 |
| --- | --- | --- |
| doi | 去 `https://doi.org/`、`doi:` 前缀并小写 | `https://doi.org/10.1038/Nature12373` → `10.1038/nature12373` |
| arxiv_id | 去 URL 与 `arXiv:` 前缀、去版本号 | `2310.15264v2` → `2310.15264` |
| pmid | 只保留数字 | `PMID: 38123654` → `38123654` |
| openalex_id | 从 URL 取末段 ID | `https://openalex.org/W123` → `W123` |
| orcid | 去 URL 与连字符取纯数字 | `https://orcid.org/0000-0002-1825-0097` → `0000000218250097` |

归一结果可直接比较：相等的归一字符串即同一标识符。

## 工作流二：聚合判定（resolve）

`resolve(records)` 输入若干同一对象的候选记录（每条含 identifiers 与可选 title、authors、year、source、queried_at），输出 object_type、merged_identifiers、verdict、match_fields、conflict_fields、sources 与 human_confirmed（初始 false）。判定规则集中在 `judge(facts)`，按优先级：

| verdict | 含义 | 触发条件 |
| --- | --- | --- |
| CONFLICT | 候选记录互相冲突 | 同一标识符类型出现两个不同归一值 |
| EXACT | 确认同一对象 | 至少一个规范标识符跨记录一致（单记录自带标识符亦算自洽） |
| STRONG_MATCH | 强匹配 | 无共享标识符，但规范标题与作者全部一致 |
| CANDIDATE | 疑似同一对象 | 无共享标识符，标题 token Jaccard 相似度不小于 0.5，或作者集合有重叠 |
| UNRESOLVED | 无法判断 | 信息不足（含空记录列表、单记录且无任何标识符） |

match_fields 记录一致字段名，conflict_fields 记录冲突字段名，全部是离散字段，供人复核与下游引用。

## 工作流三：建边（link）

`link(a, b, kind, evidence)` 在 a 到 b 之间建有方向的边：

- kind 属于 relations（cites、contradicts、replicates、derived_from）：只写入 a 的 relations（方向 a→b），反向断言不自动回填，需要反向关系时显式调用 link（b， a， kind， evidence）；a 与 b 的 object_id 相同则抛 ValueError；
- kind 属于 lineage（preprint_to_vor、correction、retraction、version_chain）：同一条边（from=a，to=b）写入双方 lineage，方向保留在边内。

evidence 必须含五个键：source、queried_at、match_fields、conflict_fields、human_confirmed，缺一抛 ValueError。边的证据结构在 schema 的 `$defs/edgeEvidence` 中固定。

## 向后兼容 CanonicalWork

`from_canonical_work(cw)` 把 literature-analysis 的 CanonicalWork 转成 Work 型 ResearchObject 草案：鸭子类型接受实例或同名字段 dict，不 import 对方模块；doi 与 extra.arxiv_id 经 normalize 后入 identifiers，title、authors、year、container 作为信息字段附带，供 resolve 聚合。CanonicalWork 本身与其格式转换函数原样不动。无 DOI 时 object_id 用标题前六词的 slug 生成，两篇标题前六词相同的论文可能撞同一 object_id，此时 link 会按自环拒绝，需人工补标识符后再建边。

## 消费 Evidence Receipt

`consume_receipt(receipt)` 消费符合 [`../../schemas/evidence-receipt.schema.json`](../../schemas/evidence-receipt.schema.json) 1.0 的回执，产出可并入对象的 source_observations 与 uncertainty：

- schema_version 非 1.0 时：sources 照常保留为观察记录，其余语义内容（claims、conflicts、failures）一律不解读，统一进一条 uncertainty（kind=unsupported_schema_version），needs_human 置 true；
- sources 逐条直传为 source_observations（source、queried_at、status、coverage、raw_identifier）；
- support_status 为 contradicted 的 claim 进 uncertainty，needs_human 置 true；
- support_status 为 unverifiable 的 claim 进 uncertainty，needs_human 为 false；
- support_status 为 out_of_scope 的 claim 进 uncertainty（kind=out_of_scope_claim），needs_human 为 false，不静默丢弃；
- conflicts 每条进 uncertainty（kind=receipt_conflict），needs_human 置 true；
- failures 每条进 uncertainty（kind=query_failure），needs_human 为 false。

回执中的冲突绝不静默合并：必须落到 uncertainty 等待人工确认，这与 evidence 中的 human_confirmed 布尔位配套。

## 边界

- 不评分：任何字段都不是概率或置信度，判定依据只有离散字段比较；
- 不联网：归一、判定、建边全部离线可重放；
- 不替代领域判断：CANDIDATE 与 CONFLICT 一律留给上游流程或人工处理，human_confirmed 置 true 前不得当作定论。

## Verification

离线冒烟：归一各类标识符，对五态各构造一条 fixture，建边验证有向语义，消费一条迷你回执。

```python
# smoke-test: true
import os, sys
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', os.getcwd()), 'scripts'))
import identity as rid

# 归一：每类一条
assert rid.normalize('doi', 'https://doi.org/10.1038/Nature12373') == '10.1038/nature12373'
assert rid.normalize('arxiv_id', '2310.15264v2') == '2310.15264'
assert rid.normalize('pmid', 'PMID:38123654') == '38123654'
assert rid.normalize('openalex_id', 'https://openalex.org/W123') == 'W123'
assert rid.normalize('orcid', 'https://orcid.org/0000-0002-1825-0097') == '0000000218250097'

# 五态：EXACT（共享 DOI）、CONFLICT（两个不同 DOI）、STRONG_MATCH（标题作者全一致）、
# CANDIDATE（作者重叠）、UNRESOLVED（空记录）
exact = rid.resolve([
    {'identifiers': [{'type': 'doi', 'value': '10.1/a'}], 'title': 'T', 'authors': ['A, B'], 'year': 2020},
    {'identifiers': [{'type': 'doi', 'value': 'doi:10.1/A'}], 'title': 'T', 'authors': ['A, B'], 'year': 2020}])
assert exact['verdict'] == 'EXACT' and exact['human_confirmed'] is False
conflict = rid.resolve([
    {'identifiers': [{'type': 'doi', 'value': '10.1/a'}]},
    {'identifiers': [{'type': 'doi', 'value': '10.1/b'}]}])
assert conflict['verdict'] == 'CONFLICT' and 'doi' in conflict['conflict_fields']
strong = rid.resolve([
    {'title': 'Attention Is All You Need', 'authors': ['Vaswani, Ashish'], 'year': 2017},
    {'title': 'Attention is all you need', 'authors': ['Vaswani, Ashish'], 'year': 2017}])
assert strong['verdict'] == 'STRONG_MATCH'
cand = rid.resolve([
    {'title': 'Deep learning for graphs', 'authors': ['Zhang, Wei']},
    {'title': 'Deep learning for graphs: a survey', 'authors': ['Zhang, W.']}])
assert cand['verdict'] == 'CANDIDATE'
assert rid.resolve([])['verdict'] == 'UNRESOLVED'

# 建边：relations 只落在 a 侧（有向），lineage 双向回填，evidence 五键齐全
a = rid.from_canonical_work({'doi': '10.1/vor', 'title': 'T', 'authors': ['A'], 'year': 2021})
b = rid.from_canonical_work({'doi': '10.1/pre', 'title': 'T', 'authors': ['A'], 'year': 2020})
ev = {'source': 'Crossref', 'queried_at': '2026-09-17T00:00:00Z',
      'match_fields': ['title'], 'conflict_fields': [], 'human_confirmed': False}
edge = rid.link(a, b, 'preprint_to_vor', ev)
assert b['lineage'] and a['lineage'] and edge['to_object_id'] == b['object_id']
rel = rid.link(a, b, 'cites', ev)
assert a['relations'][0]['target_object_id'] == b['object_id']
assert b['relations'] == []  # 有向边不得反向回填

# 回执消费：conflicts 落 uncertainty 且 needs_human 为 true
out = rid.consume_receipt({'sources': [{'source': 'OpenAlex', 'queried_at': '2026-09-17T00:00:00Z',
                                        'status': 'ok', 'raw_identifier': None}],
                           'claims': [], 'conflicts': ['citation count differs'], 'failures': []})
assert out['source_observations'][0]['status'] == 'ok'
assert out['uncertainty'][0]['needs_human'] is True
print('research-object-identity smoke PASS')
```
