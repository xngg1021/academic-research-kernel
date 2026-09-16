"""quantitative-paper-audit 技能 scripts/recompute.py 的最小正确性测试。

所有期望值来自手算小例子或经典统计表界值(t/χ² 0.05 临界值、
d=0.5 每组 64 人≈80% 功效等),不依赖被测库自身输出当期望。
"""
import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'recompute', ROOT / 'skills' / 'quantitative-paper-audit' / 'scripts' / 'recompute.py')
recompute = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recompute)


# ---------------------------------------------------------------------------
# 结构化结果契约
# ---------------------------------------------------------------------------

def test_result_structure_keys():
    result = recompute.p_from_t(2.0, 8, reported=0.08)
    for key in ('reported', 'recomputed', 'difference', 'inputs', 'formula', 'library', 'confidence'):
        assert key in result, f'缺少字段 {key}'
    assert result['reported'] == 0.08
    assert result['difference'] == pytest.approx(result['recomputed'] - 0.08)
    assert result['confidence'] in ('high', 'medium')


# ---------------------------------------------------------------------------
# 均值与标准差 → 效应量
# ---------------------------------------------------------------------------

def test_cohens_d_equal_sds():
    # sp = sqrt((9*4 + 9*4)/18) = 2;d = (5-3)/2 = 1.0
    result = recompute.cohens_d(5, 2, 10, 3, 2, 10)
    assert result['recomputed']['cohens_d'] == pytest.approx(1.0)
    # Hedges 校正 J = 1 - 3/(4*18-1) = 68/71
    assert result['recomputed']['hedges_g'] == pytest.approx(68 / 71)
    assert result['recomputed']['df'] == 18


def test_cohens_d_unequal_groups():
    # sp = sqrt((19*9 + 9*1)/28) = sqrt(180/28) = sqrt(6.428...)
    result = recompute.cohens_d(7, 3, 20, 5, 1, 10)
    sp = math.sqrt(180 / 28)
    assert result['recomputed']['pooled_sd'] == pytest.approx(sp)
    assert result['recomputed']['cohens_d'] == pytest.approx(2 / sp)


def test_cohens_d_rejects_bad_input():
    with pytest.raises(ValueError):
        recompute.cohens_d(5, 2, 1, 3, 2, 10)


# ---------------------------------------------------------------------------
# t / F / χ² + 自由度 → p
# ---------------------------------------------------------------------------

def test_p_from_t_critical_value():
    # df=8 双侧 0.05 临界 t = 2.306
    assert recompute.p_from_t(2.306, 8)['recomputed'] == pytest.approx(0.05, abs=1e-3)
    assert recompute.p_from_t(0.0, 8)['recomputed'] == pytest.approx(1.0)


def test_p_from_f_matches_t_squared():
    # F(1, df) = t_df^2,两者 p 值应精确一致
    p_t = recompute.p_from_t(2.0, 30)['recomputed']
    p_f = recompute.p_from_f(4.0, 1, 30)['recomputed']
    assert p_f == pytest.approx(p_t, rel=1e-12)
    assert recompute.p_from_f(0.0, 2, 30)['recomputed'] == pytest.approx(1.0)


def test_p_from_chi2_critical_value():
    # χ²(1) 0.05 界值 3.841
    assert recompute.p_from_chi2(3.841, 1)['recomputed'] == pytest.approx(0.05, abs=1e-3)
    with pytest.raises(ValueError):
        recompute.p_from_chi2(-1.0, 1)


# ---------------------------------------------------------------------------
# β 与 SE → Wald 统计量
# ---------------------------------------------------------------------------

def test_z_from_beta_se():
    result = recompute.z_from_beta_se(1.96, 1.0)
    assert result['recomputed']['z'] == pytest.approx(1.96)
    assert result['recomputed']['p'] == pytest.approx(0.05, abs=1e-3)


def test_z_from_beta_se_negative_beta():
    # β 为负时 z 取负,p 与 |z| 对称
    result = recompute.z_from_beta_se(-3.92, 2.0)
    assert result['recomputed']['z'] == pytest.approx(-1.96)
    assert result['recomputed']['p'] == pytest.approx(0.05, abs=1e-3)


