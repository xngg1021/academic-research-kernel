# academic-research-kernel `v3.0.0`

<!-- mcp-name: io.github.xngg1021/academic-research-kernel -->

[English](README.md) · [简体中文](README.zh-CN.md)

**面向科研人员与 AI 智能体的确定性论文核查、顶会审稿透视与投稿安检内核。**

大语言模型擅长顺畅概括论文大意，但在需要精确算术和外部事实核对的环节极易出错：读外部论文时，模型经常顺着原文复述算错的 $p$ 值与凑出来的消融表格，或者引用已撤稿文献与虚构 DOI；写自有稿件时，单靠自然语言提示词也拦不住双盲 PDF 元数据里的作者实名残留、LaTeX 手抄表格误差与正文超页。

`academic-research-kernel` 在 `3.0.0` 版本将语义阅读与确定性核查拆开：自然语言阅读与提炼交给研究人员或大模型，统计重算与 Crossref、OpenAlex 双源核验，以及 OpenReview 离线审稿透视、荟萃分析合并和多文件 LaTeX 投稿门禁，全部收拢进单一标准库优先包 `src/academic_research_kernel/`，持久状态由 `SQLite STRICT + WAL` 事务库统一管理。

作者为 Junfu Shi，笔名 SJF，GitHub 账号 `xngg1021`。许可证适用 [Source Lineage License 1.0](LICENSE)，架构说明见 [docs/kernel-architecture.md](docs/kernel-architecture.md)。

---

## 一、五大 AI 顶会审稿水位与机器审稿异常实测：2025 至 2027

为什么读论文和投论文都应当配备确定性核查工具？我们直接运行本内核的 `openreview-audit --venue-summary` 命令，对五大 AI 顶会公开镜像共 `74,933` 篇论文记录与 `234,128` 条官方评审做了全量确定性统计，原始镜像 SHA-256 与分母口径存档于 [peer-review-forensics-2025-2027-v1.json](docs/benchmarks/peer-review-forensics-2025-2027-v1.json)：

| 顶会与公开范围 | 含评分论文数 $N$ | 官方评审总数 | 论文均分均值与分制 | 评审词数中位数：`conf=2` 对照 `conf=4` | 多审稿人全员同分率 | 除初始评审外零后续讨论率 |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| **ICLR 2026** 全量投稿公开 | 15,922 | 60,829 | `4.33` 1至10偶分制 | 总中位数 `468`：`419` 对 `481` | **10.50%** 即 `1,667 / 15,879` | 12.66% |
| **ICLR 2027** 答辩期快照共 `42,790` 篇 | 32,835 | 126,369 | `2.06` 1至4整数制 | 总中位数 `492`：**`491`** 对 `496` | **23.76%** 即 `7,800 / 32,834` | **91.85%** 答辩第7天 |
| **ICML 2026** 公开录用稿 | 6,556 | 24,877 | `3.59` 1至5推荐制 | 总中位数 `429`：`397` 对 `436` | 8.13% 即 `533 / 6,556` | 8.63% |
| **NeurIPS 2025** 公开录用稿 | 5,280 | 20,257 | `4.42` 1至6评分制 | 总中位数 `536`：**`541`** 对 `536` | 6.14% 即 `324 / 5,280` | 3.12% |
| **COLM 2025** 公开录用稿 | 497 | 1,796 | `6.66` 1至10评分制 | 总中位数 `453`：`416` 对 `451` | 5.63% 即 `28 / 497` | 20.12% |

