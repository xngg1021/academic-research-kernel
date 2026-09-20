# 变更日志与版本发布清单 (CHANGELOG & Release Manifest)

本文件记录 `academic-research-kernel` 仓库各版本的接口变更与迁移规范，列明输入输出形态变化以及发布身份清单。

---

## 2026-09-20（PR #12 / Research Artifact Ingestion Bridge v1，分支 work/research-artifact-ingestion-bridge-v1）

### 统一科研产物入库桥接与确定性内核公开界面 (Research Artifact Ingestion Bridge v1 / 协议：ingestion-receipt-1.0)

按战略路线图全面打通 13 项技能产物沉淀至确定性科研状态内核的入口，消解界面债务（Surface Debt）：

- **共享证据契约 (`scripts/shared_contracts/evidence.py`)**：
  - 抽取并统一维护 `ReceiptRef`、`canonical_json_bytes`、学术证据物理载荷 SHA-256 校验以及谱系收据契约验证；
  - 消除 CEG 与 Decision Ledger 之间的内部重复代码，全仓实现 100% 逐字节序列化与哈希恒等；
- **产物信封与入库凭证模式 (`schemas/`)**：
  - `research-artifact-envelope.schema.json`（协议 `artifact-envelope-1.0`）：强制内容寻址派生 `artifact_id`（`art-` + 32 位 hex），将内容身份与环境元数据严格隔离；
  - `artifact-ingestion-receipt.schema.json`（协议 `ingestion-receipt-1.0`）：强制确定性生成 `receipt_id`（`ingest-` + 32 位 hex），记录命中的适配器、输入校验状态、生成的对象标识与输出状态摘要；
- **确定性适配器注册表与入库引擎 (`scripts/ingestion/`)**：
  - 机器可读注册表 (`docs/artifact-adapter-matrix.json`) 覆盖全仓 13 项技能的 3 档适配器：
    - Tier 1（原生凭证）：`academic-source-verification`、`research-object-identity`、`claim-evidence-graph`、`decision-ledger`；
    - Tier 2（结构化分析）：`quantitative-paper-audit`、`research-reproducibility`、`cross-review-five`、`systematic-review-meta-analysis`、`literature-analysis`、`literature-watch`、`retraction-watch`、`math-computation`；
    - Tier 3（非结构化存证）：`academic-writing` 严格遵循“非结构化保持不透明（Opaque stays opaque）、绝不替研究者代做决策”的安全红线；
  - 事务性与幂等性：基于 `IngestionKernelState.clone()` 机制实现全批次原子提交与回滚（`atomic=True`），重复入库幂等命中；
- **通用 MCP 服务能力升级 (`scripts/mcp_server.py`)**：
  - 由原有的 3 个外围统计与硬件探测工具，全面扩展为 12 个确定性无状态科研内核工具（新增 `research_artifact_validate`、`research_artifact_ingest`、`research_receipt_verify`、`research_object_resolve`、`research_lineage_trace`、`claim_evidence_validate`、`claim_evidence_trace`、`decision_ledger_validate`、`decision_trace`）；
- **端到端完整生命周期与对抗性用例**：
  - 新增 `tests/test_evidence_contract.py`、`tests/test_artifact_envelope.py`、`tests/test_ingestion_bridge.py`、`tests/test_ingestion_adversarial.py`、`tests/test_mcp_surface.py` 与 `tests/test_research_lifecycle_e2e.py`；
  - 新增 `tests/test_ingestion_hardening.py`，覆盖深不可变、运行时 schema、真实生产者契约、原子回滚、语义幂等、完整状态回放、防篡改摘要、三态证据语义与真实 stdio MCP 握手；
  - 单测基线由 632 项扩充至 **736 passed, 3 intentionally skipped**（40 independent executable smoke fences PASS）。

### PR #12 合并前完整性加固与历史对账

