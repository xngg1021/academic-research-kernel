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

from decimal import Decimal, localcontext
import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

# d 与 log OR 之间的 logistic 分布桥接系数(Borenstein et al. 2009, Ch.7)

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


def _scaled_inverse_weights(v_arr: np.ndarray) -> tuple[np.ndarray, float]:
    """Scale variances by v_min before inversion so extreme positive variances (e.g. 1e-320) never overflow."""
    v_min = float(np.min(v_arr))
    if not (v_min > 0.0 and math.isfinite(v_min)):
        raise ValueError("Study variances must be strictly positive and finite")
    w_rel = v_min / v_arr
    w_rel_sum = float(np.sum(w_rel))
    if not (w_rel_sum > 0.0 and math.isfinite(w_rel_sum)):
        raise ValueError("Scaled study weights failed finite-sum check")
    return w_rel, v_min


def _prefix_suffix_complements(p_norm: np.ndarray) -> np.ndarray:
    """Compute sum_{j != i} p_norm[j] in O(k) via non-negative prefix + suffix sums (zero subtraction cancellation)."""
    n = int(p_norm.size)
    if n <= 1:
        return np.zeros(n, dtype=float)
    pref = np.empty(n, dtype=float)
    suff = np.empty(n, dtype=float)
    pref[0] = 0.0
    for i in range(1, n):
        pref[i] = pref[i - 1] + float(p_norm[i - 1])
    suff[n - 1] = 0.0
    for i in range(n - 2, -1, -1):
        suff[i] = suff[i + 1] + float(p_norm[i + 1])
    return pref + suff


def _heterogeneity_decimal(y: np.ndarray, v: np.ndarray) -> tuple[float, int, float, float]:
    """Exact high-precision Decimal fallback when variance dynamic range exceeds IEEE-754 float64 (~700 orders of magnitude)."""
    n = int(y.size)
    df = n - 1
    if df <= 0:
        return 0.0, 0, 0.0, 0.0
    with localcontext() as ctx:
        ctx.prec = 900
        dy = [Decimal(repr(float(val))) for val in y]
        dv = [Decimal(repr(float(val))) for val in v]
        dw = [Decimal(1) / val for val in dv]
        w_sum = sum(dw, Decimal(0))
        theta_f = sum((w * yv for w, yv in zip(dw, dy)), Decimal(0)) / w_sum
        q_dec = sum((w * (yv - theta_f) * (yv - theta_f) for w, yv in zip(dw, dy)), Decimal(0))
        dp = [w / w_sum for w in dw]
        pref = [Decimal(0)] * n
        suff = [Decimal(0)] * n
        for i in range(1, n):
            pref[i] = pref[i - 1] + dp[i - 1]
        for i in range(n - 2, -1, -1):
            suff[i] = suff[i + 1] + dp[i + 1]
        c_dec = sum((dw[i] * (pref[i] + suff[i]) for i in range(n)), Decimal(0))
        df_dec = Decimal(df)
        i2_dec = max(Decimal(0), (q_dec - df_dec) / q_dec) if q_dec > 0 else Decimal(0)
        tau2_dec = max(Decimal(0), (q_dec - df_dec) / c_dec) if c_dec > 0 else Decimal(0)
        try:
            q_f = float(q_dec)
            i2_f = float(i2_dec)
            tau2_f = float(tau2_dec)
        except OverflowError as exc:
            raise ValueError("Heterogeneity statistics overflowed float64 range") from exc
    if not (math.isfinite(q_f) and math.isfinite(i2_f) and math.isfinite(tau2_f)):
        raise ValueError("Heterogeneity statistics overflowed float64 range")
    return max(0.0, q_f), df, max(0.0, i2_f), max(0.0, tau2_f)


