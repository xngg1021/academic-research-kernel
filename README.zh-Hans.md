# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

这是一套给科研人员和 AI 助手使用的学术核查与文献研究工具包。平时用大模型读论文或写综述，最怕模型编造参考文献与算错统计数字，或者读完几十篇文献后找不到某句结论出自哪一页。为了解决这些问题，本仓库把 14 项常用科研工作流与 12 个确定性核查工具封装成标准 MCP 服务和命令行工具，用来核对文献真伪与撤稿状态，重算论文里的统计结果，精读论文并生成带原文页码的中文报告，管理文献综述筛选记录，以及把每一条研究结论和背后的证据及失败尝试对应保存下来。所有工具均可在 Claude Code 与 Cursor 中直接调用，也原生支持 Codex、Gemini CLI 与 Hermes Agent。详细的验证范围与外部接口限制见[审计文档](docs/project-lineage-audit-20260920.md)。

作者为 Junfu Shi，笔名 SJF，GitHub 账号 xngg1021，联合 Hermes Agent 共同完成。当前授权范围适用 [Source Lineage License 1.0](LICENSE)。

## 快速开始

如果您想直接让 AI 助手帮您读论文、核对统计数字并生成中文报告，请先安装带 PDF 解析功能的软件包并把 `paper-research` 技能导出给您的助手；如果您需要将 12 个核查工具挂载为后台 MCP 服务供客户端自动调用，请先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/) 再启动 2.1.0 版本的 MCP 服务：

```bash
# 方式一：让 AI 助手直接读 PDF 论文并生成中文报告
uv tool install "academic-research-kernel[research]==2.1.0"
academic-research-kernel research skill --output ./paper-research

# 方式二：作为后台 MCP 服务启动，供客户端连接调用
uvx academic-research-kernel@2.1.0 mcp
```

直接在终端运行 `mcp` 命令会让程序进入后台静默等待客户端连接的状态，不会弹出交互菜单。[2.1.0 Release](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0) 页面记录了安装包哈希值与发布状态。如果您已将发布的 wheel 安装包下载到本地，也可以直接运行 `uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp`。本工具支持 Python 3.10–3.14，`uvx --python 3.12` 命令可显式指定受支持的 Python 解释器。基础安装包已内置全部 12 个核查工具，统计计算库会在调用统计重算功能时按需加载。

## 验证安装

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

`doctor` 自检命令默认离线运行，负责检查运行环境依赖、数据格式定义与全部 12 个工具接口；即使没有配置可选的外部数据库密钥，自检也不会报错。运行 `doctor --json` 可输出供程序读取的 JSON 结果。

## 安装软件包

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

您也可以使用 `pipx install academic-research-kernel==2.1.0` 安装，或者在虚拟环境内运行 `python -m pip install academic-research-kernel==2.1.0`。安装时加上 `[full]` 会一并安装扩展科学计算示例所需的库；加上 `[research]` 会安装 `pypdf==6.19.0` 与 `fonttools==4.65.0`，保证不同机器解析 PDF 字体时结果一致，这两个库均支持 Python 3.10；加上 `[qa]` 则会安装仓库自检与测试所需的解析依赖。结构化 HTML/XML 解析和常规 DOCX/XLSX 读取直接使用 Python 标准库，GPU 加速与付费数据库均为可选项。

## Hermes

请先确认 Hermes 进程的环境变量 `PATH` 中包含 `uv`，再安装并启用插件：

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

