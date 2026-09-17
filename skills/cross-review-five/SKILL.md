---
name: cross-review-five
description: "五人异构模型小组:交叉评审、红队、生成对比,一任务书五独立产出加轮转互审."
version: 1.0.0
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cross-review, red-team, multi-model, orchestration, five-models]
    related_skills: [research-object-identity, academic-source-verification]
---

# cross-review-five

五人异构模型小组:把一个任务书分发给五个不同模型,各自独立产出,再轮转互审。适用于交叉评审、代码红队、结论核对与生成对比。

## 五人构成

| 短名 | 模型 | 提供方 (首选规范名 / 兼容别名) |
| --- | --- | --- |
| kimi-k3 | Kimi K3 | kimi-coding (兼容 kimi) |
| dsv4pro | DeepSeek V4 Pro | deepseek |
| glm53 | GLM 5.3(始终思考推理模型) | zai |
| gemini38flash | Gemini 3.8 Flash | gemini (兼容 google) |
| gemini31pro | Gemini 3.1 Pro | gemini (兼容 google) |

凭证要求:各提供方的密钥按 Hermes 常规配置(DeepSeek 在 auth.json 凭证池，Kimi 首选 KIMI_API_KEY 或 KIMI_CODING_API_KEY，兼容 MOONSHOT_API_KEY；GLM 用 GLM_API_KEY；Gemini 用 GEMINI_API_KEY 或 GOOGLE_API_KEY)。子进程已启用安全环境白名单隔离与 --ignore-rules 参数。

## 工作流 (v1 经典轮转)

一个任务流是一个目录,内含 task.md(任务书)与可选材料。两个阶段:

1. plan:五个模型各拿同一份任务书,独立产出互不可见,写入 review-<短名>.md;
2. review:轮转配对,模型 i 审查模型 i+1 的产出,写入 review-of-<被审短名>-by-<短名>.md。

完成判定靠产物文件落盘与子进程退出,不依赖完成通知。每个模型是一个完整 Hermes 子进程,用 -m 与 --provider 覆盖模型,不动主配置。

### 用法 (v1)

```bash
python ${HERMES_SKILL_DIR}/scripts/orchestrate.py <流目录> --task <任务书> --stage plan
python ${HERMES_SKILL_DIR}/scripts/orchestrate.py <流目录> --stage review
python ${HERMES_SKILL_DIR}/scripts/orchestrate.py <流目录> --stage status
```

---

## 工作流 (v2 稀疏自适应质询 Sparse Deliberation)

v2 摒弃全篇通读与固定有向环，按**最大信息增量与核心分歧**进行定向质询。包含四个阶段：

1. **plan (独立盲审)**：各模型独立产出文本并提供 `findings-<短名>.json` 结构化数据（target, claim, evidence, severity）；
2. **merge (本地图分析，零 LLM 消耗)**：本地脚本聚类 Consensus、Singleton 与 Contradiction，计算互补权重矩阵并规划质询包；
3. **challenge (定向匿名质询)**：仅对矛盾项与独有高危项生成匿名议题包，分派给互补模型进行四步法质询（增量提取→反例核验→分歧归因→CONCEDE/REFUTED 表态）；
4. **synthesize (合议与未决账本)**：生成 `consensus-report.md`，执行**少数派证据保护**（有具体定位符的独立发现绝不被多数票抹除，自动进入 `unresolved-ledger.json`）。

### 三档模式 (v2)

- `--mode economy`：3 模型盲审（kimi-k3, dsv4pro, gemini38flash），最多 1 组质询，共 3–4 次调用（轻量快捷）；
- `--mode standard`（默认推荐）：5 模型盲审，最多 3 组关键争议与单例质询，共 5–8 次调用；
- `--mode audit`：5 模型盲审，最多 5 组质询，配额有余时追加最大互补错排匹配（derangement），共 5–10 次调用（高危收口）。

调用次数 = 盲审次数 + 实际质询组数（0 到 max_challenges），与 orchestrate_v2.py 的 MODE_PRESETS 一致。

### 用法 (v2)

```bash
# 单步推进:
python ${HERMES_SKILL_DIR}/scripts/orchestrate_v2.py <流目录> --task <任务书> --stage plan --mode standard
python ${HERMES_SKILL_DIR}/scripts/orchestrate_v2.py <流目录> --stage merge --mode standard
python ${HERMES_SKILL_DIR}/scripts/orchestrate_v2.py <流目录> --task <任务书> --stage challenge
python ${HERMES_SKILL_DIR}/scripts/orchestrate_v2.py <流目录> --stage synthesize
python ${HERMES_SKILL_DIR}/scripts/orchestrate_v2.py <流目录> --stage status

# 或一键全流程执行:
python ${HERMES_SKILL_DIR}/scripts/orchestrate_v2.py <流目录> --task <任务书> --stage all --mode standard
```

--models 参数按短名选择子集,默认五人全上。任务书模板与约束见脚本内的 PLAN_PROMPT 与 REVIEW_PROMPT。

## 纪律

- 三模型一致不是证据:模型产出只是线索,出处谱系才是证据;
- 产出文件各自独立,评审者不得修改他人产出;
- 汇总与裁决由主线程完成,不在模型间多数表决;
- GLM 5.3 是始终思考模型,服务器默认思考档位为 max,耗时很长;编排器对其子进程显式传 --reasoning low,其余模型保持默认。

## Verification

```python
# smoke-test: true
import os, sys
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', os.getcwd()), 'scripts'))
# v1 smoke
import orchestrate as oc
assert set(oc.MODELS) == {'kimi-k3', 'dsv4pro', 'glm53', 'gemini38flash', 'gemini31pro'}
assert oc.MODELS['glm53'] == ('zai', 'glm-5.3')
pair = oc.pairings(['kimi-k3', 'dsv4pro', 'glm53', 'gemini38flash', 'gemini31pro'])
assert len(pair) == 5 and pair[0] == ('kimi-k3', 'dsv4pro') and pair[-1] == ('gemini31pro', 'kimi-k3')

# v2 smoke
import orchestrate_v2 as oc2
assert set(oc2.MODELS) == {'kimi-k3', 'dsv4pro', 'glm53', 'gemini38flash', 'gemini31pro'}
assert set(oc2.MODE_PRESETS) == {'economy', 'standard', 'audit'}
derange = oc2.max_weight_derangement(['A', 'B', 'C'], {('A', 'B'): 2.0, ('B', 'C'): 2.0, ('C', 'A'): 2.0})
assert len(derange) == 3 and all(r != t for r, t in derange)
print('cross-review-five (v1 + v2) smoke PASS')
```
