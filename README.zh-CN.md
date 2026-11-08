# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

这是一套面向科研人员与 AI 智能体的确定性学术核查与论文工程内核。

平时用大语言模型读论文或写论文，最容易撞上两类硬伤。读别人的论文时，模型按概率续写文字，经常顺着作者的叙述把算错的统计量与凑出来的消融表格，或者已经撤稿的文献与空壳代码仓库当成事实复述出来。写自己的论文时，单靠提示词叮嘱模型检查格式，很难拦住双盲匿名残留与手抄表格涂改，也难以自动发现图表悬空引用或漏掉目标会议的必写章节。

本仓库从第一性原理出发，把这两件事拆开处理：让大语言模型专心负责自然语言阅读与语义提炼，把所有能用数学公式与公开数据库接口，以及语法解析树和哈希校验定死的环节，全部交给确定性代码执行。全仓将 14 项科研工作流与 12 个标准 MCP 服务工具，以及 13 组命令行子命令收拢在同一套状态内核之上，原生支持 Claude Code 与 Cursor，也直接兼容 Codex、Gemini CLI 与 Hermes Agent。详细的验证范围与外部接口范围见[审计文档](docs/kernel-architecture.md)。

作者为 Junfu Shi，笔名 SJF，GitHub 账号 xngg1021，联合 Hermes Agent 共同完成。当前授权范围适用 [Source Lineage License 1.0](LICENSE)。

---

## 一、两分钟快速上手

先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，再按您的使用方式任选一条命令安装 `2.3.0` 版本：

```bash
# 方式一：安装带 PDF 解析支持的完整命令行工具，并导出论文精读技能给本地智能体
uv tool install "academic-research-kernel[research]==2.3.0"
academic-research-kernel research skill --output ./paper-research

# 方式二：作为标准 stdio MCP 服务启动，供 Claude Code / Cursor / Codex 等客户端调用
uvx academic-research-kernel@2.3.0 mcp
```

安装完成后，可以先跑一次离线环境自检，并直接试试文献核查与会刊规则查询：

```bash
academic-research-kernel doctor
academic-research-kernel verify-source https://doi.org/10.1038/nature14539 --normalize-only
academic-research-kernel venue-template --action list-venues
```

`doctor` 命令默认离线运行，负责检查运行环境依赖、26 套 JSON 数据格式与全部 12 个 MCP 工具接口；即使没有配置可选的外部数据库密钥，自检也不会报错。直接在终端运行 `mcp` 子命令会让程序进入标准输入输出监听状态，等待 MCP 客户端发来请求。[2.3.0 Release](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.3.0) 页面记录了构建产物的 SHA-256 哈希值。本工具支持 Python 3.10 至 3.14，基础安装包已内置全部工具，科学计算库只在调用分布检验或功效重算时按需加载。

---

## 二、上半场：读别人的论文与核查外部证据

审读外部论文或撰写文献综述时，系统按“先核实文献与代码真伪，再重算表格与统计数字，最后生成带原文页码的报告”逐层推进。

### 1. 让本地智能体精读单篇论文或横向对比两篇论文

将导出的 `./paper-research/SKILL.md` 交给您的本地智能体，发给它一个 DOI、公开网页链接或本地文件夹，直接下达指令：
“请研究这篇论文与补充材料，整理实验方法并核对能重算的关键数字，给我一份带出处的中文报告。”

命令行分三步配合智能体完成核验：

```bash
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` 负责读取 PDF 与 HTML、XML/JATS 与 DOCX/XLSX，或者 LaTeX/BibTeX 源码包，计算文件哈希并按页码与章节建立原文段落索引。智能体读完原文填好候选提取结果后，`finish` 会逐条核对每个数字是否真实出现在声明的原文位置，自动调用统计重算引擎验证数值是否自洽，保存研究状态并生成带页码出处的中文 Markdown 与 HTML 报告。`compare` 负责核验两篇论文在数据集、实验条件与评估指标上是否具备直接可比性。保存下来的原始材料与提取快照随时可用 `academic-research-kernel research replay --project PROJECT` 离线重放。

### 2. 查证文献真伪、开放获取全文与审稿记录及代码仓库

针对单篇论文的外部取证，可以直接在终端调用四个子命令：