为了保持旧配置兼容，插件名称仍为 `academic-skills`，内部已包含新增 `paper-research` 在内的全部 14 项技能。`mcp.json` 会调用 `uv run --frozen --no-dev --no-editable` 与 Python 3.12，并按照仓库的 `uv.lock` 锁文件把独立运行环境安装到 `${PLUGIN_DATA}/runtime` 目录。首次启动时系统会自动下载缺失的依赖包，不会改动 Hermes 本身或系统的 Python 环境。如果您只想安装纯技能文档而不启用插件服务，请参考下方[安装与集成](#安装与集成)章节。

## 从源码运行

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

各类依赖的用途划分、本地复现步骤与发布校验清单，详见[分发与发布说明](docs/distribution-release.md)。

## 许可证

包含本声明的代码版本按照 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 界定的范围，对受版权保护的项目材料适用 **Source Lineage License 1.0**。首次切换到 SLL 的提交与后续记录分界的提交，分别登记在 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 与 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) 中。自该节点起保留本声明的后续版本，均沿用相同的授权范围。

截至提交 `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` 的早期版本按 MIT 许可证发布，继续适用当时的许可条款。早期版本的获取者保留完整的 MIT 授权，不需要迁移到 SLL。仓库完整保留了[原项目 MIT 许可文本](LICENSES/MIT-pre-SLL.txt)，且 [tests/upstream/LICENSE](tests/upstream/LICENSE) 与第三方代码来源说明均未改动，新的许可证不会取消早期版本的既有授权。

SLL 许可证允许自由使用与研究，支持修改代码与商业应用，也允许重新分发和闭源扩展，前提是保留规定的许可声明与来源追溯信息。该许可证不是传染性的 copyleft 协议，不要求使用者公开自己的源码。单纯通过网络提供服务而不分发软件副本，不会触发核心服务的来源署名要求。本许可证不包含明示专利授权，第三方材料继续适用各自原有的许可证。具体条款以英文原版 [LICENSE](LICENSE) 为准；`LicenseRef-Source-Lineage-1.0` 只是本地标识名，并非 SPDX 官方编号，也不代表已通过 OSI 认证。[外部贡献规则](CONTRIBUTING.md)与下游使用者的许可权限相互独立。

## 技能一览

| 技能 | 版本 | 能帮您做什么 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | 交叉核对论文真伪与各数据库的被引次数，排查更正或撤稿记录，查找开放获取全文，并核对本地 PDF 是否真是目标论文 |
| `skills/literature-analysis` | 1.3.0 | 提供十二项日常文献分析流程，可以查找相似论文与比对段落重复，检索反面证据与梳理作者学术背景。该技能同时支持模拟审稿与检查论证漏洞，生成文献对比表与推荐投稿期刊，并支持导出 BibTeX、双语对照阅读以及筛查研究空白与评估复现条件 |
| `skills/academic-writing` | 1.1.1 | 辅助润色学术文稿并核对引用格式，支持 ISO 690 国际标准与各国高校期刊规范，提供投稿指南查询与可选检测服务，并协助准备投稿材料与盲审匿名检查 |
| `skills/math-computation` | 1.2.1 | 把符号推导、数值计算与统计检验任务分发给可靠的 Python 计算工具，附带四篇分学科参考指南 |
| `skills/quantitative-paper-audit` | 1.1.0 | 根据论文正文给出的均值、标准差和样本量，独立重算效应量、p 值、置信区间与优势比及统计检验力，帮您揪出论文里的算术错误或统计矛盾 |
| `skills/research-reproducibility` | 1.0.1 | 按照十四步核查清单，逐项检查一篇论文的代码与数据、依赖版本与关键指标能不能真正跑通复现 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | 记录 PRISMA 文献检索与筛选过程，换算不同研究的效应量，执行异质性检验与固定或随机效应合并，并做敏感性分析与发表偏倚诊断 |
| `skills/literature-watch` | 1.1.0 | 按周自动查询 OpenAlex 与 Crossref，监控指定主题、作者或某篇 DOI 的最新施引文献，自动去重后只汇报新发表的论文 |
| `skills/retraction-watch` | 1.1.0 | 按周复查关注清单里的论文 DOI，比对 OpenAlex 的 `is_retracted` 标记与 Crossref 的 `update-to` 更正记录，只在论文发生撤稿或更正时发出提醒 |
| `skills/research-object-identity` | 1.1.0 | 把杂乱的 DOI、arXiv 编号与本地文件哈希整理成统一的身份记录，核实资源有效状态，并看清每份分析结果是由哪些原始材料一步步生成的 |
| `skills/claim-evidence-graph` | 1.0.0 | 把文章里的每一条学术论断和背后的原文段落、数据表或计算记录直接关联起来，方便随时核对某句结论有没有证据支撑 |
| `skills/decision-ledger` | 1.0.0 | 按时间顺序维护研究决策与失败记录，把做过的方法选择与走不通的失败尝试记下来，同时保存放弃某条路线的原因及后来的结果修正，避免重复踩坑 |
| `skills/paper-research` | 1.0.0 | 输入 DOI、网页链接或本地论文及补充材料，验证提取出的关键字段并重算核对统计数字，持续保存研究记录，生成带原文页码出处的中文报告或两篇论文的横向对比 |
| `skills/cross-review-five` | 2.0.0 | 组织多个不同大模型或子智能体对同一份文稿或代码独立盲审，自动合并重复意见并安排交叉质询，按 P0 至 P3 标注问题严重程度，同时把未达成共识的分歧单独保留下来 |

