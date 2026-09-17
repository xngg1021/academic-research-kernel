"""第三批裁决回归测试: 统计实现与方法配方 P1 (八项)。

- SR-01 trim-and-fill 镜像不变性 (y→-y 且 side 互换)
- SR-02 迭代振荡检测, 不得把 maxiter 奇偶性当结果
- SR-05/07/10 配方文档修正 (偏倚工具档位、CI 反推 SE、OR/RR 混用界)
- QA-01 values_agree 非有限输入拒绝
- QA-02 Welch 自由度不误报样本量错误
- LA-01 无 DOI 同标题降级为候选关系
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def _load(rel_path, name):
    spec = importlib.util.spec_from_file_location(name, SKILLS / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


meta_core = _load("systematic-review-meta-analysis/scripts/meta_core.py", "batch3_meta_core")
recompute = _load("quantitative-paper-audit/scripts/recompute.py", "batch3_recompute")
dedup = _load("literature-analysis/scripts/deduplicate_works.py", "batch3_dedup")


# ---------- SR-01: 镜像不变性 ----------

def test_sr01_trimfill_mirror_symmetric_case():
    """对称数据: 两侧 k0 均为 0, adjusted 镜像相等。"""
    y = np.array([1.3, 0.9, 0.8, 0.55, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05])
    v = np.full(12, 0.1)
    res_l = meta_core.trim_and_fill(y, v, side='left')
    res_r = meta_core.trim_and_fill(-y, v, side='right')
    assert res_l['converged'] and res_r['converged']
    assert res_l['k0'] == res_r['k0'] == 0
    assert res_l['adjusted'] == pytest.approx(-res_r['adjusted'])


def test_sr01_trimfill_mirror_nonconvergent_case():
    """强偏数据: 两侧必须同判未收敛, 不得一侧 k0=N 一侧 k0=0。"""
    y = np.array([2.5, 2.2, 1.9, 1.7, 1.5, 1.3, 1.1, 0.9, 0.7, 0.2, -0.4, -1.0])
    v = np.full(12, 0.15)
    res_l = meta_core.trim_and_fill(y, v, side='left')
    res_r = meta_core.trim_and_fill(-y, v, side='right')
    assert res_l['converged'] is False
    assert res_r['converged'] is False
    assert res_l['k0'] is None and res_r['k0'] is None


# ---------- SR-02: 振荡检测 ----------

def test_sr02_oscillation_detected_not_parity():
    """固定输入 (0.05,0.05,0.05,0.1,0.1) 在任何 maxiter 下都不得把奇偶性当结果。"""
    for maxiter in (99, 100, 200):
        res = meta_core.trim_and_fill([0.05, 0.05, 0.05, 0.1, 0.1],
                                      [0.1] * 5, side='left', maxiter=maxiter)
        assert res['converged'] is False
        assert res['k0'] is None
        assert '状态循环' in res['note']


def test_sr02_hit_maxiter_reported_unconverged():
    """达到迭代上限仍未收敛时返回 converged=False, 不返回 k0。"""
    res = meta_core.trim_and_fill([0.05, 0.05, 0.05, 0.1, 0.1],
                                  [0.1] * 5, side='left', maxiter=1)
    assert res['converged'] is False
    assert res['k0'] is None


# ---------- SR-05/07/10: 配方文档 ----------

def test_sr05_bias_tool_native_levels_in_docs():
    skill = (SKILLS / "systematic-review-meta-analysis/SKILL.md").read_text(encoding='utf-8')
    assert 'ROBINS-I 判 low / moderate / serious / critical / no information' in skill
    assert '不得压成同一三档' in skill
    assert 'QUADAS-2 各域经 signaling questions 判 low / high / unclear' in skill


def test_sr07_ci_to_se_no_extra_sqrt_n():
    skill = (SKILLS / "systematic-review-meta-analysis/SKILL.md").read_text(encoding='utf-8')
    assert '(upper−lower)/(2×1.96)' in skill
    assert '不得再乘 √n' in skill
    assert '仅当 CI 属于单组均值且目标是 SD 时才乘 √n' in skill


def test_sr10_or_rr_mixing_error_bound():
    ref = (SKILLS / "systematic-review-meta-analysis"
           / "references/effect-size-conversions.md").read_text(encoding='utf-8')
    assert '相对偏差 ≤ 5% 才允许 OR/RR 混用' in ref
    assert 'p0=0.01、OR=100 时 RR≈50.25' in ref


# ---------- QA-01: 非有限输入 ----------

def test_qa01_inf_not_consistent():
    with pytest.raises(ValueError):
        recompute.values_agree(float('inf'), 1.0)
    with pytest.raises(ValueError):
        recompute.values_agree(1.0, float('-inf'))
    with pytest.raises(ValueError):
        recompute.values_agree(float('nan'), 0.5)


def test_qa01_invalid_tolerance_rejected():
    with pytest.raises(ValueError):
        recompute.values_agree(0.05, 0.05, rel_tol=-0.1)
    with pytest.raises(ValueError):
        recompute.values_agree(0.05, 0.05, abs_tol=float('inf'))


def test_qa01_finite_path_unchanged():
    assert recompute.values_agree(0.05, 0.0500001)['consistent']
    assert not recompute.values_agree(0.05, 0.06)['consistent']


# ---------- QA-02: Welch df ----------

def test_qa02_welch_df_not_misreported():
    """合法 Welch 自由度 (37.4) 不得被 N=df+2 误报为样本量错误。"""
    res = recompute.check_sample_size_from_df(37.4, 39, kind='ttest_2sample')
    assert res['consistent'] is None
    assert 'Welch' in res['note']


def test_qa02_welch_kind_undetermined():
    res = recompute.check_sample_size_from_df(37.4, 39, kind='ttest_2sample_welch')
    assert res['consistent'] is None
    assert '无法反推' in res['note']


def test_qa02_student_df_path_unchanged():
    assert recompute.check_sample_size_from_df(58, 60)['consistent']
    assert not recompute.check_sample_size_from_df(58, 58)['consistent']


# ---------- LA-01: 无 DOI 同标题候选 ----------

def test_la01_same_title_different_authors_kept_as_candidates():
    works = [
        {'title': 'Same Title Study', 'authors': ['Zhang San'], 'year': 2020},
        {'title': 'Same Title Study', 'authors': ['Li Si'], 'year': 2020},
    ]
    res = dedup.deduplicate_works(works)
    assert res['summary']['kept'] == 2
    assert res['summary']['removed'] == 0
    assert res['summary']['title_candidates'] == 1
    assert len(res['title_candidates']) == 1


def test_la01_same_title_different_years_kept_as_candidates():
    works = [
        {'title': 'Same Title Study', 'authors': ['Zhang San'], 'year': 2020},
        {'title': 'Same Title Study', 'authors': ['Zhang San'], 'year': 2022},
    ]
    res = dedup.deduplicate_works(works)
    assert res['summary']['kept'] == 2
    assert res['summary']['title_candidates'] == 1


def test_la01_same_title_same_author_year_deduped():
    works = [
        {'title': 'Same Title Study', 'authors': ['Zhang San'], 'year': 2020},
        {'title': 'Same Title Study', 'authors': ['Zhang San'], 'year': 2020},
    ]
    res = dedup.deduplicate_works(works)
    assert res['summary']['kept'] == 1
    assert res['summary']['removed'] == 1
    assert res['removed'][0]['reason'] == 'same-title'


def test_la01_no_author_info_is_candidate_not_dedup():
    works = [
        {'title': 'Attention Is All You Need'},
        {'title': 'attention  is all you need'},
    ]
    res = dedup.deduplicate_works(works)
    assert res['summary']['kept'] == 2
    assert res['summary']['title_candidates'] == 1