# ---------------------------------------------------------------------------
# CI 与点估计一致性(含一个错配案例)
# ---------------------------------------------------------------------------

def test_ci_consistent_arithmetic():
    # 中点 (0.51+1.49)/2 = 1.0;implied SE = 0.98/(2*1.96) = 0.25
    result = recompute.check_ci_consistency(1.0, 0.51, 1.49)
    assert result['consistent']
    assert result['ci_midpoint'] == pytest.approx(1.0)
    assert result['implied_se'] == pytest.approx(0.25, abs=1e-3)


def test_ci_mismatch_arithmetic():
    # 点估计 1.0 不在 [0.5, 2.0] 的算术中点 1.25 上 → 错配
    result = recompute.check_ci_consistency(1.0, 0.5, 2.0, log_scale=False)
    assert not result['consistent']
    assert result['relative_deviation'] == pytest.approx(0.2)


def test_ci_log_scale_ratio_measure():
    # OR=2.0,CI [1.0, 4.0]:几何中点 sqrt(1*4) = 2.0 → 一致
    result = recompute.check_ci_consistency(2.0, 1.0, 4.0, log_scale=True)
    assert result['consistent']
    # log 尺度 implied SE = ln(4)/(2*1.96)
    assert result['implied_se'] == pytest.approx(math.log(4) / (2 * 1.96), abs=1e-3)


# ---------------------------------------------------------------------------
# 2×2 表 → OR / RR
# ---------------------------------------------------------------------------

def test_or_rr_from_2x2_hand_example():
    # a=20, b=80, c=15, d=85:OR = 1700/1200 ≈ 1.4167
    # 风险 0.20 vs 0.15 → RR = 4/3 ≈ 1.3333
    result = recompute.or_rr_from_2x2(20, 80, 15, 85)
    rec = result['recomputed']
    assert rec['odds_ratio'] == pytest.approx(1700 / 1200)
    assert rec['risk_ratio'] == pytest.approx(4 / 3)
    assert rec['risk_exposed'] == pytest.approx(0.20)
    assert rec['risk_control'] == pytest.approx(0.15)
    assert rec['or_ci'][0] < rec['odds_ratio'] < rec['or_ci'][1]
    assert rec['rr_ci'][0] < rec['risk_ratio'] < rec['rr_ci'][1]
    assert not rec['zero_cell_correction']


def test_or_rr_zero_cell_correction():
    result = recompute.or_rr_from_2x2(0, 50, 10, 40)
    assert result['recomputed']['zero_cell_correction']
    # 0.5 校正后 OR = (0.5*40.5)/(50.5*10.5)
    assert result['recomputed']['odds_ratio'] == pytest.approx((0.5 * 40.5) / (50.5 * 10.5))
    assert result['confidence'] == 'medium'


# ---------------------------------------------------------------------------
# 实现功效与所需样本量
# ---------------------------------------------------------------------------

def test_achieved_power_classic_80pct():
    # 经典设计:d=0.5、每组 64 人、α=0.05 双侧 → 功效约 0.80
    result = recompute.achieved_power_ttest(0.5, 64)
    assert result['recomputed'] == pytest.approx(0.80, abs=0.01)


def test_achieved_power_unequal_groups():
    # 不等组功效低于等组(总 N 相同):2×64=128 vs 96+32=128
    equal = recompute.achieved_power_ttest(0.5, 64, 64)['recomputed']
    unequal = recompute.achieved_power_ttest(0.5, 96, 32)['recomputed']
    assert unequal < equal


def test_required_n_inverts_achieved_power():
    result = recompute.required_n_ttest(0.5, power=0.8)
    n = result['recomputed']
    assert 63 < n < 65  # 连续解约 63.77
    # 向上取整后回算功效应达标
    assert recompute.achieved_power_ttest(0.5, math.ceil(n))['recomputed'] >= 0.8


# ---------------------------------------------------------------------------
# p 值错配检测
# ---------------------------------------------------------------------------

