---
name: math-computation
description: "全领域计算中枢:数学、金融、社科、生物医学、物理工程计算与两层自动路由."
version: 1.2.1
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [math, symbolic, numeric, statistics, sympy, scipy, statsmodels, matplotlib, pandas, torch]
    related_skills: [manim-video, huggingface-hub]
---

# 数理计算 Skill

符号计算（sympy）、数值计算（numpy/scipy）、高精度（mpmath）、统计建模（statsmodels/scikit-learn）、数据分析（pandas）、图论（networkx）、自动微分（torch）、科学绘图（matplotlib）、生存分析（lifelines）、波动率建模（arch）、心理测量（pingouin）的统一入口。依赖按任务安装；`terminal` 与 `execute_code` 的解释器/后端可能不同，先打印 `sys.executable` 并核查所需包。

跨学科计算走"领域自动路由"：先识别领域（金融/社科/生物医学/物理工程/纯数统计），再映射任务类型到具体算法与库，领域配方在 `references/domain-recipes-*.md`。各学科共用的底层因子（优化、统计推断、蒙特卡洛、微分方程、时间序列）即"最大公约数"，一次学会全部学科复用。

不做：机器学习训练调参（按任务查找专用训练工具；`huggingface-hub`/`llama-cpp` 是可选的模型管理/推理相关技能）、数学动画视频（去 `manim-video` skill）、硬件跑分（使用另行安装并核实的专用工具）。

## When to Use

- 解方程/方程组、求导/积分/极限/级数、化简、因式分解、矩阵运算/特征值、LaTeX 公式输出 → sympy
- 数值积分（含重积分）、优化（最小化/拟合/线性规划）、线性方程组、FFT、ODE 初值与边值问题、插值、特殊函数 → scipy/numpy
- 任意精度高精度计算（几十位小数）→ mpmath
- 描述统计、t 检验/卡方/ANOVA、回归（OLS/WLS/稳健 RLM）、功效分析、时间序列平稳性 → statsmodels + scipy.stats
- 表格数据读写、分组、透视、清洗 → pandas
- 图/网络（最短路径、连通性、中心性、最大流）→ networkx
- 梯度/自动微分、张量运算 → torch
- 出图（函数曲线、散点、直方图、3D、拟合线、热力图）→ matplotlib

Don't use for: 纯算术四则运算（直接算）、需要联网查数据（用 web_search）、要发给用户的图片需先存文件再说明路径。

## Prerequisites

Python 3.11+；数值配方要求 NumPy、SciPy >=1.9（含 MILP）。其余按任务检查 pandas、sympy、mpmath、statsmodels、scikit-learn >=0.24（含旋转）、matplotlib、networkx、torch、lifelines、arch、pingouin。Excel .xlsx 读取另需 openpyxl，.xls 另需 xlrd。

不假定 Hermes 预装这些库。用所选解释器执行 `python -c "import sys; print(sys.executable)"`；安装时用该解释器的 `-m pip install <package>`，或 `uv pip install --python <venv-python> <package>`。占位符须换成已确认的解释器，不把作者本机版本当成锁定环境。离线计算本身不需 API key；首次安装依赖可能需联网。

## 执行方式

使用会话实际暴露的 `terminal` 运行 Python 脚本；`execute_code` 可编排工具调用或在其解释器有依赖时直接计算。不要假定两个环境共享包。打印中间量、单位和结果；检查退出码与 stderr。

出图必须无头运行：**先 `import matplotlib; matplotlib.use('Agg')` 再 import pyplot，最后 `fig.savefig(path)` 存文件**，不要 `plt.show()`（无 GUI 会卡住/报错）。中文标签需先设字体（见 Pitfalls）。

## 领域自动路由（全领域计算中枢）

每次计算先输出一行路由说明再执行：

【路由】领域:金融 | 任务:组合优化 | 工具:scipy.optimize.minimize(约束) | 配方:references/domain-recipes-finance.md

### 第一步：领域识别（按用户需求关键词）

| 领域 | 触发词 | 配方文件 |
| --- | --- | --- |
| 金融 | 收益率、期权、组合、VaR、波动率、GARCH、夏普、定价、因子回归 | domain-recipes-finance.md |
| 社会科学 | 问卷、量表、信度、效度、效应量、中介、调节、面板、抽样 | domain-recipes-social-science.md |
| 生物医学 | 生存、删失、Kaplan-Meier、Cox、发病率、剂量 | domain-recipes-social-science.md（生存分析节） |
| 物理/工程 | 微分方程、场、扩散、谱、滤波、信号、振动、电路 | domain-recipes-physics-engineering.md |
| 纯数/统计 | 无领域词（默认） | 本 SKILL.md 速查 + advanced-recipes.md |

### 第二步：任务类型 → 工具映射（最大公约数因子）

