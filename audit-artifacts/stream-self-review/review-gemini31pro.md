# 评审意见：cross-review-five v2 编排器

依据任务书要求，我独立完成了对 v2 编排器（`orchestrate_v2.py`）及关联证据材料的审查。以下是按维度输出的评审结果。

## 一、算法正确性

1. **Issue 聚类逻辑存在缺陷（核心漏洞）**：`cluster_issues` 函数在判定单例、共识与矛盾时，仅仅校验同一目标的条目总数（`len(items) > 1`），未对输出该条目的模型身份（`raised_by`）去重。在实际产生的 `issue-registry.json` 证据中，`I12` 仅由 `gemini38flash` 一家提出，`I14` 仅由 `gemini31pro` 一家提出，均因包含多个细分断言（claims）而被错误聚类为“共识”（Consensus）。这彻底破坏了交叉评审的“共识”语义。
2. **路径归一化失配**：`normalize_target` 函数仅做了截断行号与替换斜杠的浅层清理，无法对齐绝对路径与相对路径。在证据中，指向同一文件 `approval_detection.py` 的发现，因路径格式不同被拆分成了孤立的 `I14` 和跨模型争议的 `I01`。
3. **互补错排匹配正确**：`compute_complementarity_matrix` 与 `max_weight_derangement` 的权重构建和无定点双谱匹配（消除自环）逻辑实现无误，理论时间复杂度能够支撑小规模模型池的运算。

## 二、流程健壮性

1. **缺乏对单节点崩溃的降级宽容**：`wait_for_outputs` 方法在判定 `procs_ok and not files_ok` 时返回 `False`，这使得任何一个模型的接口超时或异常退出，都会在 `main` 函数中抛出退出码 1，从而中止后续所有的图分析与质询流程。在异构多模型调用场景下，由于外部 API 不稳定的单点故障导致全局瘫痪，健壮性欠佳。
2. **重跑幂等性良好**：数据基于本地 `json` 与 `markdown` 承载，各阶段（plan / merge / challenge / synthesize）读写操作边界分明，状态依赖明确，中断后反复触发不会发生数据脏写。

## 三、经济性

1. **无本地 LLM 消耗属实**：`merge` 阶段聚类与图计算、`synthesize` 阶段账本核算均纯靠 Python 字典逻辑及正则规则实现，没有夹带隐式的 LLM API 轮询。
2. **拓扑规模与文档声明存在偏差**：`SKILL.md` 标注 Audit 模式为 10-12 次调用。但在 `orchestrate_v2.py` 中，`max_challenges` 配置项直接卡死了质询增量的天花板为 5 组，因此实际总调用次数被严格封顶在 10 次（5次盲审 + 5次质询），在当前硬编码逻辑下无法触及文档所称的 11-12 次调用。

## 四、文档一致性

`SKILL.md` 中的用法说明与命令范例（包含各个 `--stage` 及 `--mode`）均与脚本实际参数表（`argparse`）严密映射，不存在过期的旧版参数残留。

## 五、设计性质疑

1. **少数派证据保护存在致命的“免死金牌”漏洞**：系统标榜“提取增量优先于表态”，设立了未决账本以保护高危单例。但在 `stage_synthesize_v2` 代码中，对 `registry.get("singletons")` 的遍历判定，直接全数摘取了带有证据的 P0/P1 项目，**全然没有剔除已被质询对象标记为【REFUTED】的被证伪项**。单例无论是否通过了针对性质询，都会直接硬着陆进入 `unresolved-ledger.json`。
2. **冲突推测正则易导致假阳性**：在判定同一目标的相异断言是否为冲突时，采用的是 `any("不" in claim or "错" in claim)` 的极简规则。如果两个模型高度一致地认为“这段代码存在错漏”，此机制会直接将其误判为 `contradiction`，平白浪费了后续的质询调用额度。
3. **防身份泄露存在盲区**：虽然系统对 `bundle.json` 做了源别名（如 `Proposal-1`）封装，但在直接复制模型原始 `claim` 入参时，未进行代词或自我声明的清洗，其他模型仍能凭借文风或内嵌的特征描述还原审查者身份。

## 六、测试覆盖

`test_cross_review_five_v2.py` 的测试用例覆盖面停留在“理想单路径”校验。例如 `test_cluster_issues` 用例中，构造的 `findings_by_model` 输入均为“一模型、一目标、单断言”的扁平分布，彻底遗漏了单模型对同一目标输出多条断言的场景测试，导致无法在单元测试阶段阻断聚类算法的错判漏洞。

