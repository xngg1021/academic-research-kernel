# Cross-Review Five v2 Implementation Contract

来源:2026-09-17 五人异构模型自我评审合议报告(consensus-report.md),25 项未决发现全部入约。
依据分支:review/v2-self-audit-20260917(对抗性证据分支)。
施工起点:main@7fd5e797b4bbc3b216f9afe374a6b5a9119562c0。
设计原则:确定性计算归本地脚本,语义判断归质询阶段;每项验收标准必须可测试。

## P0(必须全部修掉,任一不达标不送 PR)

### C01 聚类按独立模型数判定,消灭伪共识
缺陷:cluster_issues 按 finding 条数(len(items)==1)判定单例/多例,同一模型对同一 target 的多条 finding 被标为 consensus 或 contradiction。
定位:orchestrate_v2.py cluster_issues(约 293-347 行)。
验收:
- state 判定输入改为"raised_by 去重后的模型集合",consensus 要求 ≥2 个不同模型;
- 单模型多条 findings 同 target 归为 singleton;
- 测试:单模型双 findings 同 target 不产生 consensus。

### C02 矛盾判定改为断言级,消灭伪矛盾
缺陷:is_conflict 用"kinds 不同或 claim 含'不/错'字"判定矛盾,同向观点大量误判为对立,伪矛盾占满质询配额。
定位:orchestrate_v2.py cluster_issues 内 is_conflict 段(约 326-332 行)。
验收:
- 删除"不/错"字面启发式与 kinds 异同启发式;
- 矛盾判定改为:同 target 下,≥2 个不同模型给出互斥断言(polarity 字段:present/absent 或 positive/negative);findings JSON 无 polarity 时,疑似冲突对交由 challenge 阶段 LLM 判定,merge 阶段不得自行贴 contradiction 标签;
- 测试:五模型同向 findings 不再产出 contradiction;互斥 polarity 对产出 contradiction。

### C03 目标路径 canonical 归一,消灭路径裂变与幽灵路径
缺陷:normalize_target 不做路径等价归一,同一文件以绝对/相对/裸名出现裂成多个 target;fallback 正则不匹配盘符冒号,正则片段被当文件路径。
定位:orchestrate_v2.py normalize_target(约 215-222 行)与 extract_findings_json fallback 正则(约 186-212 行)。
验收:
- normalize_target 输出 canonical 形式:basename + 关键父目录段的小写路径,去行号;绝对/相对/盘符冒号/正反斜杠全部等价;复合描述式 target(文件名+函数+行号)归一后按文件聚合(C12 实测补充);
- fallback 提取的 target 必须匹配实际存在的文件路径或 basename,否则丢弃;
- 测试:同一文件五种写法归一后相等;复合描述归一相等;正则片段不产生 target。

### C04 findings 结构化强制 + provenance 标记
缺陷:该轮 run 五模型无一自觉落盘 findings JSON,100% 由正则启发式合成,claim 截断 140 字符,证据引用行被当 finding;sidecar 与亲笔 JSON 无来源区分,重跑时陈旧 sidecar 无条件压过新产出。
定位:orchestrate_v2.py extract_findings_json(约 158-212 行)、PLAN_PROMPT_V2(约 68-101 行)。
验收:
- PLAN_PROMPT_V2 明确要求模型写出 findings JSON 文件(指定 schema),kind 枚举与代码一致(消灭 'observation' 等枚举外值);
- findings 条目带 provenance 字段:model_written 或 synthetic_fallback;
- extract_findings_json 优先读模型亲写 sidecar;fallback 仅在 sidecar 缺失时运行且标记 provenance;sidecar 解析失败时报错而非静默用旧文件;
- 测试:sidecar 存在时不走 fallback;fallback 产物带 synthetic 标记;非对象 JSON(sidecar 为数组)不引发 AttributeError。

### C05 synthesize 完整对账 + 逐断言表态解析
缺陷:synthesize 不与 challenge-plan 对账,3 组质询 1 份答复静默通过;表态按整文件 if-elif 归类,混合表态答复被压成单一类别,REFUTED/UNRESOLVED 丢失;矛盾项与质询答复内容整体缺席最终报告。
定位:orchestrate_v2.py stage_synthesize_v2(约 567-645 行)。
验收:
- synthesize 与 challenge-plan 逐项对账,缺失答复在报告显式列出(标 MISSING);
- 表态解析按块/逐条收集:一份答复可同时计入 CONCEDE、REFUTED、UNRESOLVED 三个集合;
- 最终报告增加"矛盾与质询"章节,呈现 contradiction 聚类与质询答复要点;
- 测试:混合表态答复解析出三类各计数;缺席答复被报告点名。