```bash
# 核对 DOI/arXiv 编号并在 OpenAlex 与 Crossref 交叉核查元数据与撤稿状态
academic-research-kernel verify-source 10.1038/nature14539

# 按 Unpaywall 与 arXiv、OpenAlex 与 Semantic Scholar 及 Europe PMC 顺序定位开放获取全文并校验 DOI
academic-research-kernel locate-oa 10.1038/nature14539

# 核查 OpenReview 审稿记录、评分均值与方差，或计算会刊全量投稿的真实分位数与赛道录用率
academic-research-kernel openreview-audit --forum-id Forum_Synth_01 --mirror-json ./venue-mirror.json
academic-research-kernel openreview-audit --venue-stats ./venue-mirror.json --topic-regex "memory|agent"

# 扫描代码仓库的真实非第三方源码体量、Git 提交记录与 README 宣称命令是否对得上
academic-research-kernel repo-forensics --local-repo ./target-repo
```

`locate-oa` 会拒绝把 `is_oa=false` 的付费墙落地页或 DOI 不匹配的记录当成全文链接。`openreview-audit` 会自动过滤缺失评分并按 `forum_id` 去重，只用普通审稿人的评分计算均分与方差，把领域主席的元审稿与最终决定单独分列。`repo-forensics` 优先通过 `git ls-files` 区分项目自有源码与打包进来的第三方目录，防止把塞满第三方库的仓库误判为高工作量项目。

### 3. 15 类统计与取证重算、物理下界校验与荟萃分析

公开的 `academic_recompute_statistics` MCP 工具与 `recompute.py` 引擎支持 15 类确定性核查。基础检验涵盖 $t$ 检验与 $F$ 检验，以及 $\chi^2$ 检验与回归系数 $\beta/\text{SE}$ 的 Wald 检验；区间与效应量检验涵盖置信区间对称性与 $2\times 2$ 列联表优势比及风险比，以及双样本 Cohen's $d$ 与 Hedges' $g$ 效应量；自洽检验涵盖百分比分母反推与有界量表标准差可能性，以及自由度核对和 $t$ 检验统计功效反算。

针对机器学习与系统论文常见的表格异常，`2.3.0` 版本新增了三项表格取证体检能力（可通过 `academic-research-kernel table-forensics --input spec.json` 或 MCP 调用）：
- **样本分区守恒 `partition_conservation`**：核对总样本量是否严格等于各互斥子集计数之和；
- **消融实验恒定偏移 `ablation_delta_regularity`**：检测消融表的多列指标之间是否存在人为加减常数的固定平移现象；
- **未压缩存储与全量扫描带宽下界 `storage_bandwidth_bounds`**：在假定未压缩定宽浮点表示与单次全量线性扫描的前提下，根据向量条数、向量长度与字节宽度计算裸向量体积下界与全表扫描延迟下界，排查声称完整未压缩存储却低于裸向量体积的矛盾。

如果核对论文时需要保留小数点末尾的有效零，可以传入字符串参数 `p_value_literal` 如 `"1.0e-5"`，或用 `p_value_decimals` 指定小数位数。多篇研究的固定效应与 DerSimonian-Laird 随机效应合并、异质性 $Q/I^2/\tau^2$ 与 Egger 偏倚检验可直接运行：

```bash
academic-research-kernel meta-analyze --input studies.json
```

---

## 三、下半场：写自己的论文与投稿前确定性门禁

自己动手写论文与准备投稿时，系统提供从工作区初始化与实验数据转三线表，到双盲匿名清洗与投稿前硬性门禁的四步工具链。

```bash
# 1. 查看内置的 8 大会刊规格并初始化论文目录
academic-research-kernel venue-template --action list-venues
academic-research-kernel venue-template --action scaffold --workspace-dir ./workspace --slug my-paper --venue iclr

# 2. 将核验通过的实验结果 JSON 直接渲染为带最优粗体与次优下划线的 LaTeX booktabs 三线表
academic-research-kernel receipt-to-latex --input ./results-receipt.json --caption "Main Results" --label "tab:main"

# 3. 执行双盲匿名扫描，拦截 .tex/.bib 与编译后 PDF 元数据中的实名与致谢及自引暗号和本机路径
academic-research-kernel sanitize-blind --target ./workspace/my-paper

# 4. 执行投稿前全量门禁，检查匿名宏包与页数上限，以及必含章节、悬空引用和 ClaimEvidenceGraph 证据支撑边
academic-research-kernel pre-submission-lint --tex ./workspace/my-paper/main.tex --venue iclr --contribution-type systems_architecture
```

