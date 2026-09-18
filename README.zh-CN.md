# academic-research-kernel

[English](README.md) · 简体中文 · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md)

跨宿主中立的学术能力内核与多智能体交叉审议工具套件。仓库提供 13 个学术技能与核验工具，支持便携式 Agent Plugins v1 规范与 MCP (Model Context Protocol) 服务入口，原生兼容 Hermes Agent、Claude Code、Cursor 与终端独立子代理。涵盖来源核验、文献分析、学术写作、数值计算、定量论文审计、复现审计、系统综述与元分析、研究对象身份与谱系、动态多模型交叉审议，以及两套周更监控自动化。仓库附带可执行的示例检查；验证范围与外部服务限制记录于[审计文档](docs/audit-20260906.md)。

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
| `skills/academic-writing` | 1.1.1 | 编辑、引文规范（APA、MLA、Chicago、IEEE、AMA、GB/T）、期刊须知、可选检测服务、投稿材料、中文学术要求 |
| `skills/math-computation` | 1.2.1 | 既有领域与任务路由及修正后的数值与统计示例；四篇领域参考文件 |
| `skills/quantitative-paper-audit` | 1.1.0 | 反算论文报告的统计量（效应量、p 值、置信区间、OR/RR、实现功效）并检测数值错配 |
| `skills/research-reproducibility` | 1.0.1 | 十四阶段复现审计流水线，含结构化清单引擎、五层事实与四态回执 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA 检索日志、筛选台账、效应量换算、异质性、固定与随机效应合并、敏感性与发表偏倚诊断 |
| `skills/literature-watch` | 1.1.0 | 周更蓝图：监控主题、作者与 DOI 在 OpenAlex 与 Crossref 的新作品；去重并只报告新增 |
| `skills/retraction-watch` | 1.1.0 | 周更蓝图：对照 OpenAlex is_retracted 与 Crossref 更新记录（update-to 信号）复查 DOI 监控清单；只报告状态变化 |
| `skills/research-object-identity` | 1.1.0 | 确定性研究对象身份层与生产谱系内核（Provenance Kernel v1）：标识符归一、五态判定、内容寻址衍生图、因果 DAG 校验与毫秒级脱机逆向溯源 |
| `skills/claim-evidence-graph` | 1.0.0 | 确定性科学论断-证据图内核：连接学术论断、实证证据锚点、事实核验与计算谱系 |
| `skills/decision-ledger` | 1.0.0 | 确定性追加式决策与负结果台账内核：决策图谱、失败路径存证、剪枝因果追溯与内容寻址结果修正 |
| `skills/cross-review-five` | 2.0.0 | 动态多席位异构模型/子代理交叉审议（Kimi K3、DeepSeek V4 Pro、GLM 5.3、Claude、Gemini 等）：v2 四阶段 Sparse Deliberation 流（盲审产出、断言级聚类合并、基于匈牙利算法的全局最优互补错排匿名质询、对账与未决保护账本，支持 P0-P3 严重级别） |

十三个技能共含 21 篇 Markdown 参考文件，按需加载。GB/T 7714-2025 已生效；写作参考区分其已核实生效日期与显式标注的 2015 示例。完全符合 2025 版需以目标机构的模板或标准文本为准。

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

技能通过公开学术 API 工作：OpenAlex、Crossref、Semantic Scholar、Unpaywall 与 arXiv。OpenAlex 匿名查询有每日预算；在 `~/.hermes/.env` 配置 `OPENALEX_API_KEY` 可放宽限制。任何技能都不要求付费账号；密钥只发给它所属的域名，绝不写入技能文件或聊天记录。

## QA 与测试

仓库 QA 校验元数据、参考文件、个人路径与已知密钥模式、Python 语法与标记为可执行的代码块。每个 smoke 示例在全新子进程中原样运行；绘图示例接受 `PLOT_DIR`（默认 `~/plots`，显式展开），测试使用临时目录。未分类的 Python 代码块被拒绝；`fragment:` 块做语法检查但需显式输入，不单独执行。`external-test:` 块仅经手动外部命令运行。QA 在通过的检查上返回 0，代码、schema 或身份失败返回 1，传输、认证或配额不可用返回 2；未配置的可选服务保持 SKIP。

本地执行验证（从仓库根目录）：
```bash
# 运行全部 571 项单元测试与严苛回归套件
pytest

# 运行代码块静态语法与独立执行检查
python scripts/qa.py
```

固定版本的技能编写规范测试（authoring tests）被复用，其逐技能规则不改动。完整 Hermes 上游发行包的全局测试不适用于本 tap；本仓库测试覆盖全部十三个技能，并按固定的捆绑与可选目录解析参考文件。这不是完整的 Hermes 安装测试。CI 仅在安装依赖时使用网络；常规 PR 测试不调用学术 API。

CI 经 GitHub Actions 覆盖 Linux x86_64（Python 3.10-3.14）、Linux ARM64（ubuntu-24.04-arm）、Ubuntu 26.04 预迁移 Canary（ubuntu-26.04 与 ubuntu-26.04-arm）、Windows x86_64、Windows ARM64（windows-11-arm）、macOS ARM64（macos-latest）与 macOS Intel（macos-15-intel）全平台全架构，全仓 571 项单元测试全部通过，并附带针对上游 main 最新分支的实时 Canary 加载检验。另有一个 tap 集成工作流在 main 推送时运行：安装 tests/upstream/provenance.json 所记录的固定 Hermes 检出，并针对本仓库执行 tap add、search、install 与 list。确切版本、检查项与限制见[审计文档](docs/audit-20260906.md)。

tools/longtail/ 存放确定性极端长尾场景生成器：4096 个 SHA256 种子候选组合铺满解耦因子轴，贪心覆盖选择，generated-scenarios.json 内附机器计算的覆盖报告。它是压测技能的输入层；语义展开（任务链、判据、注入事件）是独立阶段。

scripts/scfabric/ 是科学计算执行层：硬件探针、带 dtype 门禁的后端目录、五个工作负载画像、带数值等价检查的配对基准与 ComputeReceipt。本机首轮实测见 [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md)；经验规则是默认 CPU，加速器只凭 receipt 启用。

## 研究与规划文档

这两份文档是探索性规划参考，不是强制路线图。其中的方向数字按 docs/direction-primitive-mapping.json 的入库归组重算。

- [痛点图集 v0（英文）](docs/pain-atlas-v0.en.md)与[中文版](docs/pain-atlas-v0.zh.md)：按生命周期枚举学术知识工作摩擦，定量论断标注核实状态。
- [研究计划 v0（英文）](docs/research-plan-v0.en.md)与[中文版](docs/research-plan-v0.zh.md)：十四原语架构、Research Object 模型、四平面、候选方向与阶段一因子分解矩阵。
