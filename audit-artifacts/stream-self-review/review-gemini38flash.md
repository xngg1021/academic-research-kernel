# 五人组 v2 编排器（orchestrate_v2.py）独立深度评审报告

评审对象：`<WORKSPACE>\repos\hermes-academic-skills\skills\cross-review-five\scripts\orchestrate_v2.py`  
对比基准：`orchestrate.py`（v1 经典轮转编排器）  
测试套件：`tests\test_cross_review_five_v2.py`  
文档声明：`skills\cross-review-five\SKILL.md`  
运行证据：`<WORKSPACE>\cross-reviews\stop-process-20260917\` 实际产物目录  

---

## 核心结论

我经过对代码源码逐行审查与真实产物比对，确认该 v2 编排器当前**绝对不值得信任用于生产评审**。

该系统在设计意图上提出了稀疏自适应质询、信息增量导向以及少数派保护等优秀设想，但在代码工程实现中存在严重的逻辑缺陷与伪实现。核心聚类算法将单模型自言自语的多次陈述判定为全员高度共识；冲突识别依赖中文字符粗暴匹配，导致数十项不相干议题被机械打包；质询流程让原作者自我审查自身观点；合议阶段互斥的分支判断直接吞噬了所有否定意见与未决记录；少数派保护机制缺乏质询校验，已被证伪的观点仍然无条件进入账本。该编排器在当前形态下输出的合议报告具有严重的误导性，必须在全面重构修复阻断缺陷后方可考虑投入生产环境。

---

## 六大维度深度审查

### 一、算法正确性审查

#### 1. 单模型多条发现被误判为全员高度共识
在 `orchestrate_v2.py` 第 311 至 347 行的 `cluster_issues` 函数中，代码遍历各个模型的发现条目，按归一化后的目标对象存入字典 `by_target[tgt]`。第 325 行注释声称“2 个及以上模型命中同一 target”，但在代码实现中，分支条件仅仅是：
```python
if len(items) == 1:
    ...
else:
    # 2 个及以上模型命中同一 target
    ...