| 任务类型 | 工具 |
| --- | --- |
| 回归/假设检验 | statsmodels + scipy.stats |
| 分类/聚类/降维/因子分析 | scikit-learn |
| 优化（无约束/约束/线性规划/全局） | scipy.optimize（minimize / linprog / differential_evolution） |
| 随机模拟/蒙特卡洛 | numpy `default_rng` |
| 时间序列（ARIMA/波动率） | statsmodels / arch |
| 生存分析 | lifelines |
| 心理测量（信度/效应量/事后检验） | pingouin |
| 符号/高精度 | sympy / mpmath |
| ODE/PDE | scipy.integrate / 有限差分手写 |
| 图/网络 | networkx |
| 自动微分 | torch |

### 第三步：执行与路由规则

按映射工具找速查（本 SKILL.md）或配方（references）。路由规则：领域词命中即走对应配方；多领域词按金融 > 社科 > 生物医学 > 物理工程的优先级；用户明确领域时以用户为准；拿不准时路由行标"存疑"并说明假设。

## 各库核心 API 速查

### 符号计算 sympy

```python
# fragment: API reference; supply the named input variables and required imports.
import sympy as sp
x, y = sp.symbols('x y')
sp.diff(x**3 + sp.sin(x), x)          # 求导
sp.integrate(sp.exp(-x**2), x)         # 不定积分（符号）
sp.limit(sp.sin(x)/x, x, 0)            # 极限
sp.solve(x**2 - 5*x + 6, x)            # 解方程
sp.solve([x+y-3, x-y-1], [x, y])       # 解方程组
sp.solveset(sp.sin(x) - 0.5, x)        # 解集形式（含周期解）
sp.simplify((x**2-1)/(x-1))            # 化简
sp.factor(x**3 - 1)                    # 因式分解
sp.Matrix([[1,2],[3,4]]).eigenvals()   # 特征值
sp.series(sp.exp(x), x, 0, 5)          # 泰勒展开
sp.latex(sp.Integral(sp.exp(x), x))    # 输出 LaTeX 字符串
sp.sqrt(2).evalf(30)                         # 任意精度求数值（30位）
sp.nsolve(sp.cos(x)-x, x, 0.7)         # 数值求根（无解析解时）
f = sp.lambdify(x, x**2 + 1, 'numpy')  # 符号表达式 → numpy 函数（向量化求值/绘图）
```

要点：结果想转浮点用 `float(expr)` 或 `expr.evalf()`；`solve` 解不出就用 `nsolve`（多初值扫描防漏根），要向量化数值就用 `lambdify`。

### 数值计算 scipy/numpy

```python
# fragment: API reference; supply the named input variables and required imports.
import numpy as np
from scipy import integrate, optimize, linalg, fft, interpolate
from scipy.integrate import solve_ivp, solve_bvp

integrate.quad(lambda x: x**2, 0, 1)[0]          # 数值定积分
integrate.dblquad(f, 0, 1, 0, 1)[0]              # 二重积分
optimize.minimize(lambda x: (x-3)**2, x0=0)      # 无约束最小化
optimize.minimize(f, x0, constraints=cons)       # 约束优化（cons 用 LinearConstraint/NonlinearConstraint）
optimize.curve_fit(f, xdata, ydata, p0)          # 非线性曲线拟合
optimize.linprog(c, A_ub, b_ub)                  # 线性规划（标准形式，无需额外库）
np.linalg.solve(A, b)                            # 线性方程组（良态矩阵）
np.linalg.lstsq(A, b, rcond=None)                # 最小二乘；检查秩与奇异值，病态时仍可能不稳定
np.linalg.cond(A)                                # 条件数；结合精度/缩放判断，lstsq 不会消除病态
linalg.eigh(A)                                   # 对称矩阵特征值/特征向量
fft.fft(signal)                                  # 快速傅里叶变换
solve_ivp(f, [t0, t1], y0)                       # ODE 初值问题
solve_bvp(f, bc, x, y)                           # ODE 边值问题（配方见 references）
interpolate.CubicSpline(x, y)         # 插值
np.gradient(f, x)                                # 数值微分（有限差分）
rng = np.random.default_rng(42)                  # 随机数（新 API，见 Pitfalls 8）
rng.normal(0, 1, size=1000)                      # 抽样
```

优化先检查 `result.success`、约束残差和目标值；失败时检查缩放、导数与初值。Nelder-Mead 是无梯度局部方法，不保证最稳或全局最优，也不支持通用约束。拟合同时检查警告与协方差有限性。

### 高精度 mpmath

```python
# fragment: API reference; supply the named input variables and required imports.
from mpmath import mp
mp.dps = 50                 # 50 位精度
mp.pi, mp.e                 # 高精度常数
mp.nsum(lambda n: 1/n**2, [1, mp.inf])   # 高精度级数求和
mp.quad(lambda x: mp.exp(-x**2), [-mp.inf, mp.inf])
```

