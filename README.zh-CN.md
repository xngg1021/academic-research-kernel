# academic-research-kernel `v3.0.0`

<!-- mcp-name: io.github.xngg1021/academic-research-kernel -->

[English](README.md) · [简体中文](README.zh-CN.md)

**可独立运行，也可嵌入任意智能体工作流的确定性论文核查、投稿门禁与证据状态内核。**

大语言模型擅长顺畅概括论文大意，但在需要精确算术和外部事实核对的环节经常出错：读外部论文时容易顺着原文复述算错的 $p$ 值与失衡表格，或者漏掉已撤稿文献与虚构 DOI；准备自有投稿时，仅靠自然语言提示词也拦不住双盲 PDF 元数据里的作者实名残留、多文件 LaTeX 未引用书目与版面超页。

`academic-research-kernel` `3.0.0` 将自然语言阅读与确定性检查拆开，既能在终端直接运行，也能通过 `stdio MCP` 或 `SKILL.md` 接入各类客户端：

```bash
uv tool install "academic-research-kernel[research]==3.0.0"
academic-research-kernel verify-work "10.1038/nature14539" --normalize-only
# -> {"input": "10.1038/nature14539", "type": "doi", "value": "10.1038/nature14539", "canonical": "https://doi.org/10.1038/nature14539"}
```

