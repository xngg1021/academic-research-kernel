# hermes-academic-skills

面向 Hermes Agent 的十个中文学术技能：来源核验、文献分析、学术写作、数值计算、定量论文审计、复现审计、系统综述与元分析、研究对象身份与谱系，以及两个周更监控自动化。仓库附带可执行的示例检查；验证范围与外部服务限制记录于[审计文档](docs/audit-20260906.md)。

作者：Junfu Shi（SJF，xngg1021），Hermes Agent。当前授权范围：[Source Lineage License 1.0](LICENSE)。

## 许可证

含本通知的快照依据 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 所述范围，对其中识别出的受版权保护材料采用 **Source Lineage License 1.0**。首个 SLL 提交与树、以及其后的边界记录提交，分别在 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 与 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) 中区分。自该记录边界起保留本通知的快照，携带相同的授权范围。

截至 `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` 的历史快照按 MIT 许可分发，受适用于那些副本的条款约束。接收者保留有效的 MIT 权限，无需迁移至 SLL。[前项目 MIT 文本](LICENSES/MIT-pre-SLL.txt)已保存；[tests/upstream/LICENSE](tests/upstream/LICENSE) 及其第三方来源记录保持原状。新的根授权不抹除既有权利。

SLL 广泛允许使用、研究、修改、商用、分发与专有增补，受相应许可、通知与来源谱系条件约束。它不属 copyleft，不要求源码披露。纯网络服务且不提供副本者，不单独触发核心服务谱系通知条件。无明示专利授予。第三方材料仍受其自身条款约束。以英文原版 [LICENSE](LICENSE) 为准；`LicenseRef-Source-Lineage-1.0` 为本地引用，非 SPDX 指配，亦不声称 OSI 批准。[贡献接收](CONTRIBUTING.md)与下游许可权限相互独立。

## 技能

| 技能 | 版本 | 功能 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.1.1 | 交叉核对身份与来源特定的被引数；检查更新与撤稿信号；定位开放获取文本并核验 PDF 身份 |
| `skills/literature-analysis` | 1.2.0 | 十二个工作流：主题相似、局部文本重叠、反证、作者档案、模拟评审、谬误检查、评审矩阵、期刊候选、BibTeX、双语阅读、研究空白筛查、复现 |
| `skills/academic-writing` | 1.1.1 | 编辑、引文规范（APA、MLA、Chicago、IEEE、AMA、GB/T）、期刊须知、可选检测服务、投稿材料、中文学术要求 |
| `skills/math-computation` | 1.2.1 | 既有领域与任务路由及修正后的数值与统计示例；四篇领域参考文件 |
| `skills/quantitative-paper-audit` | 1.0.0 | 反算论文报告的统计量（效应量、p 值、置信区间、OR/RR、实现功效）并检测数值错配 |
| `skills/research-reproducibility` | 1.0.0 | 十四阶段复现审计流水线，含结构化清单引擎、五层事实与四态回执 |
| `skills/systematic-review-meta-analysis` | 1.0.0 | PRISMA 检索日志、筛选台账、效应量换算、异质性、固定与随机效应合并、敏感性与发表偏倚诊断 |
| `skills/literature-watch` | 1.0.0 | 周更蓝图：监控主题、作者与 DOI 在 OpenAlex 与 Crossref 的新作品；去重并只报告新增 |
| `skills/retraction-watch` | 1.0.0 | 周更蓝图：对照 OpenAlex is_retracted 与 Crossref 更新记录（update-to 信号）复查 DOI 监控清单；只报告状态变化 |
| `skills/research-object-identity` | 1.0.0 | 确定性研究对象身份层：标识符归一、五态判定（无置信分）、关系与谱系建边；消费 Evidence Receipt |

十个技能共含 21 篇 Markdown 参考文件，按需加载。GB/T 7714-2025 已生效；写作参考区分其已核实生效日期与显式标注的 2015 示例。完全符合 2025 版需以目标机构的模板或标准文本为准。

## 在 Hermes 中安装

当前上游 tap 发现机制检查 `skills/` 的直接子目录，因此每个技能直接位于该根目录下。在 Hermes 安装环境中执行：

```bash
hermes skills tap add xngg1021/hermes-academic-skills
hermes skills search academic-source-verification
hermes skills install xngg1021/hermes-academic-skills/skills/academic-source-verification
```

安装其余技能时替换完整标识符中的目录名。常规 tap 读取默认分支，新装即得上述技能集。如需在合并前检查工作分支，在本地检出该分支并遵循所装 Hermes 版本的本地目录安装说明。不要假定 tap 命令会选中 PR 分支。

捆绑相关技能以上游 `245e48008fa814b3251f50755eb656bd9fb86cb1` 为准核对：arxiv、grounded-citations、docx、pdf、manim-video。huggingface-hub 与 llama-cpp 在可选目录中，可能需另行安装。ocr-and-documents 与 pc-hardware-benchmark 在该快照中未找到，亦非依赖项。会话工具与文档及浏览器后端取决于本地配置。

## 数据源访问

技能通过公开学术 API 工作：OpenAlex、Crossref、Semantic Scholar、Unpaywall 与 arXiv。OpenAlex 匿名查询有每日预算；在 `~/.hermes/.env` 配置 `OPENALEX_API_KEY` 可放宽限制。任何技能都不要求付费账号；密钥只发给它所属的域名，绝不写入技能文件或聊天记录。

## QA 与测试

仓库 QA 校验元数据、参考文件、个人路径与已知密钥模式、Python 语法与标记过的可执行围栏。每个 smoke 示例在全新子进程中原样运行；绘图示例接受 `PLOT_DIR`（默认 `~/plots`，显式展开），测试使用临时目录。未分类的 Python 围栏被拒绝；`fragment:` 块做语法检查但需显式输入，不单独执行。`external-test:` 块仅经手动外部命令运行。QA 在通过的检查上返回 0，代码、schema 或身份失败返回 1，传输、认证或配额不可用返回 2；未配置的可选服务保持 SKIP。

固定的 Hermes 作者测试被复用，其逐技能规则不改动。上游全分布总体检查不适用于本 tap；本仓库测试覆盖全部十个技能，并按固定的捆绑与可选目录解析参考文件。这不是完整的 Hermes 安装测试。CI 仅在安装依赖时使用网络；常规 PR 测试不调用学术 API。

CI 经 GitHub Actions 在 Ubuntu（Python 3.12 与 3.13）、Windows 与 macOS 上运行完整 QA 套件。另有一个 tap 集成工作流在 main 推送时运行：安装 tests/upstream/provenance.json 所记录的固定 Hermes 检出，并针对本仓库执行 tap add、search、install 与 list。不声称全新 Hermes 会话与每种依赖版本组合已验证。确切版本、检查项与限制见[审计文档](docs/audit-20260906.md)。

## 研究与规划文档

- [痛点图集 v0（英文）](docs/pain-atlas-v0.en.md)与[中文版](docs/pain-atlas-v0.zh.md)：按生命周期枚举学术知识工作摩擦，定量论断标注核实状态。
- [研究计划 v0（英文）](docs/research-plan-v0.en.md)与[中文版](docs/research-plan-v0.zh.md)：十四原语架构、Research Object 模型、四平面、候选方向与阶段一因子分解矩阵。
