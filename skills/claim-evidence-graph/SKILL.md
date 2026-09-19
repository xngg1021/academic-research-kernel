---
name: claim-evidence-graph
description: 确定性科学论断-证据图 (Claim-Evidence Graph v1)，连接学术论断、证据记录与计算过程追溯.
version: 1.0.0
author: Junfu Shi (SJF, xngg1021), Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms:
- linux
- macos
- windows
tags:
- claim
- evidence
- graph
- provenance
- deterministic
metadata:
  tags: claim, evidence, graph, provenance, deterministic
  related_skills: research-object-identity, quantitative-paper-audit, academic-source-verification
---

# claim-evidence-graph

Claim-Evidence Graph Kernel v1：科学论断与实证证据的**确定性公共拓扑内核**。直接消费 `ResearchObject`（研究对象实体）、`AcademicEvidenceReceipt`（事实核验收据）与 `LineageReceipt`（生产谱系回执）。

纯 Python 标准库实现、无外部大模型依赖、零网络调用。判定结论一律为离散枚举，**严禁任何伪置信分与主观数值打分**。

## When to Use

- 需要将学术论文的高阶论断（Claims）精确锚定到底层图表、统计量、事实收据或生产谱系；
- 需要在多篇论文或多个实验之间建立学术论断关系网络（`contradicts`, `corroborates`, `cites`, `refines`, `depends_on`）；
- 需要毫秒级排查文献之间的学术争议与直接矛盾，且允许命题相互反驳（语义成环）；
- 需要从一个科学结论一键递归穿透回其底层的原始数据清洗与统计计算执行谱系（Traceable Lineage）。

## 核心设计纪律

1. **因果谱系严格有向无环 (DAG)，语义关系网络允许自然成环**：
   生产过程（`derived_from`）由 Provenance Kernel 强制无环；学术命题关系（如 A 论文反驳 B 论文，B 论文反驳 A 论文，`CONTRADICTS` 双向互斥）天然成环且完全合法。
2. **拒绝绝对裁判**：
   确定性内核只负责节点唯一性、定位符坐标、引用完整性、收据绑定、图遍历与覆盖率检查；不合成分数（严禁 0.85 这种主观打分）。
3. **不可决断分歧沉淀至不确定性账本 (UncertaintyQueue)**：
   机器不可观测（`unverifiable`）不等于必须人工介入（`needs_human=False`）；而直接矛盾（`contradicted`）则标记为需要审查员/人工介入（`needs_human=True`）。

## 核心工作流与 API

```python
# fragment: true
from graph import ClaimEvidenceGraph, ReceiptRef

graph = ClaimEvidenceGraph(graph_id="ceg-example")

# 1. 注册科学论断 (Claim)
c1 = graph.add_claim(
    id="claim-scaling-collapse",
    text="Diminishing returns emerge in LLM scaling under fixed data distributions.",
    target_work_id="work-deepseek-2026",
    locator="paper.pdf#page=5:sec=3.1",
    claim_type="empirical_finding"
)

# 2. 注册实证证据锚点 (EvidenceAnchor) 并绑定强类型收据引用 (ReceiptRef)
ev1 = graph.add_evidence(
    id="ev-benchmark-table3",
    anchor_type="table_cell",
    source_work_id="work-deepseek-2026",
    locator="paper.pdf#table=3:cell=C4",
    receipt_ref=ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id="rec-3ce2b64386d0033b",
        receipt_digest="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    ),
    excerpt="Loss delta < 0.001 after 10^24 FLOPs"
)

# 3. 建立证据支撑边 (EvidenceSupportEdge)
graph.add_support_edge(ev1.id, c1.id, support_status="supported")

# 4. 建立论断关系边 (ClaimRelationEdge, 允许成环)
c2 = graph.add_claim(id="claim-infinite-scaling", text="LLM capabilities scale indefinitely without plateau.")
graph.add_claim_relation(c1.id, c2.id, relation_type="contradicts")
graph.add_claim_relation(c2.id, c1.id, relation_type="contradicts")

# 5. 确定性检索支持、反驳与不确定性账本
supports = graph.find_support(c1.id)
contradictions = graph.find_contradictions(c1.id)
uncertainties = graph.extract_uncertainties()
```

## 边界

- 不做全文自由文本大模型抽取：节点文本与定位符由上游产生，内核负责图结构与确定性拓扑管理；
- 不做模糊语义匹配：命题文本只做 Unicode NFC 与空白规整，绝对不篡改重写语义；
- 离线确定性：全图指纹（`graph_digest()`）与回溯遍历完全独立于节点的插入顺序。

## Verification

离线冒烟测试：

```python
# smoke-test: true
import os, sys
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', os.getcwd()), 'scripts'))
from graph import ClaimEvidenceGraph, ReceiptRef

graph = ClaimEvidenceGraph(graph_id="smoke-ceg")

# 注册论断与证据
c_a = graph.add_claim(id="claim-a", text="Drug X reduces viral load by 40%.")
c_b = graph.add_claim(id="claim-b", text="Drug X shows no significant difference compared to placebo.")

ev_a = graph.add_evidence(
    id="ev-clinical-trial",
    anchor_type="table_cell",
    excerpt="p = 0.002, CI [25%, 55%]"
)

# 支撑与相互矛盾 (循环语义关系合法)
graph.add_support_edge(ev_a.id, c_a.id, support_status="supported")
graph.add_claim_relation(c_a.id, c_b.id, relation_type="contradicts")
graph.add_claim_relation(c_b.id, c_a.id, relation_type="contradicts")

# 验证结构完整性
valid, errors = graph.validate_graph()
assert valid is True and not errors

# 确定性发现矛盾
contras = graph.find_contradictions(c_a.id)
assert len(contras) == 1
assert contras[0]["conflicting_claim_id"] == "claim-b"

# 导出不可变深拷贝字典与指纹
d = graph.to_dict()
assert d["protocol"] == "claim-evidence-graph-1.0"
assert len(d["graph_digest"]) == 64

print("claim-evidence-graph smoke PASS")
```