## P1(必须修,优先级略低于 P0)

### C06 质询匿名性:排除当事人 + 去指纹
缺陷:reviewer = raised[0] 即争议当事人;bundle 提案按模型阵容顺序排列可解码作者;质询子进程可读同目录全部 review 原文。
定位:orchestrate_v2.py stage_challenge_v2 reviewer 选取(约 419-421 行)、bundle 生成。
验收:
- reviewer 从"未参与该 issue 的模型"中选,确定性且可复现(不再依赖 set 迭代序);
- bundle 提案以 Proposal-N 匿名呈现,排列顺序随机化(固定随机种子),不含模型短名;
- challenge prompt 声明"不得读同目录其他评审产出"。

### C07 少数派保护与证伪联动 + 证据校验
缺陷:保护逻辑无条件收录全部 P0/P1 单例,不与被 REFUTED 项求交集;evidence 定位符不校验是否真实存在。
定位:orchestrate_v2.py stage_synthesize_v2 保护段(约 596-608 行)。
验收:
- 保护前排除已被质询 REFUTED 的条目;
- evidence 中文件路径经存在性校验,幽灵路径不得入账;
- 测试:REFUTED 单例不进 ledger;幽灵证据不进 ledger。

### C08 三档模式拓扑与文档一致
缺陷:SKILL.md 声明 standard 7-8 次、audit 10-12 次,代码实际 5-8、5-10;derangement 与矛盾/单例质询共享配额,与文档暗示不符。
验收:SKILL.md 与 MODE_PRESETS 调用次数逐档核对后修正;删除"压降 60%+"等无测量对应物的表述,或补上测量方法。

### C09 raised_by 顺序确定性
缺陷:raised_by 由 set 去重生成,哈希随机化导致重跑 merge 时质询分配不确定,幂等性不成立。
验收:raised_by 保序(list + 按出现序去重),同一输入两次 merge 产出字节一致。

### C10 容错链加固
缺陷:单模型失败整阶段判负且无降级续跑;JSON 提取用非贪婪正则,嵌套括号提前截断。
验收:
- wait_for_outputs 单模型超时/失败时,其余产出正常进入 merge,缺失模型在报告标注;
- JSON 块提取改用平衡括号扫描或 json.JSONDecoder.raw_decode;
- 测试:嵌套括号 JSON 正确解析。

### C11 测试覆盖补全
缺陷:6 项测试避开全部真实雷区(伪共识、路径混用、fallback 启发式、混合表态、缺席对账、超时分支)。
验收:为 C01-C10 每项补至少一条测试;测试总数不少于 15 项;全部通过。

### C12 验证性运行
验收:修复完成后,用 economy 档(3 模型 3-4 次调用)跑一轮真实评审作为冒烟验证,产出四阶段文件完整且对账无 MISSING。此步消耗模型 API,需主线程批准后执行。

## 完成定义(Definition of Done)

- C01-C11 全部达标,pytest 全绿;
- SKILL.md 与代码一致(C08);
- 施工分支 push 后 CI(Skill correctness QA)成功;
- 契约本文件随施工分支更新状态标记(每项:未开始/进行中/已达标);
- C12 验证性运行完成后,方可开 PR 进 main。

## 演进与落地状态 (2026-09-17 最新对账)

1. C01~C12 全部验收项均已达标并经测试锁定；
2. 经多轮深度重审，缺陷治理范围已由最初的 C01-C12 扩充至全仓 41 项缺陷治理：
   - 编排状态机与裁决机制 (R01~R09) 全部落实并通过测试验收；
   - 学术监控并发与三态 (M01~M06) 全部完成逻辑加固并通过测试；
   - 语料合并并查集与 BibTeX 互转 (L01~L07) 全部实现算法升级并通过单测锁定；
   - 来源核验与统计反算 (A01~A02, S01~S02, Q01~Q03) 全部完成边界修正并通过校验；
   - 科学计算执行层薄层 (C01~C11) 全部完成六平台适配与门禁覆盖；
   - 长尾场景生成元数据 (F01) 已完成重生成与校验；
3. 全仓回归测试集扩充至 439 项（包含 test_audit_batch2 ~ batch6），六平台 CI 矩阵全绿。
