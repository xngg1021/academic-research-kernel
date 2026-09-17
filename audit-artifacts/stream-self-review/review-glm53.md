# cross-review-five v2 编排器独立评审（glm53）

评审对象：`skills/cross-review-five/scripts/orchestrate_v2.py`（735 行，四阶段 Sparse Deliberation）。对比基线为 v1 `orchestrate.py`。证据抽查采用 `cross-reviews/stop-process-20260917/` 的真实运行产物。所有判断均基于我实际读到的行号与文件内容。

## 一、算法正确性

四个核心函数里，`normalize_target` 与 `max_weight_derangement` 的实现在其设计意图内基本正确，但 `cluster_issues` 有两个实质缺陷，直接污染下游全部产物。

**缺陷一：聚类单元是“条目”而非“模型”，单模型多条发现会被误判为共识或矛盾。**
`cluster_issues`（orchestrate_v2.py:293-347）把每个模型每条 finding 追加进 `by_target`，判定只看 `len(items)`：同一 target 下只要凑够两条条目就走“多模型”分支。它从不检查 `raised_by` 是否真的有多个不同模型。后果在 stop-process 运行里真实发生了：

- `issue-registry.json` 的 I14，标签为 consensus（“高度共识项”），`raised_by` 只有 `["gemini31pro"]` 三条 claims 全部来自同一模型。共识报告（consensus-report.md:18-22）把它当作 "Verified Consensus" 展示，读者会以为多模型独立复核过，实际上是 gemini31pro 一家之言。
- I06 标签为 contradiction（“矛盾”），`raised_by` 只有 `["dsv4pro"]` 三条 claims——单模型内部三条 finding 被判为“跨模型矛盾”，并因此消耗了一个质询名额（虽然该组未被选中执行）。
- I12 同理，"consensus" 实为 gemini38flash 单模型两条。

这次运行的 2 项“共识”全部是单模型伪共识，8 项“矛盾”中至少 I06、I08、I16 是单模型或明显同向的伪矛盾。聚类层面的 `state` 字段在这次真实运行中没有一条名实相符。

**缺陷二：矛盾判定启发式近乎失效。**
orchestrate_v2.py:328-331 用 `len(kinds) > 1 或 claim 含"不"/"错"` 判矛盾。中文技术评述几乎必然含“不”字（stop-process 运行里 28 条 claim 聚成的 I01 被判 contradiction，五方观点其实高度一致：都指向 :238 规则粒度太粗）。结果是 C01 质询包塞了 28 条 Proposal（challenge-plan.json:11-207），绝大多数是同向观点被当成分歧送审，质询预算浪费在裁决“假矛盾”上，而且 bundle 里 28 条 proposal 的 claim 大多是被截断的残句（见第三节），gemini38flash 的答复实际上无法逐条裁决，只能挑三条代表性的（challenge-reply-C01-gemini38flash.md 实际只裁了三大类）。

**缺陷三：`normalize_target` 只去行号，不处理绝对路径/相对路径混用。**
同一文件 `approval_detection.py` 在 I01（相对名）与 I14（`<USER_HOME>/appdata/.../approval_detection.py`）被聚成两个独立 issue；同一测试文件出现三个 target：I02 `test_approval_windows.py`、I09 `tests/tools/test_approval_windows.py`、I15 绝对全路径。这直接制造伪单例（I15、I09 本可并入 I02），也把本应五方共聚的 approval_detection.py 稀释成两簇。修法不难：basename 匹配或路径后缀折叠。

`max_weight_derangement` 本身正确（错排枚举、择优），n=5 时 120 种排列可接受；`compute_complementarity_matrix` 的 Jaccard 项与高危单例加权方向合理，但它喂进去的 findings 质量差（见下），权重精度无从谈起。

## 二、流程健壮性

**findings JSON 依赖模型自觉，降级路径产出了这次运行的主要数据，且质量是灾难级的。**
`extract_findings_json`（orchestrate_v2.py:156-212）三级降级：sidecar → markdown 代码块 → 行级启发式。启发式 fallback 会把含文件名引用的任意行截前 140 字符当 claim（:203），kind 只有 "bug"/"observation"（:202）。证据表明这次运行大量 findings 走了 fallback：