def heterogeneity(yi, vi) -> tuple[float, int, float, float]:
    """Cochran's Q、自由度、I²(0–1)与 DL 法 τ²。

    Q = Σ w_i (y_i - θ_F)²,w_i = 1/v_i;
    I² = max(0, (Q - df) / Q);
    τ² = max(0, (Q - df) / C),C = Σw - Σw²/Σw(DerSimonian–Laird)。
    """
    y, v = _arrays(yi, vi)
    if y.size <= 1:
        return 0.0, 0, 0.0, 0.0
    w_rel, v_min = _scaled_inverse_weights(v)
    if np.any(w_rel == 0.0) or v_min < 1e-290:
        return _heterogeneity_decimal(y, v)
    w_rel_sum = float(math.fsum(w_rel))
    p_norm = w_rel / w_rel_sum
    # Center around y[0] before weighted residual computation so equal/near-equal effects with tiny v do not suffer rounding amplification
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        y_centered = y - float(y[0])
    if not np.all(np.isfinite(y_centered)):
        return _heterogeneity_decimal(y, v)
    theta_centered = float(math.fsum(float(pn) * float(yc) for pn, yc in zip(p_norm, y_centered)))
    if not math.isfinite(theta_centered):
        return _heterogeneity_decimal(y, v)
    # Q = sum(((y_centered_i - theta_centered) / sqrt(v_i))^2) avoids premature squaring overflow and absolute-mean rounding error
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        z_resid = (y_centered - theta_centered) / np.sqrt(v)
        q_raw = float(math.fsum(float(zr) * float(zr) for zr in z_resid))
    if not math.isfinite(q_raw):
        return _heterogeneity_decimal(y, v)
    q = max(0.0, q_raw)
    df = y.size - 1
    i2 = max(0.0, (q - df) / q) if q > 0 else 0.0
    comp = _prefix_suffix_complements(p_norm)
    c_rel = float(math.fsum(float(wr) * float(cp) for wr, cp in zip(w_rel, comp)))
    if df > 0 and c_rel <= 0.0:
        return _heterogeneity_decimal(y, v)
    if q > df and ((q - df) * v_min) == 0.0:
        return _heterogeneity_decimal(y, v)
    tau2 = max(0.0, ((q - df) * v_min) / c_rel) if (c_rel > 0 and df > 0) else 0.0
    if not math.isfinite(tau2):
        return _heterogeneity_decimal(y, v)
    return q, df, i2, tau2


def _pool(yi, vi, model: str) -> PoolResult:
    y, v = _arrays(yi, vi)
    q, df, i2, tau2 = heterogeneity(y, v)
    extra = tau2 if model == 'random' else 0.0
    if extra > 0.0 and np.any((v + extra) == extra) and np.any(v < extra * 1e-16):
        # High-precision pooling when v_i + tau2 suffers float64 absorption on ultra-small v_i
        with localcontext() as ctx:
            ctx.prec = 900
            dtau2 = Decimal(repr(float(extra)))
            dy = [Decimal(repr(float(val))) for val in y]
            dv = [Decimal(repr(float(val))) + dtau2 for val in v]
            dw = [Decimal(1) / val for val in dv]
            w_sum = sum(dw, Decimal(0))
            norm_weights_list = [float(w / w_sum) for w in dw]
            est = float(sum((w * yv for w, yv in zip(dw, dy)), Decimal(0)) / w_sum)
            se = float((Decimal(1) / w_sum).sqrt())
    else:
        v_eff = v + extra
        w_rel, v_min = _scaled_inverse_weights(v_eff)
        if np.any(w_rel == 0.0):
            with localcontext() as ctx:
                ctx.prec = 900
                dtau2 = Decimal(repr(float(extra)))
                dy = [Decimal(repr(float(val))) for val in y]
                dv = [Decimal(repr(float(val))) + dtau2 for val in v]
                dw = [Decimal(1) / val for val in dv]
                w_sum = sum(dw, Decimal(0))
                norm_weights_list = [float(w / w_sum) for w in dw]
                est = float(sum((w * yv for w, yv in zip(dw, dy)), Decimal(0)) / w_sum)
                se = float((Decimal(1) / w_sum).sqrt())
        else:
            w_rel_sum = float(math.fsum(w_rel))
            norm_weights = w_rel / w_rel_sum
            norm_weights_list = norm_weights.tolist()
            est = float(math.fsum(float(nw) * float(yv) for nw, yv in zip(norm_weights, y)))
            se = math.sqrt(v_min) / math.sqrt(w_rel_sum)
    if not (math.isfinite(est) and math.isfinite(se) and se > 0.0):
        raise ValueError("Pooled meta-analysis estimate or standard error is non-finite or underflowed")
    z = stats.norm.ppf(0.975)
    return PoolResult(estimate=est, se=se, ci_low=est - z * se, ci_high=est + z * se,
                      q=q, df=df, i2=i2, tau2=tau2, k=y.size, model=model,
                      weights=norm_weights_list)


def pool_fixed(yi, vi) -> PoolResult:
    """固定效应合并:权重 w = 1/v,θ = Σwy/Σw,se = 1/√Σw。"""
    return _pool(yi, vi, 'fixed')


