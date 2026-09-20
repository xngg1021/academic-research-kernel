# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

跨宿主中立的面向自主 Agent 科研工作流确定性科研状态内核。仓库通过统一产物入库桥接与通用 Model Context Protocol (MCP) 服务，将研究对象身份归一、因果凭证（Receipts）、主张证据图谱（CEG）与追加式研究决策与失败记录深度连接。全仓 13 项学术技能作为科研状态的生产者与消费者，原生兼容 Claude Code、Cursor、Codex、Gemini CLI 与 Hermes Agent。验证范围与外部服务限制记录于[审计文档](docs/project-lineage-audit-20260920.md)。

作者：Junfu Shi（SJF，xngg1021），Hermes Agent。当前授权范围：[Source Lineage License 1.0](LICENSE)。

## 许可证

含本通知的快照依据 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 所述范围，对其中识别出的受版权保护材料采用 **Source Lineage License 1.0**。首个 SLL 提交与树、以及其后的边界记录提交，分别在 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 与 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) 中区分。自该记录边界起保留本通知的快照，携带相同的授权范围。

截至 `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` 的历史快照按 MIT 许可分发，受适用于那些副本的条款约束。接收者保留有效的 MIT 权限，无需迁移至 SLL。[前项目 MIT 文本](LICENSES/MIT-pre-SLL.txt)已保存；[tests/upstream/LICENSE](tests/upstream/LICENSE) 及其第三方来源记录保持原状。新的根授权不抹除既有权利。

SLL 广泛允许使用、研究、修改、商用、分发与专有增补，受相应许可、通知与来源谱系条件约束。它不属 copyleft，不要求源码披露。纯网络服务且不提供副本者，不单独触发核心服务谱系通知条件。无明示专利授予。第三方材料仍受其自身条款约束。以英文原版 [LICENSE](LICENSE) 为准；`LicenseRef-Source-Lineage-1.0` 为本地引用，非 SPDX 指配，亦不声称 OSI 批准。[贡献接收](CONTRIBUTING.md)与下游许可权限相互独立。

## 技能

| 技能 | 版本 | 功能 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | 交叉核对身份与来源特定的被引数；检查更新与撤稿信号；定位开放获取文本并核验 PDF 身份 |
| `skills/literature-analysis` | 1.3.0 | 十二个工作流：主题相似、局部文本重叠、反证、作者档案、模拟评审、谬误检查、评审矩阵、期刊候选、BibTeX、双语阅读、研究空白筛查、复现 |
| `skills/academic-writing` | 1.1.1 | 论文辅助编辑、引用规范指南（支持 ISO 690 国际基准与地区/机构规范）、期刊投稿指引、可选检测服务、投稿材料以及高校盲审要求 |
| `skills/math-computation` | 1.2.1 | 既有领域与任务路由及修正后的数值与统计示例；四篇领域参考文件 |
| `skills/quantitative-paper-audit` | 1.1.0 | 反算论文报告的统计量（效应量、p 值、置信区间、OR/RR、实现功效）并检测数值错配 |
| `skills/research-reproducibility` | 1.0.1 | 十四阶段复现审计流水线，含结构化核验清单、五层事实与可复现审计记录 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA 检索日志、文献筛选记录、效应量换算、异质性、固定与随机效应合并、敏感性与发表偏倚诊断 |
| `skills/literature-watch` | 1.1.0 | 周更蓝图：监控主题、作者与 DOI 在 OpenAlex 与 Crossref 的新作品；去重并只报告新增 |
| `skills/retraction-watch` | 1.1.0 | 周更蓝图：对照 OpenAlex is_retracted 与 Crossref 更新记录（update-to 信号）复查 DOI 监控清单；只报告状态变化 |
| `skills/research-object-identity` | 1.1.0 | 确定性科研资源标识与来源追溯：标识符归一、五态判定、内容寻址衍生图、因果 DAG 校验与毫秒级脱机逆向溯源 |
| `skills/claim-evidence-graph` | 1.0.0 | 确定性学术论断与证据关联：连接科学论断、实证证据记录、事实核验与计算过程追溯 |
| `skills/decision-ledger` | 1.0.0 | 研究决策与失败记录：记录科研选择、失败尝试存证、为什么放弃某路线与按时序追加结果修正 |
| `skills/cross-review-five` | 2.0.0 | 动态多席位异构模型/子代理交叉审议（Kimi K3、DeepSeek V4 Pro、GLM 5.3、Claude、Gemini 等）：v2 四阶段 Sparse Deliberation 流（盲审产出、断言级聚类合并、基于匈牙利算法的全局最优互补错排匿名质询、对账与未决保护账本，支持 P0-P3 严重级别） |