- `findings-glm53.json` 的 F1 claim 是 `"approval_detection.py:238 有专门规则:"`，F3 截断在“而 Windows ”半句话处；全部 claim 恰在 140 字符附近截断。
- kind 出现 `"observation"`——PLAN_PROMPT_V2 的枚举（orchestrate_v2.py:83）根本没有这个值，唯一产出 "observation" 的代码路径是 fallback 的 :202。
- registry 与 unresolved-ledger 里因此充斥 markdown 残句，unresolved-ledger.json 的 I11 claim 是一段裸正则字面量，target 是正则误匹配出的伪文件名 `cli/.py`（evidence 为 `cli\.py`，是 `cli\.py` 转义序列被文件名正则 :192 误捕）。

这意味着“少数派证据保护”账本里躺着一条由正则误捕产生的伪发现（I11，P0，blocking）。少数派保护机制本身逻辑严密（P0/P1 单例且有 evidence 一律入账，orchestrate_v2.py:596-608），但它对 evidence 的真实性零校验，garbage in → P0 garbage preserved。

**challenge 阶段与计划项的对应无核对，缺失答复被静默吞掉。**
challenge-plan.json 规划了 C01/C02/C03 三组质询，但目录里只有 `challenge-reply-C01-gemini38flash.md` 一份答复（C02 应由 glm53、C03 应由 gemini38flash 产出，均缺失，log 存在但产物为空或未落盘）。`stage_synthesize_v2`（:577-581）只 glob 存在的答复文件，不与 plan 对账，consensus-report 照常生成，报告里看不出三分之二的质询根本没发生。这对一个“审计收口”工具是严重问题：合议报告在质询大量缺席时依然自信地给出结论。

**CONCEDE/REFUTED 解析是文件级 if/elif，一个答复里多种表态被压成一种。**
orchestrate_v2.py:588-594 按整个文件文本先后判 CONCEDE → REFUTED → UNRESOLVED。实际的 C01 答复同时含三类表态（:43 CONCEDE、:48 REFUTED、:52 UNRESOLVED，这是四步法提示词的必然产物——一个 bundle 多个议题本来就该多种裁决）。结果整个文件记成 1 条 conceded，refuted 计数为 0（consensus-report.md:8），报告数字与答复内容不符。解析粒度应到议题级而非文件级。

**wait_for_outputs 的一个反向问题**：产物齐但进程未退时会一直轮询到 40 分钟超时才返回（:146-148 的组合逻辑），`hermes chat --oneshot` 若有尾巴进程挂住，时间白耗。另外超时后 `p.terminate()`（:369-371, :558-560）在 Windows 上只杀直接子进程，`hermes` 命令包装的子进程树可能残留——v1 同病，不算 v2 退化。

**幂等性**：merge/synthesize 重跑覆盖产物，无累积污染，这点合格。challenge 重跑会对全部计划项重新 spawn，不跳过已有答复，中断续跑等于全量重花钱——对以“经济性”为卖点的 v2 来说应当做断点续传。

## 三、设计性质疑

**匿名质询的匿名性是脆弱的。** bundle 用 Proposal-N 别名（:432-437），但三条通道泄底：其一，contradiction 质询的 reviewer 直接取 `raised[0]`（:421），即质询者本人就是被审断言的作者之一（C01 的 reviewer gemini38flash 正是 I01 的 claim 作者，C02 的 glm53 同理）——它会在 bundle 里认出自己的原话，“对等匿名”对它不成立，倒是引入了自证偏置；其二，claim 原文逐字保留，五个模型文风差异明显，跨模型身份推断门槛很低；其三，五个模型的 review-*.md 就在同一 stream 目录，质询子进程拥有全工具权限，没有任何机制阻止它读原文。匿名性声明只能防君子。

**少数派保护的方向正确，但保护的门槛错在证据形态而非证据质量。** `s.get("evidence")` 只查非空（:599），I11 那条正则误捕的伪定位符也享受 P0 保护。建议至少校验 evidence 条目形如真实路径（存在或可解析），否则账本会被 fallback 噪声填满。