实测数据呈现出三个清晰的结构变化：
1. **分制压缩下的全员同分翻倍**：ICLR 2027 总投稿增至 `42,790` 篇并改用 `1–4` 四分制后，`57.36%` 的评审集中在 `2` 分档，多审稿人给出完全相同分数的论文占比从 ICLR 2026 的 **`10.50%`** 翻倍升至 **`23.76%`**，涉及 `7,800` 篇投稿。
2. **低把握度审稿词数反常倒挂**：在传统人工审稿分布中，把握度为 `2` 分的外行审稿词数明显短于 `4` 分专家，例如 ICLR 2026 为 `419` 词对 `481` 词，COLM 2025 为 `416` 词对 `451` 词。但在 NeurIPS 2025 录用稿中，`conf=2` 词数中位数达 `541` 词，反超 `conf=4` 专家的 `536` 词；ICLR 2027 中 `conf=2` 也涨至 `491` 词，追平 `conf=4` 的 `496` 词。同期 ICML 2026 程序委员会官方通报查处了 `398` 名违规使用大模型生成审稿意见的审稿人，NeurIPS 2026 官方总投稿也已升至 `30,709` 篇。
3. **稿件自身的确定性硬伤发生率高**：在 ICLR 2026 共 `19,473` 篇有分投稿的审稿意见统计中，见 [iclr2026-openreview-incidence-receipt.json](docs/benchmarks/iclr2026-openreview-incidence-receipt.json)，缺失误差棒或标准差、版式章节违规，以及表格消融矛盾、漏引基线与缺失复现代码这五类确定性问题，在 Oral 稿件中被指出的比例为 **`48.2%`**，Poster 为 **`54.0%`**，拒稿为 **`59.8%`**，带评语桌拒达 **`63.6%`**。在包含 16 项真实撤稿与虚构引文以及 14 项 Nuijten 与 Bakker 统计错案的实测基准中，见 [real-world-audit-benchmark-v1.json](docs/benchmarks/real-world-audit-benchmark-v1.json)，本内核在引文与撤稿核查上取得 `TP=10, TN=6, FP=0, FN=0`，在已发表统计错案复核上取得 `TP=8, TN=5, FP=1, FN=0`。

---

## 二、两分钟快速上手：三种使用方式

先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，再按您的工作场景任选一种方式接入。内核支持 Python `3.10` 至 `3.14`，命令行延迟加载冷启动仅约 `25 ms`。

### 方式一：独立命令行工具，适合科研人员与脚本直接调用

```bash
uv tool install "academic-research-kernel[research]==3.0.0"
academic-research-kernel doctor
academic-research-kernel verify-work "10.1038/nature14539" --normalize-only
```

### 方式二：标准 stdio MCP 服务，适合 Claude Code 与 Codex，以及 Cursor 与 Gemini CLI

对外暴露 **24 个确定性 MCP 工具**，支持 `2024-11-05` 至 `2026-07-28` 协议版本协商：

```bash
# 在 Claude Code CLI 中一键注册
claude mcp add academic-research-kernel -- uvx --from "academic-research-kernel[research]==3.0.0" academic-research-kernel mcp

# 在 OpenAI Codex CLI 中一键注册
codex mcp add academic-research-kernel -- uvx --from "academic-research-kernel[research]==3.0.0" academic-research-kernel mcp
```

### 方式三：智能体技能包，适合 Hermes Agent 或支持 `SKILL.md` 的客户端

```bash
# 在 Hermes Agent 中安装完整七技能插件
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills

# 或将单篇论文审读技能与配套 Schema 导出到任意目录
academic-research-kernel research skill --output ./audit-paper
```

---

## 三、完整整合原版十四项能力的七大核心技能

`3.0.0` 版本把旧版按内部脚本拆分的十四项技能目录完整归并为七个直观的“动词加宾语”技能，方便科研人员与智能体第一眼识别用途：