- **[P1] 运行时契约与防篡改**：21 个结构化 payload schema 进入 Draft 2020-12 运行时门禁；信封、CEG、谱系收据与内核快照均重算声明摘要，非法枚举、未知字段、版本漂移、超限载荷与篡改状态 fail closed。
- **[P1] 事务、幂等与状态本真**：缓存键绑定全部变异上下文并限定于目标状态；原子批次只在最终提交后发布缓存；CEG、Ledger、收据注册表、不确定性与入库记录完整克隆/回放，冲突对象和悬空边拒绝写入。
- **[P1] 真实生产者契约闭环**：修正 reproduction `status`、ResearchObject 标准字段、cross-review 2.x registry、lineage edge `type`、直接 `CanonicalWork`、meta-analysis-only、screening-only 与 citation-only payload；定量审计覆盖真实返回字段，缺失或 `null` 的数学/定量核验结果进入 `unverifiable`，不再伪装为支持或反驳。
- **[P1] MCP 公共面闭环**：严格工具入参 schema、统一 `isError`、完整 kernel state 输入输出、实际 lineage/ledger API、物理收据复核，并以真实 stdio 子进程覆盖 initialize/list/call。
- **[P1] 深不可变**：信封、入库收据、LineageReceipt、CEG 与 Ledger 的全部嵌套 JSON 数据递归冻结；对 `to_dict()` 结果和底层映射的外部变异均不影响域对象。
- **[P2] 审计上下文**：caller metadata 完整传递但不污染内容寻址 receipt ID；对象、物理收据、不确定性、已入库产物与总内核内容均有独立摘要。
- **[P1] 二次复审闭环**：继续修复 7 个新发现的边界条件：CEG ID 绑定目标 work、MCP 快照校验接收物理收据、筛选/纳入研究对象隔离、caller metadata 不触发重复变异、回执引用真实 correction ID、`missing_input` 谱系收据可验证、时间戳变体不冲突。
- **[P1/P2] 三次复审闭环**：修复后续 6 个 P1 与 1 个 P2：稳定 work 身份与检索元数据解耦、CEG claim/evidence 分层绑定 locator 与物理回执、筛选记录优先 `record_id`、撤稿 retained-prior 状态进入不确定性、预检重算 lineage 身份、MCP lineage 活动强制显式时间戳、Ledger 快照仅按声明 manifest 重放。
- **[P1/P2] 四次复审闭环**：修复后续 5 个 P1 与 3 个 P2：lineage locator 与撤稿 target 进入身份、CEG 校验错误保持验证契约、claim trace 返回支持/反驳锚点、截断撤稿进入覆盖不确定性、筛选决策闭集、增量与快照不确定性同步、适配器内容 ID 统一为 128-bit；同时将同类约束扩展到相邻适配器并复用已有丰富 work 对象。
- **[P1] 五次复审闭环**：修复后续 5 个 P1：派生不确定性随因果状态同步清退、系统综述抽取与筛选决策按 review artifact 命名空间隔离、成功的 receipt verify 不再误标 MCP `isError`、适配器 bindings 先归一化并拒绝未知字段、同一命题的支持与反驳证据汇聚至同一语义 claim 节点。
- **[P1/P2] 六次复审闭环**：修复后续 8 个 P1 与 1 个 P2：缓存命中绑定完整入库上下文、信封 `lineage_ref` 被持久化并核验、物理回执递归冻结、CEG 快照按声明的回执可用性重放、仅清退内核拥有的不确定性、筛选决策按评审实例隔离、空白 claim fail closed、wrapped canonical work 复用完整 schema、确认撤稿在结果截断时同时保留告警与覆盖不确定性。
- **[P1/P2] 七次复审闭环**：修复后续 5 个 P1 与 3 个 P2：CEG 快照按每个引用精确投影回执缺失状态、预检与实际入库统一核验 `lineage_ref`、retained-prior 的既有撤稿告警不再丢失、手稿对象按信封上下文隔离、计算证据保留并绑定有效 locator、一次显式 binding 只追加一次 correction、多 work 产物拒绝冲突身份、MCP lineage 的畸形实体与边归入参数错误。
- **[P1/P2] 八次复审闭环**：修复后续 4 个 P1 与 4 个 P2：计划内 ResearchObject 身份冲突统一 fail closed、cross-review 证据按完整入库上下文隔离并保留 locator、lineage 实体/活动类型在 MCP dispatch 前按闭集拒绝、无标题评审意见使用规范 JSON 原因、残缺 lineage receipt 返回普通 invalid、falsy 物理回执不再伪装成缺失、canonical work 可确定性升级临时占位对象、opaque fallback 对象按完整信封上下文隔离。
- **历史台账**：新增 `docs/project-lineage-audit-20260920.md` 与机器可读 JSON，逐项核对 PR #1–#12 的精确 head/CI、累计观察到的 83 个 PR #12 评审线程以及仍开放的 P2/P3 运营和治理边界。

---

## 2026-09-19（PR #11 / Research Decision Log v1，分支 work/decision-ledger-v1）

### 研究决策与失败记录 (Research Decision Log v1 / 协议：decision-ledger-1.0)

按 `docs/post-pr9-roadmap-reevaluation.md` 的立项裁定，填补十四核心能力中的状态变更历史 (Primitive 3)：

- **核心数据契约 (`schemas/decision-ledger-receipt.schema.json`)**：
  - JSON Schema draft 2020-12、`additionalProperties: false`、协议常量 `decision-ledger-1.0`；
  - 核心记录模型：`decisions`（区分 entry_kind 与 decision_action，严禁将失败结果与决策行为混维，Schema 严格校验 entry_kind 与 decision_action 的条件映射）、`bases`（decision / negative_result 依据边，彻底移除 claim 别名）、`forks`（considered/explored/deferred/rejected 分支边，含 `receipt_ref`）、`state_events`（追加式状态转移事件，sequence >= 1，驱动生命周期状态）、`corrections`（128 位内容 ID 与单调 sequence >= 1 结果修正）、`uncertainties`（离散枚举）；导出包含 `verification_manifest` 与 `verification_digest`，内容身份与本地验证态严格解耦；字段长度与正则模式（title 512、locator 2048、rationale 4096、context_work_id ID 规范）在 Schema 与 Python 间实现 100% 严格一致；
  - `receiptRef` 复用 CEG 的 `oneOf` 双契约（lineage / academic_evidence），与 `schemas/claim-evidence-graph.schema.json` 逐字段一致。