十三个技能共含 21 篇 Markdown 参考文件，按需加载。

## 学术规范与多区域基线

学术引文、元数据与报告规范遵循目标期刊、资助机构、学科与司法辖区规则。仓库确立 **ISO 690:2021**（参考文献与引文指南）、**ISO 5127:2017**（文献与信息概念词汇）与 **W3C PROV**（溯源数据模型）为全球基线，并支持中国大陆 GB/T 7714-2025、西班牙 UNE-ISO 690:2024、德国 DIN ISO 690:2021 等地区 Profile 与 APA、IEEE、PRISMA 2020、ICMJE 等学科规范。目标投稿机构的具体要求优先于默认规则。详见[学术规范架构](docs/standards/README.md)与[自然学术术语指南](docs/terminology/README.md)。

## 安装与集成

### 1. 便携式 Agent Plugins v1 与 MCP 工具服务
本仓库遵循厂商中立的 **Agent Plugins v1** 规范（`plugin.json`），并通过 stdio 协议暴露通用的 **MCP 服务器**（`mcp.json` / `scripts/mcp_server.py`），原生兼容 Claude Code、Cursor、Gemini CLI 与任意现代智能体宿主（注：仓库身份已迁移为 `academic-research-kernel`，便携包标识符 `name: "academic-skills"` 与 MCP 工具配置别名保持长期稳定向后兼容）：

```bash
# 在您的智能体宿主中直接作为 stdio MCP 服务加载
python scripts/mcp_server.py
```

### 2. 在 Hermes 中安装
在 Hermes 安装环境中执行：

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

安装其余技能时替换完整标识符中的目录名。常规 tap 读取默认分支，新装即得上述技能集。如需在合并前检查工作分支，在本地检出该分支并遵循所装 Hermes 版本的本地目录安装说明。不要假定 tap 命令会选中 PR 分支。

捆绑相关技能以上游 `245e48008fa814b3251f50755eb656bd9fb86cb1` 为准核对：arxiv、grounded-citations、docx、pdf、manim-video。huggingface-hub 与 llama-cpp 在可选目录中，可能需另行安装。ocr-and-documents 与 pc-hardware-benchmark 在该快照中未找到，亦非依赖项。会话工具与文档及浏览器后端取决于本地配置。

## 数据源访问

- OpenAlex 基础查询可匿名执行，但每日预算较小。2026-09-06 核对的文档列出匿名每日 $0.10、免费 API key 每日 $1，以及每秒 100 请求上限；各查询类型成本不同，并非无限访问。可选密钥存于 `OPENALEX_API_KEY`，使用 `per_page`（最大 100）与游标分页。
- Crossref 提供受限流的公开元数据。更新关系及 Retraction Watch 信号须核对 DOI 与方向；没有记录不等于论文未受影响。
- Unpaywall 要求在 `UNPAYWALL_EMAIL` 配置真实联系邮箱。未返回位置不等于不存在开放获取副本。
- arXiv、Europe PMC、PubMed E-utilities 与 DOAJ 为补充来源，各自有访问政策；默认测试未全部覆盖。Semantic Scholar 的匿名共享限额与密钥额度分别管理；可访问 API 不保证可取得引文上下文。
- Scite、Dimensions、Scopus、Web of Science 与 AI 检测产品为可选外部服务。使用前须核对当前账号权限、API 权利和配额，不承诺通用免费层或固定价格。