`receipt-to-latex` 全程采用 `Decimal` 精确十进制舍入，避免手抄实验表格改错数字或浮点精度漂移。`double-blind-sanitize` 既扫描文本中的 `\author` 与自定义实名宏，以及 `\icmlauthor` 与 `pdfauthor` 配置，也会直接读取编译后 PDF 的 `/Author` 与 `/Creator` 文档属性字典。`pre-submission-lint` 对照 `skills/academic-writing/references/venue-specs.json` 中的当届规则，检查是否误开 `final`、`preprint` 或 `camera-ready` 宏包选项，跨页追踪文末豁免声明使 `Reproducibility Statement`、`Ethics Statement` 与 `Acknowledgments` 不再虚增正文页数，利用平衡花括号屏蔽 `\newcommand` 与 `\def` 宏定义体以消除未调用草稿宏的 `TODO` 误报，跨文件核对 `\ref`、`\Cref` 与 `\label{...}` 及 `lstlisting[label={...}]` 是否闭合，拦截 `Author et al. ~\cite{...}` 作者名重复伪影与著者年份制下全篇混用裸 `\cite` 的排印缺陷，拦截双盲初审稿中的非匿名致谢与基金号披露，并在耗时随文本长度线性增长的前提下校验摘要与结论中的定量论断在 `ClaimEvidenceGraph` 中是否真正连向 `support_status == "supported"` 的正向证据边。

参考文献格式转换与排序可直接调用：

```bash
academic-research-kernel bibliography --from bibtex --to csl --input refs.bib
```

### 同行评议中五类确定性缺陷的宏观分布：ICLR 2026 共 `19,473` 篇有分稿件

为说明缺失误差棒与版式超限、表格消融异常与漏引基线及缺失复现代码这五类确定性检查的现实依据，我们在不拟合任何经验权重与主观分数阈值的前提下，按论文粒度统计了 ICLR 2026 共 `19,473` 篇有分投稿与 `75,769` 条官方审稿意见中至少一条审稿意见指出对应缺陷的稿件占比 `k / N`；全集包含下表四类常规决定共 `18,791` 篇与带评语程序性拒稿 `682` 篇，`SHA-256` 奇偶分半子集分别为 `9,765` 篇与 `9,708` 篇，所有单篇稿件均保持完全匿名：

| 录用档位与可靠度分层 | 有效投稿数 $N$ | 评分均值 / Soundness 均值 | 审稿意见提及五类确定性缺陷的稿件占比 `k / N` |
| --- | --- | --- | --- |
| **Oral 口头报告** | 224 | 6.40 / 3.07 | **48.2%** 即 `108 / 224`，含缺失误差棒 12.1% 与表格消融 7.1%，以及漏引基线 2.7% |
| **Poster 海报录用** | 5,134 | 5.36 / 2.83 | **54.0%** 即 `2,772 / 5,134`，含缺失误差棒 15.8% 与表格消融 8.9%，以及漏引基线 4.1% |
| **Rejected 拒稿** | 8,453 | 3.96 / 2.49 | **59.8%** 即 `5,055 / 8,453`，含缺失误差棒 21.4% 与表格消融 11.6%，以及漏引基线 6.2% |
| **Withdrawn 撤稿** | 4,980 | 3.35 / 2.33 | **62.6%** 即 `3,117 / 4,980`，含缺失误差棒 23.8% 与表格消融 12.4%，以及漏引基线 6.8% |
| **Soundness $\ge 3.25 \to \le 2.0$** | 1,077 $\to$ 2,861 | $\ge 3.25 \to \le 2.0$ | **49.1% $\to$ 67.4%** 即 `529 / 1,077` $\to$ `1,928 / 2,861`，缺失误差棒 14.9% $\to$ 27.5% |

---

## 四、14 项学术技能一览与智能体集成