- **确定性内核 (`skills/decision-ledger/scripts/ledger.py`)**：
  - 自然科研 API：正式暴露 `RouteStatus`、`record_route_status()`、`trace_stop_reason()`、`add_negative_result()` 等科研语义接口，兼容保留内部别名；`RouteStatus.to_dict()` 仅输出标准科研状态字段，不泄露内部算法名；
  - 状态变更历史纯追加：所有记录为 frozen dataclass + `FrozenDict`（`MappingProxyType` 背板真不可变）；当前状态（active/pruned/reopened）由追加式 `DecisionStateEvent` 重放派生，严格状态迁移闭集自动机校验，`current_state()` 正确暴露 `reopened` 状态；
  - 结果修正时序严格保护：`OutcomeCorrection` 引入单调 sequence 参与 ID 派生，sequence 严格要求 >= 1，幂等仅对当前最新事件生效，历史中再次发生的相同结果正确记录为新事件；
  - 失败尝试存证纪律：`negative_result` 必须携带依据边（E404），必须有决策类正证据基础（E405），依据类型与目标决策类型强校验（E103），自指或负结果互指判错（E406），负结果依据闭包成环硬失败（E407）；
  - 路线终止原因与可追溯性：封闭词表终止原因 + `closed_by` 主导决策 + `alternative_ref` 备选路径；派生当前图终止链严格无环（E304，路径索引法只报真环成员）；`trace_stop_reason` 递归返回完整因果链；
  - 单遍图分析与全链路索引：单遍 Tarjan's SCC 算法提取强连通分量与环可达集；建立按决策索引的 `_bases_by_decision`、`_bases_by_target`、`_state_events_by_decision`、`_corrections_by_decision` 与 `_academic_hash_index`，`_resolve_receipt` 直接基于索引实现真正的严格 O(1) 检索；`to_dict()` 单次流计算哈希与清单；
  - 严格回放加载器 `from_dict`：四门严密防篡改（Gate 1 原始摘要核验、Gate 2 派生一致性断言、Gate 3 全量不确定性队列（含 missing_receipt）100% 验证、Gate 4 图结构强校验 `validate_ledger()` fail-closed）；严格拒绝额外顶层字段；
  - 构造期严厉失败关闭：`_validate_json_metadata_value` 拦截非有限浮点（NaN/Inf）、非字符串键、非法对象与循环引用；收据冲突采用规范 JSON 字节流比对。
- **全球学术标准基线 (`docs/standards/`) 与自然术语清单 (`docs/terminology/`)**：
  - 确立 ISO 690:2021、ISO 704:2022、ISO 860:2007、ISO 5127:2017 与 W3C PROV 为全球基线，解耦语言与司法管辖区规范；标准注册表逐项完善 `authority_url`、`verified_at`、`evidence_status` 与 `supersedes` 证据链；
  - 建立机器可读标准清单 `docs/standards/registry.json` 与涵盖 18 组概念、覆盖全部 21 个目标语种自然学术表达的 `docs/terminology/registry.json` 及完整说明指南 `docs/terminology/README.md`；
  - 建立 AIDetox 公开文档写作契约 `docs/style/aidetox-contract.json` 与涵盖 21 个语种独立规则库的 `docs/style/profiles/`；
  - 落地 21 语种 README 核心能力与结构对齐（全 11 节结构、SLL/MIT 许可边界、13 技能、MCP/Hermes、数据源、longtail 与 scfabric 全覆盖），全语种顶栏导航互联；
  - 全仓 53 篇规范 Markdown 文档密码学级增量同步清册 `docs/i18n/manifest.json`（53 篇源文档 × 21 语种 = 1,113 理论实例；53 canonical_current、22 localized_current、1,038 queued_for_generation），内置代码块感知的章节哈希提取与陈旧度检测，杜绝重跑脚本静默洗白；
  - `scripts/qa.py` 静态门禁强制固化 21 语种 Profile、18×21 术语矩阵、53 篇清单源文件与本地文件双层哈希、以及 `README.zh-CN.md` / `README.zh-TW.md` 中文别名逐字节恒等不变量。
- **技能文档 (`skills/decision-ledger/SKILL.md`)**：以自然科研语言重写，frontmatter 齐全、Verification 段提供可执行离线冒烟 fence。
- **测试 (`tests/test_decision_ledger.py`)**：100 项对抗性回归，单测基线升至 **632 passed**。

**验证**：`pytest` 632 项全部通过（0 failures, 0 warnings）；`scripts/qa.py` 静态门禁全部 PASS（40 independent executable fences）。

### 交叉评审加固（五模型盲审第一轮 + 主线程复核，同 PR 内实施）

五模型 Sparse Deliberation 盲审（kimi-k3/dsv4pro/glm53/gemini38flash/gemini31pro）提出若干发现，主线程逐项实测复核后裁决并修复（假阳性驳回，真缺陷全部修复并补对抗回归）：

