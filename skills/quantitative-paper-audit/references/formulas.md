# 反算公式与适用条件

本文件给出 `../scripts/recompute.py` 各函数背后的公式、适用条件与边界情形。符号:sf 为生存函数(1-CDF),z_α 为标准正态分位数。

## 1. 效应量(两组独立样本)

合并标准差:

```
sp = sqrt(((n1-1)·sd1² + (n2-1)·sd2²) / (n1+n2-2))
d  = (m1 - m2) / sp
```

Hedges' g 小样本校正:df = n1+n2-2,J = 1 - 3/(4·df - 1),g = d·J。

适用条件:sd 为样本标准差(分母 n-1)。论文若给的是 SE,先换算 SD = SE·sqrt(n) 再代入,换算本身要在报告里写明。两样本相关(配对)设计不能用此式,需配对 SD 或相关系数。

## 2. 统计量 → p 值

| 统计量 | 公式 | 尾部 |
| --- | --- | --- |
| t(df) | p = 2·sf_t(\|t\|, df) | 双侧 |
| F(df1, df2) | p = sf_F(F, df1, df2) | 右尾 |
| χ²(df) | p = sf_χ²(χ², df) | 右尾 |

注意:F(1, df) = t_df²,两者 p 值应精确一致,可互相交叉验证。论文报告单侧 p 时,重算双侧 p 应约等于报告值的 2 倍;先确认检验方向再判定错配。

## 3. CI 与点估计

差值类指标(均值差、β):estimate ≈ (lower+upper)/2,反推 SE = (upper-lower)/(2·z),z = Φ⁻¹(1-(1-level)/2),95% 时 z ≈ 1.959964。

比值类指标(OR/RR/HR):estimate ≈ sqrt(lower·upper),log 尺度反推 SE = ln(upper/lower)/(2·z)。对数变换后区间对称,所以几何中点才是正确的核对点。

边界:点估计为 0 或区间跨 0 时,相对偏差的分母退化,实现里用 max(|lower|,|upper|) 兜底,解释时以绝对差为准。

## 4. β 与 SE → Wald 统计量

z = β/SE,p = 2·(1 - Φ(|z|))。Wald χ²(1) = z²。大样本 logistic、Cox、Poisson 回归惯例;小样本 OLS 用 t 分布(df = n - 参数个数)。β 与 OR 并存时可再核对 OR = exp(β),CI 端点同样满足 exp 关系。

## 5. 2×2 表 → OR/RR

表约定:

| | 事件 | 未事件 |
| --- | --- | --- |
| 暴露/处理 | a | b |
| 对照 | c | d |

```
OR = a·d / (b·c)              SE(ln OR) = sqrt(1/a + 1/b + 1/c + 1/d)
RR = (a/(a+b)) / (c/(c+d))    SE(ln RR) = sqrt(b/(a(a+b)) + d/(c(c+d)))
CI = exp(点估计对数 ± z·SE)(log-Wald)
```

0 格处理:Haldane-Anscombe 校正,四格各加 0.5,结果必须注明。OR 行列互换变倒数;RR 没有此对称性。病例对照研究只能报 OR,队列/试验才能报 RR。

## 6. 功效与样本量(两独立样本 t)

非中心 t 分布:非中心参数 λ = |d| / sqrt(1/n1 + 1/n2),功效 = P(|T_df,λ| > t_{1-α/2,df}),df = n1+n2-2。由 statsmodels `TTestIndPower.solve_power` 数值求解,正问题解 power,反问题解 nobs1(连续解,报告向上取整)。

其他设计的 statsmodels 入口:

- 单样本/配对 t:`TTestPower`
- 相关:`statsmodels.stats.power` 中以相关系数为效应量的求解路径
- 方差分析:`FTestAnovaPower`
- 比例检验:`NormalIndPower`

经典锚点:d = 0.5、每组 64 人、α = 0.05 双侧 → 功效约 0.80;d = 0.2 要达到 0.8 功效需每组约 394 人。锚点用于快速 sanity check,不替代逐案计算。

## 7. 错配检测的容差依据

- p 值:报告 k 位小数 → 真值区间半宽 0.5·10^-k。
- 百分比:同上,按百分数的报告位数取半宽。
- 不可能 SD:[a, b] 有界变量总体 SD 上界 (b-a)/2(两极各半分布),样本 SD(分母 n-1)上界再乘 sqrt(n/(n-1))。
- 自由度反推样本量:pooled Student 双样本 t 为 N = df + 2(要求 df 为整数、等方差假设成立),单样本/配对为 N = df + 1,回归为 N = df_残差 + 参数个数(含截距)。等式是精确的,无容差;不等即错配,但先确认论文报告的是总 N 还是每组 n。Welch t 的自由度是连续值且依赖两组方差,不能用 N = df + 2 反推;非整数 df 应视为 Welch 情形,不做样本量错配判定。
