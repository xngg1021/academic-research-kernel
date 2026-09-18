# PR #6 后续建设方向解冻与审计重估裁定 (Post-PR6 Roadmap Re-evaluation)

依据 2026-09-17 议程审计（`docs/agenda-audit-20260917.md`）与《研究计划第 0 版》（`docs/research-plan-v0.zh.md`）第 5 节的明确纪律：
> “研究对象身份与谱系落地后，候选建设队列（论断-证据图、方法与补充材料提取器等）处于冻结状态，必须结合落地事实重新执行方向审计与杠杆重估，方可解冻施工。”

随着 **PR #6**（`Research Object Provenance Kernel & Lineage Receipt v1`，提交 `7965062`）与 **PR #7**（`Repository Identity Migration`，提交 `fb2cf3a`）的正式合并，本备忘录记录针对下一阶段演进方向的正式复核事实与审计结论。

---

## 1. 既有落地资产盘点 (Implemented Foundations)

原语层与基础设施现状：
- **原语 1（对象身份）**：由 `skills/research-object-identity`（`identity.py`）落地规范化、五态无分值判定与版本建边；
- **原语 2（生产谱系）**：由 PR #6 `provenance.py` 落地 W3C PROV 风格的计算活动一等对象化、内容寻址 SHA256 校验、因果拓扑迭代 Kahn DAG 校验、毫秒级逆向溯源与双重指纹 `LineageReceipt`；
- **传输与中立工具层**：由 PR #5 落地 `ReviewerAdapter` 中立 ABI、Agent Plugins v1 规范清单（`../plugin.json`）与 stdio 通用 MCP 服务器（`../scripts/mcp_server.py`）；
- **科学计算与数值等价层**：由 `../scripts/scfabric` 落地硬件探针、dtype 门禁后端目录、float32/64 容差区分与 `ComputeReceipt`。

至此，基础证据平面已经形成三大强类型不可变收据资产：
$$\text{ResearchObject} + \text{AcademicEvidenceReceipt} + \text{LineageReceipt}$$

---

## 2. 候选方向敏感性重算 (Sensitivity Analysis over 235 Pain Items)

运行 `../scripts/recompute_direction_coverage.py` 对 235 项极端长尾科研痛点矩阵进行覆盖重算：

| 候选方向 (Direction) | 单一原语覆盖 (Single) | 核心原语覆盖 (Core) | 基线综合覆盖 (Baseline) | 跨运行位次稳定性 |
| :--- | :--- | :--- | :--- | :--- |
| **Research Object Identity & Lineage** | 34 (14.5%) | 64 (27.2%) | 88 (37.4%) | [2, 1, 1] — **已落地闭环** |
| **Claim-Evidence Graph** | 15 (6.4%) | 47 (20.0%) | 58 (24.7%) | [6, 3, 4] |
| **Method / Supplement Miner** | 30 (12.8%) | 59 (25.1%) | 85 (36.2%) | [3, 2, 2] |
| **Decision / Negative Result Ledger** | 36 (15.3%) | 36 (15.3%) | 63 (26.8%) | [1, 4, 3] |
| **Constraint Compiler** | 18 (7.7%) | 18 (7.7%) | 49 (20.9%) | [5, 6, 5] |
| **Learning Error + Adaptive Practice** | 20 (8.5%) | 20 (8.5%) | 29 (12.3%) | [4, 5, 6] — **已剥离出本仓** |

---

## 3. 杠杆比与工程风险评估

1. **为什么不是 Method / Supplement Miner？**
   - 尽管该方向在痛点覆盖数量上排名靠前（85 项），但它高度依赖外部非结构化 PDF/Word 解析、表格抽取启发式规则与第三方大模型信息提取，具有极高的外部脆弱性与不确定性；
   - 在缺乏“断言-证据拓扑（Claim-Evidence）”这一消费层的情况下，提取出的方法材料与补充数据将缺乏承载的数据结构，容易再次退化为散乱文本。
2. **为什么不是 Decision / Negative Result Ledger 或 Constraint Compiler？**
   - 决策账本与阴性结果记录本质上是对“研究论断及其反面证据”的流转跟踪，必须依附于论断-证据图谱；
   - 规则编译器需要预先存在结构化的论断和约束条件，在缺乏证据图时属于无源之水。
3. **为什么 Claim-Evidence Graph 是当下最优战略解？**
   - **资产直接承接**：它能够无缝直接消费当前已就绪的 `ResearchObject`（实体锚点）、`AcademicEvidenceReceipt`（事实核验凭据）与 `LineageReceipt`（生产谱系证明）；
   - **确定性内核**：图的存储、节点唯一性哈希、证据链完整性、引用与矛盾边校验完全由纯 Python 确定性实现，零网络、零外部大模型依赖；
   - **为后续模块奠基**：一旦建立结构化的断言-证据图，后续的 Method Miner 可以直接作为“证据抽取者”接入，Decision Ledger 可以直接作为“图状态演进账本”接入。

---

## 4. 最终审计裁定与 PR #9 施工纪律

### 审计结论：
正式解除路线图构建队列的冻结状态，**核准 PR #9 的建设方向为：`Claim-Evidence Graph v1`（论断-证据图内核 v1）**。

### PR #9 架构边界纪律：
1. **语义图与谱系 DAG 的区分**：
   - 生产谱系（`DERIVED_FROM`）严格保持有向无环图（DAG）；
   - 论断-证据语义图允许自然成环（如 A 论文反驳 B 论文，B 论文反驳 A 论文，`CONTRADICTS` 天然双向互斥）；
2. **拒绝 Truth Authority 与主观打分**：
   - 绝不合成分数（严禁 0.85 这种主观置信度）；
   - 确定性内核负责实体标识、定位符坐标、引用完整性、收据绑定、图遍历与覆盖率检查；
   - 无法通过机械逻辑裁决的语义分歧，显式存入不确定性账本（`UncertaintyQueue`），供人工或上游审议小组决断。