- **[P0] 负结果循环证据伪造封死**：`negative_result` 自指（引自身为 claim）与互指（两个负结果互相引为 claim）原本可绕过 E405；新增 E406 自指判错，E405 改为要求依据引用**其他**非负结果决策；混合支撑（伪 claim + 负结果边）同样无法通过。
- **[P1] 结果修正时序语义**：`outcome_of` 原按内容寻址 ID 字典序取"最新"，哈希随机分布导致时序失真；为 `OutcomeCorrection` 引入台账分配的 `sequence` 单调序号（幂等重放保持不变），`latest_verdict` 反映真实追加历史；schema 同步 `sequence` 必填字段；摘要不变量明确唯一例外：不同修正的到达顺序属于追加历史，合法影响 `ledger_digest`。
- **[P1] 摘要对对象收据崩溃**：`register_receipt` 接受带 `to_dict()` 的对象但 `ledger_digest` 直接 JSON 序列化会 TypeError；新增 `_jsonable` 确定性降级（Mapping/list/JSON 原语直通、to_dict 递归解包、其余 repr），对象收据与等价 dict 给出相同摘要。
- **[P2] 内容 ID 碰撞防御**：16 位截断（64 位熵）的内容 ID 在命中已注册键时校验完整负载指纹，不同负载碰撞直接抛错，同负载保持幂等。
- **[P2] E304 环报错归一**：同一剪枝环不再按起点重复报多条，收敛为单条并列环成员。
- **[P2] fork 边收据位补齐**：`DecisionForkEdge` 增加 `receipt_ref`（分支探索也可挂实验证据），`validate_ledger` 与不确定性队列同步校验 fork 收据解析。
- **[P2] 导出补全**：`to_dict()` 补齐 `uncertainties` 字段序列化，与 schema 的可选属性对齐。
- **误报驳回**：zh-TW "十二個"残留指控实测为 literature-analysis 的工作流数表述，非技能计数；任务书"8 个 README 计数"表述经复核仅在 en/zh-CN 硬编码数字，其余语言为泛化表述，无遗漏。
- 新增 10 项对抗回归（test_decision_ledger.py 45→55 项），全仓 571→581。

**验证（加固后）**：`pytest` 581 项全部通过；`scripts/qa.py` 40 fences PASS。

### 交叉评审加固第二轮（dsv4pro 深度盲审 + 主线程复核，同 PR 内实施）

- **[P1] FrozenDict 哈希缓存失配封死**：惰性缓存的 `_hash` 在越权 slot 写入后不失效，同一对象哈希与内容失配；取消缓存、哈希每次按当前内容现算（条目规模小，开销可忽略），越权写入后哈希立即跟随内容，陈旧哈希无处发生；补 `__eq__`/`__ne__` 规范 Mapping 语义（递归 thaw 比较）。
- **[P1] 不确定性 item_id 派生与 CEG 对齐**：台账原哈希 `{kind, subject_id, reason}` 三字段，CEG 哈希 `{kind, needs_human, reason, subject_id}` 四字段，同一逻辑项跨内核 ID 不同，PR #12 队列合并将错配；改为与 CEG 逐字节一致的派生公式，并对去重引入负载指纹碰撞防御（不同负载碰撞直接抛错，同内容幂等合并）。
- **[P2] 不变量 6 措辞精确化**：原文"至少一条依据边引用 Claim 节点"的"Claim 节点"易被误读为外部证据实体；改为"claim-kind 依据边指向**另一个**非负结果决策"，并说明证据链经目标自身依据传递、无据根经不确定性队列浮出。
- **[P2] 注册表 docstring 精确化**：`register_receipt` 注册键只是登记标签，"lineage 按 receipt_id / academic 按 payload_sha256 键优先 + 全表扫描"的解析约定在 `_resolve_receipt`，以注释显式声明，消除"注册键即解析键"的误读。
- **[P2] CHANGELOG 测试计数归因修正**：526→571 的增量实为 test_decision_ledger 39 项 + test_authoring 参数化随第 13 技能增长 6 项（73→79），归因更正。
- dsv4pro 其余发现（E405 标签洗白、截断碰撞、对象收据崩溃、无时序、fork 收据位、E304 归一、导出缺队列）已在第一轮修复或与第一轮收敛。
- 新增 4 项对抗回归（55→59 项专项），全仓 581 项保持全绿。

**验证（第二轮加固后）**：`pytest` 581 项全部通过；`scripts/qa.py` 40 fences PASS。

### 交叉评审合议收口（质询对账 + 未决账本清偿，同 PR 内实施）

五模型盲审（3/5 产出：dsv4pro、gemini38flash、gemini31pro；kimi-k3 连接错误、glm53 配额中断）后完成 Sparse Deliberation 质询与合议：dsv4pro 质询答复 4 项全部 CONCEDE 并独立证实 sequence 修复；未决账本 5 项中 4 项（自指/互指绕过、时序、对象收据崩溃、导出缺队列）已由前两轮加固清偿，剩余 1 项（gemini31pro 的 E102 语义断言）处理如下：

