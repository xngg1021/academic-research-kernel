# 五人组 v2 编排器自我评审报告(kimi-k3)

评审对象:`orchestrate_v2.py`(735 行),对比基线 `orchestrate.py`(199 行),测试套件 `test_cross_review_five_v2.py`(177 行),文档 `SKILL.md`(107 行),以及 stop-process-20260917 任务流的全部指定产物。

评审方法:四份代码与文档文件逐行实读;运行产物全量实读;对算法行为编写了只读探针脚本(置于系统临时目录,不触碰任何被审文件)直接导入 `orchestrate_v2.py` 执行验证;对产物目录做了关键词检索以确认 findings JSON 的来源。下文每条判断附行号或文件证据,探针输出在第十节归档。

## 一、算法正确性

### 1. cluster_issues 把同一模型的多条 findings 聚成多模型共识与矛盾(P0)

`orchestrate_v2.py:310-345` 的聚类条件是 `len(items) == 1` 判单例,否则进入"2 个及以上模型命中同一 target"分支(第 325 行注释原文)。这个条件数的是 findings 条数,不是去重后的模型数。同一模型对同一 target 写出多条 findings 时,`len(items) > 1` 而 `raised_by` 只有一个模型,条目仍被打上 consensus 或 contradiction 标签。

生产证据:`issue-registry.json` 的 I12(state=consensus,raised_by 仅 gemini38flash,2 条 claims)、I14(state=consensus,raised_by 仅 gemini31pro,3 条 claims,P0)、I06(state=contradiction,raised_by 仅 dsv4pro)、I08(state=contradiction,raised_by 仅 glm53)、I16(state=contradiction,raised_by 仅 gemini31pro)。16 个 issue 里 5 个是这种单模型伪多模型聚类。探针用单一模型、同一 target 两条 findings 复现:输出 `consensus: [('a.py', ['m1'], 'consensus')]`。

最终后果落在 `consensus-report.md` 第 11-22 行:"高度共识项 (Verified Consensus)"章节列出 I12 与 I14,提出方各只有一个模型,I14 还是 P0。任何读者都会把"Verified Consensus"理解为多模型交叉确认,实际是一家之言的复述。

### 2. 矛盾判定启发式把一致意见标成对立(P0)

`orchestrate_v2.py:326-332` 的判定是:kinds 集合大小超过 1,或任一 claim 含有"不"字、"错"字,即判 contradiction。中文技术写作里"不存在""不再提示""未覆盖"是常态措辞,kind 字段在不同模型间自由取值(bug、observation、suggestion 混用)也是常态。这条启发式因此几乎必然误报。

生产证据:8 条 contradictions 逐条读过,没有一条是断言层面的对立。I01 五个模型一致确认 Windows 侧缺无差别杀进程的硬线规则与自毁保护的 POSIX 偏向,措辞方向完全相同;I02 三个模型一致指出测试缺口;I04 四个模型一致归因目标绑定错误。它们被判矛盾,是因为 kinds 不同且 claim 含"不"字。真正存在的分歧(kill -9 -1 归属硬线层还是危险层、是否该在静态分类器里注入主机上下文)是子断言级别的,出现在 challenge-reply-C01-gemini38flash.md 第 19-26 行的反证里,target 级聚类根本看不见。

连带伤害:standard 模式 `max_challenges=3`,三条质询配额被 I01、I02、I03 这三组伪矛盾占满(`challenge-plan.json`),`orchestrate_v2.py:443-446` 的高危单例质询一段因此轮空,P0 单例 I05(agents.md 硬纪律,kimi-k3 提出)从未被任何他模型核验。

### 3. normalize_target 不做路径等价归一,聚类被路径写法打碎(P1)

