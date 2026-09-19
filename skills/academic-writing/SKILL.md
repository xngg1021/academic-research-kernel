---
name: academic-writing
description: 学术写作:润色编辑、引用规范生成、期刊投稿格式检索、AI 生成成分检测.
version: 1.1.1
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms:
- linux
- macos
- windows
tags:
- writing
- citation
- journal-submission
- ai-detection
- editing
metadata:
  tags: writing, citation, journal-submission, ai-detection, editing
  related_skills: literature-analysis, academic-source-verification, docx, pdf
---


# 学术写作 Skill

本技能包含六个工作流，涵盖学术论文辅助编辑、引用规范生成（支持 ISO 690:2021 国际基线、地区 Profile 与学科格式）、期刊投稿格式检索、AI 生成成分检测、投稿材料撰写，以及地区与机构学术规范。本技能与 `literature-analysis` 明确分工：后者面向论文阅读与分析，本技能面向学术写作与投稿。

核心原则：编辑不改作者原意与数据；引用条目不编造字段；AI 检测结果只作概率参考不作事实判定；期刊指南注明检索日期。输出语言默认跟随用户输入语言；引文与论文原文保留原文不翻译。

## When to Use

- 用户要求润色、修改或审查本地论文（支持 docx、pdf、md 与 tex 格式）
- 用户在 Overleaf/Word 在线等平台编辑，需要辅助编辑建议
- 用户要求"按 ISO 690/APA/MLA/Chicago/IEEE/GB-T 格式排参考文献"
- 用户要投稿某期刊，需要最新的投稿格式与引用规范
- 用户要求检测论文的 AI 生成成分比例
- 用户要求写投稿信、审稿回复信（rebuttal）或预印本提交材料
- 用户需要学位论文盲审格式核查、开题报告框架，或需要咨询中文期刊投稿与 CCF 目录

## 工作流 A：论文辅助编辑

输入：本地文件（`read_file` 可提取 docx/pdf 文本（当前 Hermes 上游支持，受转换依赖/大小限制）；md/tex 按文本读，扫描 PDF 需 OCR，版式核对仍须文档工具）、平台文本（用户粘贴）、或浏览器里的在线编辑器。

三层编辑，逐层执行并分开报告：

1. **语言层**：检查语法错误、时态一致性（方法用过去时，结论用现在时）、全文术语统一性与拼写。逐条给出“原文 → 修改后 → 理由”。
2. **结构层**：核对 IMRaD 结构（检查摘要是否具备目的、方法、结果与结论四要素），检查段落过渡、标题层级，并确认图表编号与正文引用对应。
3. **论证层**：每个 claim 是否有对应证据句；结论是否超出实验范围；"显著/证明/首次"等强措辞是否过火。

编辑规则（硬约束）：不改变作者原意，不增删数据，不确定的修改标"建议"而不是直接改；所有修改集中成 diff 式清单供用户逐条确认；docx 的实际写入用 `docx` 技能（python-docx）执行，改前先备份。

## 工作流 B：引用规范生成

用户选择风格后，按 `references/citation-styles.md` 的规则生成文中引用与文末参考文献条目。现行版本（2026 核查）：ISO 690:2021（国际基准）、APA 7th（2020）、MLA 9th（2021）、Chicago 18th（2024 年发布，注意部分机构仍指定 17th，先确认再排）、IEEE（持续更新）、AMA 11th（2020）、GB/T 7714-2025（2026-07-01 实施）；机构明确要求 2015 时沿用指定版本。

执行方式：

1. 让用户确认风格与目标刊物/机构要求（优先遵循目标刊物或学校规范；未指定时提供 ISO 690 或学科基准，不根据语言假定司法辖区规范）。
2. 逐条解析文献字段（包括作者、年份、标题、期刊或出版社、卷期页码以及 DOI），缺少字段时标注“【待补】”，严禁编造信息。
3. 按风格规则输出格式化条目 + 文中引用样例（正文内 (Author, Year) 或 [1] 式）。
4. 批量转换时输出对照表（原始信息 → 格式化条目），便于核对。

## 工作流 C：期刊投稿格式检索

用户给出期刊名 → 检索该刊最新投稿指南：

1. `web_search` 用"<期刊名> Instructions for Authors"（中文期刊用"<期刊名> 投稿须知 投稿指南"）找官网页面，优先期刊官网域名。
2. `web_extract` 抓取指南页，提取：字数/页数限制、摘要结构要求、正文结构、参考文献风格、图表规范（分辨率、格式）、投稿系统入口、审稿周期说明。
3. 输出"投稿清单"（逐项要求 + 来源链接 + 检索日期）。指南页若为动态渲染抓不到，检查当前浏览器后端：默认用 `browser_navigate` → `browser_snapshot`；browser-use 后端用其实际暴露的 `browser_exec`，不混用两套 schema，或如实说明只能拿到部分信息。

