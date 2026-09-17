# cross-review-five v2 编排器自我评审（deepseek-v4-pro）

我的总体判断：v2 编排器当前不宜直接用于生产评审。它的错排算法、零 LLM 归并、三档调用预算这些骨架是对的，但聚类语义、质询分配、表态解析、少数派保护、路径归一化五个缺陷叠加在一起，让"共识、矛盾、保护"这三大核心输出的标签在当前实现下不可信。本次实际运行产物（stop-process-20260917）恰好逐条踩中了这些缺陷，下面逐维展开，每条判断都附代码行号与产物证据。

## 一、算法正确性

我实读了 orchestrate_v2.py 全文（735 行），并用一份临时验证脚本对四个核心函数做了内存级重放与暴力对照。验证脚本只读材料、不落盘任何产物，符合只读纪律。

max_weight_derangement 是正确的。我对 n=1、2、3、5 分别做了暴力全排列对照：n=1 返回空列表，n=2 起全部无自环，且得分等于暴力枚举的全局最优解。n=5 时全排列只有 120 个，O(n!) 在本项目固定的五模型阵容下不成问题。这是四个核心函数里唯一经得起验证的一个。

normalize_target 的快乐路径正确，但归一化维度不足。它只做斜杠统一、小写化、截行号（行 215-222），不统一绝对路径与裸文件名。实测同一文件两种写法归一化后不相等："<HERMES_HOME>/hermes-agent/tools/approval_detection.py" 与 "approval_detection.py" 判为不同目标。本次运行的 issue-registry.json 里这个缺陷的后果清晰可见：I01（approval_detection.py，五模型）与 I14（/users/...approval_detection.py，仅 gemini31pro）被拆成两个簇，I04（scan_history.py）与 I16（<HOME_ROOT>/...scan_history.py）同样分裂。同一实体出现两次，一次进矛盾清单、一次被标成 P0 共识。任务书点名的边界条件"相同 claim 不同措辞"在此处就是失败案例。

cluster_issues 的矛盾判定是错的，而且错得系统性。行 328-331 的判定式是：kinds 多于一种，或任一 claim 含"不"字或"错"字，即判 contradiction。用"不/错"这两个汉字做字面子串匹配，在中文 claim 里几乎必然触发。我的验证实验一：两个模型、同 kind（bug）、实质相同（"资源未释放"对"句柄不会被释放，存在泄漏"），仅因后者含一个"不"字就被判为矛盾。真实数据重放更说明问题：I01 是五模型全部指向 approval_detection.py 的全员共识，28 条 claim 里 12 条含"不/错"字，于是它被标成 contradiction；I04 是四模型一致认定"目标绑定错误"，也被标成 contradiction。反向失真同样存在：I12 与 I14 两个"共识项"的 raised_by 各自只有一个模型——gemini38flash 自己的两条 findings 撞到同一 target 后与自身聚成"共识"，consensus-report.md 却把它们写进"高度共识项 (Verified Consensus)"。单模型自说自话贴共识标签，五模型全员一致贴矛盾标签，标签语义整体颠倒。而仓库自带的 test_cluster_issues 恰好绕开了这个缺陷：它的两个 claim（"资源未释放"与"资源句柄泄漏"）都不含"不/错"字，测试为错误实现背书。

cluster_issues 还有两个次级问题。行 337 取最高 severity 时用字典 {"P0": 3, "P1": 2, "P2": 1}.get(s, 0)，没有先 upper；而 compute_complementarity_matrix 行 257 对 severity 做了 .upper()。两处不一致。我的实验六验证：小写 "p0" 与 "P2" 同 target 时，聚类取到的 severity 是 P2，小写高危项静默降权。概率不高（提示词模板给了大写示例），但是确定性缺口。