上述 14 项技能共配有 22 篇 Markdown 参考指南，只在执行对应任务时按需读取。

## 学术规范与各国引用标准

参考文献格式、统计报告要求与元数据规范因目标期刊与资助机构而异，同时取决于所属学科与所在地区。本仓库以国际标准 **ISO 690:2021** 参考文献与引文指南、**ISO 5127:2017** 文献与信息词汇，以及 **W3C PROV** 来源追溯模型作为通用基线，同时内置中国大陆 GB/T 7714-2025、西班牙 UNE-ISO 690:2024 与德国 DIN ISO 690:2021 等地区规范，并支持 APA 与 IEEE，以及 PRISMA 2020 和 ICMJE 等学科标准。实际写作时，目标投稿期刊或学校的具体规定始终优先于默认规则，详见[学术规范架构](docs/standards/README.md)与[自然学术术语指南](docs/terminology/README.md)。

系统保存研究状态时会自动检查 DOI 等文献编号前后是否一致，防止同一项统计核查同时出现互相矛盾的判定结果，并把尚待人工确认的疑点统一收进待核实清单。缓存校验会直接根据保存下来的原始材料与哈希记录重新核对完整性，哪怕同时删掉状态记录和核验声明，重放时也会报错拦下而不会误判通过。具体修复细节见[四项阻塞收尾说明](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21)。

## 安装与集成

### 1. 通用 Agent Plugins v1 与 MCP 服务
本仓库遵循通用的 **Agent Plugins v1** 规范并提供 `plugin.json`，同时通过标准输入输出协议运行 `mcp.json` 与 `scripts/mcp_server.py` 定义的 **MCP 服务器**，可直接在 Claude Code 与 Cursor、Gemini CLI 以及各类支持 MCP 的智能体客户端中使用。虽然仓库现已改名为 `academic-research-kernel`，但插件名 `name: "academic-skills"` 与原有的 MCP 配置别名均保持不变，旧配置无需修改即可继续使用：

```bash
# 在您的智能体客户端中直接作为 stdio MCP 服务启动
uvx academic-research-kernel mcp
```

### 2. 在 Hermes 中按需安装单项技能
如果您在 Hermes 环境中只想安装某几项技能文档，可以直接添加技能源：

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

安装其他技能时，只需替换命令末尾的技能目录名。常规 `tap` 命令默认读取主分支，新安装即可获取上述全部 14 项技能。如果您想在代码合并前测试某个开发分支，请先把该分支检出到本地文件夹，再按本地目录方式安装，不要指望 `tap` 命令会自动拉取未合并的分支。

配套关联技能已对照上游提交 `245e48008fa814b3251f50755eb656bd9fb86cb1` 核对完毕，包含 `arxiv` 与 `grounded-citations`，以及 `docx`、`pdf` 和 `manim-video`。可选技能目录包含 `huggingface-hub` 与 `llama-cpp`，需要时可单独安装。该上游版本不包含 `ocr-and-documents` 与 `pc-hardware-benchmark`，本仓库也不依赖这两项。

