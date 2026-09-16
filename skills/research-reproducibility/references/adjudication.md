# 四态判定规则

`../scripts/repro_checklist.py` 的判定是确定性的：同一份清单永远得到同一份收据。规则按优先级排列如下。

## 判定优先级

1. **inconsistent**：任一阶段状态为 `mismatch`。矛盾是头等信号——身份错配、版本对不上、实测与声称反向，任何一个都让"复现"二字失去对象。即使其他阶段全 pass，也判 inconsistent。
2. **blocked**：硬阶段（identity、code-link、repo-identity、dependencies、build-install、smoke-run）任一不是 `pass`。负面事实（fail/missing/blocked）与未核对（skipped/unknown）同等处理：没核对的硬阶段不允许"没跑就当能跑"。收据 `blocking` 字段列出所有未通过的硬阶段。
3. **reproducible**：全部十四个阶段为 `pass`，或仅 dataset / model-weights / license 三个阶段以 `skipped` + `waived: true` + reason 豁免。metric-diff 必须是 `pass`。
4. **partially-reproducible**：硬阶段全过但不满足第 3 条——软阶段有 fail/unknown，或指标链断在某个位置。收据 `gaps` 字段列出挡住 full 的具体阶段。

## 五层事实 tier

status 是结论，tier 是事实水位，两者独立报告：

| tier | 判据 |
| --- | --- |
| no-code-found | code-link 或 repo-identity 有负面事实或 mismatch（找到的代码不是论文的代码） |
| environment-broken | 找到代码，但 dependencies / build-install / smoke-run 有负面事实 |
| runs | smoke-run 通过，但 claimed-metrics 或 measured-metrics 没拿到 |
| direction-reproduced | 实测完成，metric-diff 为 fail（方向一致、数值超差） |
| numbers-reproduced | 实测完成，metric-diff 为 pass（容差内一致） |
| null | 门控阶段未核对，事实不足，不定层 |

几个刻意的设计：

- tier 只看"找代码 → 跑起来 → 对指标"这条主轴，不受版本一致性、许可证等影响。所以可能出现 `partially-reproducible` + `numbers-reproduced`：数值复现了，但许可证缺失或版本对不齐，整体仍够不上 reproducible。
- identity 未核对时 tier 为 null：论文是谁都没确认，谈不到"找到它的代码"。
- metric-diff 为 mismatch 时 tier 落回 runs：能跑、数也测了，但测出的数与论文矛盾，不能称复现了方向。

## 容差怎么定

引擎不定容差，操作者在清单的 `tolerance` 字段写明并自己判 pass/fail/mismatch。经验值：

- 分类准确率/F1：±0.5 个百分点以内算 numbers-reproduced；±2 个点以内、排序不变算 direction。
- 生成类指标（BLEU、ROUGE）：评测脚本与分词差异本身能造成 1 个点以上波动，容差放宽前先确认评测管线一致。
- 跨硬件/跨框架的数值漂移：先排种子与精度（fp32/fp16/bf16），再谈容差。

论文给了方差/置信区间的，实测值落在区间内即可判 pass。

## 反例（判错的写法）

- smoke 没跑，但"看起来代码很正规"就把 smoke-run 标 pass。→ 硬阶段未核对必须 blocked。
- 数据集要申请，申请还没批，把 dataset 标 skipped。→ 外部阻断是 `blocked`，skipped 只用于"本阶段不适用"。
- 实测低了 5 个点，把 metric-diff 标 fail 但 status 仍写 reproducible。→ 引擎不会出这种收据；手写收据出现这种组合就是假的。
- 第三方复现仓库当官方仓库核对，officiality 不标。→ 结论必须区分官方与第三方。

## 判定示例

输入清单（硬阶段全过、方向一致但数值超差）：

```json
{
  "schema_version": "1.0",
  "paper": {"title": "Example", "doi": "10.1234/example"},
  "repository": {"url": "https://github.com/<org>/<repo>", "officiality": "official",
                 "commit": "<40位commit hash>"},
  "stages": [
    {"id": "identity", "status": "pass"},
    {"id": "code-link", "status": "pass"},
    {"id": "repo-identity", "status": "pass"},
    {"id": "version-consistency", "status": "pass"},
    {"id": "release-commit", "status": "pass"},
    {"id": "dataset", "status": "pass"},
    {"id": "model-weights", "status": "missing", "detail": "作者未发布权重"},
    {"id": "dependencies", "status": "pass"},
    {"id": "license", "status": "pass"},
    {"id": "build-install", "status": "pass"},
    {"id": "smoke-run", "status": "pass"},
    {"id": "claimed-metrics", "status": "pass", "evidence": "Table 2, test split"},
    {"id": "measured-metrics", "status": "pass"},
    {"id": "metric-diff", "status": "fail", "claimed_value": 92.4,
     "measured_value": 89.8, "tolerance": "±0.5pp"}
  ]
}
```

收据要点：`status: partially-reproducible`，`tier: direction-reproduced`，`gaps: [model-weights, metric-diff]`。权重缺失与数值超差都写在明处，结论不夸大也不缩小。