`orchestrate_v2.py:215-222` 只做小写化、反斜杠替换与尾部行号截除。同一个文件在 registry 里裂成多个 target:approval_detection.py 出现 3 种写法(I01 裸文件名、I13 tools/ 前缀、I14 全路径归一化后的 `<USER_HOME>/appdata/...`),test_approval_windows.py 出现 3 种,scan_history.py 与 approval.py 各 2 种。探针按 basename 归并后,16 个 issue 塌缩为 10 个真实文件。真共识被拆成"单例",伪单例又反过来污染少数派保护账本。`compute_complementarity_matrix`(225-269 行)的 Jaccard 重合度在同一套碎 target 上计算,互补权重矩阵的语义同步失真。

另一处同源缺陷:fallback 正则 `[\w/\\.-]+`(192 行)不匹配盘符冒号,`C:\Users\...` 被抓成 `\Users\...`,normalize 后变成 `/users/...`;正则片段 `cli\.py` 被抓成文件引用,normalize 后变成 `cli/.py` 这个不存在的路径(探针实测 `normalize_target('cli\\.py') -> 'cli/.py'`),最终以 P0 身份进入 I11、未决账本与共识报告第二节。

### 4. 其余算法细节

`max_weight_derangement`(272-290 行)对 5 模型穷举 120 种排列,正确且够用;n≥2 时错排必然存在,第 288-289 行的 fallback 分支是死代码。`compute_complementarity_matrix` 第 264-266 行注释写"同一目标,检查是否有矛盾",实现是无条件加 0.5 分,注释与实现不符。第 337 行 severity 取最大值用 `{"P0":3,...}.get(s, 0)`,小写 `"p0"` 会按 0 计。

## 二、流程健壮性

### 5. findings 结构化层完全靠启发式兜底生成,且无来源标记(P1)

这是本次评审最重要的实证发现,证据链有三环。第一环:`stop-process-20260917/prompt-kimi-k3.txt` 全文 11 行,逐字比对确认是 v1 的 `PLAN_PROMPT`(`orchestrate.py:44-55`),通篇没有 findings、JSON、结构化字样;该任务流的 task.md 同样没有这些要求。也就是说,那次运行的 plan 阶段从未向五个模型索要结构化发现。第二环:对五份 review-*.md 检索 "findings"、"severity"、代码围栏,命中数为零,五个模型也确实没有主动补写。第三环:五份 findings-*.json 呈现完全一致的兜底特征——kind 只有 bug 与 observation 两种(规范允许六种),claim 一律在第 140 字符处硬截断(截在词中间,如 "fork bom"、"full terminal/fi"、"定向 PI"),evidence 只有单个定位符,unknowns 与 assumptions 全空。

结论:那次生产运行的"结构化 Issue 拓扑"全部来自 `extract_findings_json` 第 186-212 行的正则启发式,没有一条是模型自己声明的。启发式把 kimi-k3 正文的"材料范围:任务书指定材料全部实读……"这种流程说明抓成 P2 finding(findings-kimi-k3.json F1),它还作为 Proposal-1 混进 C01 质询包;把 gemini38flash 引用检测规则的一行抓成 P0 finding(findings-gemini38flash.json F9,即 cli/.py 幽灵)。兜底产物经第 180-181、210-211 行落盘为 sidecar 文件,与模型亲笔 JSON 在外观上不可区分,下游与消费者无法分辨来源。

这里要替模型说一句公道话:这不是模型不遵守指令,是运行方混用了 v1 提示词与 v2 后段。但它暴露了编排器的真问题——merge 与 synthesize 对"上游是否请求过结构化产出"毫无校验,对兜底产物与亲笔产物不做任何区分与提示。PLAN_PROMPT_V2 的引导能力因此也没有任何生产证据支撑,现有唯一一次运行从未送达过它。

### 6. 质询答复与计划失配时静默通过,报告无任何警示(P1)

`challenge-plan.json` 规划了 C01、C02、C03 三组质询,产物目录里只有 `challenge-reply-C01-gemini38flash.md` 一份答复,且 bundle-C01.json、prompt-challenge-*.txt、log-challenge-*.txt 全部缺失,这次质询的执行过程无法从产物复原。`stage_synthesize_v2`(577-581 行)只 glob 现存的 reply 文件,不回读 challenge-plan 核对缺哪些,`consensus-report.md` 头部计数"Conceded: 1 项、Refuted: 0 项"看起来一切正常,读者无从知道三分之二的质询没有完成。

