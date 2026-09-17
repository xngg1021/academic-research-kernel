"""系统综述与元分析核心计算(纯函数,可单测)。

只依赖 numpy/scipy,无 I/O、无全局状态。每个函数均可对照手算小例子验证,
见 tests/test_systematic_review.py。约定:yi 为效应量向量,vi 为对应方差。

效应量尺度:
- d  : Cohen's d(标准化均差,两组)
- g  : Hedges' g(小样本校正后的 d)
- lor: 对数优势比 log OR
- r  : 相关系数
- rr/or: 风险比 / 优势比(二分类结局,互转需对照组风险 p0)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

# d 与 log OR 之间的 logistic 分布桥接系数(Borenstein et al. 2009, Ch.7)
import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

LOGISTIC_SCALE = math.pi / math.sqrt(3.0)  # ≈ 1.8138


# ---------------------------------------------------------------------------
# 效应量归一与互转
# ---------------------------------------------------------------------------

def cohens_d(n1: float, n2: float, m1: float, m2: float, sd1: float, sd2: float) -> float:
    """两独立组标准化均差 Cohen's d = (m1 - m2) / sd_pooled。"""
    df = n1 + n2 - 2
    sd_pooled = math.sqrt(((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / df)
    return (m1 - m2) / sd_pooled


def var_d(d: float, n1: float, n2: float) -> float:
    """Cohen's d 的抽样方差(大样本近似)。"""
    return (n1 + n2) / (n1 * n2) + d ** 2 / (2.0 * (n1 + n2 - 2))


def hedges_j(df: float) -> float:
    """小样本校正因子 J(df) = 1 - 3 / (4 df - 1)。"""
    return 1.0 - 3.0 / (4.0 * df - 1.0)


def hedges_g(d: float, n1: float, n2: float) -> float:
    """Hedges' g = J(df) * d,df = n1 + n2 - 2。"""
    return hedges_j(n1 + n2 - 2) * d


def var_g(g: float, n1: float, n2: float) -> float:
    """Hedges' g 的抽样方差 = J^2 * var(d)。"""
    j = hedges_j(n1 + n2 - 2)
    return j ** 2 * var_d(g / j, n1, n2)


def d_to_log_or(d: float) -> float:
    """d → log OR:lor = (π / √3) * d。"""
    return LOGISTIC_SCALE * d


def log_or_to_d(lor: float) -> float:
    """log OR → d:d = lor * √3 / π。"""
    return lor / LOGISTIC_SCALE


def var_log_or_from_d(v_d: float) -> float:
    """d 的方差换算到 log OR 尺度:var(lor) = (π^2 / 3) * var(d)。"""
    return LOGISTIC_SCALE ** 2 * v_d


def log_or(n_events1: int, n1: int, n_events0: int, n0: int) -> tuple[float, float]:
    """由四格表直接计算 log OR 及其方差(返回 (lor, var))。"""
    a, b = n_events1, n1 - n_events1
    c, d_ = n_events0, n0 - n_events0
    lor = math.log((a * d_) / (b * c))
    var = 1.0 / a + 1.0 / b + 1.0 / c + 1.0 / d_
    return lor, var


def d_to_r(d: float, n1: float | None = None, n2: float | None = None) -> float:
    """d → 点二列相关 r = d / √(d² + a)。

    两组等样本时 a = 4;不等样本时 a = (n1 + n2)² / (n1 n2)。
    """
    if n1 is not None and n2 is not None:
        a = (n1 + n2) ** 2 / (n1 * n2)
    else:
        a = 4.0
    return d / math.sqrt(d ** 2 + a)


def r_to_d(r: float) -> float:
    """r → d(等组近似):d = 2r / √(1 - r²)。"""
    return 2.0 * r / math.sqrt(1.0 - r ** 2)


def or_to_rr(or_: float, p0: float) -> float:
    """OR → RR,需对照组事件率 p0:RR = OR / (1 - p0 + p0 * OR)。"""
    return or_ / (1.0 - p0 + p0 * or_)


def rr_to_or(rr: float, p0: float) -> float:
    """RR → OR,需对照组事件率 p0:OR = RR (1 - p0) / (1 - p0 RR)。"""
    return rr * (1.0 - p0) / (1.0 - p0 * rr)


# ---------------------------------------------------------------------------
# 异质性与合并估计
# ---------------------------------------------------------------------------

@dataclass
class PoolResult:
    """合并估计结果。ci 为 95% 正态近似置信区间。"""
    estimate: float
    se: float
    ci_low: float
    ci_high: float
    q: float
    df: int
    i2: float
    tau2: float
    k: int
    model: str
    weights: list[float] = field(default_factory=list)


def _arrays(yi, vi) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(yi, dtype=float)
    v = np.asarray(vi, dtype=float)
    if y.shape != v.shape or y.ndim != 1 or y.size < 1:
        raise ValueError('yi 与 vi 必须等长且非空')
    if np.any(v <= 0):
        raise ValueError('方差 vi 必须全部为正')
    if not (np.all(np.isfinite(y)) and np.all(np.isfinite(v))):
        raise ValueError('yi 与 vi 必须全部为有限数 (SR-03: NaN/inf 一律拒绝)')
    return y, v


def heterogeneity(yi, vi) -> tuple[float, int, float, float]:
    """Cochran's Q、自由度、I²(0–1)与 DL 法 τ²。

    Q = Σ w_i (y_i - θ_F)²,w_i = 1/v_i;
    I² = max(0, (Q - df) / Q);
    τ² = max(0, (Q - df) / C),C = Σw - Σw²/Σw(DerSimonian–Laird)。
    """
    y, v = _arrays(yi, vi)
    w = 1.0 / v
    theta_f = float(np.sum(w * y) / np.sum(w))
    q = float(np.sum(w * (y - theta_f) ** 2))
    df = y.size - 1
    i2 = max(0.0, (q - df) / q) if q > 0 else 0.0
    c = float(np.sum(w) - np.sum(w ** 2) / np.sum(w))
    tau2 = max(0.0, (q - df) / c) if (c > 0 and df > 0) else 0.0
    return q, df, i2, tau2


def _pool(yi, vi, model: str) -> PoolResult:
    y, v = _arrays(yi, vi)
    q, df, i2, tau2 = heterogeneity(y, v)
    extra = tau2 if model == 'random' else 0.0
    w = 1.0 / (v + extra)
    est = float(np.sum(w * y) / np.sum(w))
    se = math.sqrt(1.0 / float(np.sum(w)))
    z = stats.norm.ppf(0.975)
    return PoolResult(estimate=est, se=se, ci_low=est - z * se, ci_high=est + z * se,
                      q=q, df=df, i2=i2, tau2=tau2, k=y.size, model=model,
                      weights=(w / np.sum(w)).tolist())


def pool_fixed(yi, vi) -> PoolResult:
    """固定效应合并:权重 w = 1/v,θ = Σwy/Σw,se = 1/√Σw。"""
    return _pool(yi, vi, 'fixed')


def pool_random(yi, vi) -> PoolResult:
    """随机效应合并(DL τ²):权重 w* = 1/(v + τ²)。τ² = 0 时退化为固定效应。"""
    return _pool(yi, vi, 'random')


# ---------------------------------------------------------------------------
# 敏感性分析与发表偏倚
# ---------------------------------------------------------------------------

def leave_one_out(yi, vi, model: str = 'random') -> list[PoolResult]:
    """逐一剔除单项研究后重新合并,返回 k 个 PoolResult。"""
    y, v = _arrays(yi, vi)
    out = []
    for i in range(y.size):
        mask = np.ones(y.size, dtype=bool)
        mask[i] = False
        out.append(_pool(y[mask], v[mask], model))
    return out


def trim_and_fill(yi, vi, side: str = 'left', maxiter: int = 100) -> dict:
    """Duval–Tweedie trim-and-fill(L0 估计量,固定效应框架)。

    side='left' 假设被压制的是负偏离一侧,从右侧削去最极端研究;
    side='right' 相反。迭代:合并 → 估 k0 → 削 k0 项 → 重合并,直至 k0 稳定;
    最后把被削研究关于最终 θ̂ 镜像补回,给出校正后合并估计。

    L0 = max(0, round((4·T_K − K(K+1)) / (2K − 1))),
    side='left' 时 T_K 为正偏离研究的 |X_j| 秩和,side='right' 时为负偏离的秩和
    (Duval & Tweedie 2000, Biometrics 56:455);这一对称定义保证镜像变换
    (y→−y 且 side 互换) 下 k0 与校正量不变 (SR-01)。

    返回 {'k0', 'adjusted', 'se', 'theta_observed', 'filled', 'converged'}。
    迭代振荡或达到上限未收敛时 k0=None、adjusted=None、converged=False,
    不得把迭代上限的奇偶性当结果 (SR-02)。
    异质性大时结果不稳,仅作敏感性分析;正式报告用 R metafor::trimfill 复核。
    """
    y, v = _arrays(yi, vi)
    k = y.size
    if k < 3:
        raise ValueError('trim-and-fill 至少需要 3 项研究')
    if side not in ('left', 'right'):
        raise ValueError("side 必须是 'left' 或 'right'")

    def l0_count(yy, vv, side):
        theta = float(np.sum(yy / vv) / np.sum(1.0 / vv))
        x = yy - theta
        ranks = stats.rankdata(np.abs(x))
        t_sign = float(np.sum(ranks[x < 0] if side == 'right' else ranks[x > 0]))
        kk = yy.size
        return max(0, int(round((4.0 * t_sign - kk * (kk + 1)) / (2.0 * kk - 1.0))))

    idx = np.arange(k)
    k0, prev = 0, -1
    it = 0
    seen_states = set()
    while k0 != prev and it < maxiter:
        it += 1
        prev = k0
        k0 = min(l0_count(y[idx], v[idx], side), k - 3)
        if k0 == prev:
            # S01: 连续两轮 k0 一致, 成功到达固定点
            break
        if k0 > 0:
            theta = float(np.sum(y[idx] / v[idx]) / np.sum(1.0 / v[idx]))
            x_full = y - theta
            # 从原始全集削去与缺失侧相反的最极端 k0 项
            order = np.argsort(x_full) if side == 'right' else np.argsort(-x_full)
            idx = order[k0:]
        else:
            idx = np.arange(k)
        state = (int(k0), tuple(sorted(idx.tolist())))
        if state in seen_states:
            return {'k0': None, 'adjusted': None, 'se': None,
                    'theta_observed': float(pool_fixed(y, v).estimate),
                    'filled': [], 'converged': False,
                    'note': 'trim-and-fill 迭代未收敛(检测到状态循环); '
                            '请用 R metafor::trimfill 复核 k0'}
        seen_states.add(state)
    if it >= maxiter and k0 != prev:
        return {'k0': None, 'adjusted': None, 'se': None,
                'theta_observed': float(pool_fixed(y, v).estimate),
                'filled': [], 'converged': False,
                'note': f'trim-and-fill 在 {maxiter} 次迭代内未收敛; '
                        '请用 R metafor::trimfill 复核 k0'}
    theta_obs = pool_fixed(y, v).estimate
    if k0 == 0:
        return {'k0': 0, 'adjusted': theta_obs, 'se': pool_fixed(y, v).se,
                'theta_observed': theta_obs, 'filled': [], 'converged': True}
    theta_trim = float(np.sum(y[idx] / v[idx]) / np.sum(1.0 / v[idx]))
    trimmed = np.setdiff1d(np.arange(k), idx)
    y_aug = np.concatenate([y, 2.0 * theta_trim - y[trimmed]])
    v_aug = np.concatenate([v, v[trimmed]])
    adj = pool_fixed(y_aug, v_aug)
    return {'k0': int(k0), 'adjusted': adj.estimate, 'se': adj.se,
            'theta_observed': theta_obs,
            'filled': (2.0 * theta_trim - y[trimmed]).tolist(), 'converged': True}


def egger_test(yi, vi) -> tuple[float, float, float]:
    """Egger 回归检验:标准正态离差 SND = y/√v 对精度 1/√v 的 OLS 回归。

    返回 (截距, t 值, 双侧 p 值);截距显著偏离 0 提示漏斗图不对称。
    研究数 < 3 时自由度为 0,返回 p = nan。
    """
    y, v = _arrays(yi, vi)
    snd = y / np.sqrt(v)
    precision = 1.0 / np.sqrt(v)
    slope, intercept, _, _, _ = stats.linregress(precision, snd)
    resid = snd - (intercept + slope * precision)
    df = y.size - 2
    if df < 1:
        return float(intercept), float('nan'), float('nan')
    mse = float(np.sum(resid ** 2)) / df
    se_intercept = math.sqrt(mse * float(np.sum(precision ** 2)) /
                             (y.size * float(np.sum((precision - precision.mean()) ** 2))))
    t = intercept / se_intercept
    p = 2.0 * float(stats.t.sf(abs(t), df))
    return float(intercept), float(t), p
