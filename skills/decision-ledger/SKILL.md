---
name: decision-ledger
description: Deterministic ledger of decisions and negative results.
version: 1.0.0
author: Junfu Shi (SJF, xngg1021), Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms:
- linux
- macos
- windows
tags:
- decision
- negative-result
- ledger
- provenance
- deterministic
metadata:
  tags: decision, negative-result, ledger, provenance, deterministic
  related_skills: claim-evidence-graph, research-object-identity, cross-review-five
---

# decision-ledger: Research Decision Log (研究决策与失败记录)

**Research Decision Log (研究决策与失败记录)**：记录科研过程中做过什么选择、为什么放弃某条路线、哪些尝试失败、后来为什么改变结论，并把每条记录连接到原始证据（内部内核协议：`decision-ledger-1.0`，对齐状态变更历史 Primitive 3）。

直接消费与 Claim-Evidence Graph 内核字节兼容的 `LineageReceipt` 与 `AcademicEvidenceReceipt` 证据记录契约（`schemas/decision-ledger-receipt.schema.json`）。纯 Python 标准库实现、零外部大模型依赖、零网络调用。判定结论一律为离散枚举，**严禁任何伪置信分与主观数值打分**。

## When to Use

- 需要记录研究中的关键选择与路线分叉（探索、采纳、放弃、修正与失败尝试）；
- 需要说明“为什么当初放弃这条路线”：被放弃路线的原因、取代它的决策及依据；
- 需要把失败尝试与负结果（negative result）正式记录在案，防止重复踩坑；
- 需要以纯追加事件方式修正历史结论：结论变更按内容与顺序追加新事件，从不原地改写历史。

## 核心设计纪律

1. **状态变更历史纯追加 (Event Sourcing)**：决策、依据、分支、状态事件与结果修正均为不可变记录；生命周期状态（active/pruned/reopened）由追加式状态事件重放派生，结论变化以新的修正事件入账，从不原地改写历史。
2. **客观离散裁决，不做主观数值打分**：无伪置信分、无效用分；裁决为离散枚举（`positive`/`negative`/`inconclusive`/`unverifiable`），客观记录研究者的选择与证据链。
3. **失败尝试与负结果必须附带证据**：`negative_result` 决策必须携带至少一条决策依据边（`basis_kind="decision"`）；仅由其他负结果支撑的负结果无法通过校验（E405）。
4. **路线放弃与终止原因明确且严格无环**：放弃路线以状态事件入账，记录封闭词表原因（`resource_exhausted`、`superseded`、`contradicted` 等）与主导决策、备选路径；`caused_by` 因果链严格无环（E304）；`trace_prune_cause` 递归返回完整原因链。
5. **强类型收据引用与严格互斥**：`lineage` 引用要求 `receipt_id` 与 `receipt_digest`；`academic_evidence` 引用要求 `claim_digest` 与 `payload_sha256`；契约与 CEG 内核逐字节兼容。
6. **物理级收据校验**：学术收据负载 SHA256 物理重算断言，注册表键无法绕过哈希校验；谱系收据正向断言协议、收据 ID 与摘要。
7. **构造期深度冻结与 JSON-domain 失败关闭**：所有记录为 frozen dataclass，元数据为 `FrozenDict`；构造期严厉拦截 NaN/Inf、非字符串键与非法对象；注册收据深拷贝。
8. **待核实事项清单 (Items Needing Review)**：`decision_without_basis`、`unsupported_negative_result`、`missing_receipt`、`unsupported_pruning` 以内容寻址确定性 ID 入队，不阻断结构校验。
9. **顺序无关内容身份摘要**：`ledger_digest` 只覆盖台账记录（决策、依据、分支、状态事件、修正），本地收据注册表（验证缓存）不进入内容身份；验证态另计 `verification_digest`。修正与状态事件的 `sequence` 计数器记录真实追加历史。
10. **词汇级规范化**：NFC 与空白压缩，绝不语义改写决策标题。

## Verification

离线冒烟测试：

```python
# smoke-test: true
import os, sys
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', os.getcwd()), 'scripts'))
from ledger import DecisionLedger, ReceiptRef

ledger = DecisionLedger(ledger_id="smoke-dl")

# 决策图谱:探索 → 依据 → 采纳
ledger.add_decision(id="d-explore", title="Try estimator A on corpus X.", decision_type="explore")
ledger.add_decision(id="d-commit", title="Adopt estimator A", decision_type="commit")
ledger.add_basis("d-commit", basis_kind="decision", basis_id="d-explore")
ledger.add_fork("d-commit", "d-explore", relation="considered")

# 负结果:必须携带证据依据,否则校验失败
ledger.add_decision(id="nr-baseline", title="Estimator B fails on long documents", decision_type="negative_result")
ledger.add_basis("nr-baseline", basis_kind="decision", basis_id="d-explore")

# 路线放弃与终止:封闭词表原因 + 主导决策 + 备选路径
ledger.add_decision(id="d-branch-c", title="Branch C: heuristic segmentation")
ledger.set_prune("d-branch-c", status="pruned", prune_reason="resource_exhausted",
                 pruned_by="d-commit", alternative_ref="d-explore")
trace = ledger.trace_prune_cause("d-branch-c")
assert trace["prune_state"]["status"] == "pruned"
assert trace["pruned_by_bases"] and trace["alternative_decision"]["id"] == "d-explore"

# 结果修正:按顺序与内容寻址追加新事件
c1 = ledger.add_outcome_correction("d-explore", verdict="negative", rationale="Did not replicate on held-out data.")
c2 = ledger.add_outcome_correction("d-explore", verdict="negative", rationale="Did not replicate on held-out data.")
assert c1.correction_id == c2.correction_id

# 结构校验与顺序无关摘要
valid, errors = ledger.validate_ledger()
assert valid is True and not errors
d = ledger.to_dict()
assert d["protocol"] == "decision-ledger-1.0"
assert len(d["ledger_digest"]) == 64

# 待核实事项清单:缺依据的负结果进入待核实队列
ledger.add_decision(id="nr-lonely", title="No evidence recorded", decision_type="negative_result")
uncertainties = ledger.export_uncertainties()
assert any(u.kind == "decision_without_basis" and u.needs_human for u in uncertainties)

print("decision-ledger smoke PASS")
```
