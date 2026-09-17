"""论文定量 claim 反算:纯计算函数库。

每个函数输入论文报告的统计量,重算可独立推导的数值,返回结构化结果:
{
    'reported':   论文报告的值(未提供时为 None),
    'recomputed': 本函数重算的值,
    'difference': recomputed - reported(两者皆为数值时),否则 None,
    'inputs':     实际参与计算的输入参数,
    'formula':    所用公式(文字描述),
    'library':    实际执行计算的库函数,
    'confidence': 'high' 表示确定性公式直算; 'medium' 表示结果受报告值
                  四舍五入影响(如功效反算、由 CI 反推 SE),
}

错配检测函数(check_*)返回 {'consistent': bool, ...} 与判定依据。
所有函数无 I/O、无随机性,可单测。
"""
from decimal import Decimal

import math

import numpy as np
from scipy import stats
from statsmodels.stats.power import TTestIndPower

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

__all__ = [
    'cohens_d',
    'p_from_t',
    'p_from_f',
    'p_from_chi2',
    'z_from_beta_se',
    'check_ci_consistency',
    'or_rr_from_2x2',
    'achieved_power_ttest',
    'required_n_ttest',
    'check_p_match',
    'check_percentage',
    'check_sd_possible',
    'check_sample_size_from_df',
    'values_agree',
]


def _result(reported, recomputed, inputs, formula, library, confidence='high'):
    if isinstance(recomputed, dict):
        diff = None
    elif reported is None or recomputed is None:
        diff = None
    else:
        diff = float(recomputed) - float(reported)
    return {
        'reported': reported,
        'recomputed': recomputed,
        'difference': diff,
        'inputs': inputs,
        'formula': formula,
        'library': library,
        'confidence': confidence,
    }


def _require(condition, message):
    if not condition:
        raise ValueError(message)


# ---------------------------------------------------------------------------
# 1. 均值与标准差 → 效应量
# ---------------------------------------------------------------------------

def cohens_d(m1, sd1, n1, m2, sd2, n2, reported=None):
    """两组独立样本的 Cohen's d 与 Hedges' g(合并标准差)。

    sp = sqrt(((n1-1)sd1^2 + (n2-1)sd2^2) / (n1+n2-2)); d = (m1-m2)/sp。
    Hedges' g = d * J,小样本校正 J = 1 - 3/(4*df - 1),df = n1+n2-2。
    """
    _require(n1 >= 2 and n2 >= 2, '每组样本量须 >= 2')
    _require(sd1 >= 0 and sd2 >= 0, '标准差须非负')
    df = n1 + n2 - 2
    sp = np.sqrt(((n1 - 1) * sd1**2 + (n2 - 1) * sd2**2) / df)
    _require(sp > 0, '合并标准差为 0,效应量无定义')
    d = (m1 - m2) / sp
    j = 1.0 - 3.0 / (4.0 * df - 1.0)
    return _result(
        reported,
        {'cohens_d': float(d), 'hedges_g': float(d * j), 'pooled_sd': float(sp), 'df': int(df)},
        {'m1': m1, 'sd1': sd1, 'n1': n1, 'm2': m2, 'sd2': sd2, 'n2': n2},
        "d = (m1-m2)/sqrt(((n1-1)sd1^2+(n2-1)sd2^2)/(n1+n2-2)); g = d*(1-3/(4df-1))",
        'numpy (closed form)',
    )


# ---------------------------------------------------------------------------
# 2. 检验统计量 + 自由度 → 重算 p 值
# ---------------------------------------------------------------------------

def p_from_t(t, df, reported=None):
    """t 统计量与自由度 → 双侧 p 值。p = 2 * P(T_df > |t|)。"""
    _require(df >= 1, '自由度须 >= 1')
    p = 2.0 * stats.t.sf(abs(t), df)
    return _result(reported, float(p), {'t': t, 'df': df, 'sided': 2},
                   'p = 2*sf_t(|t|, df)', 'scipy.stats.t.sf')


def p_from_f(f, df1, df2, reported=None):
    """F 统计量与分子/分母自由度 → p 值(右尾,ANOVA/回归整体检验惯例)。"""
    _require(df1 >= 1 and df2 >= 1, '自由度须 >= 1')
    _require(f >= 0, 'F 统计量须非负')
    p = stats.f.sf(f, df1, df2)
    return _result(reported, float(p), {'F': f, 'df1': df1, 'df2': df2},
                   'p = sf_F(F, df1, df2)', 'scipy.stats.f.sf')


