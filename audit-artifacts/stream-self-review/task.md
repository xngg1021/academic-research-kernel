# 任务书:五人组 v2 编排器自我评审

## 评审对象

您正在评审的工具,正是本次评审所运行的编排器自身:cross-review-five 技能的 v2 版本(orchestrate_v2.py,约 31KB,四阶段 Sparse Deliberation 架构)。这是编排器对自身代码的自我评审,请不要因为"评审用的就是它"而对它手下留情。

## 指定材料(只读)

1. <HERMES_HOME>\skills 之外的仓库路径:
   - <WORKSPACE>\repos\hermes-academic-skills\skills\cross-review-five\scripts\orchestrate_v2.py —— 评审主对象,请完整实读。
   - <WORKSPACE>\repos\hermes-academic-skills\skills\cross-review-five\scripts\orchestrate.py —— v1 版本(约 8KB),对比基线。
   - <WORKSPACE>\repos\hermes-academic-skills\tests\test_cross_review_five_v2.py —— v2 测试套件(6 项)。
   - <WORKSPACE>\repos\hermes-academic-skills\skills\cross-review-five\SKILL.md —— 文档与用法声明。
2. v2 的实际运行产物(证据抽查,用于核对"代码声明与真实行为是否一致"):
   - <WORKSPACE>\cross-reviews\stop-process-20260917\findings-*.json(五份结构化发现)
   - <WORKSPACE>\cross-reviews\stop-process-20260917\issue-registry.json
   - <WORKSPACE>\cross-reviews\stop-process-20260917\challenge-plan.json
   - <WORKSPACE>\cross-reviews\stop-process-20260917\consensus-report.md
   - <WORKSPACE>\cross-reviews\stop-process-20260917\unresolved-ledger.json

## 评审维度

一、算法正确性:cluster_issues(共识/单例/矛盾聚类)、compute_complementarity_matrix(互补权重)、max_weight_derangement(最大权错排)、normalize_target(目标归一化)的实现是否正确,有无边界条件错误(空 findings、单模型、相同 claim 不同措辞)。

二、流程健壮性:子进程超时(40 分钟)、findings JSON 解析失败(extract_findings_json 的降级路径)、单个模型产出缺失、challenge 阶段 bundle 与计划项的对应关系、中断后重跑的幂等性。

三、经济性:SKILL.md 声明的三档模式调用次数(economy 3-4 次、standard 7-8 次、audit 10-12 次)与 MODE_PRESETS 及实际拓扑是否一致;merge/synthesize 是否真零 LLM 消耗。

四、文档一致性:SKILL.md 的用法示例、参数名、阶段名与实际 CLI 是否相符。

五、设计性质疑(请大胆):匿名质询是否真匿名(评审者能否从 bundle 内容推断被审模型身份);少数派证据保护(有定位符的独立发现进 unresolved-ledger)的实现是否严密;findings JSON 依赖模型自觉落盘的脆弱性;PLAN_PROMPT_V2 与 CHALLENGE_PROMPT_V2 的提示词质量;与 v1 相比,复杂度上升是否换来了对应价值。

六、测试覆盖:test_cross_review_five_v2.py 的 6 项测试覆盖了哪些关键路径,遗漏了什么。

## 产出要求

1. 完整评审意见写入您的输出文件,用简体中文,按您自然的文风写作。
2. 结构化发现按 findings JSON 规范填写,每条发现给出:target(指向的具体代码位置或文件)、claim(判断)、evidence(您实际读到的证据,含行号或关键行原文)、severity(P0/P1/P2)。
3. 每条关键判断附证据引用,不得虚构不存在的文件、行号或接口。
4. 结论部分明确回答:这个 v2 编排器当前是否值得信任用于生产评审?哪些缺陷必须在下次使用前修掉?

## 纪律

只读任务书与指定材料;不得修改任何其他文件;不得修改其他评审者的产出文件;产出必须基于实际读到的内容。