### 7. 表态解析是文件级单标签,混合表态被吞(P1)

`orchestrate_v2.py:589-594` 用 if-elif 链按子串匹配整份答复:先 CONCEDE,再 REFUTED,再 UNRESOLVED,一份文件只归一类。CHALLENGE_PROMPT_V2 却要求"对议题包中的每个断言"逐一表态,提示词与解析器粒度天然错配。生产实证:C01 答复同时包含三种表态(第 43、48、52 行),报告只记了 Conceded。被丢弃的 REFUTED 恰恰是这次运行最有价值的产出——答复用第 116 行硬线正则的短路匹配证伪了另一模型"kill -9 -1 归第 278 行危险层"的断言,这条纠偏在最终报告与未决账本里彻底消失。UNRESOLVED 项(管道形态是否该入硬线层)同样消失。子串匹配还有一层脆弱:答复里写"我方不 CONCEDE"也会命中。

### 8. 其他健壮性观察

单模型失败会把整个阶段判负:`wait_for_outputs`(142-153 行)要求全部产物落盘且全部进程退出,`--stage all` 在 plan 失败后直接 return 1 中止(722-723 行),其余模型的有效产出没有降级续跑通道。幂等性有两处坑:`extract_findings_json` 第 158-164 行无条件优先采用已存在的 sidecar,重跑 plan 后上一轮的旧 findings 会压过新 review;`cluster_issues` 第 336 行 `raised_by` 由集合转列表,第 421 行取 `raised[0]` 选质询者,探针用四种 PYTHONHASHSEED 得到三种不同的首元素,同一输入两次 merge 可能产出不同质询者。sidecar 若是合法 JSON 但不是对象(比如一个数组),第 160-162 行原样返回,下游 `cluster_issues` 的 `.get` 会以 AttributeError 崩溃(探针实测),extract 层没有任何结构校验。

## 三、经济性

merge 与 synthesize 真零 LLM 消耗,属实:两个阶段的代码只读写本地 JSON 与 Markdown,spawn 只出现在 plan 与 challenge。这是 v2 相对 v1 的真实收益。

SKILL.md 的三档次数声明与代码拓扑不符。按 `MODE_PRESETS` 推算(探针第 5 项):economy 为 3 加 0 至 1,合计 3-4 次,与文档一致;standard 为 5 加 0 至 3,合计 5-8 次,文档写 7-8 次,下限虚高(零矛盾零高危单例时只有 5 次调用);audit 为 5 加 0 至 5,合计 5-10 次,文档写 10-12 次,上限永远到不了——错排匹配与矛盾、单例质询共享同一个 `max_challenges=5` 配额(`orchestrate_v2.py:472-492`),不是文档暗示的"5 条错排边之外再加关键弦"。文档第 61 行"压降 60%+ 上下文消耗"在代码里没有任何测量对应物,列入未决事项。

## 四、文档一致性

除上述次数声明外,还有四处。SKILL.md 第 78 行写"任务书模板与约束见脚本内的 PLAN_PROMPT 与 REVIEW_PROMPT",v2 脚本里实际叫 PLAN_PROMPT_V2 与 CHALLENGE_PROMPT_V2,REVIEW_PROMPT 只存在于 v1。frontmatter 版本号仍是 1.0.0,与文档已承载 v2 工作流的事实不符。第 56 行宣称 challenge 是"匿名议题包",实现并不匿名(见下节)。阶段名、--mode、--models 等 CLI 参数与文档示例一致,这部分没有问题。

## 五、设计性质疑

### 9. 匿名质询不匿名,三条独立泄路(P1)

