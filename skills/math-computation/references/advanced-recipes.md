# 进阶配方（Advanced Recipes）

主 SKILL.md 的 API 速查覆盖常用路径，本文件放组合型配方。需要时按节取用，不必整篇加载。

## 线性规划（scipy.optimize.linprog）

标准形式是 `min c^T x, s.t. A_ub x <= b_ub, A_eq x = b_eq, bounds`。注意目标是最小化，最大化就把 c 取负。

```python
# smoke-test: true
from scipy.optimize import linprog
# 例：max 3x+2y，s.t. x+y<=4，x<=2，x,y>=0
res = linprog(c=[-3, -2], A_ub=[[1, 1], [1, 0]], b_ub=[4, 2], bounds=[(0, None), (0, None)])
assert res.success, res.message
assert abs(-res.fun - 10) < 1e-8
print(-res.fun, res.x)   # 原问题最大值
```

SciPy >=1.9 提供混合整数线性规划 `milp`，本例无需 PuLP：

```python
# smoke-test: true
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
res = milp(c=[-3., -2.], integrality=[1, 1],
           bounds=Bounds([0., 0.], [np.inf, np.inf]),
           constraints=LinearConstraint([[1., 1.], [1., 0.]], [-np.inf, -np.inf], [4., 2.]))
assert res.success, res.message
assert np.allclose(res.x, [2., 2.]) and abs(res.fun + 10) < 1e-8
print('MILP optimum:', -res.fun)
```

## ODE 边值问题（solve_bvp）

初值问题用 solve_ivp；两端定边界条件的问题用 solve_bvp。

```python
# smoke-test: true
import numpy as np
from scipy.integrate import solve_bvp
# y'' = y, y(0)=0, y(1)=sinh(1); 唯一解 y=sinh(x)。
def fun(x, y):
    return np.vstack((y[1], y[0]))
def bc(ya, yb):
    return np.array([ya[0], yb[0] - np.sinh(1.)])
x = np.linspace(0., 1., 20)
sol = solve_bvp(fun, bc, x, np.zeros((2, x.size)), tol=1e-7)
assert sol.success, sol.message
grid = np.linspace(0., 1., 101)
assert np.max(np.abs(sol.sol(grid)[0] - np.sinh(grid))) < 1e-6
assert np.max(np.abs(bc(sol.sol(0), sol.sol(1)))) < 1e-8
print('BVP analytical residual:', np.max(np.abs(sol.sol(grid)[0] - np.sinh(grid))))
```

旧问题 y''=-y, y(0)=y(pi)=0 处在特征值条件上，任意 A sin(x) 都满足，初猜不能决定唯一数学解。更换初猜不能修复欠定问题。

## 功效分析（样本量计算）

```python
# smoke-test: true
from statsmodels.stats.power import TTestIndPower, NormalIndPower
# 独立双样本 t 检验：效应量 0.5、alpha 0.05、功效 0.8 → 所需每组样本量
n = TTestIndPower().solve_power(effect_size=0.5, nobs1=None, alpha=0.05, power=0.8)
assert 63 < n < 64
print(int(__import__('math').ceil(n)))   # 每组人数向上取整
# 反向：给定样本量求功效
p = TTestIndPower().solve_power(effect_size=0.5, nobs1=40, alpha=0.05, power=None)
assert .59 < p < .61
print(p)
```

效应量惯例：Cohen's d 的 0.2/0.5/0.8 = 小/中/大。

## 蒙特卡洛模拟

```python
# smoke-test: true
import numpy as np
rng = np.random.default_rng(2026)
# 例：估算 pi（单位圆/正方形面积比）
n = 1_000_000
assert np.isclose((0.1 / 0.01)**2, 100)
pts = rng.uniform(-1, 1, size=(n, 2))
inside = (pts**2).sum(axis=1) < 1
se = 4 * inside.std(ddof=1) / np.sqrt(n)
assert abs(4*inside.mean() - np.pi) < 5*se
print("pi ≈", 4 * inside.mean(), "| 标准误", 4 * inside.std(ddof=1) / np.sqrt(n))
```

要点：报蒙特卡洛结果必须带标准误或置信区间；样本量按误差平方反比增长（标准误从 0.1 降至 0.01，固定单次样本方差时需约 100 倍样本；相关样本需考虑有效样本量）。

