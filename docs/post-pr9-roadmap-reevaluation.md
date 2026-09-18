# PR #9 后续建设方向审计重估与 PR #11 立项裁定 (Post-PR9 Roadmap Re-evaluation)

依据《研究计划第 0 版》（`docs/research-plan-v0.zh.md`）第 6 节与第 8 节的明确纪律：
> “任何后续方向开工前必须重新过审计程序（归组定义入库、覆盖数重算、杠杆判断记录）。”

随着 **PR #9**（`Claim-Evidence Graph Kernel v1`，正常合并提交 `ab7d1fe`）与 **PR #10**（`CI Node 24 / Ubuntu 26 / Locator Determinism Maintenance`）的实施，本备忘录记录针对下一阶段战略演进方向的正式复核事实与审计裁定。

---

## 1. 既有落地资产盘点 (Implemented Foundations)

至 PR #9 合并，本仓库已建立起完整的确定性学术研究对象与证据体系：

| 资产层级 | 核心模块 / 契约 | 架构地位与解决的断言 |
| :--- | :--- | :--- |
| **研究对象身份** | `skills/research-object-identity/scripts/identity.py` (`schemas/research-object.schema.json`) | 跨 DOI/arXiv/OpenAlex 统一规范标识、五态离线判定、版本派生 |
| **计算生产谱系** | `skills/research-object-identity/scripts/provenance.py` (`schemas/lineage-receipt.schema.json`) | W3C PROV 风格的计算活动不可变记录、有向无环图 (DAG) 拓扑、内容哈希物理核验、双重摘要 `LineageReceipt` |
| **论断-证据图** | `skills/claim-evidence-graph/scripts/graph.py` (`schemas/claim-evidence-graph.schema.json`) | 词汇级命题规范化、双向支持/反驳语义成环、`FrozenDict` 深度不可变元数据、正反向因果穿透与确定性争议队列 `UncertaintyItem` |
| **科学计算与数值等价** | `scripts/scfabric` (`schemas/compute-receipt.schema.json`) | 浮点容差矩阵、硬件探针门禁、`ComputeReceipt` |
| **多模型独立审议** | `skills/cross-review-five` (`schemas/review-panel-spec.schema.json`) | 动态多模型 패널, Sparse Deliberation 四阶段无偏差仲裁 |

---

## 2. 痛点矩阵最新重算核验 (Sensitivity Verification over 235 Pain Items)

在最新主线上运行 `../scripts/recompute_direction_coverage.py`（基于入库归组定义 `direction-primitive-mapping.json` 与因子矩阵 `factor-matrix.json`）：

```text
=== single (核心单原语口径) ===
  Decision / Negative Result Ledger     36 / 235 = 15.3%
  Research Object Identity and Lineage  34 / 235 = 14.5%  [PR #6 已落地]
  Method / Supplement Miner             30 / 235 = 12.8%
  Learning Error + Adaptive Practice    20 / 235 = 8.5%   [已剥离出本仓]
  Constraint Compiler                   18 / 235 = 7.7%
  Claim-Evidence Graph                  15 / 235 = 6.4%   [PR #9 已落地]
  ranking: Decision > Research > Method > Learning > Constraint > Claim-Evidence

=== core (核心原语集合口径) ===
  Research Object Identity and Lineage  64 / 235 = 27.2%  [PR #6 已落地]
  Method / Supplement Miner             59 / 235 = 25.1%
  Claim-Evidence Graph                  47 / 235 = 20.0%  [PR #9 已落地]
  Decision / Negative Result Ledger     36 / 235 = 15.3%
  Learning Error + Adaptive Practice    20 / 235 = 8.5%
  Constraint Compiler                   18 / 235 = 7.7%
  ranking: Research > Method > Claim-Evidence > Decision > Learning > Constraint

=== baseline (核心+扩展原语口径) ===
  Research Object Identity and Lineage  88 / 235 = 37.4%  [PR #6 已落地]
  Method / Supplement Miner             85 / 235 = 36.2%
  Decision / Negative Result Ledger     63 / 235 = 26.8%
  Claim-Evidence Graph                  58 / 235 = 24.7%  [PR #9 已落地]
  Constraint Compiler                   49 / 235 = 20.9%
  Learning Error + Adaptive Practice    29 / 12.3%
  ranking: Research > Method > Decision > Claim-Evidence > Constraint > Learning
```

### 矩阵数据审计结论：
1. 数据完全稳定复现，排序位次在各次运行间保持绝对一致；
2. 原计划排在前面的两项底座（身份谱系、论断-证据图）均已交付；
3. 未落地候选方向中，**`Decision / Negative Result Ledger` 在 single 口径稳居全仓第一（36 项）**，在 baseline 口径位居第三（63 项）；**`Method / Supplement Miner` 在 baseline 口径位居第二（85 项）**。

---

## 3. 杠杆比与工程风险深度评估

| 评估维度 | 决策与负结果台账 (Decision / Negative Result Ledger) | 方法与补充材料提取器 (Method / Supplement Miner) |
| :--- | :--- | :--- |
| **前置条件依赖** | **已完全满足**：依赖 PR #6 的 `LineageGraph` 与 PR #9 的 `ClaimEvidenceGraph`（反驳边与不确定项），底座全部就绪 | **部分依赖**：需要结构化存储容器，缺少对各种非结构化文档的预处理 |
| **外部脆弱性** | **极低**：纯 Python 确定性状态机，离线无网络，无大模型幻觉与解析器漂移 | **高**：强依赖外部复杂 PDF/Word 版面分析、启发式表格解析与外部 LLM 抽取 |
| **十四原语填补** | **关键结构洞**：填补十四原语中覆盖 36 项痛点但全仓尚未形成通用原语的 **Primitive 3（State Ledger，状态台账）** | 属于应用型提取器（Primitive 2 + Primitive 10 衍生应用） |
| **可测试性与确定性** | **极高**：决策分支剪枝、负结果收据、状态迁移历史天然可通过确定性 fixture 100% 覆盖 | **中等偏低**：真实长文本抽取测试脆弱，极易出现跨平台与环境漂移 |
| **学术科研核心价值** | 解决学术界“只报喜不报忧、重复踩死胡同、缺乏失败路径记录、审稿人质疑无法溯源”的核心痛点 | 提供文档内辅助阅读与数据定位 |

---

## 4. 后续建设顺序与治理规划 (Roadmap Phasing)

经过上述量化对账与依赖拓扑分析，维护委员会正式锁定后续 PR 战略开发序列：

```text
PR #10 (当前 PR)
CI Actions Node 24 升级 + Ubuntu 26 预验证 + 定位符绝对确定性加固
      │
      ▼
PR #11 (战略核准方向)
Decision & Negative Result Ledger v1
(填补 Primitive 3 状态台账，实现科研决策图谱、负结果存证与剪枝因果追溯)
      │
      ▼
PR #12 (全仓桥接方向)
Research Artifact Ingestion Bridge v1
(实现 12 技能产物与回执向 CEG 和 Ledger 的统一确定性适配器)
      │
      ▼
后续评估
Method / Supplement Miner vs Constraint Compiler
```

---

## 5. 最终裁定

1. **正式核准 PR #11 的立项方向为：`Decision & Negative Result Ledger v1`（决策与负结果台账内核 v1）**；
2. PR #11 严禁引入外部非结构化重型依赖，继续严格遵循零 LLM、纯离线、确定性 Python 与三态证据纪律；
3. 将跨产物统一桥接规划为 PR #12，使 Ledger 与 CEG 能协同消费全仓 12 技能的沉淀资产。