compute_complementarity_matrix 的加权设计经我的验证是自洽的：对称的独有 P0 各得 6.0（基础 1.0 加 Jaccard 互补 2.0 加单例 P0 权重 3.0），P0 独有权重 3.0 显著高于 P1 的 1.5，P2 不加权，所以 findings 数量多的模型不会仅凭数量占据优势。行 265-266 的"冲突检测"实际只检查 target 重合就加 0.5 分，并不验证是否真矛盾，注释与实现有出入，属于命名失实而非数值错误。

## 二、流程健壮性

子进程超时路径基本成立。TIMEOUT_SECONDS 为 40 分钟、POLL_SECONDS 15 秒，与任务书声明一致；spawn 用列表传参、无 shell 注入面；GLM 单独传 --reasoning low 也与 SKILL.md 行 85 的说明一致。wait_for_outputs 的一个效率缺陷：行 150 的"进程已退但文件缺失"快速失败要求所有进程全部退出才触发，五个模型里只要有一个卡死，另外四个早早完成，编排器也会白等满 40 分钟。正确做法是任一进程退出且无产物即提前失败。这是性能问题，不改变最终正确性。

findings 解析的降级路径被本次运行证明了存在，同时证明了它产噪声。extract_findings_json 的降级启发（行 186-212）逐行扫 Markdown，凡含文件名引用且行长的行都当作 finding，claim 硬截断 140 字符，severity 按"崩溃/漏洞"等关键词猜。本次五份 findings 全部呈现降级产物的特征：claim 带 md 行前缀（"- "、"1. "）、140 字符处戛然而止（findings-dsv4pro.json 的 F1 结尾停在"按进"二字）、纯证据引用行被当 finding 收录（findings-dsv4pro.json 的 F15 原文就是"- 事故命令原文:task.md:7。"，findings-kimi-k3.json 的 F1 是"材料范围:任务书指定材料全部实读……"这条材料说明）。没有任何一份 findings 是模型按 prompt 要求自觉落盘的 JSON。这个判断是内容特征推断，置信度高：自觉落盘不可能产生"- "前缀与纯引用行。降级路径救回了结构化数据的可用性，代价是把建议行、引用行、说明行混进了聚类输入，I05（一条"写进 AGENTS.md 的纪律"建议）就这样以 P0 severity 进入了少数派账本。

challenge 阶段 bundle 与计划项的对应关系存在一个制度性缺陷：矛盾质询的 reviewer 取 raised_by 的第一个元素（行 420-421）。raised_by 由行 336 的 list(set(...)) 生成，set 迭代顺序受哈希随机化影响，跨进程不稳定。两个后果：其一，质询者经常就是争议的第一提出者。本次 challenge-plan.json 里 C01 与 C03 的 reviewer 都是 gemini38flash，而 C01 的 proposals 第 22 至 25 条正是 gemini38flash 自己的 findings 原文，C03 的 proposals 第 2 至 4 条也是它自己的。被派去"裁决"的评审者就是论点作者本人，还拿到了自己观点的截断原文。其二，中断后重跑 merge，同一份 findings 可能产出不同的 reviewer 分配，幂等性不成立。质询答复本身有正面价值：challenge-reply-C01-gemini38flash.md 对"kill -9 -1 归属危险层"的 REFUTED 给出了硬线层先短路的技术反证，这条纠错在技术上成立（116 行硬线正则的 flag 贪婪分组会先吞掉 -9 再命中 -1），说明四步法质询能产生真实增量。但制度上的自审漏洞必须堵。

中断重跑的幂等性还有一处确定的缺口：stage_plan_v2 重跑时不清理旧的 findings-<model>.json（行 350-379 无删除逻辑），而 extract_findings_json 优先读 findings json、读不到才从 md 提取（行 156-168）。若某轮模型没有落 json 而上一轮落过，merge 会静默消费上一轮的旧数据，与当轮 review 文本脱节。

## 三、经济性

