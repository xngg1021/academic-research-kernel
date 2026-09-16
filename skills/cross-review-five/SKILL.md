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

| 短名 | 模型 | 提供方 |
| --- | --- | --- |
| kimi-k3 | Kimi K3 | kimi |
| dsv4pro | DeepSeek V4 Pro | deepseek |
| glm53 | GLM 5.3(始终思考推理模型) | zai |
| gemini38flash | Gemini 3.8 Flash | google |
| gemini31pro | Gemini 3.1 Pro | google |

凭证要求:各提供方的密钥按 Hermes 常规配置(deepseek 在 auth.json 凭证池,kimi 用 MOONSHOT_API_KEY,GLM 用 GLM_API_KEY,Gemini 用 GOOGLE_API_KEY)。

## 工作流

一个任务流是一个目录,内含 task.md(任务书)与可选材料。两个阶段:

1. plan:五个模型各拿同一份任务书,独立产出互不可见,写入 review-<短名>.md;
2. review:轮转配对,模型 i 审查模型 i+1 的产出,写入 review-of-<被审短名>-by-<短名>.md。

完成判定靠产物文件落盘与子进程退出,不依赖完成通知。每个模型是一个完整 Hermes 子进程,用 -m 与 --provider 覆盖模型,不动主配置。

## 用法

```bash
python ${HERMES_SKILL_DIR}/scripts/orchestrate.py <流目录> --task <任务书> --stage plan
python ${HERMES_SKILL_DIR}/scripts/orchestrate.py <流目录> --stage review
python ${HERMES_SKILL_DIR}/scripts/orchestrate.py <流目录> --stage status
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
import orchestrate as oc
assert set(oc.MODELS) == {'kimi-k3', 'dsv4pro', 'glm53', 'gemini38flash', 'gemini31pro'}
assert oc.MODELS['glm53'] == ('zai', 'glm-5.3')
pair = oc.pairings(['kimi-k3', 'dsv4pro', 'glm53', 'gemini38flash', 'gemini31pro'])
assert len(pair) == 5 and pair[0] == ('kimi-k3', 'dsv4pro') and pair[-1] == ('gemini31pro', 'kimi-k3')
print('cross-review-five smoke PASS')
```