| 技能 | 版本 | 能帮您做什么 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.3.0 | 交叉核对论文真伪与各数据库被引数，排查更正或撤稿记录，定位开放获取全文，审计 OpenReview 审稿记录并取证代码仓库 |
| `skills/literature-analysis` | 1.3.0 | 按雪球法拓展相关文献，对比多篇论文的方法与分歧，梳理作者学术履历，按评审清单审读稿件并支持 BibTeX、RIS 与 CSL-JSON 互转 |
| `skills/quantitative-paper-audit` | 1.2.0 | 根据论文报告的统计量独立重算 $p$ 值与效应量及置信区间、优势比与统计功效，并核查样本分区守恒与消融恒定偏移及物理带宽下界 |
| `skills/math-computation` | 1.2.1 | 调用 SymPy 与 NumPy 及 SciPy、statsmodels 与 PyTorch 完成符号推导与微积分求解，涵盖线性代数与微分方程及运筹优化和蒙特卡洛模拟 |
| `skills/academic-writing` | 1.2.0 | 辅助润色论文结构与语言，按各国规范排版参考文献，并提供投稿前版式门禁与双盲匿名清洗，以及实验收据转 LaTeX 三线表和会刊模板生成 |
| `skills/research-reproducibility` | 1.0.1 | 核查论文配套代码的提交哈希与依赖锁文件，以及随机数种子和容差设置，把重跑实验的结果整理成可复查的核验记录 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | 记录 PRISMA 文献检索与筛选流程，转换效应量，检验异质性，执行固定或随机效应模型合并以及留一法敏感性与发表偏倚分析 |
| `skills/literature-watch` | 1.1.0 | 按主题、作者或引文 DOI 每周巡检 OpenAlex 与 Crossref，自动跨源去重并只汇报上次检查之后新发表的论文 |
| `skills/retraction-watch` | 1.1.0 | 按周复查关注清单里的论文 DOI，比对 OpenAlex 的 `is_retracted` 标记与 Crossref 的 `update-to` 更正记录，只在状态变化时提醒 |
| `skills/research-object-identity` | 1.1.0 | 把杂乱的 DOI、arXiv 编号与本地文件哈希整理成统一的身份记录，核实资源有效状态，并看清每份分析结果是由哪些原始材料生成的 |
| `skills/claim-evidence-graph` | 1.0.0 | 把文章里的每一条学术论断和背后的原文段落、数据表或计算记录直接关联起来，方便随时核对某句结论有没有正向证据支撑 |
| `skills/decision-ledger` | 1.0.0 | 按时间顺序维护研究决策与阴性结果记录，把做过的方法选择与走不通的失败尝试，以及放弃原因和后续修正记下来，避免重复踩坑 |
| `skills/paper-research` | 1.1.0 | 输入 DOI、网页链接或本地论文及补充材料，验证提取出的关键字段并重算核对统计数字，生成带原文页码出处的中文报告或双篇对比 |
| `skills/cross-review-five` | 2.0.1 | 组织多个不同大模型或子智能体对同一份文稿或代码独立盲审，自动合并重复意见并安排交叉质询，按 P0 至 P3 标注严重度并保留分歧 |

上述 14 项技能共配有 22 篇 Markdown 参考指南与 1 套机器可读会刊规格库，只在执行对应任务时按需读取。

### 安装与客户端集成方式

1. **Python 软件包与可选依赖安装**
   ```bash
   uv tool install academic-research-kernel==2.3.0
   ```
   您也可以使用 `pipx install academic-research-kernel==2.3.0` 或在虚拟环境内运行 `python -m pip install academic-research-kernel==2.3.0`。加上 `[research]` 会固定安装 `pypdf==6.19.0` 与 `fonttools==4.65.0`，保证不同机器解析数字 PDF 字体时结果一致；加上 `[full]` 会一并安装扩展科学计算示例所需的库；加上 `[qa]` 会安装仓库自检与测试所需的解析依赖。

2. **通用 Agent Plugins v1 与 MCP 客户端挂载**
   本仓库遵循 **Agent Plugins v1** 规范并提供 `plugin.json`，通过标准输入输出协议运行 `mcp.json` 与 `scripts/mcp_server.py` 定义的 **MCP 服务器**。虽然仓库名为 `academic-research-kernel`，但插件名 `name: "academic-skills"` 与原有的 MCP 配置别名保持不变，旧配置无需修改即可继续使用。