- **[P2→落实] 依据透明规则（basis-transparency）**：claim 证据链必须**终接在带收据锚点的终端**——链条经目标决策自身的 claim 依据传递，自指边永不作数；无收据锚定的终端与永不落地的互指环以新枚举 `unevidenced_claim_basis` 浮出不确定性队列（needs_human=true），结构校验保持确定性不受阻断。E102 的保留决策与语义理由随之完整：`basis_id` 必须是已注册决策（保证引用可追溯），而"证据真实性"由锚定规则与队列承担，两层职责不再含混。
- schema 不确定性枚举同步扩至六值；新增 5 项对抗回归（59→64 项专项，覆盖无锚终端、锚定链、自指锚点、互指环、孤立决策零噪音），全仓 581→590。

### 外部评审集中加固（第三方 P1 簇全清，同 PR 内实施）

外部评审针对合并前 HEAD 提出 6 簇 P1 与 9 项 P2，主线程逐项实测复核后全部属实并实施修复（`pytest` 590→608 项全绿，qa.py 40 fences PASS）：

- **[P1-01] State Ledger 本真化**：`PruneState` 单快照改为追加式 `DecisionStateEvent`（from_state/to_state/reason/caused_by/alternative_ref/receipt_ref/sequence），生命周期状态由事件重放派生；`current_state`/`state_history` 全部就绪；合法迁移闭集（genesis→active|pruned、active→pruned、pruned→reopened、reopened→pruned）强校验，重复同负载调用幂等 no-op，event_id 绑定 内容+序号 保证历史中两次相同迁移互不吞并；`PruneState` 降为派生视图，`set_prune` 保留兼容包装。
- **[P1-02] FrozenDict 真不可变**：背板从裸 dict 改 `MappingProxyType`，构造后无任何可达的变异路径（slot 写入直接 TypeError）；哈希每次现算。
- **[P1-03] forkEdge schema ABI 对齐**：`receipt_ref` 补入 `$defs.forkEdge`，schema 增加 uncertainties 必填、stateEvent 完整定义（含 if/then 跨字段约束：pruned 必填封闭词表 reason、active 禁带因果字段）、`correction_id` 升 `^corr-[0-9a-f]{32}$`、sequence 下限 1、lineage receipt_id minLength 1。
- **[P1-04] basis_kind↔目标类型强校验**：新增 E103（`negative_result` 依据必须指向负结果决策、`claim` 依据不得指向负结果决策），类型化依据边不再是自报标签。
- **[P1-05] 内容身份与验证态解耦**：`ledger_digest` 不再包含本地收据注册表（注册标签不再污染摘要，同一台账不同标签恒等）；新增 `verification_digest` 独立承载验证态；导出与 schema 同步。
- **[P1-06] `_jsonable` 严格失败关闭**：删除 `repr()` 回退（跨进程非确定且在外来对象上是任意代码路径），仅允许 JSON 原语/Mapping/序列/to_dict 对象，其余 TypeError；环形容器拒绝；`register_receipt` 注册即 fail-fast。
- **[P2] 其余落实**：修正碰撞防御死代码（重排为先比对全负载再幂等返回）+ 修正 ID 升 128 位；E407 负结果证据闭包成环硬失败（确定性结构事实不再仅浮出队列）；E304 尾巴节点修正（路径索引法，只报真环成员）+ reopen 破环后派生当前图环消失；`trace_prune_cause` 递归返回完整剪枝链；新增严格回放加载器 `from_dict`（契约校验→构造器重放→迁移链复核→摘要重算比对，篡改导出 fail closed）；README/PR 验证基线统一至 608。
- **暂缓项**：CEG/Ledger 契约共享模块抽取（scripts/contracts/evidence.py）归入 PR #12 桥接统一处理，本 PR 以跨内核字节兼容回归测试钉住两侧契约；P3 性能项（SCC 统一、索引、digest 增量缓存）登记待办，不改变语义。

**验证（本轮加固后）**：`pytest` 608 项全部通过（0 failures, 0 warnings）；`scripts/qa.py` 40 fences PASS。

### 合并前全面收口加固（零债务发布，同 PR 内完整实施）

针对合并前终审提出的各项架构完整性、事件历史时序、回放闭环、命名解耦与性能要求，主线程实施彻底加固，完全消解全部 P1/P2/P3，不向后续 PR 遗留任何技术债务：