## 七、评审结论

**明确回答**：这个 v2 编排器当前**不值得信任**用于生产评审。系统立项的核心创新点——基于共识与争议拓扑的图结构调度——存在基础设施层面的硬伤，生成的裁决清单混杂了大量噪音与逻辑错位。

**下次使用前必须修复的缺陷**：
1. 重构 `cluster_issues` 的分组去重逻辑：共识与冲突必须建立在 `len(set(raised_by)) > 1` 的基础之上，禁止把单一模型的多个细分发现识别为共识。
2. 修复“少数派证据保护”漏洞：写入 `unresolved_ledger` 之前，必须对目标进行 `refuted_items` 的查库拦截，移除被证明无效的断言。
3. 将 `normalize_target` 引入工作区相对路径约束，修复绝对路径无法对齐导致的同文件议题分裂问题。

```json
{
  "findings": [
    {
      "id": "F1",
      "target": "orchestrate_v2.py:311-344",
      "kind": "bug",
      "claim": "cluster_issues 聚类逻辑未能对模型身份去重，单模型在同一目标的多条发现被误判为跨模型共识。",
      "evidence": ["issue-registry.json 确凿记录了 I12（仅由 gemini38flash 提出）和 I14（仅由 gemini31pro 提出）被错误归入 consensus 分组。"],
      "severity": "P0",
      "blocking": true
    },
    {
      "id": "F2",
      "target": "orchestrate_v2.py:598-608",
      "kind": "bug",
      "claim": "少数派证据保护逻辑未过滤已证伪项，被成功反驳的高危单例仍会被强制保留。",
      "evidence": ["stage_synthesize_v2 函数在遍历 registry.get(\"singletons\", []) 时，直接判断 severity 和 evidence 附加到未决账本，缺乏针对 refuted_items 的拦截排查。"],
      "severity": "P0",
      "blocking": true
    },
    {
      "id": "F3",
      "target": "orchestrate_v2.py:328-331",
      "kind": "spec_mismatch",
      "claim": "is_conflict 冲突判定规则易造成假阳性误判，包含“错”字的共识表述会被错误标记为矛盾。",
      "evidence": ["代码使用 any(\"不\" in ... or \"错\" in ...) 会无差别匹配“代码写错了”等指出缺陷的肯定性共识断言。"],
      "severity": "P1",
      "blocking": true
    },
    {
      "id": "F4",
      "target": "orchestrate_v2.py:215-222",
      "kind": "bug",
      "claim": "normalize_target 未统一绝对与相对路径，导致同文件目标被拆分为多个独立议题。",
      "evidence": ["issue-registry.json 中 I14 (绝对路径) 与 I01 (相对路径) 指向同一 approval_detection.py 文件，却在图中形成了两个独立的顶点。"],
      "severity": "P1",
      "blocking": true
    },
    {
      "id": "F5",
      "target": "orchestrate_v2.py:150-151",
      "kind": "robustness",
      "claim": "wait_for_outputs 缺乏局部容错机制，任一子进程缺失产出会导致后续链路全盘中断。",
      "evidence": ["当 procs_ok and not files_ok 成立时直接 return False，无视其余正常完成的审查结果。"],
      "severity": "P1",
      "blocking": false
    },
    {
      "id": "F6",
      "target": "SKILL.md",
      "kind": "spec_mismatch",
      "claim": "SKILL.md 关于 audit 模式的 API 调用消耗估计与代码实际硬编码上限冲突。",
      "evidence": ["文档声称 audit 模式消耗 10-12 次调用，但代码配置 max_challenges 值为 5，因此总调用硬上限被封顶在 10，无法触达 11-12 的标称区间。"],
      "severity": "P2",
      "blocking": false
    }
  ],
  "unknowns": [
    "模型在 challenge 阶段输出 REFUTED/CONCEDE 等表态的具体格式容错边界（例如是否混杂了 markdown 无序列表或外层引号）未经大规模实盘数据验证，纯文本模糊匹配可能存在漏判隐患。"
  ],
  "assumptions": [
    "假设各个子模型产出的 JSON 结构能够被 `extract_findings_json` 稳定解析（未遭上下文截断破坏），以便聚类逻辑获取完整可用的底层断言数据。"
  ]
}
```