参见 [OpenAlex 认证](https://help.openalex.org/api/authentication/)、[预算与查询成本](https://help.openalex.org/api/llm-quick-reference/)及 [Crossref 更新过滤](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)。

## 确定性入库与内核公开界面

PR #12 提供 `ResearchArtifactEnvelope v1`、`ArtifactIngestionReceipt v1`、14 个适配器（13 项技能加 opaque fallback）与 12 个无状态 stdio MCP 工具。接受入库的凭证以类型、身份和规范 SHA-256 绑定每项保留的语义变异：对象、CEG 记录、Ledger 记录、不确定项、物理凭证与产物注册。缓存重放独立于传输快照摘要核验这些承诺。空 Ledger 合法；失败的原子批次不留下部分状态。

谱系内容读取权限通过带外方式显式授予。可信 Python 调用方重放序列化凭证或快照时传入 `LineageVerificationContext`；MCP 调用方只能提供受限内容字节，不能指定宿主文件系统根目录。默认内容预算为 10 MiB；可信宿主可在生产者与验证者采用同一策略的前提下显式授权更大产物。缺少内容权限时，`fully_verified` 声明无法独立重现，返回结构化无效验证结果。非结构化文本保持不透明，异议保留可见；提交、剪枝、重开、路由选择与真值判断由研究者掌控。

契约与兼容规则见[架构文档](docs/kernel-architecture.md)。PyPI、`uvx`、控制台打包与官方 MCP Registry 发布仍属 PR #13。英文及简体中文 README 已同步；其他译文状态由[清单](docs/i18n/manifest.json)如实记录。最终候选身份、精确 HEAD CI、累计评审与合并证据统一记录于[收尾账本](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5750357151)。

## QA 与测试

请使用独立 Python 环境。运行依赖因任务而异，并非 Hermes 保证预装；QA 安装更广泛的依赖，以执行全部标记示例：

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA 校验元数据、参考文件、个人路径与已知密钥模式、Python 语法与标记为可执行的代码块。每个 smoke 示例在全新子进程中原样运行；绘图示例接受 `PLOT_DIR`（默认 `~/plots`，显式展开），测试使用临时目录。未分类的 Python 代码块被拒绝；`fragment:` 块做语法检查但需显式输入，不单独执行。`external-test:` 块仅经手动外部命令运行。该外部命令在配置检查通过时返回 0，代码、schema 或身份失败返回 1，传输、认证或配额不可用返回 2；未配置的可选服务保持 SKIP。

固定版本的技能编写规范测试（authoring tests）被复用，其逐技能规则不改动。完整 Hermes 上游发行包的全局测试不适用于本 tap；本仓库测试覆盖全部十三个技能，并按固定的捆绑与可选目录解析参考文件。这不是完整的 Hermes 安装测试。CI 仅在安装依赖时使用网络；常规 PR 测试不调用学术 API。

CI 经 GitHub Actions 覆盖 Linux x86_64（Python 3.10-3.14）、Linux ARM64（ubuntu-24.04-arm）、Ubuntu 26.04 预迁移 Canary（ubuntu-26.04 与 ubuntu-26.04-arm）、Windows x86_64、Windows ARM64（windows-11-arm）、macOS ARM64（macos-latest）与 macOS Intel（macos-15-intel）全平台全架构，并附带针对上游 main 最新分支的实时 Canary 加载检验。最终候选本地测试为 873 passed、零跳过；精确 HEAD 的远端结果单独记录于收尾账本。另有一个 tap 集成工作流在 main 推送时运行：安装 tests/upstream/provenance.json 所记录的固定 Hermes 检出，并针对本仓库执行 tap add、search、install 与 list。确切版本、检查项与限制见[审计文档](docs/project-lineage-audit-20260920.md)。

tools/longtail/ 存放确定性极端长尾场景生成器：4096 个 SHA256 种子候选组合铺满解耦因子轴，贪心覆盖选择，generated-scenarios.json 内附机器计算的覆盖报告。它是压测技能的输入层；语义展开（任务链、判据、注入事件）是独立阶段。

scripts/scfabric/ 是科学计算执行层：硬件探针、带 dtype 门禁的后端目录、五个工作负载画像、带数值等价检查的配对基准与 ComputeReceipt。本机首轮实测见 [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md)；经验规则是默认 CPU，加速器只凭 receipt 启用。

## 研究与规划文档

这两份文档是探索性规划参考，不是强制路线图。其中的方向数字按 docs/direction-primitive-mapping.json 的入库归组重算。

- [痛点图集 v0（英文）](docs/pain-atlas-v0.en.md)与[中文版](docs/pain-atlas-v0.zh.md)：按生命周期枚举学术知识工作摩擦，定量论断标注核实状态。
- [研究计划 v0（英文）](docs/research-plan-v0.en.md)与[中文版](docs/research-plan-v0.zh.md)：Research Object 模型、核心能力领域、候选研究方向与阶段一因子分解矩阵。