def pool_random(yi, vi) -> PoolResult:
    """随机效应合并(DL τ²):权重 w* = 1/(v + τ²)。τ² = 0 时退化为固定效应。"""
    return _pool(yi, vi, 'random')


pool_dl = pool_random


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

    def l0_count_full(theta_est):
        x_full = y - theta_est
        ranks = stats.rankdata(np.abs(x_full), method='average')
        t_sign = float(np.sum(ranks[x_full < 0] if side == 'right' else ranks[x_full > 0]))
        return max(0, int(round((4.0 * t_sign - k * (k + 1)) / (2.0 * k - 1.0))))

    idx = np.arange(k)
    k0, prev = 0, -1
    it = 0
    seen_states = set()
    while k0 != prev and it < maxiter:
        it += 1
        prev = k0
        theta = float(np.sum(y[idx] / v[idx]) / np.sum(1.0 / v[idx]))
        k0_raw = l0_count_full(theta)
        if k0_raw > k - 2:
            return {'k0': None, 'adjusted': None, 'se': None,
                    'theta_observed': float(pool_fixed(y, v).estimate),
                    'filled': [], 'converged': False,
                    'note': 'trim-and-fill 删减后保留研究不足 2 项,无法稳定估计中心; '
                            '请用 R metafor::trimfill 复核 k0'}
        k0 = min(k0_raw, k - 2)
        if k0 == prev:
            # S01: 连续两轮 k0 一致, 成功到达固定点
            break
        if k0 > 0:
            x_full = y - theta
            # 从原始全集削去与缺失侧相反的最极端 k0 项 (稳定排序保持确定性)
            order = np.argsort(x_full, kind='mergesort') if side == 'right' else np.argsort(-x_full, kind='mergesort')
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
    if float(np.sum((precision - precision.mean()) ** 2)) == 0.0:
        raise ValueError("Egger regression requires non-identical study variances")
    slope, intercept, _, _, _ = stats.linregress(precision, snd)
    resid = snd - (intercept + slope * precision)
    df = y.size - 2
    if df < 1:
        return float(intercept), float('nan'), float('nan')
    mse = float(np.sum(resid ** 2)) / df
    se_intercept = math.sqrt(mse * float(np.sum(precision ** 2)) /
                             (y.size * float(np.sum((precision - precision.mean()) ** 2))))
    if se_intercept == 0.0 or not math.isfinite(se_intercept):
        raise ValueError("Egger regression residual variance is zero or non-finite; t-statistic undefined")
    t = intercept / se_intercept
    p = 2.0 * float(stats.t.sf(abs(t), df))
    return float(intercept), float(t), p


def subgroup_analysis(yi, vi, groups) -> dict:
    """Fixed-effect Cochran Q between/within subgroup decomposition plus random-effects per-subgroup pools."""
    from dataclasses import asdict

    y, v = _arrays(yi, vi)
    g_list = [str(g).strip() for g in groups]
    if len(g_list) != y.size:
        raise ValueError("subgroup labels length must match yi/vi length")
    unique_groups = list(dict.fromkeys(g_list))
    if len(unique_groups) < 2:
        raise ValueError("subgroup_analysis requires at least 2 distinct subgroups")

    overall_fe = pool_fixed(y, v)
    q_within = 0.0
    by_group: dict[str, dict] = {}
    for g_name in unique_groups:
        mask = np.array([g == g_name for g in g_list], dtype=bool)
        yg, vg = y[mask], v[mask]
        fe_g = pool_fixed(yg, vg)
        re_g = pool_random(yg, vg)
        q_within += fe_g.q
        by_group[g_name] = {
            "k": int(yg.size),
            "fixed_effect": asdict(fe_g),
            "random_effects_dl": asdict(re_g),
        }
    q_between = max(0.0, float(overall_fe.q - q_within))
    df_between = len(unique_groups) - 1
    p_between = float(stats.chi2.sf(q_between, df_between))
    return {
        "group_count": len(unique_groups),
        "q_total": float(overall_fe.q),
        "q_within": float(q_within),
        "q_between": q_between,
        "df_between": df_between,
        "p_between": p_between,
        "subgroups": by_group,
    }