### 统计 statsmodels + scipy.stats

```python
# fragment: API reference; supply the named input variables and required imports.
import statsmodels.api as sm
from scipy import stats
import numpy as np

stats.describe(data)                              # 描述统计
stats.ttest_ind(a, b, equal_var=False)                             # Welch 独立样本 t 检验，不假定等方差
stats.ttest_rel(a, b)                             # 配对 t 检验
stats.chi2_contingency(table)                     # 卡方独立性
stats.f_oneway(g1, g2, g3)                        # 单因素 ANOVA
stats.norm.fit(data)                              # 正态分布参数拟合
stats.pearsonr(x, y)                              # 皮尔逊相关
stats.shapiro(data)                               # 正态性检验

X = sm.add_constant(x)                            # 加截距项
sm.OLS(y, X).fit().summary()                      # 线性回归（看 p 值/R²）
sm.WLS(y, X, weights=w).fit()                     # 权重为误差方差的倒数，须有依据
sm.RLM(y, X).fit().summary()                      # 稳健回归（有离群点时）
sm.Logit(y_bin, X).fit().summary()                # 逻辑回归
sm.tsa.stattools.adfuller(series)                 # 时间序列平稳性检验
sm.stats.TTestIndPower().solve_power(effect_size, nobs1=None, alpha=0.05, power=0.8)  # 功效分析（求所需样本量）
```

`summary()` 输出长，先打印关键量（系数、p 值、R²）再决定要不要全文。残差检验用 `sm.stats.diagnostic.het_breuschpagan`（异方差）与 `statsmodels.stats.stattools.durbin_watson`（自相关）。

### 自动微分 torch

```python
# fragment: API reference; supply the named input variables and required imports.
import torch
x = torch.tensor(2.0, requires_grad=True)
y = x**3 + torch.sin(x)
y.backward()                      # dy/dx
print(x.grad)                     # 12 + cos(2)
```

只做梯度/张量运算用 CPU 版足够；不需要 GPU，也不需要任何模型权重。

### 数据 pandas

```python
import pandas as pd
# smoke-test: true
# fixture: 教学临时 CSV；真实任务改为用户 path。
import tempfile
from pathlib import Path
_tmp = tempfile.TemporaryDirectory()
path = Path(_tmp.name) / 'table.csv'
pd.DataFrame({'col': ['g', 'g'], 'v': [1., 3.], 'a': ['a', 'a'], 'b': ['b', 'b']}).to_csv(path, index=False)
from pathlib import Path
path = Path(path).expanduser()
if path.suffix.lower() == '.csv':
    df = pd.read_csv(path)
elif path.suffix.lower() in {'.xlsx', '.xls'}:
    df = pd.read_excel(path)
else:
    raise ValueError(f'Unsupported table format: {path.suffix}')
df.groupby('col')['v'].agg(['mean','std','count'])
df.pivot_table(values='v', index='a', columns='b')
df.describe()          # 快速概览
assert df['v'].sum() == 4.
_tmp.cleanup()
```

pandas 3.0 的 copy-on-write 与字符串 dtype 变化见 Pitfalls 9。

### 图论 networkx

```python
# fragment: API reference; supply the named input variables and required imports.
import networkx as nx
G = nx.Graph(); G.add_edges_from([(1,2),(2,3),(1,3)])
nx.shortest_path(G, 1, 3)          # 最短路
nx.connected_components(G)         # 连通分量
nx.pagerank(G)                     # PageRank 中心性
nx.maximum_flow(DiG, s, t)         # 最大流（有向图）
```

### 绘图 matplotlib（无头）

```python
# smoke-test: true
import matplotlib
matplotlib.use('Agg')              # 必须最先，无 GUI 后端
import matplotlib.pyplot as plt
import numpy as np

# 中文标签需先核实已安装字体（见 Pitfalls），不假定系统自带中文字体。
plt.rcParams['axes.unicode_minus'] = False

x = np.linspace(-5, 5, 200)
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
axes[0].plot(x, np.sin(x), label='sin')
axes[1].scatter(x, x + np.random.default_rng(42).normal(0, 0.5, 200), s=6, alpha=0.6)
axes[0].legend(); axes[1].set_title('Scatter')
from pathlib import Path
import os
path = Path(os.environ.get('PLOT_DIR', '~/plots')).expanduser() / 'plot.png'
path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(path, dpi=120, bbox_inches='tight')
assert path.is_file() and path.stat().st_size > 0
plt.close(fig)
print(f'saved: {path.resolve()}')
```

3D 用 `fig = plt.figure(); ax = fig.add_subplot(111, projection='3d')`。热力图用 `plt.imshow` + `plt.colorbar()`。