def test_check_p_match_consistent_rounding():
    # 报告 0.04(2 位小数),真值 0.042 四舍五入后仍为 0.04 → 一致
    assert recompute.check_p_match(0.04, 0.042)['consistent']


def test_check_p_match_mismatch():
    # 报告 0.04,重算 0.046 → 真值应报 0.05 → 错配
    result = recompute.check_p_match(0.04, 0.046)
    assert not result['consistent']
    assert result['decimals'] == 2
    assert result['tolerance'] == pytest.approx(0.005)


def test_check_p_match_explicit_decimals():
    # 报告 0.041(3 位小数),重算 0.042 → 超出 ±0.0005 → 错配
    assert not recompute.check_p_match(0.041, 0.042)['consistent']


# ---------------------------------------------------------------------------
# 百分比分母错配
# ---------------------------------------------------------------------------

def test_percentage_with_denominator_consistent():
    # 33/99 = 33.33%,报告 33.3%(1 位小数,容差 0.05)→ 一致
    assert recompute.check_percentage(33, 33.3, denominator=99)['consistent']


def test_percentage_denominator_mismatch():
    # 声称分母 100:33/100 = 33.0%,与报告 33.3% 差 0.3 → 分母错配
    result = recompute.check_percentage(33, 33.3, denominator=100)
    assert not result['consistent']
    assert result['recomputed_percent'] == pytest.approx(33.0)


def test_percentage_implied_denominator():
    # 未给分母:33/99.099 ≈ 33.3%,最近整数分母 99 → 一致
    result = recompute.check_percentage(33, 33.3)
    assert result['consistent']
    assert result['nearest_denominator'] == 99


def test_percentage_implied_denominator_mismatch():
    # 5/10.42,最近分母 10 回算得 50.0%,与报告 48.0% 差 2.0 → 错配
    result = recompute.check_percentage(5, 48.0)
    assert not result['consistent']


# ---------------------------------------------------------------------------
# 不可能的 SD
# ---------------------------------------------------------------------------

def test_sd_possible_within_bounds():
    # 5 点量表 [1,5],SD=1.2 完全可行
    assert recompute.check_sd_possible(1.2, 1, 5, n=100)['consistent']


def test_sd_impossible_bounded_scale():
    # [1,5] 总体 SD 上界 2.0;n=100 样本上界 2.0*sqrt(100/99) ≈ 2.01
    result = recompute.check_sd_possible(2.5, 1, 5, n=100)
    assert not result['consistent']
    assert result['max_possible_sd'] == pytest.approx(2.0 * math.sqrt(100 / 99))
    # 不给 n 时按总体界:2.01 > 2.0 即不可能
    assert not recompute.check_sd_possible(2.01, 1, 5)['consistent']


# ---------------------------------------------------------------------------
# 样本量与自由度一致性
# ---------------------------------------------------------------------------

def test_sample_size_from_df_two_sample():
    # 双样本 t:df = N-2 → df=58 隐含 N=60
    assert recompute.check_sample_size_from_df(58, 60)['consistent']
    result = recompute.check_sample_size_from_df(58, 58)
    assert not result['consistent']
    assert result['implied_n'] == 60


def test_sample_size_from_df_paired_and_regression():
    assert recompute.check_sample_size_from_df(29, 30, kind='ttest_paired')['consistent']
    # 回归:残差 df=95 + 5 个参数(含截距)→ N=100
    assert recompute.check_sample_size_from_df(95, 100, kind='regression', n_params=5)['consistent']
    with pytest.raises(ValueError):
        recompute.check_sample_size_from_df(95, 100, kind='regression')


# ---------------------------------------------------------------------------
# 表格与正文一致性
# ---------------------------------------------------------------------------

def test_values_agree_rounding_vs_mismatch():
    assert recompute.values_agree(0.05, 0.0500001)['consistent']
    assert not recompute.values_agree(0.05, 0.06)['consistent']
    # 近零值需要绝对容差
    assert recompute.values_agree(0.0001, 0.0002, abs_tol=0.001)['consistent']
