# 社会科学与生物医学计算配方（Domain Recipes: Social Science & Biostatistics）

社科量化分析 = 统计推断 + 心理测量 + 纵向/生存建模，按任务安装相应库实现。

## 问卷信度：Cronbach's α（pingouin）

```python
# smoke-test: true
import numpy as np
import pandas as pd
rng = np.random.default_rng(2)
latent = rng.normal(size=500)
items = pd.DataFrame(latent[:, None] + rng.normal(0, .5, (500, 6)))
import pingouin as pg
# items: DataFrame, 每列一个量表条目(已反向计分)
alpha, ci = pg.cronbach_alpha(items)
print(alpha, ci)     # 附 95% 区间；阈值取决于用途，α 不证明单维性或效度
k = items.shape[1]
formula_alpha = k/(k-1)*(1-items.var(ddof=1).sum()/items.sum(axis=1).var(ddof=1))
assert np.isclose(alpha, formula_alpha) and ci[0] < alpha < ci[1]
```

## 效应量与事后检验（pingouin + scipy）

```python
# smoke-test: true
import numpy as np
import pandas as pd
x = np.array([1., 2., 3., 4., 5.])
y = x+2
df = pd.DataFrame({'score': np.r_[x,y], 'group': ['a']*5+['b']*5})
import pingouin as pg
# Cohen's d(独立样本)
d = pg.compute_effsize(x, y, paired=False, eftype="cohen")
# ANOVA 后两两比较(Tukey)
tukey = pg.pairwise_tukey(data=df, dv="score", between="group")
# ANOVA 表(含效应量 eta 方)
aov = pg.anova(data=df, dv="score", between="group", detailed=True)
assert np.isclose(d, -2/np.sqrt(2.5))
assert len(tukey) == 1 and np.isfinite(aov['F'].dropna()).all()
```

## 因子分析（scikit-learn >=0.24 支持 varimax）

```python
# smoke-test: true
import numpy as np
import pandas as pd
rng = np.random.default_rng(2)
latent = rng.normal(size=500)
items = pd.DataFrame(latent[:, None] + rng.normal(0, .5, (500, 6)))
from sklearn.decomposition import FactorAnalysis
from sklearn.preprocessing import StandardScaler
X_scaled = StandardScaler().fit_transform(items)
fa = FactorAnalysis(n_components=3, rotation="varimax").fit(X_scaled)
loadings = fa.components_.T       # 载荷矩阵；0.4 仅启发式，还需检查交叉载荷与理论结构
assert loadings.shape == (6,3) and np.isfinite(loadings).all()
assert np.max(abs(fa.get_covariance() - np.cov(X_scaled, rowvar=False, ddof=0))) < .12
```

KMO/Bartlett 是因子分析适用性的辅助诊断，不能保证模型成立。pingouin 不提供这两项的专用 API；如计算须使用经验证实现并检查样本量、相关矩阵可逆/正定及缺失处理。因子数用理论与平行分析等选择，不为得到漂亮载荷反复试数。

## 中介与调节效应（分层回归，statsmodels 手写组合）

Baron-Kenny 可用于描述历史路径回归，总效应显著不是中介成立的必要条件；系数下降也不足以证明因果中介。主报告间接效应 a*b 和 bootstrap 区间，并明确阐述不存在未测混杂、具备明确时间顺序以及模型设定正确等因果识别假设。

```python
# smoke-test: true
import numpy as np
import statsmodels.api as sm
rng = np.random.default_rng(7)
x = rng.normal(size=500)
med = .8*x + rng.normal(size=x.size)
y = .2*x + .7*med + rng.normal(size=x.size)
def indirect(x, med, y):
    a = sm.OLS(med, sm.add_constant(x)).fit().params[1]
    b = sm.OLS(y, sm.add_constant(np.c_[x, med])).fit().params[2]
    return a*b
estimate = indirect(x, med, y)
draws = []
for _ in range(1000):
    idx = rng.integers(0, x.size, x.size)  # iid 个体成对重采样，保留 X/M/Y 联合关系
    draws.append(indirect(x[idx], med[idx], y[idx]))
ci = np.quantile(draws, [.025, .975])
assert abs(estimate - .56) < .15 and ci[0] < .56 < ci[1]
print('Indirect effect and percentile CI:', estimate, ci)
```

