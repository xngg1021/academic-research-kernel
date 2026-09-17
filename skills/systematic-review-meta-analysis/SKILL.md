---
name: systematic-review-meta-analysis
description: "系统综述与元分析流水线:PRISMA 日志、效应量互转、异质性合并、发表偏倚诊断."
version: 1.0.0
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [systematic-review, meta-analysis, prisma, effect-size, heterogeneity, publication-bias, evidence-synthesis]
    related_skills: [literature-analysis, math-computation]
---

# 系统综述与元分析 Skill

覆盖系统综述全流程:PRISMA 2020 检索日志与多库查询 manifest、DOI/标题去重、纳入排除理由账本、研究特征提取、偏倚风险表、效应量归一与互转、固定/随机效应合并、I²/τ² 异质性、敏感性与 leave-one-out、亚组分析与元回归、发表偏倚诊断(漏斗图、Egger、trim-and-fill)。

衔接:`literature-analysis` 产出候选语料与研究矩阵后进入本流水线;`math-computation` 负责通用数值与统计计算,本技能自带的 `scripts/meta_core.py` 是元分析专用纯计算函数库(numpy/scipy,无 I/O,可单测),优先用它而不是临时写公式。

不做:全文获取与 PDF 解析(用 `ocr-and-documents`/`pdf`)、文献真实性核查(用 `academic-source-verification`)、GRADE 证据分级报告排版(用 `academic-writing`)。

## When to Use

- 按 PRISMA 组织系统综述:检索日志、去重、筛选账本、流程图数字复算
- 多项研究的效应量需要统一尺度(d/g/r/OR/RR 互转)后合并
- 需要 Q、I²、τ²、固定/随机效应合并估计及其置信区间
- 敏感性分析(leave-one-out)、亚组比较、元回归
- 漏斗图、Egger 检验、trim-and-fill 发表偏倚诊断

Don't use for: 单篇文献精读(去 `literature-analysis`)、网络 Meta 分析(本库只做两两直接比较)、需要监管申报级审计追踪的临床综述(用 RevMan/Stata `meta` 出正式结果,本库作交叉验证)。

## Prerequisites

Python 3.11+,numpy、scipy。漏斗图另需 matplotlib(无头环境先 `matplotlib.use('Agg')`)。先用 `python -c "import sys; print(sys.executable)"` 确认解释器,缺包用该解释器的 `-m pip install`。离线计算不需要 API key。

## 证据回执输入(消费 evidence-receipt)

纳入研究的标识信息可以来自 `academic-source-verification` 产出的证据回执,schema 见 [evidence-receipt.schema.json](../../schemas/evidence-receipt.schema.json)。消费规则:

- 从 `identifiers`(doi / pmid / openalex_id)取去重主键;`identifiers` 全空的记录只能走标题模糊去重,并在账本里标注。
- `claims` 中 `support_status` 为 `contradicted` 或 `unverifiable` 的元数据(年份、作者、期刊)不得直接进入提取表,先人工核对原文。
- `failures` 列出的查询失败不能当作"研究不存在";全文未获取的研究进 PRISMA 的 "reports not retrieved" 格,不进排除账本。
- `generated_at` 决定回执时效;超过综述检索轮次的旧回执要重跑核查。

## 流水线

### 1. 检索日志与多库 manifest(PRISMA-S)

每库一条 manifest 记录:数据库、平台、检索日、完整执行式、限定条件、命中数、导出文件名。规则与模板见 `references/search-strategy-guide.md`。要点:全库同日检索;`query` 贴最终执行式;命中数以导出文件复核;更新检索保留旧 manifest 分轮报告。

### 2. 去重

两级去重,每级删除数单独入账(PRISMA 流程图要用):

1. 标识符精确去重:DOI 规范化(小写、去 `https://doi.org/` 前缀)后精确匹配;无 DOI 用 PMID/OpenAlex ID。
2. 标题模糊去重:标题小写、去标点、压缩空白后精确比对;候选重复对(编辑距离 ≤ 3 或一方为另一方前缀)人工确认,确认对被引合并保留最完整记录。

预印本与正式发表算同一研究的两个报告:链接到同一 study_id,提取用正式发表版本,预印本只进 PRISMA 的 "reports" 计数。

### 3. 纳入排除理由账本

每条记录一行,字段固定,存 CSV/TSV,禁止只在脑子里筛:

| 字段 | 说明 |
| --- | --- |
| record_id | 去重后的唯一编号 |
| study_id | 同一研究多报告共享 |
| stage | title-abstract / full-text |
| decision | include / exclude / maybe |
| reason_code | 单一首要理由:POP / INT / CMP / OUT / DES / DUP / LAN / FUL / DAT |
| reason_detail | 一句话原文依据(页码或段落) |
| reviewer | 筛者;双人筛选加 adjudicator 列 |

排除理由互斥且只记首要理由(按 PICO 顺序取第一个不满足项)。题录筛阶段不逐条记理由也要保证总数复算平衡。maybe 在全文筛必须清零。双人分歧率与 Cohen's κ 写入方法学部分。