def p_from_chi2(chi2, df, reported=None):
    """卡方统计量与自由度 → p 值(右尾)。"""
    _require(df >= 1, '自由度须 >= 1')
    _require(chi2 >= 0, '卡方统计量须非负')
    p = stats.chi2.sf(chi2, df)
    return _result(reported, float(p), {'chi2': chi2, 'df': df},
                   'p = sf_chi2(chi2, df)', 'scipy.stats.chi2.sf')


# ---------------------------------------------------------------------------
# 3. 报告的 β 与 SE → 重算 Wald 统计量
# ---------------------------------------------------------------------------

def z_from_beta_se(beta, se, reported=None):
    """回归系数 β 与其标准误 → Wald z 与双侧正态近似 p 值。

    z = β/SE;p = 2 * (1 - Φ(|z|))。大样本 logistic/Cox 报告惯例;
    小样本 OLS 应改用 t 分布(见 p_from_t,df = 残差自由度)。
    """
    _require(se > 0, '标准误须为正')
    z = beta / se
    p = 2.0 * stats.norm.sf(abs(z))
    return _result(
        reported,
        {'z': float(z), 'p': float(p)},
        {'beta': beta, 'se': se},
        'z = beta/se; p = 2*sf_norm(|z|)', 'scipy.stats.norm.sf',
    )


# ---------------------------------------------------------------------------
# 4. 置信区间与点估计一致性
# ---------------------------------------------------------------------------

def check_ci_consistency(estimate, lower, upper, level=0.95, log_scale=False, rel_tol=0.02):
    """点估计与报告 CI 的几何/算术一致性 + 反推 SE。

    对称区间(差值类):estimate 应约等于 (lower+upper)/2。
    比值类指标(OR/RR/HR,log_scale=True):estimate 应约等于 sqrt(lower*upper)。
    反推 SE(或 log 尺度 SE)= (upper-lower)/(2*z_{level}),log 尺度先取对数。
    rel_tol:估计值与 CI 中点的相对容差(报告四舍五入通常 <2%)。
    """
    _require(0 < level < 1, '置信水平须在 (0,1)')
    _require(lower < upper, 'CI 下限须小于上限')
    if log_scale:
        _require(lower > 0 and estimate > 0, 'log 尺度要求区间与估计值为正')
        mid = float(np.sqrt(lower * upper))
        half_width = (np.log(upper) - np.log(lower)) / 2.0
        implied_se = float(half_width / stats.norm.ppf(1 - (1 - level) / 2))
        rel_dev = abs(estimate - mid) / mid
    else:
        mid = (lower + upper) / 2.0
        implied_se = float((upper - lower) / (2.0 * stats.norm.ppf(1 - (1 - level) / 2)))
        rel_dev = abs(estimate - mid) / (abs(mid) if mid != 0 else max(abs(lower), abs(upper)))
    return {
        'consistent': bool(rel_dev <= rel_tol),
        'ci_midpoint': float(mid),
        'estimate': float(estimate),
        'relative_deviation': float(rel_dev),
        'implied_se': implied_se,
        'inputs': {'estimate': estimate, 'lower': lower, 'upper': upper,
                   'level': level, 'log_scale': log_scale},
        'formula': ('log 尺度: mid=sqrt(L*U), se=log(U/L)/(2z)' if log_scale
                    else 'mid=(L+U)/2, se=(U-L)/(2z)'),
        'library': 'scipy.stats.norm.ppf',
        'confidence': 'medium',
        'note': 'implied_se 受端点四舍五入影响,仅作交叉核对',
    }


# ---------------------------------------------------------------------------
# 5. 2×2 表 → OR / RR 及置信区间
# ---------------------------------------------------------------------------