**提示词质量**：CHALLENGE_PROMPT_V2 的四步法（增量→反例→归因→裁决）设计是好的，C01 答复显示 gemini38flash 确实执行了反证（对 `kill -9 -1` 层级的推导相当扎实）。PLAN_PROMPT_V2 的问题不在结构而在结果约束：它没有强制 sidecar JSON 必须落盘、没有给 claim 字数下限，直接导致本次运行大面积走 fallback。应把“findings-<model>.json 必须存在且合法”提为硬性交付物，并在 prompt 里给出最小 claim 完整性要求。

**与 v1 相比的复杂度是否值得**：v1 是 199 行的朴素轮转，v2 是 735 行的聚类加质询。方向我认为是对的——按信息增量定向质询确实比全篇互审省调用，merge/synthesize 也确如声明是纯本地零 LLM。但这次真实运行表明，v2 的价值兑现完全卡在聚类质量这一个环节上：伪共识、伪矛盾、伪单例让“稀疏”剪枝剪错了对象。在修好聚类之前，v2 的产出可信度低于 v1 的笨办法（v1 至少保证每份产出都被一个异构模型完整读过一遍）。

## 四、经济性与文档一致性

- economy：3 盲审 + 最多 1 质询 = 4 次，SKILL.md 声称 3-4，一致。
- standard：5 盲审 + 最多 3 质询 = 8 次，声称 7-8，一致（质询饱和时为 8；若零冲突则为 5，下限略低于声明）。
- audit：5 + 5 = 10 次，声称 10-12；实际拓扑封顶就是 10，"12" 无从达到，声明偏宽。
- merge/synthesize 纯本地，零 LLM 消耗，属实（无任何 spawn 调用）。
- SKILL.md:78 说“任务书模板与约束见脚本内的 PLAN_PROMPT 与 REVIEW_PROMPT”——v2 脚本里没有 REVIEW_PROMPT，实际是 CHALLENGE_PROMPT_V2，文档沿用了 v1 的名字。
- SKILL.md 用法示例的 stage/参数名与 CLI（:678-697）核对一致，`--mode`/`--models` 均存在。

## 五、测试覆盖

6 项测试覆盖了：模型表与预设常量、normalize_target 基本情形、错排匹配（3 模型环）、cluster_issues 的干净样例（真实模型间共识与单例）、extract_findings_json 的 markdown 代码块路径、两模型端到端冒烟。遗漏的关键路径恰好是本次运行全部踩中的雷区：

1. 无“共识需 ≥2 个不同模型”的断言——伪共识缺陷测不出来。
2. 无 normalize_target 绝对/相对路径混用测试。
3. 无 fallback 启发式路径的测试（构造一个无 JSON 块的 md 即可复现 140 截断与 "observation"）。
4. 无多表态混合文件的 CONCEDE 解析测试。
5. 无 challenge 产物缺失时 synthesize 的行为测试。
6. wait_for_outputs 的超时/半成品分支完全未测。

## 结论

这个 v2 编排器**当前不值得信任用于生产评审**。问题不在架构方向——稀疏质询与少数派保护的设计是对的——而在聚类与数据提取两个地基环节有实锤缺陷，且这次真实运行的产物已经系统性地展示了后果：2/2 的“共识”是单模型伪共识，账本里有正则误捕的伪 P0，合议报告在 2/3 质询缺席、refuted 被解析器吞掉的情况下照常出报告。

下次使用前必须修掉（按优先级）：

1. `cluster_issues` 的 state 判定改为先验证 `len(set(raised_by)) >= 2`，且矛盾判定弃用“不/错”字符启发式，改为按 claim 的语义方向或至少要求 kind/severity 实质冲突（P0）。
2. `normalize_target` 增加路径折叠，消除同文件多簇（P0）。
3. synthesize 对账 challenge-plan 与实际答复，缺席者在报告中显式标注（P0）。
4. CONCEDE/REFUTED 解析改到议题级，一个文件多种表态分别记账（P1）。
5. PLAN_PROMPT_V2 把 findings JSON 定为硬交付物；fallback 产出的条目应打上 `source: "heuristic_fallback"` 标记，未经确认不得携带 blocking=true 进入账本（P1）。
6. contradiction 质询的 reviewer 不得取 claim 作者本人（P1）。
7. 补上述六类测试（P1）。

修完 1-3 之后，建议再跑一次小规模真实任务对照 v1 产出，验证聚类修复的实效，然后才谈生产使用。
