# 物理与工程计算配方（Domain Recipes: Physics & Engineering）

物理/工程计算 = 微分方程 + 信号处理 + 数值方法，本文件示例使用 numpy/scipy，不引入 FEM 类重型工具。

## 偏微分方程：有限差分（热传导，numpy 手写）

```python
# smoke-test: true
import numpy as np
# 一维热传导 u_t = α u_xx, 显式格式
nx, nt = 50, 1000
alpha, dx, dt = 0.01, 1.0/(nx-1), 0.001
assert 0 <= alpha*dt/dx**2 <= 0.5, "违反 CFL 稳定性条件"     # 显式格式必须检查
u = np.zeros((nt+1, nx))
u[0, nx//2] = 1.0                                     # 初始离散温度脉冲，非归一化 Dirac 热源
for n in range(nt):
    u[n+1, 1:-1] = u[n, 1:-1] + alpha*dt/dx**2 * (u[n, 2:] - 2*u[n, 1:-1] + u[n, :-2])
assert np.all(u[:, [0, -1]] == 0) and u.min() >= 0 and u.max() <= 1
assert np.sum(u[-1]) < np.sum(u[0])
```

边界为两端恒定零温度（Dirichlet），x 变量单位为 m，t 变量单位为 s，alpha 扩散系数单位为 m²/s。1D 显式扩散条件 0<=alpha*dt/dx²<=1/2；2D 五点格式需 alpha*dt*(1/dx²+1/dy²)<=1/2。检验边界、非负性与网格收敛，稳定不等于精确。

上述迭代的自检应核对固定边界与离散最大值原则。

## 信号处理：滤波与功率谱（scipy.signal）

```python
# smoke-test: true
import numpy as np
t = np.arange(4096)/1000.
signal_data = np.sin(2*np.pi*31.25*t) + .2*np.sin(2*np.pi*200*t)
raw_signal = signal_data.copy()
from scipy import signal
import numpy as np

# 低通 Butterworth 滤波
fs = 1000.  # Hz
sos = signal.butter(4, 50., btype='low', fs=fs, output='sos')
filtered = signal.sosfilt(sos, raw_signal)  # 因果滤波，有相位延迟与启动瞬态

# 功率谱密度(Welch)
f, Pxx = signal.welch(signal_data, fs=1000, nperseg=256)
dominant = f[np.argmax(Pxx)]                        # 主频
assert abs(dominant - 31.25) < 1e-10
assert np.isfinite(filtered).all() and filtered.shape == raw_signal.shape
w, h = signal.sosfreqz(sos, worN=[50., 200.], fs=fs)
assert np.isclose(abs(h[0]), 1/np.sqrt(2)) and abs(h[1]) < .01
```

无 fs 时 Wn=0.1 表示 Nyquist 频率的 0.1 倍，即本例 50 Hz；使用 fs 可避免单位混淆。Welch 默认单边 PSD 单位是输入单位²/Hz，频点间隔 fs/nperseg=3.90625 Hz（信号长度>=256）；实际分辨能力还取决于窗函数。FFT 频轴用 fftfreq/rfftfreq 与采样间隔构造，幅值需另做 N/窗函数归一化。

## ODE 系统：SIR 传染病模型（solve_ivp）

```python
# smoke-test: true
import numpy as np
from scipy.integrate import solve_ivp

def sir(t, y, beta, gamma):
    S, I, R = y
    N = S + I + R
    return [-beta*S*I/N, beta*S*I/N - gamma*I, gamma*I]

sol = solve_ivp(sir, [0, 200], [0.999, 0.001, 0.0], args=(0.3, 0.1), dense_output=True, rtol=1e-9, atol=1e-11)
assert sol.success, sol.message
from scipy.optimize import minimize_scalar
peak_result = minimize_scalar(lambda t: -sol.sol(t)[1], bounds=(0., 200.), method='bounded')
assert peak_result.success
peak = max(sol.sol(0)[1], sol.sol(200)[1], -peak_result.fun)
assert np.allclose(sol.y.sum(axis=0), 1., atol=1e-8)
assert sol.y.min() > -1e-9
s_star = .1/.3
analytic_peak = .001 + .999 - s_star + s_star*np.log(s_star/.999)
assert abs(peak - analytic_peak) < 1e-7
R0 = 0.3 / 0.1                                    # 基本再生数 beta/gamma
print("R0 =", R0, "| 感染峰值 =", round(peak, 3))
```

时间以天计，beta/gamma 单位为每天，状态为人口比例。自适应求解网格的最大值会漏掉峰值；本例在连续插值上求单峰并核对端点。S+I+R=1，应检查非负性和守恒。R0 假定初始全易感环境；这是教学模型，参数并未由真实疫情标定。

## 线性时不变系统：传递函数响应（scipy.signal）

```python
# smoke-test: true
import numpy as np
from scipy import signal
sys = signal.TransferFunction([1], [1, 2, 1])     # 1 / (s²+2s+1)
t, y = signal.step(sys)                           # 阶跃响应
u_input = np.ones_like(t)
t2, y2, x2 = signal.lsim(sys, U=u_input, T=t)     # 任意输入
assert np.allclose(y, 1 - (1+t)*np.exp(-t), atol=1e-8)
assert np.allclose(y, y2)
```

## 数值方法长尾速查

| 需求 | 方法 | 位置 |
| --- | --- | --- |
| 常微分方程初值 | solve_ivp | 主 SKILL.md |
| 常微分方程边值 | solve_bvp | advanced-recipes.md |
| 偏微分方程 | 有限差分手写 | 本文件 |
| 傅里叶分析 | fft / welch | 主 SKILL.md + 本文件 |
| 插值与拟合 | CubicSpline / curve_fit | 主 SKILL.md |
| 随机微分方程 | Euler-Maruyama（numpy 可实现，无需 sdeint） | 需要时装库 |

## 边界声明

有限元、CFD 等重型数值模拟超出本技能范围（需专业工具如 FEniCS/OpenFOAM），遇到这类需求如实说明并建议走专用软件，不硬用 numpy 凑。
