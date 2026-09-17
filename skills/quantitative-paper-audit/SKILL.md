---
name: quantitative-paper-audit
description: 论文定量 claim 反算与数值体检:效应量、p 值、CI、OR/RR、功效错配检测.
version: 1.1.0
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms:
- linux
- macos
- windows
tags:
- statistics
- audit
- effect-size
- p-value
- confidence-interval
- power-analysis
- reproducibility
metadata:
  tags: statistics, audit, effect-size, p-value, confidence-interval, power-analysis,
    reproducibility
  related_skills: academic-source-verification, literature-analysis, math-computation
---


# 论文定量体检 Skill

输入论文报告的统计量(均值、SD、t/F/χ²、β、SE、CI、2×2 表计数、样本量、效应量),用确定性公式重算可独立推导的数值,输出 reported / recomputed / difference / inputs / formula / library / confidence 结构化结果,并判定八类常见错配。定位是 paper numerical lint:回答“这些数字彼此是否自洽”,不做学术打假,不判断研究结论真伪。

数字自洽不等于结论正确;数字错配也不等于造假,四舍五入、排版转录、SE 与 SD 混淆都能造成错配。报告结论时区分“不可能”(违反数学上界)与“不一致”(超出报告精度容差)。

## When to Use

- 审稿或读论文时核对“这个 p 值和 t 值对不对得上”“CI 和点估计矛不矛盾”
- 从摘要报告的均值与 SD 反算效应量,判断“效应大”的说法有无数字支撑
- 从 2×2 计数重算 OR/RR 及其 CI,核对论文报告的比值指标
- 用样本量与效应量反算实现功效,核对“样本量经功效分析确定”的表述
- 核对百分比分母、自由度与样本量、正文与表格数字的一致性
- 消费 academic-source-verification 产出的 evidence receipt,对其中的定量 claim 做重算体检

Don't use for: 原始数据再分析(本技能只处理报告层面的汇总统计量)、撤稿与真实性核查(去 `academic-source-verification`)、统计方法选择是否恰当的判断(超出数值自洽范围,须人工)。

## Prerequisites

Python 3.11+,NumPy、SciPy >=1.11、statsmodels >=0.14。先用 `python -c "import sys; print(sys.executable)"` 确认解释器,缺包用该解释器的 `-m pip install` 或 `uv pip install --python <venv-python>` 安装。全部计算离线进行,不需 API key。

## 执行方式

核心计算集中在 `scripts/recompute.py`,全部为纯函数(无 I/O、无随机性),可直接 import 使用:

```python
# fragment: 从技能目录导入函数库;SKILL_DIR 指向技能根目录。
import sys
from pathlib import Path
sys.path.insert(0, str(Path('<SKILL_DIR>') / 'scripts'))
import recompute

result = recompute.p_from_t(2.31, df=8, reported=0.05)
print(result['recomputed'], result['difference'])
```

每条重算结果包含:reported(论文报告值,未提供为 None)、recomputed(重算值)、difference(差值)、inputs(参与计算的输入)、formula(公式文字)、library(执行计算的库函数)、confidence(high=确定性公式直算;medium=受报告值四舍五入影响,如功效反算与 CI 反推 SE)。

## 工作流

### 工作流 1:效应量反算(均值与标准差 → Cohen's d / Hedges' g)

输入两组均值、SD、样本量,`cohens_d(m1, sd1, n1, m2, sd2, n2, reported=...)` 返回 d、小样本校正 g、合并 SD 与自由度。论文报告了 d 时把报告值传入 reported,直接得到 difference。SD 报告精度低时 d 的尾数不可较真,判定容差见 `references/mismatch-catalog.md`。

### 工作流 2:p 值反算(t/F/χ² + 自由度)

`p_from_t(t, df)`、`p_from_f(f, df1, df2)`、`p_from_chi2(chi2, df)` 返回重算 p 值(t 取双侧,F 与 χ² 取右尾,与 ANOVA/回归整体检验惯例一致)。论文只写“p < .05”时把重算 p 与阈值比较方向即可,不调用 `check_p_match`。单侧检验须先把论文报告的 p 乘 2 再核对,或确认其统计量对应单侧界值。

### 工作流 3:CI 与点估计一致性

`check_ci_consistency(estimate, lower, upper, level=0.95, log_scale=False)` 做两件事:点估计是否落在 CI 中点上(差值类用算术中点,OR/RR/HR 等比值类置 log_scale=True 用几何中点),并由 CI 半宽反推 SE 供交叉核对。比值类指标用错尺度是最常见误检来源,拿不准时两个尺度各跑一次。

### 工作流 4:β 与 SE → Wald 统计量

`z_from_beta_se(beta, se)` 重算 z = β/SE 与双侧正态近似 p。logistic/Cox 的大样本报告适用;小样本 OLS 应改用 p_from_t 并把残差自由度传入。返回的 z 可与论文报告的 Wald χ² 对照:Wald χ²(1) = z²。

### 工作流 5:2×2 表 → OR/RR 及置信区间

`or_rr_from_2x2(a, b, c, d, level=0.95)` 输入暴露组事件/未事件数 a、b 与对照组 c、d,返回 OR、RR、两组风险及 log-Wald CI。出现 0 格时自动施加 Haldane-Anscombe 0.5 校正并置 confidence='medium',报告时必须注明校正。行/列约定填反会把 OR 变成倒数,输入前先核对表头定义。

### 工作流 6:功效与样本量反算