def or_rr_from_2x2(a, b, c, d, level=0.95, reported=None):
    """2×2 表 → 比值比、相对危险度及 Wald(log 尺度)置信区间。

    表约定:第一行暴露/处理组 a=事件数, b=未事件数;第二行对照组 c, d。
    OR = ad/bc,SE(logOR) = sqrt(1/a+1/b+1/c+1/d)。
    RR = (a/(a+b))/(c/(c+d)),SE(logRR) = sqrt(b/(a(a+b)) + d/(c(c+d)))。
    出现 0 格时自动施加 Haldane-Anscombe 0.5 校正并在结果中标记。
    """
    cells = {'a': a, 'b': b, 'c': c, 'd': d}
    _require(all(v >= 0 for v in cells.values()), '格子计数须非负')
    _require(a + b > 0 and c + d > 0, '每行总数须为正')
    correction = any(v == 0 for v in cells.values())
    if correction:
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    z = stats.norm.ppf(1 - (1 - level) / 2)
    or_ = (a * d) / (b * c)
    se_log_or = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    log_or = np.log(or_)
    rr = (a / (a + b)) / (c / (c + d))
    se_log_rr = np.sqrt(b / (a * (a + b)) + d / (c * (c + d)))
    log_rr = np.log(rr)
    return _result(
        reported,
        {
            'odds_ratio': float(or_),
            'or_ci': [float(np.exp(log_or - z * se_log_or)), float(np.exp(log_or + z * se_log_or))],
            'risk_ratio': float(rr),
            'rr_ci': [float(np.exp(log_rr - z * se_log_rr)), float(np.exp(log_rr + z * se_log_rr))],
            'risk_exposed': float(a / (a + b)),
            'risk_control': float(c / (c + d)),
            'zero_cell_correction': correction,
        },
        {'a': cells['a'], 'b': cells['b'], 'c': cells['c'], 'd': cells['d'], 'level': level},
        'OR=ad/bc (log-Wald CI); RR=(a/(a+b))/(c/(c+d)) (log-Wald CI)',
        'scipy.stats.norm.ppf + numpy (closed form)',
        confidence='medium' if correction else 'high',
    )


# ---------------------------------------------------------------------------
# 6. 样本量与效应量 → 实现功效(achieved power)
# ---------------------------------------------------------------------------

def achieved_power_ttest(d, n1, n2=None, alpha=0.05, reported=None):
    """两独立样本 t 检验的实现功效(双侧)。

    输入 Cohen's d、每组样本量与 α,返回在给定条件下能检出该效应量的概率。
    n2 省略时按两组相等处理。结果受 d 报告精度影响,confidence='medium'。
    """
    _require(n1 >= 2, 'n1 须 >= 2')
    _require(0 < alpha < 1, 'alpha 须在 (0,1)')
    n2 = n1 if n2 is None else n2
    _require(n2 >= 2, 'n2 须 >= 2')
    power = TTestIndPower().solve_power(
        effect_size=abs(d), nobs1=n1, alpha=alpha, ratio=n2 / n1, alternative='two-sided')
    return _result(reported, float(power),
                   {'d': d, 'n1': n1, 'n2': n2, 'alpha': alpha, 'sided': 2},
                   'noncentral-t power, |d|, n1, n2, alpha',
                   'statsmodels.stats.power.TTestIndPower.solve_power',
                   confidence='medium')


def required_n_ttest(d, power=0.8, alpha=0.05, ratio=1.0, reported=None):
    """达到目标功效所需的第一组样本量(未取整,请向上取整后报告)。

    用于核对论文"样本量经功效分析确定"的表述:n_required = solve(n)。
    ratio = n2/n1;返回值是连续解,实际入组须 ceil。
    """
    _require(d != 0, '效应量须非零')
    _require(0 < power < 1 and 0 < alpha < 1, 'power/alpha 须在 (0,1)')
    _require(ratio > 0, 'ratio 须为正')
    n = TTestIndPower().solve_power(
        effect_size=abs(d), nobs1=None, alpha=alpha, power=power, ratio=ratio,
        alternative='two-sided')
    return _result(reported, float(n),
                   {'d': d, 'power': power, 'alpha': alpha, 'ratio': ratio, 'sided': 2},
                   'invert noncentral-t power for nobs1',
                   'statsmodels.stats.power.TTestIndPower.solve_power',
                   confidence='medium')


# ---------------------------------------------------------------------------
# 错配检测
# ---------------------------------------------------------------------------

def _decimals(value):
    """由浮点字面量推断报告的小数位数(0.04 → 2)。"""
    return max(0, -Decimal(str(value)).as_tuple().exponent)


