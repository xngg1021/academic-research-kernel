# 流水线各阶段核对要点

十四个阶段按序核对。每阶段记录一种状态：`pass`（核对通过且有证据）、`fail`（负面事实，如依赖装不上）、`mismatch`（与论文声称矛盾）、`missing`（应有的产物不存在）、`blocked`（外部条件阻断，如数据集需申请未获批）、`skipped`（本阶段不适用，配合 waived 与 reason）、`unknown`（未核对或证据不足）。

前六阶段（identity 到 dataset 前的 repo 侧核对）多数可以离线或半离线完成；dependencies 之后必须真实动手。证据写进 `evidence` 字段：哪个页面、哪条命令、哪段输出，一句话能复核。

## 1. identity 论文身份

确认论文本身：DOI/arXiv ID 解析出的标题、作者、年份与手头文本一致。Crossref、OpenAlex、arXiv 元数据至少两源一致；有 `academic-source-verification` 的证据回执时用 `--evidence-receipt` 并入，但身份确认仍要你自己判。

## 2. code-link 官方代码链接

找论文给出的官方代码地址：论文主页、arXiv 页面 Code 栏、项目页、作者主页。只信论文或作者本人指向的链接；搜索引擎排名第一的仓库不算官方。找不到记 `missing`——这是 tier `no-code-found` 的直接依据。

## 3. repo-identity 仓库身份

确认仓库与论文的对应关系：仓库 README 引用该论文、作者账号或其实验室账号持有、提交历史与论文时间线相容。第三方复现仓库在 `repository.officiality` 标 `third-party`；无法确认标 `unknown`。仓库张冠李戴（README 引的是另一篇）记 `mismatch`。

## 4. version-consistency 论文与代码版本/日期一致性

论文版本（v1/v2、会议版/期刊版）与代码声称对应的版本是否一致：README 是否注明对应论文版本，代码最后大改是否晚于论文关键实验。论文 v2 改了方法而仓库停在 v1 记 `mismatch`；仓库没有版本信息记 `unknown`。

## 5. release-commit 固定 release 或 commit

复现必须钉住一个点：有 release 用 release tag，没有用 commit hash，写进 `repository.commit` / `repository.release`。浮动 main 分支上的"复现"无法复核。

## 6. dataset 数据集

论文用的数据集是否可得：公开下载、需申请、还是已下线。记录数据集名称与版本/切分；需申请未获批记 `blocked`，论文自称私有数据记 `missing`。许可限制写 detail。

## 7. model-weights 模型权重

预训练权重是否发布；未发布记 `missing`。纯训练-free 方法（解析解、检索式）没有权重是正常形态，`skipped` + `waived: true` + reason。

## 8. dependencies 依赖环境

依赖声明是否完整可解析：requirements/pyproject/environment.yml 是否钉版本，Python 与 CUDA 版本要求是否写明。声明缺失、版本互相冲突、依赖已下架（旧包从源里消失）都记 `fail`。建议独立虚拟环境试装，不污染主环境。

## 9. license 许可证

代码、数据、权重三者的许可证分别是什么；无 LICENSE 文件记 `missing`，三者条款互相冲突（如代码 MIT 但权重禁商用且你要商用）写 detail。仅学术用途的限制必须如实写进收据。

## 10. build-install 构建安装

按仓库说明在干净环境里安装是否成功：编译错误、缺系统库、安装脚本本身坏都记 `fail`，错误首行写进 detail。

## 11. smoke-run 最小示例执行

跑 README 的 demo/quickstart/最小推理脚本，不跑全量训练。跑通记 `pass` 并记耗时与硬件；跑不记 `fail` 附报错首行。smoke 通过是 tier `runs` 的门槛。

## 12. claimed-metrics 论文声称指标

从论文表格/正文提取声称指标：指标名、数值、数据集切分、表号写进 `evidence`。只抄论文白纸黑字的数；论文没报的指标不要编。提取不到记 `fail`。

## 13. measured-metrics 实测指标

用钉住的 commit、论文同款切分，跑出实测值。评测脚本优先用仓库自带的；自写评测脚本时在 detail 里说明与论文描述的差异。

## 14. metric-diff 指标差异对照

声称值 vs 实测值逐项对照，容差写进 `tolerance`（如 ±0.5 个百分点、±1 个相对百分点）：

- 容差内一致 → `pass`（tier `numbers-reproduced`）
- 方向/趋势一致但数值超差 → `fail`（tier `direction-reproduced`）
- 方向都反了或矛盾到无法解释 → `mismatch`（status 直接判 `inconsistent`）

`claimed_value`、`measured_value`、`tolerance` 三个字段照实填，收据原样保留。

## 清单 JSON 格式

```json
{
  "schema_version": "1.0",
  "paper": {
    "title": "论文标题",
    "doi": "10.1234/example",
    "arxiv_id": "2401.00001",
    "venue": "Venue 2025",
    "published": "2025-03-01"
  },
  "repository": {
    "url": "https://github.com/<org>/<repo>",
    "officiality": "official",
    "commit": "<40位commit hash>",
    "release": "v1.0.0"
  },
  "stages": [
    {
      "id": "identity",
      "status": "pass",
      "evidence": "Crossref 与 arXiv 元数据一致",
      "checked_at": "2026-09-16"
    },
    {
      "id": "dataset",
      "status": "skipped",
      "waived": true,
      "reason": "论文使用纯合成数据，脚本已随仓库发布"
    },
    {
      "id": "metric-diff",
      "status": "fail",
      "claimed_value": 92.4,
      "measured_value": 90.1,
      "tolerance": "±0.5pp",
      "detail": "趋势一致，绝对值低 2.3 个点"
    }
  ]
}
```

规则：`paper` 至少带 title/doi/arxiv_id 之一；`stages` 里 `id` 必须是十四个之一且不重复，`status` 必须是七种之一；`waived` 只能配 `skipped`；没写的阶段引擎自动补 `unknown`（硬阶段有 unknown 就判 blocked）。`officiality` 取 `official / author-affiliated / third-party / unknown`。

判定规则与四态定义见 [adjudication.md](adjudication.md)。