```
这里的 `items` 是该目标下的全部发现列表，其长度表示发现条目的总数，而不是参与提出该目标的独立模型数量。若单一模型针对同一个目标提出了多条发现，`len(items)` 同样大于等于 2。一旦这些发现类型相同且不含否定词，代码便在第 332 行将其标记为 `consensus`，并在第 336 行将提出方记录为去重后的列表 `raised_by: [该单一模型]`。

在真实产物 `stop-process-20260917\consensus-report.md` 第 18 至 23 行中，`I14` 条目仅由 `gemini31pro` 单独提出，却被列为五人交叉评审合议报告的“高度共识项”。这一严重失误导致单个模型的单方陈述未经任何对等实体的背书与核验，直接变成了合议结论。

#### 2. 冲突判断启发式极其脆弱且具有严重假阳性
`cluster_issues` 函数在第 328 至 331 行使用如下逻辑判定议题是否存在矛盾：
```python
kinds = {x["raw"].get("kind", "") for x in items}
is_conflict = len(kinds) > 1 or any(
    "不" in x["raw"].get("claim", "") or "错" in x["raw"].get("claim", "")
    for x in items
)
```
这段逻辑存在两处根本性缺陷：
首先，`len(kinds) > 1` 将视角的互补误判为立场的分歧。一个模型标注为 `bug`，另一个模型标注为 `security`，两者针对同一代码文件提出了完全相容的缺陷发现，代码却将其直接判定为对立冲突。
其次，在技术评审语境下，断言文本包含“不”或“错”是极其普遍的客观描述，例如“未释放连接池”、“不可绕过”、“参数校验错误”等。文本包含否定字样完全不代表模型之间存在分歧。真实产物 `stop-process-20260917\challenge-plan.json` 第 1 至 209 行显示，5 个模型提出的 28 个关于 `approval_detection.py` 的不同发现，仅仅因为各自表述中含有此类字符，被全部归入同一个名为 `I01` 的巨大冲突议题包中。审查者被迫面对 28 个杂乱的提案，完全无法理清分歧边界。

#### 3. 互补权重累加量纲失衡与逻辑虚脱
在第 225 至 270 行的 `compute_complementarity_matrix` 函数中，权重计算内层循环 `for item in f_j:` 对目标进行遍历。若被审模型 `j` 产出了较多数量的独立发现，权重将发生无上限的线性累加。这使得互补矩阵的权重几乎完全被产出数量较多的模型主导，而非由视角的质量差异决定。同时，第 265 行的注释写明“同一目标，检查是否有矛盾”，但紧随其后的代码仅仅是无条件的 `w += 0.5`，并未执行任何矛盾判定。

#### 4. 最大权错排算法在常规流程中被旁路
第 272 至 291 行的 `max_weight_derangement` 函数在全排列空间中搜寻权重最大的无不动点置换。然而在 `stage_merge_v2` 中，该错排算法仅在 `mode == "audit"` 且质询数量未达配额时才被触发（第 472 行）。在系统默认推荐的 `standard` 模式以及轻量化的 `economy` 模式下，最大权错排算法根本不会被调用。文档中所宣称的核心算法，在绝大多数日常运行中处于完全闲置状态。

#### 5. 目标归一化缺失相对路径与绝对路径对齐
第 215 至 223 行的 `normalize_target` 函数仅完成了反斜杠替换与行号剥离。它没有将路径解析为相对于项目根目录的相对路径。当模型 A 输出相对路径 `approval_detection.py`，而模型 B 输出绝对路径 `C:\Users\...\approval_detection.py` 时，两者被切分为完全不同的目标，直接造成了聚类分裂与伪单例现象。

---

### 二、流程健壮性审查

#### 1. 质询环节出现审查者自我审议的荒谬闭环
在 `stage_merge_v2` 规划冲突质询议题时（第 420 至 421 行），代码选取审查者的逻辑为：
```python
raised = c["raised_by"]
reviewer = raised[0] if len(raised) > 0 else model_keys[0]
```
当一个矛盾项是由模型 A 与模型 B 产生时，代码直接指定 `raised[0]`（即模型 A）作为审查者，去审查包含模型 A 自己提议的议题包。在真实运行产物 `challenge-plan.json` 第 7 行与第 153 至 159 行中，`C01` 质询被分派给 `gemini38flash`，而包内的第 21 项提案正是 `gemini38flash` 自己的原始发现。让提案者自身充当仲裁者，彻底丧失了独立第三方审查的客观性。

#### 2. 合议解析使用互斥 if-elif 吞噬否定与未决记录
在 `stage_synthesize_v2` 第 588 至 595 行中，代码解析各个质询答复文本：
```python
for fname, text in challenge_replies.items():
    if "【CONCEDE】" in text or "CONCEDE" in text:
        conceded_items.append({"source_file": fname, "status": "conceded", "excerpt": text[:300]})
    elif "【REFUTED】" in text or "REFUTED" in text:
        refuted_items.append({"source_file": fname, "status": "refuted", "excerpt": text[:300]})
    elif "【UNRESOLVED" in text or "UNRESOLVED" in text:
        unresolved_ledger.append({"source_file": fname, "status": "unresolved_contested", "excerpt": text[:300]})