## 学术数据源与接口限额

- OpenAlex 基础首屏查询支持匿名使用，但匿名每日额度较小。按照官方文档现行标准，无密钥每秒最多发送 10 次请求，配置免费或预付费密钥后每秒最多 30 次请求，年度订阅方案每秒最多 50 次请求；匿名访问每日额度为 $0.10，申请免费 API 密钥后每日额度为 $1。匿名请求只能获取第一页游标结果，翻页继续读取 `next_cursor` 需要将免费密钥存入环境变量 `OPENALEX_API_KEY`，未配密钥时翻页会在保留首屏结果后自动截断。
- Crossref 提供带限流的公开元数据接口。核查论文更正与撤稿信号时必须同时核对 DOI 与更新方向；接口没查到记录不代表论文一定没有问题。
- Unpaywall 要求在环境变量 `UNPAYWALL_EMAIL` 中填入真实联系邮箱。如果接口没有返回全文地址，不代表网上不存在其他开放获取版本。
- arXiv 与 Europe PMC，以及 PubMed E-utilities 和 DOAJ 属于补充数据源，各自有独立的限流规则，默认自动化测试不会逐一请求。Semantic Scholar 的匿名公共额度与专属密钥额度分开计算，能连上接口也不保证每篇论文都开放了引文上下文。
- Scite 与 Dimensions，以及 Scopus、Web of Science 和商业 AI 检测工具属于可选的外部付费服务。调用前请先确认您自己的账号权限与剩余配额，本仓库不提供通用免费额度。

