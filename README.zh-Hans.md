# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

本仓库为自主智能体科研工作流提供确定性的研究状态管理与学术工具集。系统通过统一的研究材料接入与解析服务和通用 MCP 协议接口，将研究对象身份归一与证据核验记录串联起来，同时整合学术论断与证据关联以及研究决策与失败记录。全仓包含 14 项学术技能，直接兼容 Claude Code 与 Cursor，并原生支持 Codex、Gemini CLI 与 Hermes Agent。验证范围与外部服务限制记录于[审计文档](docs/project-lineage-audit-20260920.md)。

作者为 Junfu Shi，笔名 SJF，GitHub 账号 xngg1021，联合 Hermes Agent 共同完成。当前授权范围适用 [Source Lineage License 1.0](LICENSE)。

## 快速开始

请先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，随后启动 2.1.0 版本服务：

```bash
uvx academic-research-kernel@2.1.0 mcp
```

[2.1.0 Release](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0)
页面记录了分发物哈希与发布状态。用户下载发布的 wheel 包后，也可直接本地执行
`uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp`。
本工具支持 Python 3.10–3.14，`uvx --python 3.12` 命令可显式指定受支持的解释器。
基础安装包已内置全部 12 个确定性工具与统计计算依赖。

## 验证安装

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

诊断命令默认离线运行，负责检查运行依赖、数据结构定义与全部 12 个工具声明；未配置可选外部服务不会导致安装验证失败。
`doctor --json` 命令可输出机器可读的诊断结果。

## 安装软件包

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

用户也可执行 `pipx install academic-research-kernel==2.1.0`，或启用受支持的虚拟环境运行
`python -m pip install academic-research-kernel==2.1.0`。
`[full]` 扩展项会安装科学计算示例所需的扩展库；`[research]` 扩展项会安装 `pypdf==6.19.0` 与 `fonttools==4.65.0`，为全新环境提供一致的 PDF 字体解码依赖，这两个软件包均支持 Python 3.10；`[qa]` 扩展项会安装仓库验证工具与上述解析依赖。结构化 HTML/XML 解析与受限 DOCX/XLSX 读取直接调用标准库，GPU 加速后端与付费外部服务均为可选项。

## Hermes

请先确认 Hermes 进程的环境变量 PATH 包含 uv，随后安装并显式启用插件：

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

插件兼容名称 `academic-skills` 保持不变，目前包含全部 14 项技能，涵盖新增的 `paper-research`。`mcp.json` 配置文件调用
`uv run --frozen --no-dev --no-editable` 与 Python 3.12，配合仓库 `uv.lock` 锁文件，
将独立运行环境部署至 `${PLUGIN_DATA}/runtime`。系统首次启动时会自动安装运行依赖，若本地缺少目标解释器或软件包则需要联网获取。
既有的纯技能 tap 安装方式依然可用，具体步骤见下方[安装与集成](#安装与集成)章节。

## 从源码运行

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

依赖分类与复现步骤，以及发布身份和外部发布条件，均详见[分发与发布说明](docs/distribution-release.md)。

## 许可证

包含本通知的代码快照依据 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 所述范围，对文内列明的受版权保护材料适用 **Source Lineage License 1.0**。首个 SLL 提交与目录树，以及随后的分界记录提交，分别记录于 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 与 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md)。自该记录节点起，所有保留本通知的快照均沿用相同的授权范围。

截至 `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` 的早期快照按 MIT 许可证分发，继续适用对应副本的原有条款。既有接收者保留完整的 MIT 授权权限，无需迁移至 SLL。仓库已完整保留[前项目 MIT 文本](LICENSES/MIT-pre-SLL.txt)，且 [tests/upstream/LICENSE](tests/upstream/LICENSE) 与配套的第三方来源记录均保持原状，新的根目录授权不会抹除既有权利。