> **附带公开审稿快照案例**：仓库内置覆盖**四个 AI 会议系列、五个年份冻结快照**的可复算 `SHA-256` 收据，主比较口径含 `74,637` 篇投稿记录与 `248,174` 条有效评审，完整镜像去重共 `75,574` 条记录，详见[第四节](#四四个-ai-会议系列五个公开审稿快照案例2025-至-2027)与 [peer-review-forensics-2025-2027-v1.json](docs/benchmarks/peer-review-forensics-2025-2027-v1.json)。

作者为 Junfu Shi，笔名 SJF，GitHub 账号 `xngg1021`。许可证适用 [Source Lineage License 1.0](LICENSE)，架构说明见 [docs/kernel-architecture.md](docs/kernel-architecture.md)。

---

## 一、两分钟快速上手：三种接入方式与依赖说明

先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，再按工作场景选择接入方式。内核支持 Python `3.10` 至 `3.14`，命令行按需延迟导入冷启动约 `25 ms`：

### 方式一：独立命令行工具，面向科研人员与持续集成脚本

```bash
uv tool install "academic-research-kernel[research]==3.0.0"
academic-research-kernel doctor
academic-research-kernel lint-submission ./manuscript/main.tex --venue iclr --phase submission
```

### 方式二：标准 stdio MCP 服务，面向 Claude Code 与 Codex，以及 Cursor 与 Gemini CLI

对外提供 **24 个确定性 MCP 工具**，支持 `2024-11-05` 至 `2026-07-28` 协议版本协商：

```bash
# 在 Claude Code CLI 中注册
claude mcp add academic-research-kernel -- uvx --from "academic-research-kernel[research]==3.0.0" academic-research-kernel mcp

# 在 OpenAI Codex CLI 中注册
codex mcp add academic-research-kernel -- uvx --from "academic-research-kernel[research]==3.0.0" academic-research-kernel mcp
```

### 方式三：智能体技能包，面向 Hermes Agent 或兼容 `SKILL.md` 的客户端

```bash
# 在 Hermes Agent 中安装七技能插件
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills

# 或将单篇论文核查技能与配套 Schema 导出到任意本地目录
academic-research-kernel research skill --output ./audit-paper
```

**依赖划分说明**：`SQLite STRICT + WAL` 状态库、命令行分发与 MCP 协议控制路径使用 Python 标准库实现；统计重算、荟萃分析与 JSON Schema 校验使用显式声明的 `jsonschema` 与 `numpy` 以及 `scipy` 与 `statsmodels` 依赖并按需延迟加载。可选扩展 `[research]` 安装 `pypdf==7.0.0` 与 `fonttools==4.65.0` 用于隔离子进程解析 PDF 正文与元数据，打包规范见 [docs/distribution-release.md](docs/distribution-release.md)。若需向磁盘 SQLite 文件数据库写入跨进程持久验签的执行收据 `kernel_executions`，请提前将环境变量 `ARK_EXECUTION_KEY_HEX` 设为 `64` 位十六进制密钥，纯内存 `:memory:` 会话则自动使用进程临时密钥。

---

## 二、七大工作流技能与任务分流表

`3.0.0` 将旧版按脚本拆分的十四项技能收拢为七个面向具体科研任务的技能目录：

| 技能目录 | 具体任务与能力范围 | 常用子命令与 MCP 工具 |
| --- | --- | --- |
| [`skills/audit-paper`](skills/audit-paper/SKILL.md) | 核查单篇或双篇论文中的统计重算、表格守恒与复现清单，输出具体检查项与证据图记录，不直接包办整篇论文真伪裁定 | `research` 与 `table-forensics`、`repro-checklist` 与 `ledger` |
| [`skills/verify-citations`](skills/verify-citations/SKILL.md) | 双源核对 DOI 与元数据，基于 SQLite 监控撤稿与新文献并定位开放获取全文；文献真实存在仅证明书目有效，需另行核对正文引述含义 | `verify-work` 与 `retraction-watch`、`collect-corpus` 与 `locate-oa` |
| [`skills/audit-peer-review`](skills/audit-peer-review/SKILL.md) | 离线统计 OpenReview 公开评审分数、篇幅和同分率并盘点配套代码仓；输出数据分布与筛查线索，不直接判定评语公平性或 AI 作者身份 | `openreview-audit` 与 `repo-forensics`、`academic_openreview_audit` |
| [`skills/meta-analysis`](skills/meta-analysis/SKILL.md) | 合并多项研究固定与随机效应量，执行亚组分解、加权最小二乘元回归与发表偏倚检验，整理引文图与综述表 | `meta-analyze` 与 `bibliography`、`academic_meta_analyze` |
| [`skills/check-submission`](skills/check-submission/SKILL.md) | 投稿前检查**自己的待投稿稿件**：扫描多文件 LaTeX 与页数章节规则，核对双盲匿名残留与三线表渲染 | `lint-submission` 与 `sanitize-submission`、`generate-table` 与 `check-venue` |
| [`skills/cross-review`](skills/cross-review/SKILL.md) | 组织**多个模型**对同一结论执行独立盲审、匿名质询与保留少数派证据的结构化复核，区别于分析历史会议审稿记录 | `cross-review` 与 `academic_cross_review` |
| [`skills/compute-math`](skills/compute-math/SKILL.md) | 探测处理器、线程环境与已装科学计算库版本，生成实测 `ComputeReceipt` 回执并路由外部数理计算包 | `compute-probe` 与 `academic_scfabric_hardware_probe` |

### 四个易混入口快速对照

| 您手头的对象 | 对应技能入口 | 主要产出 |
| --- | --- | --- |
| 一篇需要核查的外部论文 | `audit-paper` | 带原文定位的统计、表格与复现检查清单 |
| 一份准备投出的自有稿件 | `check-submission` | 格式页数与双盲匿名，以及论断锚点门禁报告 |
| 一批已公开的会议审稿记录 | `audit-peer-review` | 分数直方图、词数分位数与筛查统计 |
| 一个需要多模型交叉复核的结论 | `cross-review` | 聚类分歧清单与绑定哈希的复核收据 |

**与常见开源科研工具的横向分工**：通用领域技能库如 `Scientific Agent Skills` 以及自动生成或文献问答工具如 `AI-Scientist` 与 `PaperQA` 侧重检索综述与草稿生成；垂直核查工具则分别深耕单一环节，例如支持桌面与网页多库引文核验的 `RefChecker` 及引文基准 `HALLMARK`，还有处理输入统计量舍入重算的 `statcheck` 与面向 `Claude Code + Codex` 审稿流程的 `Anti-Autoresearch`。`academic-research-kernel` 的定位是**跨宿主通用的独立 CLI 与 MCP 核查及 SQLite 证据状态内核**，在同一套事务契约下连接投稿前多文件 LaTeX 双盲门禁与投稿后统计重算、撤稿追踪及公开审稿快照复算，可与上述专精工具配合使用。

---

## 三、常用工作流、已验证范围与已知限制

### 工作流一：核查外部论文、引文撤稿与多研究效应合并

```bash
# 1. 解析本地 PDF 或多文件 LaTeX 包，校验提取数字并检查表格分区守恒
academic-research-kernel research prepare ./paper.pdf --project ./paper-state
academic-research-kernel research finish --project ./paper-state --candidate ./candidate.json
academic-research-kernel table-forensics --input ./table-spec.json

# 2. 双源核查引文与更正记录、定位合法开放获取全文，并用 SQLite 追踪撤稿状态
academic-research-kernel verify-work "10.1038/nature14539" --check-updates
academic-research-kernel locate-oa "10.1038/nature14539" --email "you@example.edu" --fallback-openalex
academic-research-kernel retraction-watch --dois "10.1038/nature14539" --state-db ./watch.sqlite3 --live

# 3. 多研究效应量合并与异质性 Q / I^2 / tau^2 及 Egger 偏倚检验
academic-research-kernel meta-analyze --input ./studies.json
```

### 工作流二：自有 LaTeX 与 PDF 稿件投稿前门禁

```bash
# 1. 查看内置会刊页数与章节规范，或从证据图导出已就绪的 % ark:claim=<id> 锚点
academic-research-kernel check-venue --list-venues
academic-research-kernel check-venue --export-ceg-anchors ./ceg.json

# 2. 将实验 JSON 收据按精确十进制舍入渲染为 LaTeX booktabs 三线表
academic-research-kernel generate-table ./results-receipt.json --caption "Main Results" --label "tab:main"

# 3. 在受控隔离子进程中扫描源码与编译后 PDF 的 /Info 字典及 XMP 流
academic-research-kernel sanitize-submission ./submission-dir --forbidden-token "Author Name"

# 4. 运行投稿前门禁：解析嵌套 \input/\subfile/\import 与声明书目，核对正文共享页计页与 CEG 绑定
academic-research-kernel lint-submission ./submission-dir/main.tex \
  --venue iclr --phase submission --pdf ./submission-dir/main.pdf \
  --ceg ./ceg.json --require-ceg-binding --check-academic-style
```

**开发回归集结果与已知限制**：
- 在 30 例离线开发回归集 [real-world-audit-benchmark-v1.json](docs/benchmarks/real-world-audit-benchmark-v1.json) 中，16 例冻结快照引文与撤稿样本重放结果为 `TP=10, TN=6, FP=0, FN=0`，12 例 Nuijten 与 Bakker 已发表统计观测加 2 例仓内门禁样本重放结果为 `TP=8, TN=5, FP=1, FN=0`，合计 `TP=18, TN=11, FP=1, FN=0`。
- **已知舍入限制说明**：当前 `recompute.py` 按报告的统计量点值核对 $p$ 值舍入区间，尚未对一位小数粗舍入统计量做双侧区间展开，样本 `S14` 即 `t(15)=2.3, p=.033` 会产生该集合中唯一一例已知假阳性 `FP=1`，实务中需结合原文有效数字人工复核。双盲匿名检查中，未携带作者标识或自建仓库表述的普通第三方公共链接仅输出 `warning` 人工待查提示，避免正常引用公共开源库时被硬阻断。

---

## 四、四个 AI 会议系列五个公开审稿快照案例：2025 至 2027

运行 [run_peer_review_and_incidence_benchmarks.py](tools/benchmarks/run_peer_review_and_incidence_benchmarks.py) 对 `papercopilot/paperlists@181a85021c63ab26745c42ed70a9d9ea7b57ad7e` 冻结修订下的四个 AI 会议系列、五个年份公开快照执行分轨道与分状态统计，主比较口径共覆盖 `74,637` 篇去重投稿、`72,289` 篇含正分论文与 `248,174` 条有效官方评审，原始字节哈希、排除分项与重放脚本见 [peer-review-forensics-2025-2027-v1.json](docs/benchmarks/peer-review-forensics-2025-2027-v1.json)：

| 快照与主比较范围 | 含正分稿件数 $N$ | 有效评审数及篇均评分数 | 论文均分均值与合法量表 | 评审词数中位数：`conf=2` 对 `conf=4` | 全员同分率与独立抽样基线 |
| --- | ---: | ---: | --- | --- | ---: |
| **ICLR 2026** 公开投稿快照共 `19,813` 篇，单列 `1,319` 条零分 | 19,454 | 74,540，篇均 `3.83` | `4.26`，2至10偶分制 | `391`：`328` 对 `409` | **8.13%** 即 `1,578/19,412`，基线 `5.07%` |
| **ICLR 2027** 答辩期公开快照共 `42,790` 篇 | 40,801 | 126,369，篇均 `3.10` | `2.06`，1至4整数制 | `429`：`405` 对 `451` | **23.90%** 即 `9,752/40,801`，基线 `19.80%` |
| **ICML 2026** 主轨公开录用快照，含 `334` 条 6 分 | 6,341 | 24,378，篇均 `3.84` | `4.15`，1至6整数推荐制 | `345`：`298` 对 `364` | **16.53%** 即 `1,048/6,341`，基线 `12.35%` |
| **NeurIPS 2025** 主轨录用快照，原镜像共 `6,212` 条* | 5,275 | 21,301，篇均 `4.04` | `4.34`，1至6整数评分制 | `389`：`330.5` 对 `409.5` | **14.01%** 即 `739/5,275`，基线 `8.97%` |
| **COLM 2025** 主轨录用快照，镜像不含词数字段 | 418 | 1,586，篇均 `3.79` | `6.50`，1至10整数评分制 | 镜像未收录词数 | **7.89%** 即 `33/418`，基线 `5.46%` |

*\*快照范围说明*：`nips/nips2025.json` 原始镜像共 `6,212` 条公开记录，除上表所列主轨录用稿 `5,275` 篇外，其余互斥的 `937` 条记录由数据集与基准轨 `591` 条与立场论文轨 `95` 条，外加主轨主动公开的拒稿 `251` 条组成；三轨公开拒稿合计 `400` 条，其中 `149` 条已含于上述两个非主轨内，另有 `74` 篇立场轨论文贡献全部 `125` 个大于 `6` 的评分。这 `937` 条非主轨录用记录已完整保留在收据的 `mirror_cohort_breakdown` 字段中，不作静默剔除。

1. **量表压缩、篇均评审人数下降与同分基线变化**：ICLR 2027 快照在分制压成 `1–4` 四档后有 `57.36%` 的评分落在 `2` 分，同时每篇有分稿件的平均有效评审人数由 2026 年的 `3.83` 人降至 `3.10` 人，多审稿人稿件最常见评审数由 `4` 人变为 `3` 人。在该经验边际独立抽样零模型下，同分基线 $\sum_k p_k^m$ 本身即由 **`5.07%`** 升至 **`19.80%`**，同期观测到的全员同分率由 **`8.13%`** 升至 **`23.90%`**。该零模型对照仅提供结构基线参考而不识别跨年真实成因，全员同分率不得直接换算为机器审稿占比或审稿人串谋比例。
2. **自报把握度与审稿词数分布**：在含词数字段的四份快照中，自报 `confidence=2` 的评语词数中位数均低于 `confidence=4`，例如 ICLR 2026 为 `328` 词对 `409` 词，ICML 2026 为 `298` 词对 `364` 词，NeurIPS 2025 主轨录用快照为 `330.5` 词对 `409.5` 词，ICLR 2027 为 `405` 词对 `451` 词。同期 ICML 2026 程序委员会在官方通报中单独披露查处了 `398` 名违反审稿规定的互惠违规者并桌拒 `497` 篇关联稿件。
3. **指定字段主题词项提及率筛查**：在关联 `insomnia7/iclr2026_stats@50507ab3` 核验的 `19,473` 篇 ICLR 2026 有分投稿与 `75,769` 条官方评审中，见 [iclr2026-openreview-incidence-receipt.json](docs/benchmarks/iclr2026-openreview-incidence-receipt.json)，对 `Weaknesses` 与 `Questions` 字段运行五类主题词正则筛查，至少命中一类主题词的稿件比例在 Oral 中为 **`48.2%`**，Poster 为 **`54.0%`**，拒稿为 **`59.8%`**，带评语桌拒为 **`63.6%`**，全量有分稿件合计 **`59.0%`**。该比例反映指定字段的主题词项提及率，不等同于存在科学硬伤的论文比例。

---

## 五、状态库结构、安全隔离与本地验收及许可证

1. **事务化 `SQLite STRICT + WAL` 状态内核**：由 `ResearchStateDB` 统一管理外键约束与 `SAVEPOINT` 原子回滚，内置 `application_id = 0x41524B33` 与 `user_version = 4` 身份迁移保护，实施全部 `26` 类受管产物 Schema 校验与单论断外层绑定的目标归属及布尔判定归一化校验，并提供有向无环谱系追踪与 `applied_seq` 及 `confirmed_seq` 双序号撤稿状态机。
2. **受控子进程 PDF 解析与公网 DNS 锁定**：读取不可信 PDF 时全程运行在带超时上限的 `python -I -c` 隔离子进程中；外部 HTTP 请求统一经过 `controlled_urlopen`，禁用环境变量代理并在建连前锁定公网解析地址，MCP 双盲扫描接口默认将命中内容遮蔽为 `[REDACTED]`。
3. **开放接口规则与本地验收命令**：`doctor` 全程离线运行，`OpenAlex` 支持匿名首屏查询，`Unpaywall` 通过 `--email` 或 `UNPAYWALL_EMAIL` 提供联系邮箱并支持 `--fallback-openalex`。命令行完整兼容 `2.4.x` 旧版子命令别名，旧版 JSON 撤稿监控文件可通过 `retraction-watch --import-legacy-json old-watch.json --state-db watch.sqlite3` 一次性导入，详见 [CHANGELOG.md](CHANGELOG.md)。

```bash
uv lock --check
uv run --frozen --extra qa --extra research pytest -q tests
uv build --no-create-gitignore
uv run --frozen --extra qa --no-editable python -m twine check --strict dist/*
PYTHONPATH=src python -m academic_research_kernel.release_gate --package-acceptance --dist dist
```

### 许可证

本仓库受保护的项目材料在 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 规定范围内适用 **Source Lineage License 1.0**，标识符为 `LicenseRef-Source-Lineage-1.0`；来源谱系与保留上游 MIT 文件的 SHA-256 清单见 [SLL-APPLICATION.json](SLL-APPLICATION.json) 与 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md)，以及 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 与 [REPOSITORY-IDENTITY.md](REPOSITORY-IDENTITY.md)。SLL 1.0 允许学术与商业自由使用及修改，同时允许重分发与闭源扩展，前提是保留规定的许可与来源声明；单纯通过网络提供服务而不分发软件副本不会触发署名义务，[tests/upstream/LICENSE](tests/upstream/LICENSE) 等第三方测试文件继续适用各自原有许可证。