注意：投稿指南频繁改版，输出必须注明检索日期，并建议用户投稿前对照官网最终确认。

## 工作流 D：AI 生成成分检测（渠道聚合）

检测输出是产品定义的评分；未验证校准时不称“作者使用 AI 的概率”或真实 AI 占比。假阳性率随模型、语言、体裁、阈值和评估集变化，不能给所有检测器统一的 2%~7% 数值。

可选渠道：GPTZero、Copyleaks、Originality.ai。执行前查各自官方当前访问条件、额度、API 许可与最小长度要求；网页订阅不等于 API 权限，不在 skill 固化未经持续验证的价格。TextSight 等未核实渠道不作默认依赖。

无 key 时只给核实后的操作步骤；有 key 时通过环境变量读取，依实际端点文档执行。遵守各服务允许长度与上下文要求，不固定按 500~1500 词切分，也不将分段分数平均解释为全文 AI 比例。保留产品、版本/查询日、输入范围与原始分数；只能作为辅助信号。对用户未授权上传的未公开文稿，不自动发送给外部检测服务。

本地模型是否可用须按具体语言/语料独立评估，不对所有开源检测器作绝对结论。

## 工作流 E：投稿材料（投稿信 / 审稿回复信 / 预印本）

投稿信半页结构、rebuttal 三要素回应法、修改对照表三列格式、arXiv 提交材料清单。模板与语气规则见 `references/submission-letters.md`。不代用户注册账号或代提交，只生成材料与步骤。

## 工作流 F：地区与机构学术规范（Regional & Institutional Profiles）

学位论文盲审格式核查（以目标高校模板为最高优先级）、开题报告八段框架、地区期刊投稿规范、CCF 推荐目录查询（带年份与版本说明）。详见 `references/china-academia.md` 与 `docs/standards/README.md`。

## Procedure

1. 识别任务类型（编辑/引用/投稿指南/AI 检测）。
2. 编辑任务：先读原文，按语言、结构、论证三层出报告，改动集中列清单。
3. 引用任务：确认风格 → 解析条目 → 按 `references/citation-styles.md` 排版 → 输出对照表。
4. 投稿任务：检索 → 提取 → 输出带日期和链接的清单。
5. AI 检测：先声明局限，无 key 给渠道指引，有 key 执行分段检测。

## Pitfalls

1. **AI 检测结果不能当事实**。需说明分数定义与适用范围，不将未校准分数当概率或给出统一假阳性率，禁止输出"确认是 AI 写的"这类定性结论。
2. **引用条目禁止编造字段**。卷、期、页码、DOI 缺失就标【待补】，宁可让用户补，也不生成看似合理的假字段。
3. **Chicago 18 与 17 并存**。2026 年 CMOS 18 已出版但大量机构仍在用 17th，排版前必须确认目标要求，两个版本页码引用规则有差异。
4. **期刊指南时效**。Instructions for Authors 随时改版，输出必须带检索日期与来源链接。
5. **编辑不改原意**。学术论文润色最大的风险是"顺手改了结论表述"；任何影响语义的修改都要单独标出请用户确认。
6. **中文期刊引用风格**。GB/T 7714-2025 已实施；目标机构若指定 2015，遵从其版本，避免混用规则；作者名、期刊名的中英双语著录规则见 `references/citation-styles.md`。
7. **GBK 陷阱**。处理中文 docx/tex 时若脚本报编码错误，文本文件明确编码；docx 是 ZIP/XML 容器，用文档库读写，不能当 UTF-8 文本解码；Windows 默认编码依配置而异（参见 hermes-agent 技能 windows-quirks）。

## Verification

```python
# smoke-test: true
# 从已安装 skill 目录运行，或把 SKILL_DIR 环境变量设为该目录。
import os
from pathlib import Path
base = Path(os.environ.get('SKILL_DIR', '.')).expanduser().resolve()
text = (base / 'references/citation-styles.md').read_text(encoding='utf-8')
for style in ('APA', 'MLA', 'Chicago', 'IEEE', 'AMA', 'GB/T 7714'):
    assert style in text, f'引用风格 {style} 缺失'
for ref in ('submission-letters.md', 'china-academia.md'):
    assert (base / 'references' / ref).is_file(), f'{ref} 缺失'
print('academic-writing reference verification passed')
```

（AI 检测渠道依赖外部服务与用户自备 key，不进自检；期刊指南检索依赖 web_search，按需验证。）
