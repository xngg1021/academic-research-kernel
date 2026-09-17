---
name: research-reproducibility
description: "论文可复现性核对流水线：身份、代码、版本、依赖、构建与指标四态判定."
version: 1.0.0
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [reproducibility, replication, code-verification, metrics, receipt]
    related_skills: [literature-analysis, academic-source-verification, grounded-citations]
---

# 论文可复现性核对 Skill

输入论文 DOI/arXiv ID 或 GitHub 仓库地址，按固定流水线逐项核对可复现性事实，输出机器可读的 ReproductionReceipt。本技能是 `literature-analysis` 的[复现清单](../literature-analysis/references/reproduction.md)的升格：那份清单管"怎么找代码、怎么跑 demo"的实务，本技能管"每一步记下什么事实、最后下什么结论"，并多出可落盘的收据与判定脚本。

边界先说清：`scripts/repro_checklist.py` 只做结构化记录与状态判定，不克隆仓库、不装依赖、不跑复现。跑复现发生在用户的环境里；脚本负责把核对过的事实变成可复核、可存档的收据。

## When to Use

- 用户要求"核对这篇论文能不能复现""评估复现工作量""出一份复现报告"
- 复现跑完或跑失败后，需要把散乱过程整理成结构化结论
- 审稿、选题或复现竞赛前，快速判断一篇论文的代码与指标可信度
- 需要把 `academic-source-verification` 产出的证据回执接进复现核对流程

## 流水线

十四个阶段按序核对，每阶段记录一种状态：

1. **identity** 论文身份 → 2. **code-link** 官方代码链接 → 3. **repo-identity** 仓库身份 → 4. **version-consistency** 论文与代码版本/日期一致性 → 5. **release-commit** 固定 release/commit → 6. **dataset** 数据集 → 7. **model-weights** 模型权重 → 8. **dependencies** 依赖环境 → 9. **license** 许可证 → 10. **build-install** 构建安装 → 11. **smoke-run** 最小示例执行 → 12. **claimed-metrics** 论文声称指标 → 13. **measured-metrics** 实测指标 → 14. **metric-diff** 指标差异对照

各阶段核什么、怎么取证、常见失败形态，见 [references/pipeline.md](references/pipeline.md)。

## 五层事实与四态结论

结论 status 只有四值，且必须同时报告事实层 tier；分不清层级的"能复现"不可信。

| tier | 含义 | 对应 status |
| --- | --- | --- |
| no-code-found | 没找到代码 | blocked |
| environment-broken | 找到代码，但依赖安装、构建或运行环节失败 | blocked |
| runs | 能运行，没对上指标 | partially-reproducible |
| direction-reproduced | 方向/趋势复现，数值超差 | partially-reproducible |
| numbers-reproduced | 数值在容差内复现 | reproducible |

矛盾优先：任一阶段出现 mismatch（身份错配、版本对不上、实测与声称反向），status 直接判 inconsistent，不管其他阶段多顺利。硬阶段（identity、code-link、repo-identity、dependencies、build-install、smoke-run）未通过或未核对，一律 blocked，不允许"没跑就当能跑"。完整判定规则见 [references/adjudication.md](references/adjudication.md)。

## 清单格式与脚本用法

清单是一个 JSON 文件，格式规范见 [references/pipeline.md](references/pipeline.md) 的"清单 JSON 格式"一节。判定命令：

```bash
python scripts/repro_checklist.py checklist.json --pretty
python scripts/repro_checklist.py checklist.json -o receipt.json
python scripts/repro_checklist.py checklist.json --evidence-receipt er.json -o receipt.json
```

第三种形态消费符合 [evidence-receipt schema](../../schemas/evidence-receipt.schema.json) 的证据回执：脚本回填 DOI/arXiv 标识符、把回执里 status 为 ok 的来源写进 identity 阶段证据，标识符冲突时向 stderr 打 warning。脚本不会替任何阶段打 pass——阶段状态只能来自实际核对。

输出 ReproductionReceipt 字段：`status`（四态）、`tier`（五层，事实不足为 null）、`stages`（全量 14 阶段含中文标签）、`contradictions` / `blocking` / `gaps` 三组问题清单、`generated_at`。加 `--generated-at <ISO时间>` 可得到逐字节确定的输出，便于存档与 diff。

## 诚实边界

- 收据的全部依据是清单里记录的事实；没核对的阶段标 skipped/unknown，收据的 blocking 清单会如实列出。
- metric-diff 的容差由你在清单里写明（如 ±0.5 个百分点），脚本只记录 pass/fail/mismatch 的判定结果，不替你定容差。
- 数据集需申请、权重未发布、许可证限制等情况如实记 fail/missing/blocked 并写 detail，不降级成 skipped 粉饰。
- 第三方复现仓库在 repository.officiality 里标明 third-party，结论中不得冒充官方实现。

## Verification

离线冒烟：构造两份清单（全流程通过、找不到代码），跑脚本判定并断言四态与层级。

```python
# smoke-test: true
import json, os, subprocess, sys, tempfile
from pathlib import Path

skill = Path(os.environ.get('SKILL_DIR', '.')).resolve()
script = skill / 'scripts' / 'repro_checklist.py'
paper = {'title': 'Example', 'doi': '10.1234/example'}
ids = ['identity', 'code-link', 'repo-identity', 'version-consistency',
       'release-commit', 'dataset', 'model-weights', 'dependencies',
       'license', 'build-install', 'smoke-run', 'claimed-metrics',
       'measured-metrics', 'metric-diff']
cases = {
    'full': {'schema_version': '1.0', 'paper': paper,
             'stages': [{'id': i, 'status': 'pass'} for i in ids]},
    'nocode': {'schema_version': '1.0', 'paper': paper, 'stages': [
        {'id': 'identity', 'status': 'pass'},
        {'id': 'code-link', 'status': 'missing'}]},
}
env = dict(os.environ, PYTHONIOENCODING='utf-8')
with tempfile.TemporaryDirectory() as tmp:
    receipts = {}
    for name, checklist in cases.items():
        src = Path(tmp) / f'{name}.json'
        src.write_text(json.dumps(checklist), encoding='utf-8')
        out = subprocess.run([sys.executable, str(script), str(src),
                              '--generated-at', '2026-09-16T00:00:00+00:00'],
                             capture_output=True, env=env)
        assert out.returncode == 0, out.stderr.decode('utf-8', 'replace')
        receipts[name] = json.loads(out.stdout)
assert receipts['full']['status'] == 'reproducible'
assert receipts['full']['tier'] == 'numbers-reproduced'
assert receipts['nocode']['status'] == 'blocked'
assert receipts['nocode']['tier'] == 'no-code-found'
print('repro_checklist smoke OK')
```