详细接口说明见 [OpenAlex 认证指南](https://help.openalex.org/api/authentication/)、[额度与查询计费说明](https://help.openalex.org/api/llm-quick-reference/)及 [Crossref 更新过滤文档](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)。

## 研究记录保存与权限范围

系统的数据接入层采用 `ResearchArtifactEnvelope v1` 与 `ArtifactIngestionReceipt v1` 格式，内置 15 个解析器，涵盖全部 14 项学术技能外加 1 个普通文本兜底解析器，并对外提供 12 个无状态的 stdio MCP 工具。每当系统保存研究对象与学术论断关联，或者写入研究决策记录、待核实事项与证据文件时，核验记录都会记下对应的类型、唯一编号与 SHA-256 哈希值。离线重放时会直接核对这些哈希值；新建的空决策记录同样有效，而一旦某次批量写入中途出错，系统会自动回滚，不会留下半截损坏的数据。

如果某条核验记录要标记为 `fully_verified` 已完全核实，调用方必须提供对应的原始文件内容，以便系统独立复核。Python 本地调用可通过 `LineageVerificationContext` 传入原文，MCP 协议调用则只允许直接传入文件内容字节流，不允许读取宿主机任意文件路径。单次读取的文件大小默认上限为 10 MiB，受信任的本地宿主环境可以按需调高上限。如果没有提供原文内容，系统不会把结果标为已完全核实。未经提取的自由文本保持原样存储，不同审稿模型的分歧意见全部公开保留；何时保存记录与放弃哪条路线，以及重开哪项尝试与最终采纳哪条学术结论，始终由研究者自己决定。

数据格式与版本兼容规则见[架构文档](docs/kernel-architecture.md)，Python 软件包、`uvx` 与官方 MCP Registry 的发布细节见[分发与发布说明](docs/distribution-release.md)。全部 21 个语种的 README 均已更新至 2.1.0 版本，全仓文档的多语言哈希同步状态记录于[多语言清单](docs/i18n/manifest.json)，早期的完整评审与合并存证汇总于[收尾记录](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342)。

## 本地自检与测试

运行测试请使用独立的 Python 虚拟环境。不同科研任务用到的计算库各不相同，Hermes 默认环境不一定全部预装；安装 `requirements-qa.txt` 可以配齐全部测试依赖，用来跑通所有带标记的代码示例：

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

`scripts/qa.py` 会自动检查技能头部信息与参考文件路径，扫描是否误留了个人电脑路径或密钥字符串，并验证 Python 语法与可执行代码示例。每个标有 `smoke-test: true` 的代码块都会在全新的子进程里原样跑一遍；画图示例通过 `PLOT_DIR` 读取保存目录，默认展开为 `~/plots`，跑自动化测试时则会写入临时文件夹。未注明类别的 Python 代码块会被直接拦下；标有 `fragment:` 的代码片段只检查语法而不单独运行；标有 `external-test:` 的代码块只有手动运行 `scripts/verify_external_apis.py` 时才会联网执行。所有配置项检查通过时该命令返回 0，代码、格式或文献核对出错返回 1，网络不通、密钥失效或配额用尽返回 2，未配置的可选外部服务则显示 `SKIP`。

测试套件沿用了固定版本的 Hermes 技能编写规范检查，完整测试本仓库的全部 14 项技能，并对照固定版本的内置与可选技能目录核对引用关系。持续集成环境只在安装依赖包时联网，平时的代码提交测试不会请求外部学术数据库。

GitHub Actions 持续集成覆盖三大操作系统的 x86_64 与 ARM64 架构。测试范围包含运行 Python 3.10 至 3.14 的 Linux x86_64 与 `ubuntu-24.04-arm` 镜像，涵盖 `ubuntu-26.04` 与 `ubuntu-26.04-arm` 预迁移环境，同时覆盖 Windows x86_64 与 `windows-11-arm`，以及 `macos-latest` 与 `macos-15-intel` 环境，并附带针对上游 `main` 分支最新代码的实时加载检验。本地完整回归测试套件共通过 1315 项测试，此前 1165 项基线与覆盖范围记录在[正确性修复记录](docs/maintenance/correctness-repair-20261008.md)中，远端测试日志会单独标明所测的代码提交哈希。每当代码推送到 `main` 分支时，独立的集成测试工作流还会自动安装 `tests/upstream/provenance.json` 记录的固定版本 Hermes，实测对本仓库执行 `tap add` 与 `search`，以及 `install` 和 `list` 全流程。各项检查的确切版本与限制见[审计文档](docs/project-lineage-audit-20260920.md)。

[tools/longtail/](tools/longtail/README.md) 目录存放确定性长尾测试场景生成器，从 4096 个 SHA256 种子候选中选出 30 个代表性测试场景，并自动生成核验覆盖度报告，分别统计 16 类能力族、仓库实际的 14 项技能以及 36 项具体任务目标。每项技能至少出现 2 次并覆盖 2 个不同任务目标，且必须包含该技能的核心目标。

`scripts/scfabric/` 目录提供科学计算与统计分析基准测试工具，包含硬件检测与数值精度门禁，并提供五类计算负载测试及 `ComputeReceipt` 核验记录。首轮实测数据见 [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md)；计算任务默认使用 CPU，只有在基准测试核验通过并生成记录后才会启用硬件加速。

## 让本地 Agent 帮您读论文写报告

安装带 `[research]` 扩展的 2.1.0 软件包后，可以把论文精读技能直接导出到您的本地智能体目录：

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

让 Work 或其他本地智能体读取导出的 `SKILL.md`，然后只需把论文 DOI、公开网页链接或本地文件夹发给智能体，直接说：
“请研究这篇论文与补充材料，整理实验方法并核对能重算的关键数字，给我一份带出处的中文报告。”
如果要对比两篇论文，可以直接说：“请比较这两篇论文的数据与实验方法，核对评估条件与主要结果，并说明哪些结论可以直接比较。”智能体会在同一个任务里读完原文与附件并提取关键数字，随后调用统计工具重算核对、保存研究状态，并生成带原文页码与段落定位的中文报告。原有的 12 个 MCP 工具保持不变，这套新流程通过命令行与导出的技能文件配合完成。

命令行工具分三步执行：

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` 负责下载或读取论文正文与补充材料，记录文件哈希并按页码和章节建立原文段落索引。`finish` 负责检查智能体读完原文后提取出的结构化数据，调用统计函数重算符合条件的 t 检验与 p 值、两组效应量以及计数和百分比，保存核验后的研究状态并导出中文 Markdown 与 HTML 报告。`compare` 负责核验智能体对两篇论文的数据、实验条件和结果可比性作出的对比结论。由于正文阅读直接由您当前使用的智能体按照 [paper-research](skills/paper-research/SKILL.md) 完成，命令行工具本身不需要额外配置大模型账号。保存下来的原始文献与提取快照随时可以离线重放，生成的报告也会明确标出哪些结论来自离线重放、联网获取或重新阅读。

## 统计重算精度与软件包验证

公开的 `academic_recompute_statistics` 工具支持重算 t 检验的 p 值以及两组样本的 Cohen's d 与 Hedges' g 效应量，置信区间、优势比与风险比计算则可调用内部 Python 函数。如果核对论文时需要保留小数点末尾的零，可以传入字符串参数 `p_value_literal` 如 `"1.0e-5"`，或者用 `p_value_decimals` 指定小数位数。字符串参数会保留末尾有效零，普通数字只按浮点数值本身处理；如果同时传入了互相冲突的精度设置，工具会直接报错提醒。四舍五入核对采用下界包含、上界排除的规则。重算后发现原论文数字与重算值不一致属于正常的科学核查结果，只有输入参数不合法或计算过程出错时才会将 `isError` 设为真值。

撤稿状态核查会把本次联网查到的 `True`、`False` 或 `unknown` 结果与上一次确认过的有效状态分开保存。系统在发起查询前通过简短锁机制按顺序记录同一篇 DOI 的观测结果，同时保留其他文献的并发更新。如果最新一次查询因为网络波动或接口限流暂时返回 `unknown`，系统会如实标出本次检查尚未核实，但不会冲掉之前已经确认过的既有记录。回归测试里用到的外部响应均已标明为本地测试样本。

MCP 服务端支持 `ping` 连通性检查，收到 `notifications/cancelled` 等合法通知时按协议保持静默，遇到格式错误的输入也不会中断当前标准输入输出连接。消息处理遵循 [MCP 消息规范](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages)与 [ping 规范](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping)。

如需使用隔离环境构建并验证当前版本的安装包，可执行：

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` 参数会把构建出的源码包解包到仓库目录之外的临时文件夹，设置 `ARK_REPO` 与 `ARK_SDIST` 环境变量，并对解包后的文件依次运行单元测试与静态自检，同时执行代码示例检查与多语言同步校验。wheel 包与源码包各自在全新的虚拟环境中测试安装，`uvx` 则使用本地 wheel 包配合独立缓存目录完成验证。定时运行的轻量级 Hermes 兼容性检查会分别汇报固定基线版本与最新上游主分支的被测提交哈希；外部接口检查报告与任务摘要明确区分 `healthy`、`degraded` 与 `failed` 三种状态，并单独列出跳过的检查项。

## 早期研究与规划文档

下面两份文档是项目立项阶段的探索性设计笔记，不是强制开发路线图；文内的研究方向编号均根据 `docs/direction-primitive-mapping.json` 保存的分组关系自动重算得出。

- [问题图集 v0 英文版](docs/pain-atlas-v0.en.md)与[问题图集 v0 中文版](docs/pain-atlas-v0.zh.md)：梳理日常科研工作各环节的常见阻碍，并为文中的定量说法标注核实状态。
- [研究计划 v0 英文版](docs/research-plan-v0.en.md)与[研究计划 v0 中文版](docs/research-plan-v0.zh.md)：说明研究对象模型与核心能力划分，并列出候选研究方向及第一阶段的长尾场景分解表。