| 技能目录 | 一句话用途说明 | 关联核心子命令与工具 |
| --- | --- | --- |
| [`skills/audit-paper`](skills/audit-paper/SKILL.md) | 审读单篇或双篇论文：重算统计量与表格守恒，裁决复现清单并管理证据图与决策台账 | `research`、`table-forensics` 与 `repro-checklist`、`ledger` |
| [`skills/verify-citations`](skills/verify-citations/SKILL.md) | 核查引文真伪：双源验证 DOI 与更正记录，追踪撤稿与新文献，合并多路语料并定位五源开放全文 | `verify-work`、`retraction-watch` 与 `collect-corpus`、`locate-oa` |
| [`skills/audit-peer-review`](skills/audit-peer-review/SKILL.md) | 透视顶会审稿：离线统计 OpenReview 评分分布与异常体征，取证本地或远端配套代码仓 | `openreview-audit`、`repo-forensics` 与 `academic_openreview_audit` |
| [`skills/meta-analysis`](skills/meta-analysis/SKILL.md) | 文献综述合并：固定与随机效应合并，执行亚组分解与元回归，生成引文图与综述对照表 | `meta-analyze`、`bibliography` 与 `academic_meta_analyze` |
| [`skills/check-submission`](skills/check-submission/SKILL.md) | 投稿前安检门：建立会刊工程，转换收据与双篇对比三线表，扫描多文件 LaTeX 与双盲 PDF | `lint-submission`、`sanitize-submission` 与 `generate-table`、`check-venue` |
| [`skills/cross-review`](skills/cross-review/SKILL.md) | 多模型稀疏审议：独立盲审与断言聚类，生成匿名质询包并保护附定位证据的少数派发现 | `cross-review`、`academic_cross_review` |
| [`skills/compute-math`](skills/compute-math/SKILL.md) | 科学计算与探针：探测处理器与科学计算库版本，生成实测计算回执并路由多学科数理计算 | `compute-probe`、`academic_scfabric_hardware_probe` |

---

## 四、高频实战命令：审外部论文与查自有投稿

### 场景一：审读外部论文、透视顶会审稿与执行荟萃分析

```bash
# 1. 解析本地 PDF 或多文件 LaTeX 源码包，校验提取数字并审计表格守恒
academic-research-kernel research prepare ./paper.pdf --project ./paper-state
academic-research-kernel research finish --project ./paper-state --candidate ./candidate.json
academic-research-kernel table-forensics --input ./table-spec.json

# 2. 基于公开镜像离线审计 ICLR / ICML / NeurIPS / COLM 审稿记录，避开线上 Cloudflare 403 拦截
academic-research-kernel openreview-audit --venue-summary ./iclr2027.json
academic-research-kernel repo-forensics ./companion-repo

# 3. 双源核查引文真伪、定位合法开放获取全文，并用 SQLite 事务库追踪撤稿信号
academic-research-kernel verify-work "10.1038/nature14539"
academic-research-kernel locate-oa "10.1038/nature14539" --email "you@example.edu" --fallback-openalex
academic-research-kernel retraction-watch --dois "10.1038/nature14539" --state-db ./watch.sqlite3 --live

# 4. 多研究效应量随机效应合并与异质性 Q / I^2 / tau^2 及 Egger 偏倚检验
academic-research-kernel meta-analyze --input ./studies.json
```

### 场景二：准备自有稿件与投稿前的确定性门禁

```bash
# 1. 查看内置会刊页数与章节规范，或从证据图导出已就绪的 % ark:claim=<id> 锚点
academic-research-kernel check-venue --list-venues
academic-research-kernel check-venue --export-ceg-anchors ./ceg.json

# 2. 将实验 JSON 收据按精确十进制舍入直接渲染为 LaTeX booktabs 三线表
academic-research-kernel generate-table ./results-receipt.json --caption "Main Results" --label "tab:main"

# 3. 在受控隔离子进程中扫描源码目录与编译后 PDF 的 /Info 字典及 XMP 流，拦截实名泄露
academic-research-kernel sanitize-submission ./submission-dir --forbidden-token "Author Name"

# 4. 运行投稿前全量检查：解析嵌套 \input 与声明书目，并核对正文共享页计页与 CEG 论断绑定
academic-research-kernel lint-submission ./submission-dir/main.tex \
  --venue iclr --phase submission --pdf ./submission-dir/main.pdf \
  --ceg ./ceg.json --require-ceg-binding --check-academic-style
```

