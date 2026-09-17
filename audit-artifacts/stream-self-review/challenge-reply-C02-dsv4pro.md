# 质询答复 C02:对议题包"cluster_issues 单模型多 findings 误标多主体状态"的定向核验

- 质询方:dsv4pro
- 议题包:bundle-C02.json(Proposal-A,P0)
- 核验对象:orchestrate_v2.py cluster_issues(第 293-347 行)及 stop-process-20260917 真实运行产物

## 第一步【提取增量】

对方提出的缺陷链在此前材料中未见记载,属新增量。其内容为四点:其一,orchestrate_v2.py 第 311 行 `if len(items) == 1:` 以 findings 条数作为聚类判定单元,而非去重后的模型数;其二,该实现与第 325 行注释"# 2 个及以上模型命中同一 target"直接矛盾,即实现与作者意图错位;其三,本轮 stop-process-20260917 真实运行中 consensus 项全部为假,I12(单模型 gemini38flash 两条 findings)与 I14(单模型 gemini31pro 三条 findings)被标为 consensus,contradiction 项中 I06、I08、I16 亦为单模型;其四,现有测试套件 test_cross_review_five_v2.py 的 test_cluster_issues 未覆盖此边界。

我在此基础上有两条延伸增量,对方未点明。第一,假共识项处在三重失位:consensus 从不进入 challenge 选题(stage_merge_v2 第 415-473 行只遍历 contradictions 与 P0/P1 singletons),假共识项零质询;少数派保护逻辑(stage_synthesize_v2 第 602-612 行)只扫 registry["singletons"],假共识项不在 singletons 内,连未决账本保护也失去。第二,假矛盾项按 by_target 插入顺序排列,若排在真矛盾之前,会挤占 challenge 配额,把真实分歧挤出质询名单。本轮三个配额恰好全被 I01/I02/I03 真矛盾占用,属侥幸。

## 第二步【核验反例】

我对对方四条证据逐一独立复核,并主动寻找可证伪的反例。

对方证据一行号:我实读确认第 311 行为 `if len(items) == 1:`,第 325 行注释原文为"# 2 个及以上模型命中同一 target"。行号与内容全部吻合。

对方证据二 registry:I12 的 raised_by 为 ["gemini38flash"],claims 两条均为 gemini38flash,state=consensus;I14 的 raised_by 为 ["gemini31pro"],claims 三条均为 gemini31pro,state=consensus;I06 的 raised_by 为 ["dsv4pro"],三条 claims 均为 dsv4pro,state=contradiction;I08 的 raised_by 为 ["glm53"],两条 claims 均为 glm53,state=contradiction;I16 的 raised_by 为 ["gemini31pro"],两条 claims 均为 gemini31pro,state=contradiction。全部吻合。

对方证据三 report:consensus-report.md 第 13-22 行确实将 I12、I14 列入"## 一、高度共识项 (Verified Consensus)"区块,提出方各仅一个模型。吻合。

对方证据四探针:我独立编写探针脚本 probe_cluster_c02.py 与 probe_cluster_c02b.py(位于本答复同目录)复现。probe1 输出 `[('a.py', ['m1'], 'consensus')]`,与对方结果逐字一致;probe2 证明单模型两条 findings 仅因 kind 不同即误标 contradiction;probe5 证明 claim 含"不"字(对应 I06/I08 真实 claim 中"不再提示"形态)误标 contradiction;probe6 证明 claim 含"错"字(对应 I16 真实 claim 中"目标绑定错误"形态)误标 contradiction;probe4 对照证明真双模型同 target 路径正常。

反例尝试全部落空。我尝试了三个反驳方向:其一,提取阶段是否去重了同模型同 target 条目?extract_findings_json 无去重逻辑,findings-gemini38flash.json 中 F10 与 F15 同为 target "tools/terminal_tool.py"、同为 kind observation 且共存,已实读确认。其二,raised_by 单模型是否因去重丢失了其他模型?claims 数组内同样只有单模型条目,无丢失。其三,这是否是聚合设计意图而非缺陷?第 325 行注释明示作者意图按模型数判定,state 字段语义与报告措辞("提出方""Verified Consensus")均按多主体设计,注释与实现矛盾坐实为缺陷。

边界条件补充,均不构成反例,反而说明缺陷面更宽。补充一:normalize_target 截除行号并小写化(第 221 行),使同一模型对同一文件的多个不同发现归一为同一 target,F10/F15 即为此形态,放大了触发概率。补充二:反向失真同样存在,approval_detection.py 在本轮 findings 中有三种路径写法,被拆成 I01(短名)、I13(tools/ 前缀)、I14(全路径)三个 cluster,同一对象既可能过度合并也可能过度分裂。

## 第三步【分歧归因】

根因是代码实现层面的确定性缺陷,不属于证据不足,也不属于规范解读差异。证据链完全闭合:实现代码(orchestrate_v2.py 第 311 行判定单元)与作者注释(第 325 行)矛盾;真实运行产物五例失真;双方独立探针一致复现;测试套件存在盲区。四项交叉印证,机制层面无任何分歧空间。唯一可能讨论的余量是 severity 档位,我核验后果链后认为 P0 成立:本轮 consensus_count=2 全部为假,"高度共识项"章节整体失真,且假共识绕过质询环节与少数派保护账本。

## 第四步【裁决与表态】

【CONCEDE】

我认同并吸收对方全部断言。cluster_issues 的聚类判定单元是 findings 条数而非去重模型数,同一模型对同一 target 的多条 findings 被错误标注为 consensus 或 contradiction,最终报告将单模型观点呈现为"高度共识项 (Verified Consensus)"。对方给出的代码行号、运行产物实例、探针复现全部经过我的独立复核,无一处失实。severity P0 亦成立:此缺陷污染报告核心章节的可信度,且假共识项无质询、无账本保护,属于生产使用前必须修复的阻断项。

修复方向建议:第 311 行判定改为按去重模型数分组,单模型多条 findings 聚合并为一条单例条目(claims 保留原文),仅当 `len({x["model"] for x in items}) >= 2` 时才进入多主体分支判定 consensus 或 contradiction。修复后回归验收的最小测试用例为三组:其一,单模型对同一 target 两条 kind 相同且无冲突词的 findings,断言不产生 consensus 条目;其二,单模型双 findings 含"不"或"错"字,断言不产生 contradiction 条目;其三,两模型各一条同 target findings,断言仍产生 consensus 条目且 raised_by 含两个模型。三组用例可直接并入 test_cross_review_five_v2.py 的 test_cluster_issues。

核验资产:探针脚本 probe_cluster_c02.py 与 probe_cluster_c02b.py 保存在本答复同目录,输出结果与对方探针一致,可供复核。