第一条,质询者恒为争议当事人。`orchestrate_v2.py:421` 的质询者选取是 `raised[0]`,第 419 行注释宣称"挑选涉及该矛盾的两方中未质询过的一方",实现里没有这句话对应的任何逻辑。生产证据:C01、C02、C03 的质询者分别是 gemini38flash、glm53、gemini38flash,全部在各自 issue 的 raised_by 名单里,且 bundle 里含有质询者本人写的 claim。C01 答复第 13 行直白承认了这一点:"已在我方独立评审中完成覆盖,不属于新增量"——质询者认出了自己的文字。第二条,提案顺序泄露身份。C01 bundle 的 28 条提案按 kimi-k3 九条、dsv4pro 六条、glm53 六条、gemini38flash 四条、gemini31pro 三条排列,与 standard 模式 models 列表顺序逐项对齐;任何读过 `orchestrate_v2.py` 的评审模型(本次任务材料就包含该文件)都握有解密密钥。第三条,claim 原文保留第一人称叙事与行文指纹("本机同一部署拦下……"这类自报实验的句子),风格即可辨认。匿名是纸面设计,实现层面从未成立。

### 10. 少数派证据保护两头失守(P1)

代码注释(596-597 行)承诺保护"未被质询直接证伪"的附证据单例,实现(598-608 行)是无条件收录:凡是 severity 为 P0/P1 且 evidence 非空的单例一律进账本,不检查它是否曾被质询驳回,也不检查证据内容是否有效。过宽的一面:幽灵路径 `cli/.py` 以 P0 身份被"保护"进 `unresolved-ledger.json` 与共识报告,兜底噪声获得了机制的背书。过窄的一面:保护只认 singleton 这个聚类状态,矛盾簇里的少数派断言没有任何保护通道,而矛盾簇本身又是误判高发区。

### 11. 提示词评价

CHALLENGE_PROMPT_V2 是全套代码里质量最高的部分:四步强制顺序、增量优先于表态、CONCEDE 机制、禁止多数票压倒附证据少数派,这些条款直接塑造了 C01 答复的专业水准。它的缺口在于没有 bundle 体量指引(C01 塞进 28 条提案,含一条流程说明噪声),表态令牌按单条断言设计而解析按文件执行。PLAN_PROMPT_V2 的 findings 要求埋在长文第四步,前面分析过,它的生产引导效果目前零证据;更稳妥的做法是把结构化产出写成独立短指令并要求先落 findings 再写正文,或在 merge 前校验 sidecar 缺失时显式告警。

### 12. v1 到 v2 的复杂度是否换来了价值

v1 是 10 次调用的全文轮转互审,产出五份互审意见供人阅读。v2 standard 是 5 至 8 次调用,省下的成本真实存在,四阶段架构(独立盲审、本地聚类、定向质询、证据保护)的方向也正确。但这次生产运行里,聚类层把一致意见标成对立、把一家之言标成共识;匿名层从未成立;质询层产出了一条高价值纠偏,综合层把它丢了;最终报告呈现给读者的是两条伪共识加一个幽灵 P0。架构挣来的每一分价值,都在实现层漏掉了。结论不是方向错了,而是实现还没有兑现设计承诺。

## 六、测试覆盖