三档模式的调用次数与 MODE_PRESETS 的对应关系我逐档核算过：economy 是 3 模型加至多 1 次质询，共 3 至 4 次；standard 是 5 模型加至多 3 次质询，共 5 至 8 次；audit 是 5 模型加至多 5 次质询，共 5 至 10 次。SKILL.md 声明的 economy 3-4 次、standard 7-8 次与实际一致，audit 声称的"10-12 次"上界 12 在代码里不可达——最大只能是 10。本次 standard 实际跑了 8 次调用（5 个 plan 加 3 个 challenge），与声称一致。merge 与 synthesize 两个阶段全程无 spawn 调用，零 LLM 消耗属实。

"压降 60%+ 上下文消耗"（SKILL.md 行 61）没有 v1 基准数据支撑，我无法独立核实。v1 是 10 次调用、v2 standard 是 8 次，调用次数只降了 20%；上下文总量确有下降（质询包只含 140 字符截断的 claim），但"60%+"这个数字在仓库里找不到测算依据。

## 四、文档一致性

三处不一致。SKILL.md 行 78 让读者"见脚本内的 PLAN_PROMPT 与 REVIEW_PROMPT"，v2 脚本里只有 PLAN_PROMPT_V2 与 CHALLENGE_PROMPT_V2，REVIEW_PROMPT 是 v1 的常量，引用不存在。SKILL.md 行 62 描述 audit 模式含"derangement 5 条边 + 关键弦质询"，代码里 derangement 只在矛盾与单例质询消耗后配额有余时才补位（行 472），且"关键弦质询"在代码中没有任何对应实现，只有 derangement_peer 一种类型。SKILL.md 行 56 说"有具体定位符的独立发现"进未决账本，代码的实际条件是 severity 为 P0/P1 且 evidence 非空（行 599），P2 的有定位符发现不进账本，文档少写了 severity 条件。用法示例、参数名、阶段名与实际 CLI 相符。

## 五、设计性质疑

匿名质询是否真匿名，我的结论是：机制上匿名，制度上泄露。bundle 用 Proposal-N 编号、不标模型名，这一步做到了；但 reviewer 选择规则（raised[0]）让"被审者"经常就是"质询者"，本次三组矛盾质询里两组是作者审自己的观点，challenge-reply-C01 里 gemini38flash 明确写出"已在我方独立评审中完成覆盖，不属于新增量"——它认出了包里有自己的内容。匿名性在这条路径上不成立。即使修掉 reviewer 选择，claim 截断文本仍保留原模型的行文风格指纹，模型之间互相识别风格的能力不弱，这是软性风险，需要在 prompt 里加"不得推断作者身份"的约束并接受残余风险。

少数派证据保护的实现有两个漏洞。漏洞一：synthesize 的表态解析是 if-elif 链（行 588-594），一个答复文件只要先命中 CONCEDE，同文件里的 REFUTED 与 UNRESOLVED 就被整体丢弃。四步法提示词要求对每个断言分别表态，混合表态是常态而非例外。本次 challenge-reply-C01-gemini38flash.md 同时含三种标记（行 43、48、52），consensus-report.md 行 8 却显示"质询证伪驳回 (Refuted): 0 项"——两条 REFUTED 与一条 UNRESOLVED 全部丢失。漏洞二：少数派保护只看 registry 的 singletons（行 598-608），不查质询结果。哪怕一个 P0 单例在质询中被明确证伪，只要它有 evidence，仍会无条件进入 unresolved-ledger.json。"未被证伪"的保护条件在实现里退化成了"存在即保护"。本次运行的账本两项（I05、I11）恰好都是从未被质询过的项（三组质询全被 contradictions 占满，singleton_audit 一组都没排上），没有踩中漏洞二，但代码路径是确定存在的。

findings JSON 依赖模型自觉落盘的脆弱性被本次运行坐实：五个模型没有一个自觉落盘，全靠降级路径兜底。兜底可用但噪声入流（见第二节）。这是架构决策问题——要么在 prompt 里把落盘设为强制验收项并在 spawn 侧校验，要么把降级提取的噪声过滤做严。