SLL 许可证允许使用与研究，支持修改与商用，并涵盖分发及专有扩展，同时要求遵守对应的许可条款与通知要求及来源追溯条件。该许可证不属于 copyleft 协议，不强制要求公开源码。仅提供网络服务而不分发软件副本的行为，不会单独触发核心服务的来源通知条件。本许可证不包含明示专利授权，第三方材料继续遵循各自原有的许可条款。法律解释以英文原版 [LICENSE](LICENSE) 为准；`LicenseRef-Source-Lineage-1.0` 仅为本地标识引用，并非 SPDX 官方指配编号，也不代表已获 OSI 批准。[贡献接收](CONTRIBUTING.md)规则与下游许可权限相互独立。

## 技能

| 技能 | 版本 | 功能 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | 交叉核对文献身份与各数据源的被引次数，检查论文更新与撤稿信号，定位开放获取全文并校验 PDF 文件身份 |
| `skills/literature-analysis` | 1.3.0 | 提供十二项文献分析流程，覆盖主题相似度比对与局部文本查重，支持反证检索与作者档案梳理。该技能同时包含模拟审稿与谬误核查，提供文献对比表与选刊评估，并支持 BibTeX 导出与双语精读以及研究空白筛查与复现评估 |
| `skills/academic-writing` | 1.1.1 | 提供论文润色编辑与引用规范指南，兼容 ISO 690 国际标准及各地区机构规范，涵盖期刊投稿指引与可选检测服务，并支持投稿材料准备与高校盲审格式核查 |
| `skills/math-computation` | 1.2.1 | 提供多学科计算任务路由与修订版数值统计计算示例，附带四篇领域参考文档 |
| `skills/quantitative-paper-audit` | 1.1.0 | 独立重算论文报告的效应量与 p 值，核验置信区间、优势比与风险比及统计检验功效，自动检测数值不一致 |
| `skills/research-reproducibility` | 1.0.1 | 执行十四阶段复现核查流程，提供结构化核验清单与五级事实分类，生成可复现的核验记录 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | 管理 PRISMA 检索日志与文献筛选记录，执行效应量换算与异质性检验，支持固定效应与随机效应合并，并提供敏感性分析与发表偏倚诊断 |
| `skills/literature-watch` | 1.1.0 | 提供按周运行的文献监控方案，追踪 OpenAlex 与 Crossref 上的主题、作者及施引文献更新，自动去重并仅报告新增条目 |
| `skills/retraction-watch` | 1.1.0 | 提供按周运行的撤稿监控方案，比对 OpenAlex 的 `is_retracted` 字段与 Crossref 的 `update-to` 更新记录，复查 DOI 监控清单并仅报告状态变更 |
| `skills/research-object-identity` | 1.1.0 | 提供确定性科研资源标识与来源追溯，涵盖标识符归一与五态核验，支持内容寻址衍生图与因果有向无环图校验，并具备毫秒级离线逆向溯源能力 |
| `skills/claim-evidence-graph` | 1.0.0 | 构建确定性的学术论断与证据关联，直接连接科学论断与实证证据记录，支持事实核验与计算过程追溯 |
| `skills/decision-ledger` | 1.0.0 | 维护研究决策与失败记录，按时间顺序保存科研选择与失败尝试存证，记录放弃特定路线的原因及后续结果修正 |
| `skills/paper-research` | 1.0.0 | 读取 DOI、公开链接或本地论文及补充材料，验证候选字段并重算核对统计数字，持续保存研究状态，生成带原文定位的中文报告与双论文对比分析 |
| `skills/cross-review-five` | 2.0.0 | 编排多席位异构模型与子智能体交叉审议，兼容 Kimi K3 与 DeepSeek V4 Pro，支持 GLM 5.3、Claude 及 Gemini 等模型；内置四阶段稀疏审议流程，涵盖独立盲审与论断聚类合并，采用匈牙利算法分配全局最优互补匿名质询，并提供审议结果核对、待核实事项记录与 P0 至 P3 严重度分级 |

