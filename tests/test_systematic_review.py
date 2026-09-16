"""systematic-review-meta-analysis 核心计算的手算对照测试。"""
import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'meta_core', ROOT / 'skills' / 'systematic-review-meta-analysis' / 'scripts' / 'meta_core.py')
meta_core = importlib.util.module_from_spec(spec)
sys.modules['meta_core'] = meta_core  # dataclass 需要模块注册
spec.loader.exec_module(meta_core)


def test_effect_size_conversions_handchecked():
    # Cohen's d → Hedges' g:d = 0.4, n1 = n2 = 25 → df = 48,
    # J = 1 - 3/(4*48 - 1) = 1 - 3/191;g = J * d。
    j = 1.0 - 3.0 / 191.0
    assert meta_core.hedges_j(48) == pytest.approx(j)
    assert meta_core.hedges_g(0.4, 25, 25) == pytest.approx(0.4 * j)
    # d ↔ log OR:lor = (π/√3) * d,往返一致。
    lor = meta_core.d_to_log_or(0.4)
    assert lor == pytest.approx(0.4 * math.pi / math.sqrt(3.0))
    assert meta_core.log_or_to_d(lor) == pytest.approx(0.4)
    # d → r(等组):r = d / √(d² + 4) = 0.4 / √4.16。
    assert meta_core.d_to_r(0.4) == pytest.approx(0.4 / math.sqrt(4.16))
    assert meta_core.r_to_d(meta_core.d_to_r(0.4)) == pytest.approx(0.4)
    # OR ↔ RR,p0 = 0.2, OR = 2.0:RR = 2 / (0.8 + 0.4) = 5/3,往返一致。
    rr = meta_core.or_to_rr(2.0, 0.2)
    assert rr == pytest.approx(5.0 / 3.0)
    assert meta_core.rr_to_or(rr, 0.2) == pytest.approx(2.0)


def test_heterogeneity_i2_tau2_handchecked():
    # yi = [0.2, 0.5, 0.8], vi = 0.05 × 3:w = 20,θ_F = 0.5,
    # Q = 20(0.3² + 0 + 0.3²) = 3.6,df = 2,I² = 1.6/3.6,τ² = 1.6/C,C = 60 - 1200/60 = 40。
    q, df, i2, tau2 = meta_core.heterogeneity([0.2, 0.5, 0.8], [0.05, 0.05, 0.05])
    assert q == pytest.approx(3.6)
    assert df == 2
    assert i2 == pytest.approx(1.6 / 3.6)
    assert tau2 == pytest.approx(0.04)


def test_pooling_handchecked():
    # 两项研究 d = 0.4、各 n = 50(25/25):
    # v = 50/625 + 0.16/96 = 0.081666...,w = 1/v,
    # 固定效应 θ = 0.4,se = √(1/2w)。
    v = meta_core.var_d(0.4, 25, 25)
    assert v == pytest.approx(0.08 + 0.16 / 96.0)
    res = meta_core.pool_fixed([0.4, 0.4], [v, v])
    assert res.estimate == pytest.approx(0.4)
    assert res.se == pytest.approx(math.sqrt(v / 2.0))
    assert res.q == pytest.approx(0.0) and res.i2 == 0.0 and res.tau2 == 0.0
    # τ² = 0 时随机效应退化为固定效应。
    rnd = meta_core.pool_random([0.4, 0.4], [v, v])
    assert rnd.estimate == pytest.approx(res.estimate)
    assert rnd.se == pytest.approx(res.se)
    # 异质例子随机效应:w* = 1/(0.05 + 0.04) = 1/0.09,θ = 0.5,se = √(0.09/3)。
    rnd2 = meta_core.pool_random([0.2, 0.5, 0.8], [0.05, 0.05, 0.05])
    assert rnd2.estimate == pytest.approx(0.5)
    assert rnd2.se == pytest.approx(math.sqrt(0.09 / 3.0))