两个提示词的对比：PLAN_PROMPT_V2 结构完整，JSON 模板的占位符转义正确（{{ }} 双花括号），约束条款齐全；一个小瑕疵是"不得修改任何现有文件"与"将完整产出写入文件 {out_path}"在重跑场景下语义冲突（out_path 已存在时写它就是修改现有文件），应改为"不得修改任务书指定材料与任何现有评审产出"。CHALLENGE_PROMPT_V2 的四步法与防从众条款（"严禁以多数票为由否定附有具体代码证据的少数派意见"）质量好，但表态输出没有结构化格式要求，全靠关键词 grep，这直接催生了第三节的解析缺陷。

与 v1 对比，我的判断是：复杂度上升换来了部分价值，但核心价值尚未兑现。v1 是 10 次调用全篇互审，v2 是 8 次调用定向质询，代码量从 199 行涨到 735 行。定向质询省上下文是真的，本地聚类替代多数表决的方向是对的，错排匹配在 audit 模式下的数学基础也扎实。但 v2 新引入的失效模式比它消灭的多：聚类标签失真（F1）、路径分裂（F5）、自审（F2）、表态丢弃（F3）、保护失真（F4）。v1 的产物是原始互审文本，人读得出来；v2 的产物是打了"Verified Consensus"标签的机器报告，标签错了就没人看得出来。v2 只有在标签可信之后才值得它的复杂度。

## 六、测试覆盖

test_cross_review_five_v2.py 共 6 项测试，覆盖情况如下。已覆盖：MODELS 与 MODE_PRESETS 常量断言、normalize_target 快乐路径（含空串）、max_weight_derangement 三模型最优性、cluster_issues 的 consensus 与 singleton 快乐路径、extract 的 md 代码块提取加 sidecar 落盘、merge 加 synthesize 的端到端文件落盘。未覆盖的关键路径：compute_complementarity_matrix 零测试（0/6）；cluster_issues 的矛盾判定路径零测试，测试用例刻意避开了含"不/错"字的 claim；降级启发路径零测试，而本次实际运行全靠它；synthesize 的表态解析零测试，多标记混合答复的丢失因此无人察觉；stage_plan_v2、stage_challenge_v2、wait_for_outputs 的超时与部分失败路径零测试；重跑幂等性零测试；normalize_target 的绝对路径对裸文件名零测试。端到端测试的断言偏弱：只检查文件存在与报告含"CONCEDE"字样，不断言账本内容正确性——它甚至没有断言那个 P0 的 crypto.py 单例进了账本，即便进了，测试也验证不了"不该进的没进"。

## 结论

v2 编排器当前不值得直接用于生产评审。骨架正确（错排、零 LLM 归并、调用预算），标签层错误（共识与矛盾判定、路径归一化），裁决层失真（自审、表态丢弃、保护不看质询结果）。这次 stop-process 事故评审恰好把全部缺陷都踩了出来，产物本身成了最好的回归样本。

下次使用前必须修掉的五项，按优先级排列。第一，cluster_issues 的矛盾判定（行 326-332）废除"不/错"字面子串，改为 kind 异同加 severity 冲突的结构化比较，并让 consensus 至少要求两个不同模型。第二，contradiction 质询的 reviewer 选择（行 420-421）排除 raised_by 全体成员并对 raised_by 做稳定排序，消除哈希序非确定性。第三，synthesize 表态解析（行 588-594）改为对三种标记分别独立提取，混合表态全部入账。第四，少数派保护（行 598-608）增加 REFUTED 排除条件，账本只收未证伪项。第五，normalize_target（行 215-222）统一绝对与相对路径（取 basename 或统一绝对化），消除同一文件的双簇分裂。这五项修完后，v2 的复杂度才第一次开始为它挣回票价。