聚类/纵向数据需按独立采样单位重抽样；上述 iid percentile bootstrap 不自动适用。总效应接近零时不报告中介比例。调节模型含 x、z 主效应及 x*z 交互项；解释系数和区间，显著性本身不证明因果机制。

## 面板数据：个体固定效应

```python
# smoke-test: true
import numpy as np
import pandas as pd
import statsmodels.api as sm
df = pd.DataFrame({'entity': np.repeat(['a', 'b', 'c'], 4),
                   'x': np.tile([0., 1., 2., 3.], 3)})
df['y'] = 2*df['x'] + df['entity'].map({'a': 1., 'b': 4., 'c': -2.})
dummies = pd.get_dummies(df['entity'], prefix='entity', drop_first=True, dtype=float)
X = sm.add_constant(pd.concat([df[['x']].astype(float), dummies], axis=1), has_constant='add')
assert np.linalg.matrix_rank(X.to_numpy()) == X.shape[1]
fit = sm.OLS(df['y'], X).fit()
assert np.isclose(fit.params['x'], 2.)
assert np.allclose(fit.fittedvalues, df['y'])
print(fit.params)
```

截距加 n-1 个体虚拟变量避免陷阱；保持索引对齐与数值 dtype。时间不变解释变量与个体效应共线；实体内 x 必须变化。此例只验证系数，不作显著性推断；实证标准误通常需按个体聚类并关注聚类数。可选 linearmodels 使用 entity/time MultiIndex，属于额外依赖。

## 生存分析（lifelines）

```python
# smoke-test: true
import numpy as np
import pandas as pd
durations = np.array([1.,2.,3.,4.])
events = np.array([1,0,1,1])
rng = np.random.default_rng(42)
covariate = rng.normal(size=1000)
event_time = rng.exponential(scale=np.exp(-.5*covariate))
censor_time = rng.exponential(scale=3., size=1000)
df = pd.DataFrame({'t': np.minimum(event_time,censor_time), 'e': event_time <= censor_time, 'x': covariate})
from lifelines import KaplanMeierFitter, CoxPHFitter
kmf = KaplanMeierFitter()
kmf.fit(durations, event_observed=events)      # 1=发生事件, 0=删失
print(kmf.survival_function_at_times([12, 24, 36]))   # 各时点生存率
# 绘图前配置 Agg；ax = kmf.plot_survival_function()，按主 SKILL 保存并关闭 figure。
cph = CoxPHFitter().fit(df, duration_col="t", event_col="e")
print(cph.summary)                             # 风险比 exp(coef) 与 p 值
assert np.allclose(kmf.survival_function_at_times([2,3,4]), [.75,.375,0])
assert abs(cph.params_['x'] - .5) < .15
```

要点：删失变量必须明确（失访=0 不是事件）；Cox 需满足比例风险假设（`cph.check_assumptions(df, show_plots=False)`），违反时如实报告并考虑分层/时变系数；需明确独立（或条件独立）右删失假设。左截断、区间删失不可直接套该 recipe，失访可能具有信息性。

## 调查抽样：分层加权估计

```python
# smoke-test: true
import numpy as np
W = np.array([.4,.6]); means = np.array([10.,20.])
vars = np.array([4.,9.]); n = np.array([20,30])
assert np.isclose(W.sum(), 1) and np.all(n >= 2)
import numpy as np
# 各层:样本均值 mean_s, 样本量 n_s, 总体占比 W_s
est = np.sum(W * means)                       # 加权总体均值
se = np.sqrt(np.sum((W**2) * vars / n))       # 近似标准误
assert np.isclose(est,16) and np.isclose(se,np.sqrt(.14))
```

上述近似计算建立在各层独立抽样、层内采取简单随机抽样，且抽样率可忽略的假定之上；W 为已知总体比例且和为 1，vars 为 ddof=1 层内方差、n>=2。不放回且抽样率不可忽略时乘 (1-n/N) 有限总体修正；复杂聚类抽样需设计型方差。缺设计/权重时不可默认为等概率，明确哪些总体推断不可识别。