- **[P1] 修正 outcome correction 历史吞噬 bug**：`OutcomeCorrection` 引入单调 sequence 参与 content-addressed ID 派生；严格比对当前最新事件，仅在与当前最新完全相同时才执行幂等 no-op，历史中再次发生的相同结果（如 negative→positive→negative）正确记录为新事件并影响最新 verdict。
- **[P1] `from_dict()` 补齐 Gate 4 结构校验**：回放结束时无条件执行 `validate_ledger()`，对带环、悬空边或非法证据闭包的自洽伪造导出执行 fail-closed。
- **[P1] `from_dict()` 双门防篡改与全量不确定性校验**：Gate 1 原始摘要核验、Gate 2 派生字段一致性断言、Gate 3 全量不确定性队列（基于 manifest 虚拟集合，不跳过 missing_receipt）100% 严格比对。
- **[P2] 明确 `reopened` 状态语义与属性**：`current_state()` 准确返回 `reopened`，`PruneState` 增加 `is_active`、`is_reopened`、`is_pruned` 属性，`VALID_PRUNE_STATUSES` 与 `VALID_DECISION_STATES` 完全对齐。
- **[P2] `set_prune(active)` 拒绝静默吞输入**：对已处于 active/reopened 的决策，若传入不同 metadata/receipt_ref 直接抛 `ValueError` 拒绝冲突，杜绝非幂等输入静默丢失。
- **[P2] 消除与 CEG Claim 的命名冲突**：`basis_kind` 主名称统一为 `"decision"`（支持 `"decision"` 与 `"negative_result"`），原有 `"claim"` 自动规范化为 `"decision"`。
- **[P2] 补全包级公开导出**：`skills/decision-ledger/scripts/__init__.py` 正式导出 `DecisionStateEvent` 与 `canonical_state_event_tuple`。
- **[P2] 运行时与 Schema 边界统一**：`DecisionNode`、`OutcomeCorrection` 等公开 dataclass 强制校验 title (<=512)、rationale (<=4096)、locator (<=2048)、sequence (>=0) 等字段范围。
- **[P2] `from_dict()` 拒绝未知顶层字段**：严格拒绝不在 `ALLOWED_TOP_LEVEL_KEYS` 中的额外键，契约对齐 `additionalProperties: false`。
- **[P2] `register_receipt()` 规范化字节比较**：收据冲突判断采用 canonical JSON bytes 对比，彻底避免 Python `1 == 1.0` 等宽松判等误判。
- **[P3] 用户面命名与去黑话**：用户面统一命名为 **Research Decision Log（研究决策与失败记录）**（内部协议保持 `decision-ledger-1.0`）；彻底剥除“Truth Authority”“剪枝因果”“三态不确定性队列”“basis-transparency”等过度工程化用词。
- **[P3] 全链路性能索引与摘要去重**：建立按决策索引的 `_bases_by_decision`、`_state_events_by_decision`、`_corrections_by_decision`，建立学术收据哈希索引 `_academic_hash_index` 实现 O(1) 检索；`to_dict()` 仅单次计算 digest 与 manifest，杜绝多重重复哈希。
- **[P3] 测试基线提升**：单测由 615 项升至 **625 项**（93 项专属于 decision-ledger 严苛回归测试），全仓绿灯通过。

**验证（最终收口后）**：`pytest` 625 项全部通过（0 failures, 0 warnings）；`scripts/qa.py` 40 fences PASS。

---

## 2026-09-18（PR #10 / CI & Locator Determinism Maintenance，HEAD / chore/ci-node24-and-locator-determinism）

### 基础设施维护、定位符确定性加固与 PR #11 立项裁定
- **GitHub Actions 全量迁移 Node 24 generation**：
  - 升级 `actions/checkout` 至 v7.0.1 不可变 SHA（`3d3c42e5aac5ba805825da76410c181273ba90b1`）；
  - 升级 `actions/setup-python` 至 v7.0.0 不可变 SHA（`5fda3b95a4ea91299a34e894583c3862153e4b97`）；
  - 覆盖 checks、upstream-canary、tap-lifecycle 全部 8 处 action 引用，彻底消解 Node 20 弃用告警与即时生效的时间性阻断风险。
- **Ubuntu 26.04 Canary 预迁移验证**：
  - 增设 `ubuntu-26.04` (x86_64) 与 `ubuntu-26.04-arm` (arm64) canary 节点，提前验证下一代系统的依赖与环境兼容性，全矩阵首轮一次性全绿。
- **谱系相对定位符绝对确定性加固 (P1/P2)**：
  - `skills/research-object-identity/scripts/provenance.py` 严格规范：`relative local locator + root_dir=None` 绝不回退至进程当前工作目录（CWD）；
  - `validate_lineage()` 将未指定 `root_dir` 的相对定位符显式标为 `unverified` 并附带 `Relative local locator requires explicit root_dir for on-disk verification`，确保跨不同 CWD 执行时验证元组与回执摘要 100% 恒定。
- **PR #11 战略立项治理审计**：
  - 新增 `docs/post-pr9-roadmap-reevaluation.md`，执行 235 项痛点矩阵重算核验，正式核准 PR #11 方向为 `Decision & Negative Result Ledger v1`（填补十四原语中的状态台账 Primitive 3），并规划 PR #12 为 `Research Artifact Ingestion Bridge v1`。
- **验证矩阵更新**：
  - 全仓单测规模扩充至 **526 项全绿**（0 failures, 0 warnings）；
  - 静态 QA 可执行代码块 39 项全部 PASS。

---

## 2026-09-18（PR #9 / Claim-Evidence Graph v1，commit ab7d1fe）

### 科学论断-证据图内核 (Claim-Evidence Graph v1)
- **核心数据契约 (`schemas/claim-evidence-graph.schema.json`)**：
  - JSON Schema 2020-12 严格规范，全量开启 `additionalProperties: false`；
  - 规范定义 `Claim`、`EvidenceAnchor`、`EvidenceSupportEdge`、`ClaimRelationEdge`、`UncertaintyItem` 与 `ReceiptRef`；
  - 强类型 `ReceiptRef` 正式解耦并无歧义绑定 `LineageReceipt`（通过 `receipt_id`/`receipt_digest`）与 `AcademicEvidenceReceipt`（通过 `claim_digest`/`payload_sha256`）。