上述 14 项技能共包含 22 篇 Markdown 参考文档，由系统按需加载。

## 学术规范与多区域基线

学术引文、元数据与报告规范遵循目标期刊与资助机构的要求，同时适配所属学科与司法辖区的规则。本仓库以国际标准 **ISO 690:2021** 参考文献与引文指南、**ISO 5127:2017** 文献与信息概念词汇，以及 **W3C PROV** 溯源数据模型作为全球基线，同时支持中国大陆 GB/T 7714-2025、西班牙 UNE-ISO 690:2024 与德国 DIN ISO 690:2021 等地区规范，并兼容 APA 与 IEEE、PRISMA 2020 与 ICMJE 等学科标准。目标投稿机构的具体规定优先于系统默认规则，详细说明见[学术规范架构](docs/standards/README.md)与[自然学术术语指南](docs/terminology/README.md)。

系统严格校验 DOI 等外部标识符的一致性、定量核验结论的互斥状态标志，以及状态管理模块与核验记录共用的待核实事项规则。系统通过已保存的原始数据包与归一化哈希绑定独立重建缓存完整性，即便同时删除状态记录与核验声明也无法触发错误的缓存命中。相关验证细节见[四项阻塞收尾](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21)。

## 安装与集成

### 1. 便携式 Agent Plugins v1 与 MCP 工具服务
本仓库遵循厂商中立的 **Agent Plugins v1** 规范并提供 `plugin.json` 清单，同时通过标准输入输出协议运行 `mcp.json` 与 `scripts/mcp_server.py` 所定义的通用 **MCP 服务器**，原生兼容 Claude Code 与 Cursor、Gemini CLI 以及各类现代智能体宿主。仓库名称现已统一为 `academic-research-kernel`，便携插件标识符 `name: "academic-skills"` 与 MCP 工具配置别名继续保持长期向后兼容：

```bash
# 在您的智能体宿主中直接作为 stdio MCP 服务加载
uvx academic-research-kernel mcp
```

### 2. 在 Hermes 中安装
请于已安装 Hermes 的环境中运行这组命令：

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

用户安装其余技能时，只需替换完整标识符里的技能目录名。常规 tap 命令默认读取主分支，全新安装即可获得上述全部技能。若需于代码合并前测试工作分支，请先将目标分支检出至本地，再参照当前 Hermes 版本的本地目录安装说明完成配置，切勿假定 tap 命令会自动切换至拉取请求分支。

捆绑的关联技能已对照上游提交 `245e48008fa814b3251f50755eb656bd9fb86cb1` 完成核对，涵盖 `arxiv` 与 `grounded-citations`，以及 `docx`、`pdf` 和 `manim-video`。可选目录包含 `huggingface-hub` 与 `llama-cpp`，使用时可能需另行安装。该上游快照未包含 `ocr-and-documents` 与 `pc-hardware-benchmark`，这两项也不是本仓库的依赖项。会话检索工具、文档处理组件与浏览器后端均取决于本地环境配置。

## 数据源访问

- OpenAlex 基础查询支持匿名调用，每日匿名额度较小。2026-09-06 核对的官方文档规定匿名访问每日额度为 $0.10，免费 API 密钥每日额度为 $1，且每秒请求上限为 100 次；不同查询类型的计费权重各异，并非无限量访问。用户可将可选密钥存入 `OPENALEX_API_KEY`，并通过上限为 100 的 `per_page` 参数配合游标分页拉取数据。
- Crossref 提供带限流的公开元数据接口。程序解析更新关系与撤稿监控信号时必须同时核对 DOI 与关联方向，未检索到更新记录并不证明目标论文未受影响。
- Unpaywall 要求通过环境变量 `UNPAYWALL_EMAIL` 配置真实联系邮箱。接口未返回全文链接并不代表该论文不存在开放获取副本。
- arXiv 与 Europe PMC，以及 PubMed E-utilities 和 DOAJ 均属于补充数据源，各自适用独立的访问策略，默认测试套件不会全部调用。Semantic Scholar 的匿名共享限额与专属密钥配额实行分离管理，能够连通 API 并不保证一定能获取引文上下文。
- Scite 与 Dimensions，以及 Scopus、Web of Science 和各类 AI 检测服务均属于可选外部商业服务。用户调用前须自行核对当前账号权限、API 授权范围与剩余配额，本仓库不承诺通用免费额度或固定价格。