六项测试里,`test_v2_model_table_and_presets` 与 `test_max_weight_derangement` 只覆盖常量与愉快路径;`test_normalize_target` 四个断言不含正则片段、不含裸盘符;`test_cluster_issues`(57-93 行)让三个模型的 target 互不相交,恰好绕开了本次生产事故的同模型多条 findings 场景,也没有断言 consensus 必须满足两个以上模型;`test_extract_findings_fallback_markdown`(96-129 行)只测 ```json 代码块提取路径,第 186-212 行的启发式兜底——生产里五比五命中的路径——完全无测试;`test_merge_and_synthesize_end_to_end`(132-177 行)第 174 行注释写明要验证 P0 单例进账本,实际断言行(176-177 行)只查了报告标题字符串,账本内容一个字也没断言。完全缺席的测试面:质询者当事人回避、表态 elif 链、缺失答复时 synthesize 的行为、sidecar 非对象崩溃、重跑幂等、wait_for_outputs 超时分支。

## 七、结论:当前是否值得信任用于生产评审

不值得,以现状直接用于生产评审会产出看似权威实则变形的结论。这次 stop-process 运行的最终报告就是样品:真正的五模型一致意见被归入"争议"且在终报中消失,单模型观点以"Verified Consensus"名义呈现,不存在的文件以 P0 身份进入未决账本,质询阶段最有价值的纠偏被解析器吞没,三分之二的质询缺失而报告只字未提。

下次使用前必须修掉的缺陷,按优先级:

1. cluster_issues 按去重后的模型数判定共识与矛盾(单模型多条 findings 永远不得进入 consensus 与 contradiction),同时把矛盾判定从"kind 不同或含否定字"换成至少基于 blocking 冲突或显式反对标记的保守判定,判不出就进人工复核队列而不是硬贴标签;
2. normalize_target 增加 basename 归并与项目根相对化,fallback 正则排除盘符截断与正则片段;
3. 表态解析改为按【CONCEDE】/【REFUTED】/【UNRESOLVED】令牌逐条抽取,答复与质询计划逐项对账,缺失答复在报告中显式列出;
4. consensus-report 增加矛盾章节与质询答复章节,共识章节只放真共识;
5. 质询者选取实现注释承诺的回避逻辑(排除当事人),并打乱 bundle 提案顺序;
6. 少数派保护接入质询结果(已被证伪的不进账本),fallback 产物在 sidecar 与 registry 里打来源标记;
7. SKILL.md 调用次数改为与代码一致的 5-8 与 5-10,或调整代码使拓扑与文档承诺对齐。

修复 1、3、4 之后,这套架构值得再给一次生产试运行;修复全部七条之后,它才配得上文档里写的那些机制名称。

## 八、探针验证记录

探针脚本 `probe_oc2.py` 置于系统临时目录,只读导入 `orchestrate_v2.py` 与 stop-process 产物,未修改任何被审文件。关键输出:normalize_target('cli\\.py') 返回 'cli/.py';单模型双 findings 同 target 聚类返回 `[('a.py', ['m1'], 'consensus')]`;四种 PYTHONHASHSEED 下 `list(raised_set)[0]` 出现 dsv4pro、gemini31pro、gemini38flash 三种取值;合法 JSON 数组在下游触发 `AttributeError: 'list' object has no attribute 'get'`;三档模式调用区间推算为 economy 3-4、standard 5-8、audit 5-10;registry 十六个 issue 按 basename 归并为十个真实文件,单模型伪多模型聚类五个;三组质询的 reviewer 全部命中各自 raised_by;C01 答复含全部三种表态令牌,报告仅记 Conceded 一项且全文无矛盾章节。

## 九、未决事项与假设

未决事项:challenge 阶段为何只有一份答复且无 bundle、prompt、log 痕迹,产物无法判定是超时、手动补跑还是事后清理;gemini31pro 的 findings 只有七条而其他模型十五条顶格,无法判定是正文提及面窄还是提取截断;"压降 60%+ 上下文消耗"无任何测量数据可核对;该次运行的完整命令行与分步顺序无记录。假设:认定该次运行使用 standard 模式(registry metadata 明示);认定 prompt-*.txt 即 plan 阶段实际送达的提示词(文件存在于任务流目录,内容为 v1 模板);五份 review-*.md 正文质量本身不在本次评审范围,仅检索了 findings 相关特征。

## 十、结构化发现

```json
{
  "findings": [
    {
      "id": "F1",
      "target": "orchestrate_v2.py:310-345 (cluster_issues)",
      "kind": "bug",
      "claim": "聚类按 findings 条数而非去重模型数判定多模型状态,同一模型对同一 target 的多条 findings 被错误标为 consensus 或 contradiction,最终报告将单模型观点呈现为“高度共识项 (Verified Consensus)”。",
      "evidence": ["orchestrate_v2.py:311 len(items)==1 与第 325 行注释“2 个及以上模型命中同一 target”不符", "issue-registry.json I12/I14(state=consensus,raised_by 单模型),I06/I08/I16(state=contradiction,raised_by 单模型)", "consensus-report.md:13-22 I12、I14 列入“高度共识项”且提出方各仅一个模型", "探针复现:单模型双 findings 同 target -> [('a.py', ['m1'], 'consensus')]"],
      "severity": "P0",
      "blocking": true
    },
    {
      "id": "F2",
      "target": "orchestrate_v2.py:326-332 (contradiction 判定)",
      "kind": "bug",
      "claim": "矛盾启发式(kinds 不同或 claim 含“不/错”字)把语义一致的意见标为对立,生产 run 的 8 条 contradictions 无一条是断言级对立;伪矛盾占满 max_challenges=3 配额,导致 P0 高危单例 I05 未获质询。",
      "evidence": ["orchestrate_v2.py:328-331 is_conflict 实现", "issue-registry.json I01 五模型同向确认 Windows 规则缺口仍标 contradiction;I02/I04 同理", "challenge-plan.json C01-C03 全部为 contradiction 类型,singleton_audit 轮空", "challenge-reply-C01-gemini38flash.md:19-26 真正分歧存在于子断言级(kill -9 -1 层级归属),target 级聚类不可见"],
      "severity": "P0",
      "blocking": true
    },
    {
      "id": "F3",
      "target": "orchestrate_v2.py:215-222 (normalize_target) 与 192 (fallback 正则)",
      "kind": "bug",
      "claim": "目标归一化不做路径等价归一且 fallback 正则不匹配盘符冒号,同一文件裂变为多个 target,正则片段被误认为文件路径,产生幽灵 target 并撕裂真共识。",
      "evidence": ["探针:normalize_target('cli\\\\.py') -> 'cli/.py'", "issue-registry.json:approval_detection.py 裂为 3 个 target(I01/I13/I14),test_approval_windows.py 3 个,scan_history.py 与 approval.py 各 2 个;16 issue 按 basename 归并仅 10 个真实文件", "unresolved-ledger.json 与 consensus-report.md:32-36 幽灵路径 cli/.py 以 P0 入账并入报告"],
      "severity": "P1",
      "blocking": true
    },
    {
      "id": "F4",
      "target": "orchestrate_v2.py:186-212 (extract_findings_json 启发式兜底) 与 158-164",
      "kind": "bug",
      "claim": "结构化 findings 层在生产中 100% 由正则启发式合成(该 run 的 prompt 与 task.md 均未要求结构化产出,五模型无一补写),兜底把流程说明与规则引用行抓成 finding;兜底落盘的 sidecar 与模型亲笔 JSON 无来源区分。",
      "evidence": ["stop-process-20260917/prompt-kimi-k3.txt 全文 11 行为 v1 PLAN_PROMPT,无 findings/JSON 字样;task.md 检索同样为零", "review-*.md 检索 findings/severity/代码围栏零命中", "五份 findings-*.json 呈现同一兜底签名:kind 仅 bug/observation、claim 第 140 字符硬截断(如 'fork bom'、'定向 PI')、evidence 单定位符、unknowns/assumptions 全空", "findings-kimi-k3.json F1“材料范围……”流程说明成为 P2 finding 并混入 C01 bundle Proposal-1;findings-gemini38flash.json F9 规则引用行成为 P0", "orchestrate_v2.py:180-181、210-211 兜底落盘无任何 provenance 标记"],
      "severity": "P1",
      "blocking": true
    },
    {
      "id": "F5",
      "target": "orchestrate_v2.py:419-421 (质询者选取) 与 challenge bundle 生成",
      "kind": "invariant",
      "claim": "匿名质询不匿名:质询者恒为争议当事人(注释承诺的回避逻辑未实现且 raised[0] 依赖不稳定的集合序),bundle 提案顺序与 models 阵容顺序逐项对齐可直接解码作者,claim 保留第一人称叙事指纹。",
      "evidence": ["challenge-plan.json:C01/C02/C03 reviewer 均在各自 issue raised_by 内(self_review=True)", "challenge-reply-C01-gemini38flash.md:13“已在我方独立评审中完成覆盖”——质询者认出自己文字", "C01 bundle 28 提案按 kimi-k3×9、dsv4pro×6、glm53×6、gemini38flash×4、gemini31pro×3 排列,与 MODE_PRESETS standard models 顺序一致", "探针:四种 PYTHONHASHSEED 下 list(raised_set)[0] 出现三种取值"],
      "severity": "P1",
      "blocking": false
    },
    {
      "id": "F6",
      "target": "orchestrate_v2.py:589-594 (表态解析 elif 链)",
      "kind": "bug",
      "claim": "表态按文件级单标签 elif 归类,与提示词要求的逐断言表态粒度错配;生产 run 中含 CONCEDE+REFUTED+UNRESOLVED 三种表态的答复只被记为 Conceded,最有价值的 REFUTED 纠偏与 UNRESOLVED 项在报告与账本中消失。",
      "evidence": ["challenge-reply-C01-gemini38flash.md:43/48/52 三种表态并存", "consensus-report.md:7-8 Conceded: 1、Refuted: 0;ledger 仅含两条单例保护项", "orchestrate_v2.py:589 'CONCEDE' in text 子串匹配,“我方不 CONCEDE”亦命中"],
      "severity": "P1",
      "blocking": true
    },
    {
      "id": "F7",
      "target": "orchestrate_v2.py:596-608 (少数派证据保护)",
      "kind": "invariant",
      "claim": "保护实现与注释承诺不符:注释限定“未被质询直接证伪”,实现无条件收录全部带非空 evidence 的 P0/P1 单例,无证据质量门槛,亦不检查质询驳回结果;幽灵路径因此获得机制背书。",
      "evidence": ["orchestrate_v2.py:596-597 注释 vs 598-608 无条件 append", "unresolved-ledger.json I11 cli/.py P0(fallback 噪声)被保护入账", "consensus-report.md:32-36 同一幽灵项呈现于终报"],
      "severity": "P1",
      "blocking": false
    },
    {
      "id": "F8",
      "target": "SKILL.md:60-62 与 orchestrate_v2.py:46-63、472-492 (三档模式拓扑)",
      "kind": "spec_mismatch",
      "claim": "文档声明的调用次数与代码拓扑不符:standard 实为 5-8 次(文档 7-8),audit 实为 5-10 次(文档 10-12),错排匹配与矛盾、单例质询共享 max_challenges=5 配额而非文档暗示的叠加;“压降 60%+”无测量对应物。",
      "evidence": ["探针按 MODE_PRESETS 推算:economy 3-4、standard 5-8、audit 5-10", "SKILL.md:60-62 次数声明原文", "orchestrate_v2.py:472-492 derangement 仅在 len(challenges)<max_challenges 时补充,共用配额"],
      "severity": "P1",
      "blocking": false
    },
    {
      "id": "F9",
      "target": "orchestrate_v2.py:614-645 (stage_synthesize_v2 报告生成)",
      "kind": "bug",
      "claim": "最终报告只写共识与未决账本两节,矛盾项(含真五模型共识 I01)与质询答复内容整体缺席,conceded/refuted 仅以头部计数出现;报告对读者呈现的是系统性变形的评审结论。",
      "evidence": ["orchestrate_v2.py:626-645 仅 consensus 与 unresolved_ledger 两节", "consensus-report.md 全文无矛盾/分歧章节(探针检索确认),8 条 contradictions 无一呈现", "C01 答复的 CONCEDE/REFUTED 细节在报告中无对应章节"],
      "severity": "P1",
      "blocking": true
    },
    {
      "id": "F10",
      "target": "orchestrate_v2.py:577-581 (synthesize 对账缺失)、142-153 (wait_for_outputs)、158-164 (陈旧 sidecar 优先)",
      "kind": "bug",
      "claim": "流程容错链薄弱:synthesize 不核对质询计划与答复的对应关系(3 计划 1 答复静默通过);单模型失败即整阶段判负且无降级续跑;重跑时旧 sidecar 无条件压过新产出,幂等性不成立;合法但非对象的 sidecar JSON 致下游 AttributeError。",
      "evidence": ["challenge-plan.json 三项 vs 目录仅 challenge-reply-C01-gemini38flash.md 一份,报告无缺失提示", "orchestrate_v2.py:722-723 all 模式 plan 失败即 return 1", "orchestrate_v2.py:158-164 sidecar 存在即直接采用,不重提取", "探针:json 数组 sidecar 下游触发 AttributeError: 'list' object has no attribute 'get'"],
      "severity": "P1",
      "blocking": false
    },
    {
      "id": "F11",
      "target": "tests/test_cross_review_five_v2.py:57-93、96-129、132-177",
      "kind": "spec_mismatch",
      "claim": "测试覆盖绕开了全部生产失效路径:聚类测试让各模型 target 互不相交(漏掉同模型多条 findings);兜底启发式路径零测试;端到端测试注释承诺验证少数派保护但断言只查报告标题字符串。",
      "evidence": ["test_cross_review_five_v2.py:62-75 三模型 target 两两不同", "第 96-129 行仅测 ```json 块提取,186-212 行启发式无对应用例", "第 174 行注释“验证少数派保护”与第 176-177 行断言内容不符", "无质询者回避、表态解析、缺失答复、sidecar 结构校验、幂等性测试"],
      "severity": "P2",
      "blocking": false
    },
    {
      "id": "F12",
      "target": "orchestrate_v2.py:68-100 (PLAN_PROMPT_V2) 与 102-125 (CHALLENGE_PROMPT_V2)",
      "kind": "suggestion",
      "claim": "CHALLENGE_PROMPT_V2 四步结构质量高且实证有效,但无 bundle 体量指引(实测 28 条提案含噪声)且表态令牌与文件级解析错配;PLAN_PROMPT_V2 的 findings 引导效果无生产证据(唯一 run 未送达该提示词),建议将结构化产出拆为独立短指令并在 merge 前对 sidecar 缺失显式告警。",
      "evidence": ["challenge-plan.json C01 bundle 28 条提案,Proposal-1 为流程说明噪声", "stop-process-20260917/prompt-kimi-k3.txt 为 v1 模板,PLAN_PROMPT_V2 从未被送达", "challenge-reply-C01-gemini38flash.md 四步结构完整,证明质询提示词设计有效"],
      "severity": "P2",
      "blocking": false
    },
    {
      "id": "F13",
      "target": "orchestrate_v2.py:264-266、288-289、337 (互补矩阵与错排细节)",
      "kind": "suggestion",
      "claim": "三处低危实现瑕疵:互补矩阵“检查是否有矛盾”注释下为无条件加 0.5 分;错排的 fallback 分支为死代码(n≥2 错排必然存在);severity 最大值比较对小写字母按 0 计。",
      "evidence": ["orchestrate_v2.py:264-266 注释与实现不符", "orchestrate_v2.py:288-289 best_perm is None 分支不可达", "orchestrate_v2.py:337 {'P0':3,...}.get(s, 0)"],
      "severity": "P2",
      "blocking": false
    }
  ],
  "unknowns": [
    "challenge 阶段为何仅一份答复且无 bundle/prompt/log 痕迹:超时、手动补跑还是事后清理,产物无法判定",
    "gemini31pro findings 仅 7 条(其他模型 15 条顶格)是正文提及面窄还是提取截断",
    "SKILL.md“压降 60%+ 上下文消耗”无任何测量代码或基准数据可核对",
    "该次运行的完整命令行与分步顺序(是否 --stage all、是否手动补跑 synthesize)无记录",
    "PLAN_PROMPT_V2 的结构化产出引导能力:唯一生产 run 送达的是 v1 提示词,该提示词的效果零证据"
  ],
  "assumptions": [
    "认定 stop-process-20260917 运行使用 standard 模式(issue-registry.json metadata 明示)",
    "认定任务流目录内 prompt-*.txt 即 plan 阶段实际送达的提示词,其内容为 v1 模板",
    "五份 review-*.md 正文质量不在本次评审范围内,仅检索其 findings 相关特征以判定结构化层来源",
    "评审探针在系统临时目录运行,只读导入被审代码与产物,未修改任何现有文件"
  ]
}
```