def check_p_match(reported_p, recomputed_p, decimals=None):
    """报告的 p 值与重算 p 值是否一致(按报告精度四舍五入容差)。

    报告 p 保留 k 位小数时,真值落在 [p - 0.5·10^-k, p + 0.5·10^-k) 即判一致;
    decimals 省略时由 reported_p 的字面精度推断。p 以 "< .05" 形式报告时
    本函数不适用(改用方向性核对,见 SKILL.md 工作流 4)。
    """
    _require(0 <= reported_p <= 1 and 0 <= recomputed_p <= 1, 'p 值须在 [0,1]')
    k = _decimals(reported_p) if decimals is None else decimals
    tol = 0.5 * 10 ** (-k)
    diff = abs(recomputed_p - reported_p)
    return {
        'consistent': bool(diff <= tol + 1e-12),
        'reported': reported_p,
        'recomputed': float(recomputed_p),
        'difference': float(recomputed_p - reported_p),
        'tolerance': float(tol),
        'decimals': int(k),
        'formula': '|p_recomputed - p_reported| <= 0.5 * 10^-decimals',
        'library': 'pure python',
        'confidence': 'high',
    }


def check_percentage(count, percent, denominator=None, max_denominator=100000):
    """百分比分母核对:报告百分比、计数与(可选)声明分母是否自洽。

    给出 denominator 时直接比较 100*count/denominator 与 percent(按 percent
    的报告精度取容差)。省略 denominator 时反推隐含分母 100*count/percent,
    在距其最近整数处回算百分比判定;同时给出最近整数分母供人工核对。
    """
    _require(count >= 0, '计数须非负')
    _require(0 < percent <= 100, '百分比须在 (0,100]')
    k = _decimals(percent)
    tol = 0.5 * 10 ** (-k) + 1e-12
    out = {
        'inputs': {'count': count, 'percent': percent},
        'tolerance': float(tol),
        'formula': 'percent ?= 100*count/denominator (按报告精度容差)',
        'library': 'pure python',
        'confidence': 'high',
    }
    if denominator is not None:
        _require(denominator > 0, '分母须为正')
        recomputed = 100.0 * count / denominator
        out.update({
            'consistent': bool(abs(recomputed - percent) <= tol),
            'denominator': denominator,
            'recomputed_percent': float(recomputed),
            'difference': float(recomputed - percent),
        })
        return out
    implied = 100.0 * count / percent
    nearest = int(round(implied))
    if not (1 <= nearest <= max_denominator):
        out.update({'consistent': False, 'implied_denominator': float(implied),
                    'note': '隐含分母超出合理范围'})
        return out
    recomputed = 100.0 * count / nearest
    out.update({
        'consistent': bool(abs(recomputed - percent) <= tol),
        'implied_denominator': float(implied),
        'nearest_denominator': nearest,
        'recomputed_percent': float(recomputed),
        'difference': float(recomputed - percent),
    })
    return out


def check_sd_possible(sd, minimum, maximum, n=None):
    """有界量表的 SD 可行性:报告 SD 是否超出理论最大标准差。

    取值范围 [minimum, maximum] 的变量,总体 SD 上界为 (maximum-minimum)/2
    (两极各半分布);样本 SD(分母 n-1)上界再乘 sqrt(n/(n-1))。
    超出即"不可能的 SD",常见于把 SE 误报为 SD 或量表范围记错。
    """
    _require(sd >= 0, 'SD 须非负')
    _require(minimum < maximum, '量表下限须小于上限')
    max_pop_sd = (maximum - minimum) / 2.0
    if n is not None:
        _require(n >= 2, 'n 须 >= 2')
        max_sd = max_pop_sd * np.sqrt(n / (n - 1.0))
    else:
        max_sd = max_pop_sd
    return {
        'consistent': bool(sd <= max_sd + 1e-12),
        'reported_sd': sd,
        'max_possible_sd': float(max_sd),
        'excess': float(sd - max_sd),
        'inputs': {'sd': sd, 'minimum': minimum, 'maximum': maximum, 'n': n},
        'formula': 'max_sd = (max-min)/2 * sqrt(n/(n-1)) (n 省略时取总体界)',
        'library': 'numpy (closed form)',
        'confidence': 'high',
    }


