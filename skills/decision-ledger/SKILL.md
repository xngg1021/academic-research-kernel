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

# decision-ledger

Decision & Negative Result Ledger Kernel v1：科研决策与负结果的**确定性追加式台账内核**。记录研究决策、负结果存证、剪枝因果与结果修正，直接消费与 Claim-Evidence Graph 内核字节兼容的 `LineageReceipt` 与 `AcademicEvidenceReceipt` 收据契约（`schemas/decision-ledger-receipt.schema.json`）。

纯 Python 标准库实现、无外部大模型依赖、零网络调用。判定结论一律为离散枚举，**严禁任何伪置信分与主观数值打分**。

## When to Use

- 需要为科研过程建立可追溯的决策图谱：探索、收敛、放弃、修正与负结果全程存证；
- 需要"为什么当初不这么走"的剪枝因果追溯：被剪分支的封闭词表原因、剪枝决策及其依据链；
- 需要把失败路径（negative result）作为一等公民收据化，防止重复踩死胡同；
- 需要以追加方式修正历史结论：结果修正按内容寻址新事件入账，从不原地改写历史。

## 核心设计纪律

1. **只追加、不销改 (Append-only)**：决策、依据、分支、状态事件与结果修正均为不可变记录；生命周期状态（active/pruned/reopened）由追加式状态事件重放派生，结论变化以新的内容寻址修正事件入账，从不原地改写历史。
2. **拒绝真理裁判所 (Truth Authority)**：无置信分、无效用分、无排名数值；裁决是离散枚举（`positive`/`negative`/`inconclusive`/`unverifiable`），台账记录选择与证据，不判定真理。
3. **负结果是携带证据的缺席断言**：`negative_result` 决策必须携带至少一条依据边，且必须有 `claim` 类依据；仅由其他负结果支撑的负结果无法通过校验（E405）。
4. **剪枝因果是一等公民且严格无环**：剪枝以状态事件入账，记录封闭词表原因（`resource_exhausted`、`superseded`、`contradicted` 等）与剪枝决策、备选路径；`caused_by` 链在派生当前图上严格无环（E304）；`trace_prune_cause` 递归返回完整剪枝链，缺 claim 依据的剪枝给出确定性 `unsupported_reason`。
5. **强类型收据引用与严格互斥**：`lineage` 引用要求 `receipt_id` 与 `receipt_digest`；`academic_evidence` 引用要求 `claim_digest` 与 `payload_sha256`；契约与 CEG 内核逐字节兼容。
6. **物理级收据校验**：学术收据负载 SHA256 物理重算断言，注册表键无法绕过哈希校验；谱系收据正向断言协议、收据 ID 与摘要。
7. **深度冻结**：所有记录为 frozen dataclass，元数据为 `FrozenDict`；注册收据深拷贝，杜绝外部变异漂移。
8. **三态不确定性队列**：`decision_without_basis`、`unsupported_negative_result`、`missing_receipt`、`unsupported_pruning` 以内容寻址确定性 ID 入队，均不阻断结构校验。
9. **顺序无关内容身份摘要**：`ledger_digest` 只覆盖台账记录（决策、依据、分支、状态事件、修正），本地收据注册表（验证缓存）不进入内容身份——同一台账无论注册标签如何命名，摘要恒等；验证态另计 `verification_digest`。唯一例外：修正与状态事件的 `sequence` 计数器记录真实追加历史，合法影响摘要。
10. **词汇级规范化**：NFC 与空白压缩，绝不语义改写决策标题。

## Verification

离线冒烟测试：

```python
# smoke-test: true
import os, sys
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', os.getcwd()), 'scripts'))
from ledger import DecisionLedger, ReceiptRef

ledger = DecisionLedger(ledger_id="smoke-dl")

# 决策图谱:探索 → 依据 → 收敛
ledger.add_decision(id="d-explore", title="Try estimator A on corpus X.", decision_type="explore")
ledger.add_decision(id="d-commit", title="Adopt estimator A", decision_type="commit")
ledger.add_basis("d-commit", basis_kind="claim", basis_id="d-explore")
ledger.add_fork("d-commit", "d-explore", relation="considered")

# 负结果:必须携带证据依据,否则校验失败
ledger.add_decision(id="nr-baseline", title="Estimator B fails on long documents", decision_type="negative_result")
ledger.add_basis("nr-baseline", basis_kind="claim", basis_id="d-explore")

# 剪枝:封闭词表原因 + 剪枝决策 + 备选路径
ledger.add_decision(id="d-branch-c", title="Branch C: heuristic segmentation")
ledger.set_prune("d-branch-c", status="pruned", prune_reason="resource_exhausted",
                 pruned_by="d-commit", alternative_ref="d-explore")
trace = ledger.trace_prune_cause("d-branch-c")
assert trace["prune_state"]["status"] == "pruned"
assert trace["pruned_by_bases"] and trace["alternative_decision"]["id"] == "d-explore"

# 结果修正:内容寻址追加事件,幂等
c1 = ledger.add_outcome_correction("d-explore", verdict="negative", rationale="Did not replicate on held-out data.")
c2 = ledger.add_outcome_correction("d-explore", verdict="negative", rationale="Did not replicate on held-out data.")
assert c1.correction_id == c2.correction_id

# 结构校验与顺序无关摘要
valid, errors = ledger.validate_ledger()
assert valid is True and not errors
d = ledger.to_dict()
assert d["protocol"] == "decision-ledger-1.0"
assert len(d["ledger_digest"]) == 64

# 三态不确定性队列:缺依据的负结果进入人工审查
ledger.add_decision(id="nr-lonely", title="No evidence recorded", decision_type="negative_result")
uncertainties = ledger.export_uncertainties()
assert any(u.kind == "decision_without_basis" and u.needs_human for u in uncertainties)

print("decision-ledger smoke PASS")
```