详细规则参见 [OpenAlex 认证](https://help.openalex.org/api/authentication/)、[预算与查询成本](https://help.openalex.org/api/llm-quick-reference/)及 [Crossref 更新过滤](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)。

## 确定性入库与内核公开界面

系统公开接口提供 `ResearchArtifactEnvelope v1` 与 `ArtifactIngestionReceipt v1` 数据结构，内置覆盖全部 14 项技能与 1 项未分类文本兜底的 15 个研究材料接入与解析适配器，并暴露 12 个无状态标准输入输出 MCP 工具。入库生成的核验记录会用类型、唯一标识与规范 SHA-256 哈希绑定每一次状态变更，涵盖研究对象与学术论断关联，以及研究决策记录、待核实事项与原始证据文件注册。缓存重放会独立于传输快照哈希之外校验这些哈希记录；空的决策记录同样合法，原子批次一旦执行失败不会残留半成品状态。

来源与生成过程的原文读取权限须通过外部调用参数显式授予。可信 Python 调用方重放序列化的核验记录或状态快照时可传入 `LineageVerificationContext`；MCP 协议调用方只能传入受限的文件内容字节流，不得指定宿主文件系统根目录。单次内容读取预算默认为 10 MiB；只要生产端与验证端采用一致的预算策略，可信宿主即可显式授权处理更大体积的研究材料。若调用时缺少原文读取权限，标记为 `fully_verified` 的核验声明将无法独立重现，系统会返回结构化的验证失败结果。未结构化的自由文本保持原样存储，评审分歧始终公开可见；状态提交与路线终止，以及路线重开、工具路由选择与最终学术判断均由研究者自主掌控。

数据结构规范与版本兼容规则详见[架构文档](docs/kernel-architecture.md)。软件包、`uvx` 运行入口与官方 MCP Registry 的发布状态记录于[发布说明](docs/distribution-release.md)。全部 21 个语种的 README 均已同步至 2.1.0 版本，全仓文档的多语言同步哈希记录于[多语言清单](docs/i18n/manifest.json)。候选版本身份与对应提交的 CI 记录，以及历次审议与合并存证，均汇总于[收尾记录](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342)。

## QA 与测试

测试与核验请使用独立的 Python 虚拟环境。具体运行依赖随任务类型变化，Hermes 宿主环境不保证默认预装；QA 环境会安装完整的测试依赖，以便执行全部带标记的代码示例：

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

QA 脚本负责校验技能元数据与参考文件路径，排查个人本地路径与已知密钥泄露模式，并检查 Python 语法及标记为可执行的代码块。每个 `smoke-test` 示例均会启动全新的独立子进程原样运行；绘图示例接收 `PLOT_DIR` 环境变量并显式展开默认路径 `~/plots`，自动化测试期间则会改用临时目录。QA 门禁会直接拒绝未标注分类的 Python 代码块；带 `fragment:` 标记的代码块仅接受语法检查，因依赖外部具名输入而不单独执行；带 `external-test:` 标记的代码块仅通过手动执行外部核验命令运行。已配置的检查项全部通过时，该外部核验命令返回状态码 0；遇到代码错误、数据结构不符或文献身份核验失败时返回 1；遇到网络传输故障、认证失败或配额耗尽时返回 2；未配置的可选外部服务则保持 `SKIP` 状态。

测试套件复用了固定版本的技能编写规范测试，并完整保留各技能原有的单项校验规则。上游 Hermes 完整发行包的全局目录检查不适用于本仓库；本仓库测试覆盖全部 14 项技能，并对照固定版本的捆绑目录与可选技能清单解析跨技能引用。这套检查不等同于完整的 Hermes 客户端安装测试。持续集成流水线仅在安装依赖包时访问网络，常规拉取请求测试不会调用外部学术 API。

持续集成流水线通过 GitHub Actions 覆盖三大操作系统的 x86_64 与 ARM64 架构。测试范围包含运行 Python 3.10 至 3.14 的 Linux x86_64 与 `ubuntu-24.04-arm` 镜像，涵盖 `ubuntu-26.04` 与 `ubuntu-26.04-arm` 预迁移环境，同时覆盖 Windows x86_64 与 `windows-11-arm`，以及 `macos-latest` 与 `macos-15-intel` 环境，并附带针对上游 `main` 分支最新代码的实时加载检验。本地完整回归测试套件通过 1165 项测试，详细验证结果与测试覆盖范围见[正确性修复记录](docs/maintenance/correctness-repair-20261008.md)，远端运行记录会单独标明被测提交哈希。同时，每当代码推送至 `main` 分支时，独立的 tap 集成工作流会自动安装 `tests/upstream/provenance.json` 所记录的固定版本 Hermes，并对本仓库依次执行 `tap add` 与 `search`，以及 `install` 和 `list` 验证。各项测试的确切版本、检查范围与已知限制详见[审计文档](docs/project-lineage-audit-20260920.md)。

[tools/longtail/](tools/longtail/README.md) 目录提供确定性长尾因子生成器，从 4096 个 SHA256 种子候选中筛选出 30 个测试场景，并输出机器计算的核验覆盖度报告。v3 模型分别统计 E01 能力族、对应仓库实际 14 项技能的 E02 技能项以及 E03 任务目标。每个测试场景仅绑定一项主测技能、一个受支持的任务目标与兼容的能力族；每项技能至少出现 2 次且覆盖 2 个不同任务目标，并必须包含该技能声明的核心目标。一旦实际技能目录与因子目录出现偏差，校验即会报错退出。包含任务链构建、验证判据设计及实际事件注入在内的语义展开仍属于独立阶段，因子层面的覆盖度并不代表完整工作流已完成执行验证。

`scripts/scfabric/` 目录提供科学计算与统计分析工具，内置硬件探针与带数据类型门禁的后端目录，包含五类工作负载画像与带数值等价校验的配对基准测试，并生成 `ComputeReceipt` 核验记录。本机首轮实测数据见 [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md)；系统默认采用 CPU 执行计算，仅在具备有效核验记录时才启用硬件加速器。

## 让本地 Agent 研究论文

请先安装 `academic-research-kernel[research]==2.1.0`，随后导出软件包随附的正式工作流：

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

请让 Work 或其他兼容的本地智能体读取导出的 `SKILL.md`，随后只需提供论文 DOI、公开链接或本地文件包，并发送指令：
“请研究这篇论文与补充材料，梳理实验方法并核对可重算的关键统计数字，生成一份带原文出处的中文报告。”
针对双论文对比任务可直接发送指令：“请比较这两篇论文的数据集与实验方法，核对评估条件与主要结果，并说明哪些结论可以直接横向对比。”
智能体会在同一任务内依次完成原文阅读与候选字段验证，执行统计重算与状态入库，并最终生成研究报告及独立原文复核结果。
既有的 MCP 服务端保持 12 个基础工具不变，新增的研究编排入口统一由命令行工具与便携技能包提供。

命令行工具的分步调用入口为：

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` 子命令负责获取并解析论文正文与补充材料，自动保存材料清单、文件哈希及原文段落定位信息。
`finish` 子命令负责校验智能体阅读原文后生成的结构化候选数据，调用内置统计函数重算符合条件的 t 检验与 p 值、两组效应量以及计数与百分比，
随后保存研究状态并导出中文 Markdown 与 HTML 报告。`compare` 子命令负责校验智能体针对两篇论文的数据集、实验条件与结果可比性生成的结构化结论。
命令行工具本身不内置驻留大模型，语义阅读完全由当前智能体参照 [paper-research](skills/paper-research/SKILL.md) 规范完成，无需额外配置模型账户。
已保存的原始文献与抽取快照支持确定性离线重放，最终报告会明确区分离线重放、联网获取与重新语义阅读。

## 2.0.1 正确性修复与分发验证

2.0.1 版本全面加固了统计重算与并发状态更新的正确性。公开的 `academic_recompute_statistics` 工具直接提供 t 检验 p 值以及两组样本的 Cohen's d 与 Hedges' g 效应量重算；置信区间与优势比及风险比计算继续作为内部 Python 函数提供。当分析任务需要严格保留原论文的报告精度时，调用方可传入字符串字面量 `p_value_literal` 如 `"1.0e-5"`，或显式指定小数位数 `p_value_decimals`。字符串字面量会完整保留末尾有效零，纯数值输入仅按本身的浮点数值解析；若同时传入相互冲突的精度参数，工具会明确报错返回。四舍五入一致性比对采用下界包含、上界排除的半开区间规则。常规的统计数值偏差属于正常的科学核查结果，仅在输入参数非法或计算过程异常中断时才会将 `isError` 设为真值。

撤稿状态核查会分别记录本轮观测到的 `True`、`False` 或 `unknown` 状态以及上一次确认的有效值。系统在发起外部查询前通过短锁分配版本号，确保同一 DOI 的观测结果按序登记，同时保留其余 DOI 的并发更新增量。本轮观测值与既往确认记录采用独立的版本序列：较晚返回的权威确认结果可以更新既往确认记录，同时不会掩盖较新一次查询因网络或接口受限而产生的本轮未知状态。回归测试任务链所使用的外部响应样例均已显式标明为测试数据。

MCP 服务端原生支持 `ping` 探活请求，收到 `notifications/cancelled` 等合法通知消息时保持静默不回包，并在遇到格式错误的输入后继续维持标准输入输出会话不中断。当前的同步服务端实现不声明支持抢占式任务取消。消息处理严格遵循 [MCP 消息规范](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages)
与 [ping 规范](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping)。

使用独立隔离环境构建并验证当前检出版本的分发软件包：

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` 选项会将候选源码分发包原样解包至仓库目录之外，显式设置 `ARK_REPO` 与
`ARK_SDIST` 环境变量，随后依次运行包内单元测试与静态 QA，并执行代码示例检查及多语言同步校验。
wheel 与 sdist 分发包各自使用全新的独立虚拟环境完成安装测试，`uvx` 验收则直接调用本地构建的 wheel 包并搭配独立缓存目录。
验收报告会完整记录分发包哈希值与实际导入路径。定时运行的轻量级 Hermes 兼容性检查会分别汇报固定基线版本与最新上游主分支的被测提交哈希；外部接口契约 JSON 报告与任务摘要明确区分 `healthy`、`degraded` 与 `failed` 三种状态，并将跳过的探测项单独列明。

## 研究与规划文档

下列两份文档属于探索性研究规划参考，并非强制性的开发路线图；文内的研究方向编号均依据 `docs/direction-primitive-mapping.json` 保存的分组关系重算得出。

- [问题图集 v0 英文版](docs/pain-atlas-v0.en.md)与[问题图集 v0 中文版](docs/pain-atlas-v0.zh.md)：按科研全生命周期梳理学术知识工作的常见阻碍，并为各项定量论断标注核实状态。
- [研究计划 v0 英文版](docs/research-plan-v0.en.md)与[研究计划 v0 中文版](docs/research-plan-v0.zh.md)：阐述研究对象模型与核心能力领域，并列出候选研究方向及阶段一因子分解表。