## Procedure

1. 明确问题是符号还是数值：能解析解（求导/精确积分/方程有闭式解）走 sympy；否则走 scipy 数值。
2. 写 `execute_code` 脚本，一次算完中间量和最终答案，`print` 出来；需要图就 `savefig` 到稳定目录（`~/plots/` 或 `tempfile.gettempdir()`，路径保证 UTF-8 可用）。
3. 结果核对：符号解代入验算（sympy 的 `expr.subs(x, 值)` 或数值回代）；数值解检查量纲/数量级是否合理；统计结果检查 p 值与效应量的自洽性。
4. 把最终答案（数字/公式/图路径）用纯文本回给用户；公式用 LaTeX 字符串或 `expr.pretty()` 的文本形式，不贴整段代码。

进阶配方（线性规划、边值问题、功效分析、蒙特卡洛、torch 梯度、3D 曲面）见 `references/advanced-recipes.md`。领域配方：金融见 `references/domain-recipes-finance.md`，社科与生物医学见 `references/domain-recipes-social-science.md`，物理工程见 `references/domain-recipes-physics-engineering.md`。

## Pitfalls

1. **matplotlib 无头**：CLI 环境没有 GUI，`plt.show()` 会卡住或报错。必须 `matplotlib.use('Agg')` + `savefig`。这个错误最常见。
2. **中文乱码**：默认字体不含中文，标签会变方块。先 `plt.rcParams['font.sans-serif']=['Microsoft YaHei']`（Windows 已内置）；Linux/macOS 用 `['SimHei']` 或系统可用字体，查字体用 `matplotlib.font_manager.fontManager.ttflist`。
3. **sympy 结果转数值**：`solve` 返回符号对象，直接打印是 `x = -sqrt(5)+1` 之类，用户可能要数值——用 `float(expr)` 或 `expr.evalf()`。`nsolve` 需要初值，多解时用多个初值扫描，防漏根。
4. **scipy 优化/拟合不收敛**：检查尺度、初值、导数及算法是否支持所需约束；失败结果不能当作有效解。
5. **符号积分积不出**：sympy 积不出不代表无解，立刻转 `integrate.quad` 数值积分，不要卡在符号路径。
6. **`summary()` 太啰嗦**：statsmodels 的 summary 输出几十行，直接回给用户会被淹没，先提取系数表/关键统计量。
7. **包名陷阱**：scikit-learn 的 import 名是 `sklearn`（不是 `scikit-learn`）；opencv 是 `cv2`；检查是否安装用 `importlib.util.find_spec('sklearn')`，别拿 pip 包名做 `find_spec`。
8. **随机数必须用新 API**：numpy 2.x 里 `np.random.seed()` 是全局旧 API，同一会话多个任务会互相污染。用 `rng = np.random.default_rng(seed)` 后调 `rng.normal(...)` 等方法。numpy 2.x 还移除了 `np.NaN`/`np.float_` 等旧别名，一律写 `np.nan`/`float`。
9. **pandas 版本注意**：统一用 `loc` 一步赋值，避免链式赋值；3.x 默认 copy-on-write，字符串 dtype 也有变化。升级依赖后重跑自检。
10. **环境变化**：遇到 ModuleNotFoundError 先确认当前解释器和任务所需依赖，不推断用户机器曾安装哪些包。

## Verification

```python
# smoke-test: true
import sympy as sp, numpy as np, tempfile, os
from scipy.integrate import quad
import statsmodels.api as sm
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd, networkx as nx, torch
import lifelines, arch, pingouin

x = sp.symbols('x')
assert str(sp.diff(x**3, x)) == '3*x**2'          # 符号求导
assert abs(quad(lambda t: t**2, 0, 1)[0] - 1/3) < 1e-9   # 数值积分
assert np.allclose(sm.OLS([1., 3., 5., 7.], sm.add_constant([0., 1., 2., 3.])).fit().params, [1., 2.])                    # 统计回归
rng = np.random.default_rng(0)                     # numpy 新 API
assert abs(rng.normal(0, 1, 100).mean()) < 0.5
assert pd.DataFrame({'a': [1, 2]}).a.sum() == 3    # pandas
G = nx.Graph(); G.add_edge(1, 2)                   # networkx
assert nx.shortest_path_length(G, 1, 2) == 1
t = torch.tensor(2.0, requires_grad=True)          # torch 自动微分
(t**2).backward()
assert abs(t.grad.item() - 4.0) < 1e-6
p = os.path.join(tempfile.gettempdir(), '_v.png')
fig, ax = plt.subplots(); ax.plot([0, 1], [0, 1]); fig.savefig(p); os.remove(p)  # 出图
plt.close(fig)
print('math-computation Verification passed (basic invariants; not every recipe)')
```