---

## 五、纯标准库 SQLite 架构、安全隔离与外部数据源说明

1. **单包 `SQLite STRICT + WAL` 状态内核**：`v3.0.0` 将非测试 Python 源码从 `32,167` 行精简至约 `14,000` 行，移除分散在各目录的自定义 JSON 文件锁与重复包装脚本，统一由 `ResearchStateDB` 提供外键约束与 `SAVEPOINT` 原子回滚，内置 `application_id = 0x41524B33` 与 `user_version = 3` 身份校验、谱系有向无环检查以及 `applied_seq` 与 `confirmed_seq` 双序号撤稿状态机。单侧外部接口超时或格式异常时，系统自动保留另一侧已确认的撤稿信号。
2. **受控子进程 PDF 解析与网络防重绑定隔离**：`research prepare`、`lint-submission` 与 `sanitize-submission` 读取不可信 PDF 时，全程在带超时熔断的 `python -I -c` 隔离子进程中提取正文、`/Info` 属性与 XMP 流，固定使用 `pypdf==7.0.0` 与 `fonttools==4.65.0`。外部联网请求统一经过 `controlled_urlopen`，默认禁用环境变量代理并在连接前锁定公网 DNS 解析结果，严格限制响应体字节上限。MCP 双盲扫描接口默认遮蔽命中文本，防止作者真名回流进第三方客户端日志。
3. **外部开放接口配额规则**：`doctor` 全程离线运行。`OpenAlex` 首屏查询支持匿名调用，翻页或高频检索建议配置 `OPENALEX_API_KEY`；`Crossref` 提供公开元数据与 `update-to` 更正记录查询；`Unpaywall` 需通过 `--email` 或环境变量 `UNPAYWALL_EMAIL` 提供联系邮箱，未配置邮箱时可加 `--fallback-openalex` 回退检索。

---

## 六、从 `2.x` 升级至 `3.0.0`、本地验证与许可证

### `2.4.x` 至 `3.0.0` 升级要点

- **统一包内入口**：原 `scripts/mcp_server.py` 统一为 `academic-research-kernel mcp`；原发布门禁脚本统一收拢为 `python -m academic_research_kernel.release_gate`。命令行同时兼容旧版子命令名与新版精简别名。
- **撤稿巡检状态一次性迁移**：如存有 `2.4.x` 时期的 JSON 监控状态文件，可执行一次 `academic-research-kernel retraction-watch --import-legacy-json old-watch.json --state-db watch.sqlite3` 导入 SQLite 状态库。完整变更见 [CHANGELOG.md](CHANGELOG.md)。

### 本地测试与仓外隔离打包验收

```bash
uv lock --check
uv run --frozen --extra qa --extra research pytest -q tests
uv build --no-create-gitignore
uv run --frozen --extra qa --no-editable python -m twine check --strict dist/*
PYTHONPATH=src python -m academic_research_kernel.release_gate --package-acceptance --dist dist
```

### 许可证

本仓库受保护的项目材料在 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 界定范围内适用 **Source Lineage License 1.0**，标识符为 `LicenseRef-Source-Lineage-1.0`；来源谱系与保留上游 MIT 文件的 SHA-256 清单见 [SLL-APPLICATION.json](SLL-APPLICATION.json) 与 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md)，以及 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 与 [REPOSITORY-IDENTITY.md](REPOSITORY-IDENTITY.md)。SLL 1.0 允许学术与商业自由使用与修改，也允许重分发及闭源扩展，前提是保留规定的许可与来源声明；单纯通过网络提供服务而不分发软件副本不会触发署名义务，[tests/upstream/LICENSE](tests/upstream/LICENSE) 等第三方测试文件继续适用各自原有许可证。