```
质询提示词明确要求审查者针对不同论点分别给出认同、驳回或未决表态。一份高质量的审查答复必然同时包含这三类结论。例如在 `challenge-reply-C01-gemini38flash.md` 中，第 43 行标注了 `【CONCEDE】`，第 48 行标注了 `【REFUTED】`，第 52 行标注了 `【UNRESOLVED】`。
然而编排器采用了互斥的 `if-elif` 结构。只要文本中出现了 `CONCEDE` 字符串，程序便直接将整个答复归入认同项，位于后面的 `REFUTED` 与 `UNRESOLVED` 表态被完全跳过。在 `consensus-report.md` 中，被审查者以详实反证驳回的错误观点显示为 0 项，合议报告呈现出完全虚假的认同假象。同时，代码提取的摘要仅为文件开头的 300 个字符，包含的全部是标题与引言，真正的裁决依据全部丢失。

#### 3. 非贪婪正则导致嵌套 JSON 解析失败并退化至粗糙词频
在 `extract_findings_json` 第 174 行中，正则模式采用了非贪婪匹配 ````json\s*(\{[\s\S]*?\})\s*````。当模型输出的结构化 JSON 内部含有多层大括号嵌套时，非贪婪匹配在遇到第一个内部闭合大括号时便提前终止，导致 JSON 反序列化崩溃。
解析失败后，程序退化到第 187 至 208 行的启发式抽取分支。该分支仅仅扫描含有文件后缀的行，并通过是否含有“崩溃”、“漏洞”、“误杀”等词语盲目分配严重级别，将正文任意文字截断 140 字符作为断言。这种降级行为产生了大量低劣的伪数据，直接破坏了后续图分析的基础。

#### 4. 进程超时与中断恢复缺陷
在第 96 至 107 行以及第 142 至 153 行的等待逻辑中，当进程超时后，代码使用 `p.terminate()` 终止子进程。在 Windows 操作系统下，非递归的进程终止无法清理其衍生的底层工具进程，极易导致孤儿进程逃逸。在幂等性方面，各个阶段重新执行时均缺乏断点跳过机制，会盲目覆盖已经成功生成的中间资产。

---

### 三、经济性与调用拓扑评估

#### 1. 模式配额硬编码截断与文档声明矛盾
`SKILL.md` 第 62 行明确声明：`--mode audit` 包含 5 模型盲审、最大互补错排匹配 5 条边加关键弦质询，总计 10 至 12 次调用。
但在 `orchestrate_v2.py` 第 59 行的配置中，`MODE_PRESETS["audit"]["max_challenges"]` 被硬编码为 5。更关键的是，在 `stage_merge_v2` 中，规划质询的三个循环均受到全局配额限制：
```python
if len(challenges) >= max_challenges:
    break
```
质询任务的总数上限在代码中被严格锁定为 5 组。加上盲审阶段的 5 次调用，全流程的真实调用次数上限严格为 10 次。文档中宣称的“10 至 12 次调用”以及“5 条错排边加关键弦质询”在数学逻辑上根本无法达成。一旦前面存在矛盾或高危单例，错排循环会因为配额耗尽而直接退出。

#### 2. 本地零消耗背后的高昂语义代价
编排器在 `merge` 和 `synthesize` 阶段确实实现了纯本地运行，不消耗外部大模型调用配额。但由于合议合成阶段完全舍弃了具备语义理解能力的分析机制，转而使用机械简陋的子串检索和字典拼装，使得系统无法处理多论点的复杂表态。节省了几次轻量模型调用的算力开销，却换来了整份合议报告失真、结论颠倒的灾难性后果，在工程经济性上属于得不偿失的典型负优化。

---

### 四、文档一致性审查

1. **调用量与执行拓扑脱节**：`SKILL.md` 声称 audit 模式具有错排加弦质询的双重保障，但脚本内部的配额机制彻底封死了该拓扑的成立条件。
2. **命令行参数对齐现状**：`orchestrate_v2.py` 的 CLI 参数支持 `--stage`、`--mode`、`--task`、`--models`，在接口形态上与 `SKILL.md` 给出的单步与一键全流程命令保持一致。
3. **依赖隐含假设未予说明**：脚本重度依赖外部命令 `hermes` 在当前系统环境路径中可用，且依赖子进程主动向标准输出和文件系统完整落盘结构化侧车文件，文档对此类前置约束缺乏防御性说明。

---

### 五、设计性质疑

#### 1. 少数派保护机制沦为虚假空壳
v2 宣称的核心设计原则之一是“少数派证据保护”，承诺“有具体定位符的独立发现绝不被多数票抹除”。
然而审视 `stage_synthesize_v2` 第 598 至 609 行的实际实现：
```python
for s in registry.get("singletons", []):
    if s.get("severity") in ("P0", "P1") and s.get("evidence"):
        unresolved_ledger.append({ ... })
