# 变更日志与版本发布清单 (CHANGELOG & Release Manifest)

本文件记录 `academic-research-kernel` 仓库各版本的接口变更与迁移规范，列明输入输出形态变化以及发布身份清单。

---

## 2026-09-18（HEAD / work/claim-evidence-graph-v1）

### 科学论断-证据图内核 (Claim-Evidence Graph v1)
- **核心数据契约 (`schemas/claim-evidence-graph.schema.json`)**：
  - JSON Schema 2020-12 严格规范，全量开启 `additionalProperties: false`；
  - 规范定义 `Claim`、`EvidenceAnchor`、`EvidenceSupportEdge`、`ClaimRelationEdge`、`UncertaintyItem` 与 `ReceiptRef`；
  - 强类型 `ReceiptRef` 正式解耦并无歧义绑定 `LineageReceipt`（通过 `receipt_id`/`receipt_digest`）与 `AcademicEvidenceReceipt`（通过 `claim_digest`/`payload_sha256`）。
- **确定性图内核 (`skills/claim-evidence-graph`)**：
  - 确立生产谱系（DAG）与学术命题关系（允许自然成环，如双向互斥反驳）的分立纪律；
  - 严禁任何形式的真理裁判所与主观置信度打分（如 0.85），裁决一律离散化，争议显式进入不确定性账本（`UncertaintyQueue`）；
  - `claim_digest` 严格绑定规范化命题文本（仅做 NFC 与空白压缩，绝不重写语义）、定位符与所属论文；
  - 纯 Python 离线实现矛盾发现器（`find_contradictions`）与全链执行谱系回溯穿透（`trace_claim_provenance`）。
- **验证矩阵更新**：
  - 全仓单测规模扩充至 **515 项全绿**（0 failures, 0 warnings）；
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

- **Repository**: `xngg1021/hermes-academic-skills`
- **Protocol**: `compute-receipt-1.0` / `evidence-receipt-1.0`
- **Skills & Components**:
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
  - Unit & Regression Tests: 515 passed, 0 failures, 0 warnings
  - Static QA Fences: 39 independent executable blocks passed
  - Provenance & Lineage: 毫秒级因果拓扑逆向溯源、完整三阶段物理科研流水线、内容与回执指纹双重独立存证、防篡改哈希核验、因果 DAG 迭代无环检测与 JSON Schema 2020-12 严格匹配全量通过
  - Security & Contracts: Command adapter isolated env, strict participant slug validation, path containment guard, and JSON schema parity check passed
  - Scientific Integrity: MCP statistical recompute fixed, non-forgery Cohen's d enforced, literature-watch unobservable cites correctly surfaced
  - Agent Plugins v1 Loader: Live verified against 11 portable skills, MCP tools, and manifest with 0 diagnostics
  - CI Matrix Platforms: Linux x86_64 (Python 3.10-3.14), Linux ARM64 (Python 3.12), macOS ARM64 & Intel (macos-15-intel, Python 3.12), Windows x86_64 & Windows ARM64 (Python 3.12)