- **确定性图内核 (`skills/claim-evidence-graph`)**：
  - 确立生产谱系（DAG）与学术命题关系（允许自然成环，如双向互斥反驳）的分立纪律；
  - 严禁任何形式的真理裁判所与主观置信度打分（如 0.85），裁决一律离散化，争议显式进入不确定性账本（`UncertaintyQueue`）；
  - `claim_digest` 严格绑定规范化命题文本（仅做 NFC 与空白压缩，绝不重写语义）、定位符与所属论文；
  - 纯 Python 离线实现矛盾发现器（`find_contradictions`）与全链执行谱系回溯穿透（`trace_claim_provenance`）；
  - 采用 `FrozenDict` 深度冻结机制，严格封死对象属性嵌套变异导致的 edge 幂等键失步。
- **验证矩阵**：
  - 全仓单测规模扩充至 **524 项全绿**（0 failures, 0 warnings）；
  - 静态 QA 可执行代码块扩充至 39 项全部 PASS。

---

## 2026-09-18（chore/repo-identity-closeout-and-roadmap）

### 仓库身份闭环与路线图解冻重估 (Identity Closeout & Roadmap Re-evaluation)
- **现行 CI 彻底脱离旧重定向**：`.github/workflows/qa.yml` tap 集成全面切至 `xngg1021/academic-research-kernel`。
- **全多语言文档定位与基线对齐**：8 份 README 头部全面对齐中立定位，测试基线统一切至 495 项通过；明确便携包与 MCP 别名长期向后兼容。
- **仓库身份连续性存证**：建立 `REPOSITORY-IDENTITY.md`，记录官方不可变 ID（`1358731364`）与历史过渡 Commit。
- **路线图解冻审计裁定**：完成痛点矩阵与杠杆重估（`docs/post-pr6-roadmap-reevaluation.md`），基于三项已就绪资产（`ResearchObject`、`AcademicEvidenceReceipt`、`LineageReceipt`），正式核准 PR #9 为 `Claim-Evidence Graph v1`。

---

## 2026-09-17（work/cross-review-five-v2-20260917）

本次更新包含对五人交叉评审 v2（Sparse Deliberation）的完整重构，以及全仓 41 项重审缺陷治理与科学计算执行层（`scfabric`）的引入。

### 1. 接口与返回值变更 (Migration Guide)

| 模块 / 脚本 | 原行为 (旧接口) | 现行规范 (新接口) | 迁移与兼容性说明 |
| :--- | :--- | :--- | :--- |
| `cross-review-five/orchestrate_v2.py` | 轮转互审两阶段模式；粗粒度按 target 聚类；单断言反驳清除整项 | v2 四阶段流：盲审生成 -> 断言级聚类合并 -> 定向匿名质询 -> 对账与未决保护账本 | 旧命令兼容执行，`stage_synthesize_v2` 产出 `unresolved-ledger.json` 与结构化收敛状态 |
| `retraction-watch/watch.py` | `check_doi` 仅读首批 100 条 Crossref 记录；404 时将旧值直接覆盖回当前状态 | 引入 `truncated` 状态指示；快照如实记录 `current_observation` 与 `verification_status='retained_prior'` | 状态快照向后兼容，下游解析器可直接读取 `current_observation` 判断本轮是否真实触网 |
| `retraction-watch/watch.py` | `update-to` 信号绑定 target DOI（出现重复压缩） | 信号身份优先绑定通知记录自身 DOI（`update-doi=<notice_doi>`） | 历史状态中旧格式字符串平滑保留，新检测事件使用独立更正身份 |
| `literature-watch/watch.py` | OpenAlex 查无 ID 时将原论文作为引用者输出 | `fetch_citing_works` 产出 `source='crossref-fallback'`，`collect()` 过滤该种子记录 | 杜绝被监控论文自身被报告为自己的新引用者 |
| `literature-analysis/collect_corpus.py` | 仅使用线性字典别名映射；丢弃作者与摘要 | 采用并查集（DSU）两遍归并；保留 `authors`, `abstract`, `referenced_works` 等元数据 | 彻底消除输入顺序依赖；下游引文图与评审矩阵直接消费完整材料 |
| `literature-analysis/interop.py` | BibTeX 互转单向转义，往复导致 `\\&` 等符号膨胀；剥光机构作者花括号 | 增加对称的 `tex_unescape`；仅剥除单层字段定界符，保护单一机构作者不被拆分 | `to_bibtex(from_bibtex(text))` 达到幂等性 |
| `quantitative-paper-audit/recompute.py` | `percent=0` 且 `count>0`、未给分母时直接判不可能；float 丢尾随零 | 根据报告精度容差判定最小合理分母，记为欠定；支持直接传入原始字符串保留有效小数位数 | 浮点数与字符串输入同时兼容 |
| `scfabric` (科学计算执行层) | （新增模块） | 提供硬件探针与后端目录，配备五项基准负载与严格等价门禁，产出完整的 `ComputeReceipt` 回执 | 默认基于 CPU 执行，仅在实测提速超过阈值且通过数值门禁时准入加速器 |
| `literature-watch/watch.py` & `retraction-watch/watch.py` | 404 错误触发三次无谓重试导致 Crossref 兜底受阻；Token 凭证校验依赖前缀匹配 | 404 直接抛出不参与重试；凭证注入限定为 HTTPS 与官方域名权威校验；端点显式指向 `/v1` | 兼容旧版调用，消除无谓重试延迟并杜绝凭证泄露 |
| `cross-review-five/orchestrate_v2.py` | 子进程继承父进程全量环境变量；固定 15 秒轮询；依赖兼容别名 | 注入 `--ignore-rules` 参数与最小环境白名单；引入自适应轮询与规范提供方名称解析 | 隔离无关凭证并消除评审进程空等 |
| `scfabric/backends.py` & `hardware_probe.py` | ROCm 平台误标为 CUDA；缺少 Intel XPU 执行后端 | 区分 `torch.version.hip` 并标记 `rocm` 运行环境；补齐 `torch_xpu` 执行后端与类型约束 | 准确反映各硬件运行时身份 |
| `cross-review-five/orchestrate_v2.py` | 仅支持固定 5 种预置模型；不支持第三方子代理与动态配置 | 支持 `--models` 动态内联声明与 `--models-file` 外部清单；支持自定义 CLI 子代理模板；自适应 $N$ 阶错排降级 | 用户可自由指定任意数量与种类的模型及子代理 |