## torch 自动微分（梯度/雅可比）

```python
# smoke-test: true
import sys
try:
    import torch
except ImportError:
    print("torch not installed on platform, skipping")
    sys.exit(0)
# 多变量梯度
x = torch.tensor([1.0, 2.0], requires_grad=True)
f = (x[0]**2 + 3 * x[0] * x[1]).sum()
f.backward()
assert torch.allclose(x.grad, torch.tensor([8., 3.]))
print(x.grad)

# 高阶：create_graph 链式求二阶导
x = torch.tensor(1.5, requires_grad=True)
y = x**3
g = torch.autograd.grad(y, x, create_graph=True)[0]
g2 = torch.autograd.grad(g, x)[0]
assert abs(g.item()-6.75) < 1e-6 and abs(g2.item()-9) < 1e-6
print(g.item(), g2.item())   # 3x²=6.75, 6x=9
```

## 3D 曲面与等高线

```python
# smoke-test: true
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

X, Y = np.meshgrid(np.linspace(-3, 3, 100), np.linspace(-3, 3, 100))
Z = np.sin(np.sqrt(X**2 + Y**2))
fig = plt.figure(figsize=(12, 5))
ax1 = fig.add_subplot(121, projection='3d')
ax1.plot_surface(X, Y, Z, cmap='viridis')
ax2 = fig.add_subplot(122)
c = ax2.contourf(X, Y, Z, levels=20, cmap='viridis')
fig.colorbar(c, ax=ax2)
import os
path = Path(os.environ.get('PLOT_DIR', '~/plots')).expanduser() / 'surface.png'
path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(path, dpi=120, bbox_inches='tight')
plt.close(fig)
assert path.stat().st_size > 0
print(f'saved: {path.resolve()}')
```

## 符号 → 数值的完整链路（sympy 求导 + lambdify + 数值绘图）

```python
# smoke-test: true
import sympy as sp
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

x = sp.symbols('x')
expr = sp.exp(-x**2 / 2) / sp.sqrt(2 * sp.pi)          # 标准正态密度
d1 = sp.diff(expr, x)                                    # 符号一阶导
f, f1 = sp.lambdify(x, expr, 'numpy'), sp.lambdify(x, d1, 'numpy')
xs = np.linspace(-4, 4, 200)
fig, ax = plt.subplots()
ax.plot(xs, f(xs), label='pdf'); ax.plot(xs, f1(xs), label='dpdf')
ax.legend()
import os
path = Path(os.environ.get('PLOT_DIR', '~/plots')).expanduser() / 'gauss.png'
path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(path, dpi=120)
plt.close(fig)
assert path.stat().st_size > 0
print(f'saved: {path.resolve()}')
```

## 非线性拟合（参数标准误与局部近似置信区间）

```python
# smoke-test: true
import numpy as np
from scipy import optimize, stats

def model(x, a, b):
    return a * np.exp(-b * x)

rng = np.random.default_rng(1)
x = np.linspace(0, 4, 30)
y = model(x, 2.5, 0.8) + rng.normal(0, 0.15, x.size)
popt, pcov = optimize.curve_fit(model, x, y, p0=[1, 1])
perr = np.sqrt(np.diag(pcov))
resid = y - model(x, *popt)
ss_res = (resid**2).sum()
ss_tot = ((y - y.mean())**2).sum()
r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
t = popt / perr
dof = x.size - len(popt)
assert dof > 0 and np.isfinite(pcov).all() and np.all(perr > 0)
pvals = 2 * stats.t.sf(np.abs(t), df=dof)  # 局部线性化 Wald 近似，不是精确非线性检验
ci = popt[:, None] + np.array([-1, 1]) * stats.t.ppf(.975, dof) * perr[:, None]
assert np.allclose(popt, [2.5, .8], atol=.15)
print('Approximate parameter CI:', ci)
print("参数±标准误:", popt, perr)
print("R²:", r2, "| p 值:", pvals)
```

要点：默认 absolute_sigma=False 会用残差估计尺度；pcov 与 Wald 区间依赖局部线性化、可辨识性及独立同方差误差等条件。R² 在这里仅作描述，非通用质量保证，可为负、常数响应时未定义；不强制所有模型报告 R²。强非线性/边界参数用合适的 bootstrap 或 profile likelihood。上述区间是参数区间，不是预测带。