3. **在 Hermes 中安装插件或按需安装单项技能**
   请先确认 Hermes 进程的环境变量 `PATH` 中包含 `uv`，再安装并启用插件，或直接通过 `tap` 按需安装单项技能：
   ```bash
   # 方式 A：安装完整插件
   hermes plugins install xngg1021/academic-research-kernel --no-enable
   hermes plugins enable academic-skills

   # 方式 B：通过 tap 按需安装单项技能文档
   hermes skills tap add xngg1021/academic-research-kernel
   hermes skills search academic-source-verification
   hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
   ```
   `mcp.json` 会调用 `uv run --frozen --no-dev --no-editable` 与 Python 3.12，按照仓库的 `uv.lock` 锁文件把独立运行环境安装到 `${PLUGIN_DATA}/runtime` 目录，不会改动宿主环境。配套关联技能已对照上游提交 `245e48008fa814b3251f50755eb656bd9fb86cb1` 核对完毕，包含 `arxiv` 与 `grounded-citations`，以及 `docx`、`pdf` 和 `manim-video`。

4. **从源码运行**
   ```bash
   git clone https://github.com/xngg1021/academic-research-kernel.git
   cd academic-research-kernel
   uv sync --frozen --no-dev --no-editable
   uv run --frozen --no-dev --no-editable academic-research-kernel doctor
   uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
   ```
   各类依赖的用途划分与发布校验流程详见[分发与发布说明](docs/distribution-release.md)。

---

## 五、工作原理：三层确定性状态内核与学术规范及外部数据源

### 1. 研究记录保存与字节级复核规则

系统的数据接入层采用 `ResearchArtifactEnvelope v1` 与 `ArtifactIngestionReceipt v1` 格式，内置 15 个解析器，涵盖全部 14 项学术技能外加 1 个普通文本兜底解析器，对外提供 12 个无状态的 stdio MCP 工具。每当系统保存研究对象与学术论断关联，或者写入研究决策记录与待核实事项及证据文件时，核验记录都会记下对应的类型、唯一编号与 SHA-256 哈希值。离线重放时会直接根据保存下来的原始材料与哈希记录重新核对完整性；一旦某次批量写入中途出错，系统会自动原子回滚，不会留下半截损坏的数据。

如果某条核验记录要标记为 `fully_verified` 已完全核实，调用方必须提供对应的原始文件内容，以便系统独立复核。Python 本地调用可通过 `LineageVerificationContext` 传入原文，MCP 协议调用则只允许直接传入文件内容字节流，不允许读取宿主机任意文件路径，单次读取的文件大小默认上限为 10 MiB。如果没有提供原文内容，系统不会把结果标为已完全核实。未经提取的自由文本保持原样存储，不同审稿模型的分歧意见全部公开保留；何时保存记录、放弃哪条路线以及最终采纳哪条学术结论，始终由研究者自己决定。

撤稿状态核查会把本次联网查到的 `True`、`False` 或 `unknown` 结果与上一次确认过的有效状态分开保存。如果最新一次查询因为网络波动或接口限流暂时返回 `unknown`，系统会如实标出本次检查尚未核实，不会冲掉之前已经确认过的既有记录。MCP 服务端支持 `ping` 连通性检查，收到 `notifications/cancelled` 等合法通知时按协议保持静默，遵循 [MCP 消息规范](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages)与 [ping 规范](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping)。

### 2. 学术规范与各国引用标准基线

本仓库以国际标准 **ISO 690:2021** 参考文献与引文指南、**ISO 5127:2017** 文献与信息词汇，以及 **W3C PROV** 来源追溯模型作为通用基线，同时内置中国大陆 GB/T 7714-2025 与西班牙 UNE-ISO 690:2024 及德国 DIN ISO 690:2021 等地区规范，并支持 APA 与 IEEE，以及 PRISMA 2020 和 ICMJE 等学科标准。实际写作时，目标投稿期刊或学校的具体规定始终优先于默认规则，详见[学术规范架构](docs/standards/README.md)与[自然学术术语指南](docs/terminology/README.md)。

### 3. 学术数据源与接口限额