### 2. 发布身份清单 (Release Manifest)

- **Repository**: `xngg1021/academic-research-kernel` (历史版本标记为 `hermes-academic-skills`)
- **Protocol**: `compute-receipt-1.0` / `evidence-receipt-1.0` / `lineage-receipt-1.0` / `claim-evidence-graph-1.0`
- **Skills & Components (12 一等技能)**:
  - `skills/cross-review-five` (2.0.0) — v2 四阶段 Sparse Deliberation 稀疏审议流重大升级
  - `skills/academic-source-verification` (1.2.0) — 增加全 Unicode 分词与词元集合匹配算法
  - `skills/academic-writing` (1.1.1) — 写作规范与引文参考
  - `skills/literature-analysis` (1.3.0) — 并查集两遍归并与 LaTeX 对称反转义
  - `skills/math-computation` (1.2.1) — 全领域计算中枢与分流
  - `skills/quantitative-paper-audit` (1.1.0) — 0% 欠定判定与有效数字尾随零保留
  - `skills/research-reproducibility` (1.0.1) — 复现审计流水线与排版修复
  - `skills/systematic-review-meta-analysis` (1.0.1) — trim-and-fill 固定点收敛判断修复
  - `skills/literature-watch` (1.1.0) — Crossref 兜底、凭证域名权威校验与并发锁租约
  - `skills/retraction-watch` (1.1.0) — 状态合并、并发租约锁与分页截断检测
  - `skills/research-object-identity` (1.1.0) — 确定性研究对象身份层与生产谱系内核（Provenance Kernel v1，落地路线图原语 2 谱系，为原语 3 奠定对象与事件底座）
  - `skills/claim-evidence-graph` (1.0.0) — 确定性科学论断-证据图内核（Claim-Evidence Graph v1，连接论断、事实收据与计算谱系）
  - `scripts/scfabric` (1.0.0) — 科学计算执行层薄层与严格数值门禁
- **Schemas & Protocols**:
  - `schemas/compute-receipt.schema.json`
  - `schemas/evidence-receipt.schema.json`
  - `schemas/review-panel-spec.schema.json`
  - `schemas/review-finding.schema.json`
  - `schemas/review-result.schema.json`
  - `schemas/review-run-receipt.schema.json`
  - `schemas/lineage-receipt.schema.json` (Research Object Provenance Kernel v1, JSON Schema 2020-12)
  - `schemas/claim-evidence-graph.schema.json` (Claim-Evidence Graph v1, JSON Schema 2020-12)
  - `plugin.json` (Agent Plugins v1 portable manifest)
  - `mcp.json` / `scripts/mcp_server.py` (Portable MCP tools surface)
- **Verification Matrix**:
  - Unit & Regression Tests: 526 passed, 0 failures, 0 warnings (PR #10)
  - Static QA Fences: 39 independent executable blocks passed
  - Provenance & Lineage: 毫秒级因果拓扑逆向溯源、完整三阶段物理科研流水线、内容与回执指纹双重独立存证、防篡改哈希核验、因果 DAG 迭代无环检测与 JSON Schema 2020-12 严格匹配全量通过
  - Security & Contracts: Command adapter isolated env, strict participant slug validation, path containment guard, and JSON schema parity check passed
  - Scientific Integrity: MCP statistical recompute fixed, non-forgery Cohen's d enforced, literature-watch unobservable cites correctly surfaced
  - Agent Plugins v1 Loader: Live verified against 12 portable skills, MCP tools, and manifest with 0 diagnostics
  - CI Matrix Platforms: Linux x86_64 (Python 3.10-3.14), Linux ARM64 (Python 3.12), Ubuntu 26.04 preview canary (x86_64 & arm64, Python 3.12), macOS ARM64 & Intel (macos-15-intel, Python 3.12), Windows x86_64 & Windows ARM64 (Python 3.12)