def check_sample_size_from_df(df, reported_n, kind='ttest_2sample', n_params=None):
    """由报告自由度反推样本量,与论文声明的 N 核对。

    kind:
      'ttest_1sample' / 'ttest_paired' → N = df + 1
      'ttest_2sample'                  → N = df + 2(两组总数)
      'regression'                     → N = df + n_params(残差 df + 参数个数,
                                          含截距;n_params 必填)
    """
    _require(df >= 1, '自由度须 >= 1')
    _require(reported_n >= 1, '样本量须 >= 1')
    if kind in ('ttest_1sample', 'ttest_paired'):
        implied = df + 1
    elif kind == 'ttest_2sample':
        # QA-02: N = df + 2 只对 pooled Student t 成立且要求整数 df;
        # 非整数 df 是 Welch-Satterthwaite 自由度的特征, 不能反推 N。
        if float(df) != int(df):
            return {
                'consistent': None,
                'implied_n': None,
                'reported_n': int(reported_n),
                'difference': None,
                'inputs': {'df': df, 'reported_n': reported_n, 'kind': kind,
                           'n_params': n_params},
                'formula': 'Student t: N = df+2 (仅整数 df); 非整数 df 属于 Welch',
                'library': 'pure python',
                'confidence': 'medium',
                'note': '非整数自由度属于 Welch 情形, N = df+2 不成立, 不得据此判定样本量错误; '
                        '用 kind="ttest_2sample_welch" 显式声明, 或核对论文是否报告了 Welch 校正',
            }
        implied = df + 2
    elif kind == 'ttest_2sample_welch':
        return {
            'consistent': None,
            'implied_n': None,
            'reported_n': int(reported_n),
            'difference': None,
            'inputs': {'df': df, 'reported_n': reported_n, 'kind': kind,
                       'n_params': n_params},
            'formula': 'Welch df 依赖两组方差与样本量, 无法仅由 df 反推 N',
            'library': 'pure python',
            'confidence': 'medium',
            'note': 'Welch 自由度无法反推样本量, 本函数不做判定',
        }
    elif kind == 'regression':
        _require(n_params is not None and n_params >= 1,
                 "kind='regression' 须提供 n_params(含截距)")
        implied = df + n_params
    else:
        raise ValueError(f'未知 kind: {kind}')
    return {
        'consistent': bool(implied == reported_n),
        'implied_n': int(implied),
        'reported_n': int(reported_n),
        'difference': int(reported_n - implied),
        'inputs': {'df': df, 'reported_n': reported_n, 'kind': kind,
                   'n_params': n_params},
        'formula': {'ttest_1sample': 'N = df+1', 'ttest_paired': 'N = df+1',
                    'ttest_2sample': 'N = df+2 (pooled Student, 整数 df)',
                    'ttest_2sample_welch': 'Welch df 不可反推 N',
                    'regression': 'N = df_residual + n_params'}[kind],
        'library': 'pure python',
        'confidence': 'high',
    }


def values_agree(value_a, value_b, rel_tol=1e-3, abs_tol=None):
    """两处报告值(正文 vs 表格、摘要 vs 结果)是否一致。

    默认相对容差 1e-3(容忍排版四舍五入);跨量级或近零值用 abs_tol。
    QA-01: 输入与容差必须为有限数, inf/nan 一律 ValueError, 不得判成一致。
    """
    for name, val in (('value_a', value_a), ('value_b', value_b)):
        if not math.isfinite(float(val)):
            raise ValueError(f'{name} 必须是有限数, got {val!r}')
    if not math.isfinite(float(rel_tol)) or float(rel_tol) < 0:
        raise ValueError(f'rel_tol 必须是有限非负数, got {rel_tol!r}')
    if abs_tol is not None and (not math.isfinite(float(abs_tol)) or float(abs_tol) < 0):
        raise ValueError(f'abs_tol 必须是有限非负数, got {abs_tol!r}')
    diff = abs(value_a - value_b)
    scale = max(abs(value_a), abs(value_b))
    tol = abs_tol if abs_tol is not None else rel_tol * scale
    return {
        'consistent': bool(diff <= tol + 1e-15),
        'value_a': value_a,
        'value_b': value_b,
        'difference': float(value_a - value_b),
        'tolerance': float(tol),
        'formula': '|a-b| <= rel_tol*max(|a|,|b|) 或 abs_tol',
        'library': 'pure python',
        'confidence': 'high',
    }