### 4. 研究特征提取与偏倚风险表

提取表每行一个 study_id:设计、样本量(分组)、人群要点、干预与对照细节、随访时长、结局定义与测量时点、效应数据(均值/SD 或四格表)、资金来源。效应数据缺失时按指南换算(中位数/四分位→均值/SD 用 Wan 法;SE→SD 乘 √n;差值尺度 95% CI→SE = (upper−lower)/(2×1.96),不得再乘 √n——再乘 √n 得到的是 SD,会污染方差与权重;仅当 CI 属于单组均值且目标是 SD 时才乘 √n,并在提取表写明尺度),换算全部记 `converted_from` 列。

偏倚风险按设计选工具:RCT 用 RoB 2(五域:随机化、偏离既定干预、结局数据缺失、结局测量、结果报告选择),非随机用 ROBINS-I,诊断准确性用 QUADAS-2。判定必须附原文引句。各工具保留原生档位,不得压成同一三档:RoB 2 各域 low / some concerns / high;ROBINS-I 判 low / moderate / serious / critical / no information;QUADAS-2 各域经 signaling questions 判 low / high / unclear。敏感性分析剔除标准按工具档位:RoB 2 剔除 high,ROBINS-I 剔除 serious 与 critical,QUADAS-2 剔除 high。偏倚风险表是敏感性分析与亚组分析的分层变量。

### 5. 效应量归一与互转

合并前把全部研究归一到同一尺度、同一方向。公式与判读见 `references/effect-size-conversions.md`;一律调 `scripts/meta_core.py`,不手写公式:

```python
# fragment: 单研究效应量换算;n1/n2 为两组样本量
import sys, os
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', '.'), 'scripts'))
import meta_core as mc

d = mc.cohens_d(n1=25, n2=25, m1=5.6, m2=4.8, sd1=1.9, sd2=2.1)   # 两独立组均差
g = mc.hedges_g(d, 25, 25)                 # 小样本校正
v_g = mc.var_g(g, 25, 25)                  # 抽样方差
lor, v_lor = mc.log_or(18, 60, 9, 62)      # 四格表直接算 log OR
d2 = mc.log_or_to_d(lor)                   # log OR → d
rr = mc.or_to_rr(2.0, p0=0.2)              # OR → RR(需对照组事件率)
```

连续结局归一到 Hedges' g;二分类结局统一到 log OR,仅当满足相对偏差界(见 effect-size-conversions:给定 p0 与 OR 后 |1−RR/OR| ≤ 5%)才允许保留 RR 混用并注明。方向约定(如"正值=干预获益")写进提取表表头。

### 6. 合并估计与异质性

```python
# fragment: yi 为各研究效应量向量,vi 为对应方差(来自第 5 步)
import sys, os
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', '.'), 'scripts'))
import meta_core as mc

q, df, i2, tau2 = mc.heterogeneity(yi, vi)    # Q、df、I²(0–1)、DL 法 τ²
fe = mc.pool_fixed(yi, vi)                    # 固定效应
re_ = mc.pool_random(yi, vi)                  # 随机效应(τ²=0 时退化为固定)
print(f"FE {fe.estimate:.3f} [{fe.ci_low:.3f}, {fe.ci_high:.3f}]; "
      f"RE {re_.estimate:.3f}; I²={i2:.1%}, τ²={tau2:.4f}")
```

报告五件套:Q、df、p、I²、τ²。模型选择在方案里预先写明,不许按 I² 大小事后换模型;两模型结论不一致时两个都报并解释。τ² 默认 DL;研究数 ≥ 10 且需要更稳的 τ² 时可用 R metafor 的 REML 交叉验证。

### 7. 敏感性分析、亚组与元回归

```python
# fragment: leave-one-out 与亚组比较
import sys, os
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', '.'), 'scripts'))
import meta_core as mc
import numpy as np

loo = mc.leave_one_out(yi, vi, model='random')     # 逐一剔除重合并
ests = [r.estimate for r in loo]
print(f"leave-one-out 范围 [{min(ests):.3f}, {max(ests):.3f}]")

# 亚组:mask 为布尔向量(如 RoB 低 vs 高);Q_between = Q_total - ΣQ_within
import numpy as np
def q_between(yi, vi, mask):
    yi, vi = np.asarray(yi), np.asarray(vi)
    q_tot = mc.heterogeneity(yi, vi)[0]
    q_w = sum(mc.heterogeneity(yi[m], vi[m])[0] for m in (mask, ~mask))
    df = 1  # 两亚组
    from scipy import stats
    return q_tot - q_w, 1 - stats.chi2.cdf(q_tot - q_w, df)

# 元回归:加权最小二乘,X 为研究层协变量(每研究一行)
def meta_regression(yi, vi, X):
    yi, vi, X = map(np.asarray, (yi, vi, X))
    W = np.diag(1.0 / (vi + mc.heterogeneity(yi, vi)[3]))
    Xt = X.T @ W
    beta = np.linalg.solve(Xt @ X, Xt @ yi)
    cov = np.linalg.inv(Xt @ X)
    return beta, np.sqrt(np.diag(cov))
```