`achieved_power_ttest(d, n1, n2, alpha=0.05)` 由 Cohen's d 与每组样本量算实现功效;`required_n_ttest(d, power=0.8, alpha=0.05)` 反解所需样本量(连续解,报告时向上取整)。两者都基于两独立样本 t 检验,功效结果受 d 报告精度影响,confidence='medium',判定时给出区间而非单点。其他设计的功效分析(相关、单样本、方差分析)见 `references/formulas.md` 的 statsmodels 对应入口。

### 工作流 7:错配检测

检测函数统一返回 {'consistent': bool, ...} 与判定依据:

- `check_p_match(reported_p, recomputed_p, decimals=None)`:按报告精度(小数位数)取四舍五入容差判定 p 值错配。
- `check_percentage(count, percent, denominator=None)`:百分比分母核对;给了分母直接重算,没给就反推隐含分母。
- `check_sd_possible(sd, minimum, maximum, n=None)`:有界量表 SD 是否超出理论上界(不可能的 SD)。
- `check_sample_size_from_df(df, reported_n, kind=...)`:由自由度反推样本量,与声明 N 核对,支持单样本/配对/双样本 t 与回归残差自由度。
- `values_agree(a, b, rel_tol=1e-3, abs_tol=None)`:正文与表格、摘要与结果两处报告值一致性。

八类错配的判定规则、容差依据与报告模板见 `references/mismatch-catalog.md`;多重比较表述含糊没有可编程判定,按该文件的核对清单人工标注。

## Pitfalls

1. **报告精度限制判定强度**。统计量只给两位小数时,重算 p 的尾数差异多是舍入噪声;结论区分“超出舍入容差”与“数学上不可能”,后者(如 SD 超过有界量表上界)才是硬错配。
2. **单侧/双侧混淆**。论文若做单侧检验却按双侧惯例核对,会误报 p 值错配;先确认检验方向再选函数或换算。
3. **SE 与 SD 混淆是高频错误**。反推 SE 与报告“SD”相差 sqrt(n) 倍时,优先怀疑作者把 SE 标成了 SD,在报告中写明这一可能性,不直接断言错误。
4. **2×2 表方向**。OR 的倒数对应行/列互换;RR 对方向敏感且没有对称性,核对前确认暴露定义与事件定义。
5. **CI 反推 SE 仅供交叉核对**。端点四舍五入会放大 SE 尾数误差,不用它做精确推断;log 尺度与算术尺度选错会产生假错配。
6. **自洽 ≠ 正确**。全部数字一致只说明转录层面没有矛盾,不证明统计方法恰当、数据真实或结论成立;报告措辞保持“未发现数值不一致”而非“结果可信”。

## Verification

```python
# smoke-test: true
# 离线自检:经典统计界值与手算例子,不需网络与外部服务。
import os
import sys
from pathlib import Path

base = Path(os.environ.get('SKILL_DIR', '.')).expanduser().resolve()
sys.path.insert(0, str(base / 'scripts'))
import recompute

assert abs(recompute.p_from_t(2.306, 8)['recomputed'] - 0.05) < 1e-3
assert abs(recompute.p_from_chi2(3.841, 1)['recomputed'] - 0.05) < 1e-3
d = recompute.cohens_d(5, 2, 10, 3, 2, 10)['recomputed']
assert abs(d['cohens_d'] - 1.0) < 1e-12 and abs(d['hedges_g'] - 68 / 71) < 1e-12
orr = recompute.or_rr_from_2x2(20, 80, 15, 85)['recomputed']
assert abs(orr['odds_ratio'] - 1700 / 1200) < 1e-9
assert abs(orr['risk_ratio'] - 4 / 3) < 1e-9
assert abs(recompute.achieved_power_ttest(0.5, 64)['recomputed'] - 0.80) < 0.01
assert not recompute.check_p_match(0.04, 0.046)['consistent']
assert recompute.check_percentage(33, 33.3, denominator=99)['consistent']
assert not recompute.check_sd_possible(2.5, 1, 5, n=100)['consistent']
assert recompute.check_sample_size_from_df(58, 60)['consistent']
assert recompute.check_ci_consistency(1.0, 0.51, 1.49)['consistent']
assert not recompute.check_ci_consistency(1.0, 0.5, 2.0)['consistent']
assert (base / 'references' / 'formulas.md').is_file()
assert (base / 'references' / 'mismatch-catalog.md').is_file()
print('quantitative-paper-audit Verification passed (deterministic landmarks)')
```

## Evidence Receipt 输出约定

输入侧可以直接消费上游 receipt:把 [schemas/evidence-receipt.schema.json](../../schemas/evidence-receipt.schema.json) 中 claims 数组里 evidence_type 为 "computed" 或 "full_text" 的定量 claim 提取出来,逐条重算。输出侧把体检结论写回同一份 receipt 结构(示例见 [examples/evidence-receipt.example.json](../../examples/evidence-receipt.example.json)),要点:

- 每条体检结论写成一个 claim,`evidence_type` 固定为 "computed",`source` 注明 "quantitative-paper-audit/recompute.py"。
- `support_status` 映射:重算与报告一致写 "supported";确认错配写 "contradicted";报告精度不足无法判定写 "unverifiable"。
- `locator` 填论文内的统计量位置(表号、页码、小节);错配细节(reported/recomputed/difference)并入 claim 文本,不塞进口径之外的字段。
- 原始输入缺项(如缺自由度)导致的无法重算写入 `failures`,不当作 claim 推断。