def _wls_fit_decimal(
    y: np.ndarray,
    x: np.ndarray,
    v: np.ndarray,
    tau2_add: float = 0.0,
    df_resid: int | None = None,
) -> tuple[float, float, float, float, float, float]:
    """High-precision WLS fit returning (intercept, se_intercept, slope, se_slope, q_resid, tau2_resid_est)."""
    with localcontext() as ctx:
        ctx.prec = 900
        dtau2 = Decimal(repr(float(tau2_add)))
        dy = [Decimal(repr(float(val))) for val in y]
        dx = [Decimal(repr(float(val))) for val in x]
        dw = [Decimal(1) / (Decimal(repr(float(val))) + dtau2) for val in v]
        w_sum = sum(dw, Decimal(0))
        x_bar = sum((w * xv for w, xv in zip(dw, dx)), Decimal(0)) / w_sum
        y_bar = sum((w * yv for w, yv in zip(dw, dy)), Decimal(0)) / w_sum
        ddx = [xv - x_bar for xv in dx]
        s_xx = sum((w * d * d for w, d in zip(dw, ddx)), Decimal(0))
        if s_xx <= 0:
            raise ValueError("Moderator design matrix is numerically singular under study weights")
        s_xy = sum((w * d * (yv - y_bar) for w, d, yv in zip(dw, ddx, dy)), Decimal(0))
        slope_d = s_xy / s_xx
        icp_d = y_bar - slope_d * x_bar
        se_sl_d = (Decimal(1) / s_xx).sqrt()
        se_ic_d = ((Decimal(1) / w_sum) + (x_bar * x_bar) / s_xx).sqrt()
        q_d = max(Decimal(0), sum((w * (yv - (icp_d + slope_d * xv)) ** 2 for w, xv, yv in zip(dw, dx, dy)), Decimal(0)))
        # trace(P) = sum_i w_i * (1 - w_i / w_sum - w_i * d_i^2 / s_xx)
        tr_p_d = sum((w * (Decimal(1) - (w / w_sum) - (w * d * d / s_xx)) for w, d in zip(dw, ddx)), Decimal(0))
        if df_resid is not None and tr_p_d > Decimal(0) and q_d > Decimal(df_resid):
            tau2_est_d = (q_d - Decimal(df_resid)) / tr_p_d
        else:
            tau2_est_d = Decimal(0)
        return float(icp_d), float(se_ic_d), float(slope_d), float(se_sl_d), max(0.0, float(q_d)), max(0.0, float(tau2_est_d))


def meta_regression(yi, vi, moderators, model: str = "random") -> dict:
    """Univariate weighted least squares (WLS) meta-regression with generalized DerSimonian-Laird residual tau^2."""
    if model not in ("random", "fixed"):
        raise ValueError(f"Unsupported meta_regression model {model!r}; expected 'random' or 'fixed'")
    y, v = _arrays(yi, vi)
    x = np.asarray(moderators, dtype=float)
    if x.ndim != 1 or x.size != y.size:
        raise ValueError("moderators must be a 1-D array matching yi/vi length")
    if not np.all(np.isfinite(x)):
        raise ValueError("moderators must be finite numbers")
    if y.size < 3:
        raise ValueError("meta_regression requires at least 3 studies")
    if float(np.sum((x - x.mean()) ** 2)) == 0.0:
        raise ValueError("meta_regression requires non-constant moderator values")

    df_resid = int(y.size - 2)
    # Step 1: Fit null fixed-effects regression under H0: tau^2_resid = 0 using sampling variances v_i (ratio evaluated in Decimal)
    icp0, se_icp0, sl0, se_sl0, q_e, tau2_dl = _wls_fit_decimal(y, x, v, tau2_add=0.0, df_resid=df_resid)
    tau2 = tau2_dl if model == "random" else 0.0

    # Step 2: Refit WLS with v_i + tau^2_resid when tau^2_resid > 0
    if tau2 > 0.0:
        intercept, se_intercept, slope, se_slope, _, _ = _wls_fit_decimal(y, x, v, tau2_add=tau2)
    else:
        intercept, se_intercept, slope, se_slope = icp0, se_icp0, sl0, se_sl0

    if not all(math.isfinite(val) for val in (tau2, intercept, se_intercept, slope, se_slope, q_e)) or se_slope <= 0.0:
        raise ValueError("meta_regression encountered non-finite or degenerate standard error")
    z_slope = slope / se_slope
    p_slope = 2.0 * float(stats.norm.sf(abs(z_slope)))
    return {
        "model": model,
        "k": int(y.size),
        "tau2": float(tau2),
        "intercept": intercept,
        "se_intercept": se_intercept,
        "slope": slope,
        "se_slope": se_slope,
        "z_slope": z_slope,
        "p_slope": p_slope,
        "q_residual": q_e,
        "df_residual": df_resid,
        "p_residual": float(stats.chi2.sf(q_e, df_resid)),
    }