leave-one-out 报估计值范围;某研究剔除后结论翻转必须讨论。亚组差异用 Q_between 卡方检验,不凭两个亚组各自 CI 是否重叠下结论。元回归每协变量至少约 10 项研究,否则只作探索。

### 8. 发表偏倚诊断

```python
# fragment: 漏斗图 + Egger + trim-and-fill;yi/vi 同前,k = len(yi)
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', '.'), 'scripts'))
import meta_core as mc
import numpy as np

se = np.sqrt(np.asarray(vi))
if len(se) >= 3:
    intercept, t, p = mc.egger_test(yi, vi)   # 截距偏离 0 提示不对称
if len(se) >= 10:
    tf = mc.trim_and_fill(yi, vi, side='left')  # L0 估计量;k0 为估计缺失数
    print(f"trim-and-fill: k0={tf['k0']}, 校正后 {tf['adjusted']:.3f}")

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.scatter(yi, se)
ylim = ax.get_ylim(); ax.set_ylim(ylim[1], 0)   # 纵轴倒置
est = mc.pool_fixed(yi, vi).estimate
ax.axvline(est, ls='--', lw=0.8)
ax.set_xlabel('effect size'); ax.set_ylabel('standard error')
out = os.path.join(os.environ.get('PLOT_DIR', tempfile.gettempdir()), 'funnel.png')
fig.savefig(out, dpi=150); plt.close(fig)
```

k < 10 时漏斗图与 Egger 效能不足,只描述不检验;trim-and-fill 只在 k ≥ 10 时给,且标为敏感性分析。不对称 ≠ 发表偏倚:异质性、小研究方法学质量、结局选择同样造成不对称。正式投稿用 R `metafor::trimfill` 复核 k0。

## 输出物清单

1. `search-manifest.yaml` + 各库原始导出文件
2. `screening-ledger.csv`(含去重删除明细)
3. `extraction.csv` + `risk-of-bias.csv`
4. 各结局合并结果表(效应量、CI、Q/I²/τ²、模型)
5. 敏感性分析表(leave-one-out 范围、剔除 high-risk 结果)
6. 漏斗图 + Egger 结果(+ k ≥ 10 时 trim-and-fill)
7. PRISMA 2020 流程图数字(全部由账本复算)

## Pitfalls

- 事后按 I² 换模型、按结果挑效应量尺度:都是方案偏离,必须注明。
- OR/RR 互转忘给 p0,或 d↔r 互转用于正式合并:尺度换算的假设写不清楚就别转。
- τ² 为 0 时报"无异质性":τ² 估计不确定,报告点估计即可,不下"同质"结论。
- 把"全文未获取"混进"排除":两类在 PRISMA 里是不同格子。
- 中文库记录 UTF-8 没统一就模糊去重:漏配率显著升高。
- Egger 检验用普通最小二乘忘了精度是 1/√v:`meta_core.egger_test` 已内置正确回归,别自己拼。

## Verification

```python
# smoke-test: true
import sys, os, math
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', os.getcwd()), 'scripts'))
import meta_core as mc

# 手算对照一:d=0.4, n1=n2=25 → J=1-3/191, g=J·d
assert abs(mc.hedges_g(0.4, 25, 25) - 0.4 * (1 - 3 / 191)) < 1e-12
# d→log OR = (π/√3)d,往返一致
assert abs(mc.log_or_to_d(mc.d_to_log_or(0.4)) - 0.4) < 1e-12
# 手算对照二:yi=[0.2,0.5,0.8], vi=0.05×3 → Q=3.6, I²=1.6/3.6, τ²=0.04
q, df, i2, tau2 = mc.heterogeneity([0.2, 0.5, 0.8], [0.05, 0.05, 0.05])
assert abs(q - 3.6) < 1e-12 and df == 2 and abs(i2 - 1.6 / 3.6) < 1e-12 and abs(tau2 - 0.04) < 1e-12
# 手算对照三:两项 d=0.4、n=50 研究固定效应合并 θ=0.4, se=√(v/2)
v = mc.var_d(0.4, 25, 25)
fe = mc.pool_fixed([0.4, 0.4], [v, v])
assert abs(fe.estimate - 0.4) < 1e-12 and abs(fe.se - math.sqrt(v / 2)) < 1e-12
# τ²=0 时随机效应退化;对称数据 trim-and-fill k0=0;leave-one-out 长度=k
re_ = mc.pool_random([0.4, 0.4], [v, v])
assert abs(re_.estimate - fe.estimate) < 1e-12 and abs(re_.se - fe.se) < 1e-12
assert mc.trim_and_fill([0.2, 0.5, 0.8], [0.05, 0.05, 0.05])['k0'] == 0
assert len(mc.leave_one_out([0.2, 0.5, 0.8], [0.05, 0.05, 0.05])) == 3
print('systematic-review-meta-analysis Verification passed (hand-checked invariants)')
```