```
这段代码存在两个不可容忍的破绽：
其一，代码根本没有核对该单例在质询阶段的实际裁决结果。哪怕该单例在 Phase 3 质询中已经被对手通过确凿的代码证据完全证伪（标记为 `【REFUTED】`），只要它最初被列为 P0 或 P1 且 `evidence` 字段不为空，它在第 600 行依然被无条件塞入未决账本。这种无视对验证据的保护，彻底背离了交叉评审追寻客观事实的初衷。
其二，证据核验形同虚设。代码仅通过 `if s.get("evidence"):` 判定列表非空，未对列表中的元素进行任何格式与有效性校验。在真实产物 `unresolved-ledger.json` 中，条目 `I05` 仅提供了一个毫无行号的文件名 `["AGENTS.md"]`，条目 `I11` 提供了一个拼写错误的路径 `["cli\\.py"]`，两者均被编排器视作附有具体证据定位符的坚实发现记录在案。

#### 2. 提示词与编排器后处理完全脱节
`CHALLENGE_PROMPT_V2` 规范了详尽的四步思考法，并引导模型针对议题包内的不同论点进行独立辩驳与裁决。但编排器的后处理逻辑却将包含 28 个提议的超大议题包一股脑推给模型，并在收集答复时用单层子串包含粗暴归类。编排器向模型索要细粒度的学术辩论，自己却在后台使用连脚本初学者都会避免的文本切片，提示词工程的高度精致与代码实现的极其粗放形成了荒谬的割裂。

#### 3. v2 与 v1 的复杂度收益失衡
相比于 v1 清晰稳健的 8KB 环形互审架构，v2 代码体量膨胀近 4 倍。它引入了复杂的图聚类、互补矩阵、状态机以及错排逻辑，但每一个新增模块都布满了致命的逻辑断层。其产出的合议报告非但没有提升决策效率，反而制造了单模型伪共识、自我审查、颠倒质询结果等大量系统性误导。当前的 v2 版本并未换来预期价值，构成了明显的过度设计与劣化实现。

---

### 六、测试覆盖盲区与假绿分析

在对 `tests\test_cross_review_five_v2.py` 中的 6 项测试进行代码走查后，我确认该测试套件存在严重的盲区与假绿特征：
1. **测试数据刻意回避边界缺陷**：在 `test_cluster_issues`（第 57 至 95 行）中，输入的测试数据恰好让每个模型仅贡献 1 至 2 条互不重叠的文件目标，且断言文本均不包含任何否定词。该测试完全绕过了“单模型同目标多条发现导致伪共识”的致命缺陷，也掩盖了“否定词导致虚假冲突”的高频故障。
2. **端到端测试覆盖不完整**：在 `test_merge_and_synthesize_end_to_end`（第 132 至 177 行）中，模拟的质询答复仅包含单一的 `【CONCEDE】` 表态，故意避开了多状态混合响应。测试没有断言被驳回的条目是否被错误保留，也没有断言质询计划中是否存在自我审查，整个套件只能验证预先编排的狭窄正确路径。
3. **关键算法缺失鲁棒性验证**：路径归一化测试未包含绝对路径与相对路径的互操作；错排算法未测试非强连通分解与权重平局；JSON 提取未测试深度嵌套与畸形转义。

---

## 必须在下次使用前修复的缺陷清单

为了使编排器具备基本的可用性与可信度，以下 6 项阻断缺陷必须在下次执行评审前完成彻底整改：

1. **重写聚类逻辑，消除单模型伪共识**：
   在 `cluster_issues` 中，共识的成立条件必须严格定义为独立模型提出方数量大于等于 2，即 `len({x['model'] for x in items}) >= 2`。单一模型提出的所有条目必须保留为单例或模型内部细分条目，严禁进入全员高度共识清单。

2. **废除中文词频冲突判定，引入细粒度 Issue 建模**：
   彻底移除 `len(kinds) > 1` 以及“不”、“错”等硬编码字符检测。两个模型针对同一文件的发现应当按其指涉的代码行范围或语义切片分别比对，只有在立场明确对立时才归入冲突；若无法在本地精确判定，应保持为独立议题并行求证，严禁将数十个不同方向的提案合并为一个超大包。

3. **修复审查者选择机制，坚决杜绝自我质询**：
   质询计划生成时，审查者必须严格从提出该冲突的当事方之外、或者在当事双方之间进行单向配对，严禁将包含审查者自身提案的议题包派发给自己审查。

4. **重构质询回复解析器，支持多论点结构化提取**：
   废除 `stage_synthesize_v2` 中的 `if-elif` 粗暴判断。要求质询答复阶段输出针对具体 Issue ID 的结构化 JSON 判定列表，或者在脚本中使用分块正则独立提取每一个 `【CONCEDE】`、`【REFUTED】` 与 `【UNRESOLVED】` 块，并精确定位其指涉的提案编号。

5. **对少数派保护引入真实过滤与证据核验**：
   在单例进入未决账本前，必须核对其是否经过质询；凡在质询中被有效驳回（`REFUTED`）的单例，严禁进入保护账本。同时必须校验 `evidence` 列表中是否包含可定位的行号或有效上下文，杜绝无意义占位符滥用保护机制。

6. **统一目标路径的绝对化与相对化归一标准**：
   `normalize_target` 必须接受工程根目录参数，利用标准库将所有输入路径统一解析为相对于根目录的标准正斜杠相对路径，消除因模型习惯差异导致的聚类断层。

---

## 结构化发现汇总

```json
{
  "findings": [
    {
      "id": "F1",
      "target": "orchestrate_v2.py:311-347",
      "kind": "bug",
      "claim": "cluster_issues 仅依据条目数量而非独立模型数量判断共识，导致单一模型针对同一目标提出的多项发现被错误升级为五人全员高度共识。",
      "evidence": [
        "orchestrate_v2.py:311,325 中使用 len(items) == 1 判断单例，else 分支未校验 len({x['model'] for x in items}) > 1",
        "stop-process-20260917/consensus-report.md:18-23 中由 gemini31pro 单独提出的 I14 approval_detection.py 被归入 Verified Consensus"
      ],
      "severity": "P0",
      "blocking": true
    },
    {
      "id": "F2",
      "target": "orchestrate_v2.py:328-332",
      "kind": "bug",
      "claim": "冲突判定依赖 kind 差异与中文否定字符匹配，导致正常的互补分类和客观技术描述被大面积误判为对立矛盾并粗暴合并为超大议题包。",
      "evidence": [
        "orchestrate_v2.py:328-331 使用 len(kinds) > 1 or any('不' in claim or '错' in claim) 作为矛盾判定标准",
        "stop-process-20260917/challenge-plan.json:1-210 将 28 个不同模型的发现全部打包为单一矛盾议题 C01"
      ],
      "severity": "P0",
      "blocking": true
    },
    {
      "id": "F3",
      "target": "orchestrate_v2.py:420-421",
      "kind": "bug",
      "claim": "矛盾质询计划直接选取 raised[0] 作为审查者，导致编排器要求提案模型审查包含其自身原话的议题包，破坏了交叉审查的独立性。",
      "evidence": [
        "orchestrate_v2.py:420-421 中 reviewer = raised[0] if len(raised) > 0 else model_keys[0]",
        "stop-process-20260917/challenge-plan.json:7 中 C01 由 gemini38flash 审查，但议题包内第 21 个提案即为其自身意见"
      ],
      "severity": "P0",
      "blocking": true
    },
    {
      "id": "F4",
      "target": "orchestrate_v2.py:588-595",
      "kind": "bug",
      "claim": "合议解析采用互斥的 if-elif 结构匹配全文关键字，导致同时包含吸收、驳回与未决的复合质询答复中，后面的 REFUTED 和 UNRESOLVED 表态被完全吞噬。",
      "evidence": [
        "orchestrate_v2.py:588-595 中 if 'CONCEDE' ... elif 'REFUTED' ... elif 'UNRESOLVED' 互斥执行",
        "stop-process-20260917/challenge-reply-C01-gemini38flash.md:43-53 明确包含三类表态，但 consensus-report.md:7-9 显示 Refuted 为 0 项"
      ],
      "severity": "P0",
      "blocking": true
    },
    {
      "id": "F5",
      "target": "orchestrate_v2.py:598-609",
      "kind": "spec_mismatch",
      "claim": "少数派证据保护逻辑未检查单例在质询阶段的驳回状态，导致已被确凿证据证伪的错误观点依然无条件进入最终未决账本。",
      "evidence": [
        "orchestrate_v2.py:598-609 无条件将所有带 evidence 的 P0/P1 单例加入账本，未过滤 refuted_items",
        "stop-process-20260917/unresolved-ledger.json:9-11 中仅包含无行号文件名 AGENTS.md 的条目被无条件保护"
      ],
      "severity": "P1",
      "blocking": true
    },
    {
      "id": "F6",
      "target": "orchestrate_v2.py:215-223",
      "kind": "bug",
      "claim": "normalize_target 缺失绝对路径向相对路径的转换对齐，导致不同模型针对同一代码文件的发现被切分为不同目标并产生聚类分裂。",
      "evidence": [
        "orchestrate_v2.py:219 仅执行 strip、replace 与行号正则截断",
        "stop-process-20260917/consensus-report.md:18 中绝对路径成为独立 target I14，与相对路径 I01 割裂"
      ],
      "severity": "P1",
      "blocking": true
    },
    {
      "id": "F7",
      "target": "orchestrate_v2.py:174,187-212",
      "kind": "bug",
      "claim": "extract_findings_json 采用非贪婪正则匹配 JSON 块，遭遇嵌套大括号时解析崩溃，且降级机制依赖中文关键词硬编码截断并生成低质伪发现。",
      "evidence": [
        "orchestrate_v2.py:174 中正则 r'```(?:json)?\\s*(\\{[\\s\\S]*?\\})\\s*```' 在内部嵌套闭合括号处提前截断",
        "orchestrate_v2.py:196-207 依据崩溃、误杀等字样强行切词构造 fallback findings"
      ],
      "severity": "P1",
      "blocking": false
    },
    {
      "id": "F8",
      "target": "orchestrate_v2.py:59,417,445,475 与 SKILL.md:62",
      "kind": "spec_mismatch",
      "claim": "audit 模式最大质询数被硬编码为 5，导致错排匹配质询被配额耗尽提前截断，与文档声明的 10 至 12 次调用及拓扑保证存在冲突。",
      "evidence": [
        "orchestrate_v2.py:59 设置 audit 模式 max_challenges 为 5",
        "orchestrate_v2.py:475 在 len(challenges) >= max_challenges 时跳过错排生成，实际调用次数上限严格为 10 次"
      ],
      "severity": "P2",
      "blocking": false
    },
    {
      "id": "F9",
      "target": "tests/test_cross_review_five_v2.py:57-95,132-177",
      "kind": "spec_mismatch",
      "claim": "离线单元测试套件的数据构造过于理想化，未覆盖单模型多条发现、复合表态响应与否定字符干扰等已知边界，呈现假绿特征。",
      "evidence": [
        "test_cross_review_five_v2.py:57-95 中输入数据规避了相同 target 的多重输入与中文字符冲突",
        "test_cross_review_five_v2.py:161-164 仅使用纯 CONCEDE 字符串作为质询响应模拟"
      ],
      "severity": "P2",
      "blocking": false
    }
  ],
  "unknowns": [
    "在真实的 Hermes CLI 运行环境中，各个外部 LLM 模型是否会稳定生成格式严格合规的 findings JSON 侧车文件",
    "各子进程在 Windows 环境中超时并被终止后，底层 Python 与网络连接进程的具体资源清理行为与残留状态"
  ],
  "assumptions": [
    "评估基于当前提供的 orchestrate_v2.py 源码以及 stop-process-20260917 目录下的真实静态产物记录",
    "假设评审系统的核心目标在于客观发现系统真实缺陷，而非追求表面上的流程收敛或格式统一"
  ]
}
```