- **OpenAlex**：基础首屏查询支持匿名使用。无密钥每秒最多发送 10 次请求，配置免费或预付费密钥后每秒最多 30 次请求，年度订阅方案每秒最多 50 次请求；匿名访问每日额度为 $0.10，申请免费 API 密钥后每日额度为 $1。翻页读取 `next_cursor` 需配置环境变量 `OPENALEX_API_KEY`，未配密钥时翻页会在保留首屏结果后自动截断。
- **Crossref**：提供带限流的公开元数据接口。核查论文更正与撤稿信号时必须同时核对 DOI 与更新方向；接口没查到记录不代表论文一定没有问题。
- **Unpaywall**：要求在环境变量 `UNPAYWALL_EMAIL` 中填入真实联系邮箱。如果接口没有返回全文地址，不代表网上不存在其他开放获取版本。
- **arXiv 与 Europe PMC、PubMed E-utilities 与 DOAJ 以及 Semantic Scholar**：各自有独立的限流规则，Semantic Scholar 的匿名公共额度与专属密钥额度分开计算。
- **Scite 与 Dimensions、Scopus 与 Web of Science 以及商业 AI 检测工具**：属于可选的外部付费服务，调用前请先确认您自己的账号权限与剩余配额。

详细接口说明见 [OpenAlex 认证指南](https://help.openalex.org/api/authentication/)、[额度与查询计费说明](https://help.openalex.org/api/llm-quick-reference/)及 [Crossref 更新过滤文档](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)。

---

## 六、本地验证与测试套件及许可证

### 1. 本地自检、长尾基准与打包验证

运行测试请使用独立的 Python 虚拟环境，安装 `requirements-qa.txt` 可以配齐全部测试依赖：

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

如需在仓库目录之外的纯净虚拟环境中构建并验证 Wheel 与源码分发包，涵盖全部 11 组 CLI 子命令、`[research]` PDF 提取与 `uvx` 独立缓存运行，可执行：

```bash
uv build --no-create-gitignore
python scripts/release_manifest.py --dist dist --output dist/release-manifest.json
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

GitHub Actions 持续集成覆盖 Linux x86_64 的 Python 3.10、3.12 与 3.14 环境，同时覆盖 Linux ARM64 的 `ubuntu-24.04-arm` 镜像与 Windows x86_64、Windows ARM64 的 `windows-11-arm` 镜像以及 macOS ARM64 的 `macos-latest` 镜像，并附带针对上游 Hermes 的实时兼容性检验。本地完整回归测试套件共通过 1340 项测试，在[正确性修复记录](docs/maintenance/correctness-repair-20261008.md)与早期的[收尾记录](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342)基线上持续扩充。[tools/longtail/](tools/longtail/README.md) 目录存放确定性长尾测试场景生成器，`scripts/scfabric/` 目录提供科学计算基准测试工具，首轮实测说明见 [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md)。全部 21 个语种共 23 份 README 文件均已同步至 2.3.0 版本，状态记录于[多语言清单](docs/i18n/manifest.json)。

### 2. 许可证

包含本声明的代码版本按照 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 界定的范围，对受版权保护的项目材料适用 **Source Lineage License 1.0**。首次切换到 SLL 的提交与后续记录分界的提交，分别登记在 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 与 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) 中。自该节点起保留本声明的后续版本，均沿用相同的授权范围。

截至提交 `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` 的早期版本按 MIT 许可证发布，继续适用当时的许可条款。早期版本的获取者保留完整的 MIT 授权，不需要迁移到 SLL。仓库完整保留了[原项目 MIT 许可文本](LICENSES/MIT-pre-SLL.txt)，且 [tests/upstream/LICENSE](tests/upstream/LICENSE) 与第三方代码来源说明均未改动，新的许可证不会取消早期版本的既有授权。

SLL 许可证允许自由使用与研究，支持修改代码与商业应用，也允许重新分发和闭源扩展，前提是保留规定的许可声明与来源追溯信息。该许可证不是传染性的 copyleft 协议，不要求使用者公开自己的源码。单纯通过网络提供服务而不分发软件副本，不会触发核心服务的来源署名要求。本许可证不包含明示专利授权，第三方材料继续适用各自原有的许可证。具体条款以英文原版 [LICENSE](LICENSE) 为准；`LicenseRef-Source-Lineage-1.0` 只是本地标识名，并非 SPDX 官方编号，也不代表已通过 OSI 认证。[外部贡献规则](CONTRIBUTING.md)与下游使用者的许可权限相互独立。
