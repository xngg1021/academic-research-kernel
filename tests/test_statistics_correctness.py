"""Production regressions for P1-01/P2-01: decimal rounding and domains."""

from decimal import Decimal
import importlib.util
import json
import math
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "statistics_correctness_recompute",
    ROOT / "skills/quantitative-paper-audit/scripts/recompute.py",
)
recompute = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recompute)


def test_small_p_counterexample_and_ordinary_positive_control():
    actual = recompute.p_from_t(1, 30)["recomputed"]
    # Independent recorded numerical landmark, not the matcher's own output.
    assert actual == pytest.approx(0.3253086154260302, abs=1e-14)
    mismatch = recompute.check_p_match(0.00001, actual)
    assert mismatch["consistent"] is False
    assert mismatch["decimals"] == 5
    assert mismatch["tolerance"] == pytest.approx(0.000005)
    assert recompute.check_p_match(0.3253, actual)["consistent"] is True


@pytest.mark.parametrize("literal,places,tolerance", [
    ("0.050", 3, "0.0005"),
    ("1.0e-5", 6, "0.0000005"),
    ("1e-5", 5, "0.000005"),
    ("5.00E-2", 4, "0.00005"),
    ("5e-300", 300, "5e-301"),
    ("0.00", 2, "0.005"),
    ("1.000", 3, "0.0005"),
])
def test_decimal_exponents_preserve_places_and_trailing_zeros(literal, places, tolerance):
    result = recompute.check_p_match(literal, literal)
    assert result["consistent"] is True
    assert result["decimals"] == places
    assert Decimal(result["tolerance_decimal"]) == Decimal(tolerance)
    assert result["precision_source"] == "literal"
    assert recompute._decimals(literal) == places


def test_scientific_literal_counterexample_is_inconsistent():
    assert recompute.check_p_match("1.0e-5", 0.04)["consistent"] is False


def test_numeric_input_never_claims_to_recover_lost_trailing_zeros():
    inferred = recompute.check_p_match(0.050, 0.0504)
    assert inferred["decimals"] == 2
    assert inferred["precision_source"] == "numeric_representation"
    assert inferred["reported_literal"] is None
    restored = recompute.check_p_match(0.05, 0.0504, reported_literal="0.050")
    assert restored["decimals"] == 3
    assert restored["reported_literal"] == "0.050"
    assert recompute.check_p_match(0.05, 0.0506, decimals=3)["consistent"] is False


@pytest.mark.parametrize("reported,recomputed,consistent", [
    ("0.04", "0.035", True),
    ("0.04", "0.0349999999999999999999", False),
    ("0.04", "0.0449999999999999999999", True),
    ("0.04", "0.045", False),
    ("0.00", "0", True),
    ("0.00", "0.0049999999999999999999", True),
    ("0.00", "0.005", False),
    ("1.00", "0.9949999999999999999999", False),
    ("1.00", "0.995", True),
    ("1.00", "1", True),
    ("1.0e-5", "0.0000095", True),
    ("1.0e-5", "0.0000105", False),
])
def test_round_half_up_interval_has_exact_inclusive_lower_and_exclusive_upper(
    reported, recomputed, consistent,
):
    result = recompute.check_p_match(reported, recomputed)
    assert result["consistent"] is consistent
    assert result["rounding_interval"]["lower_inclusive"] is True
    assert result["rounding_interval"]["upper_inclusive"] is False


@pytest.mark.parametrize("precision", [-1, 1.5, True, "2", 10001])
def test_invalid_decimal_precision_is_rejected(precision):
    with pytest.raises(ValueError, match="decimals"):
        recompute.check_p_match(0.05, 0.05, decimals=precision)
    with pytest.raises(ValueError, match="decimals"):
        recompute.check_percentage(5, 5, denominator=100, decimals=precision)


@pytest.mark.parametrize("reported,kwargs", [
    (0.05, {"reported_literal": "0.051"}),
    (0.05, {"reported_literal": "0.050", "decimals": 2}),
    ("0.050", {"decimals": 2}),
    (0.051, {"decimals": 2}),
    (0.05, {"reported_literal": 0.05}),
])
def test_conflicting_precision_sources_are_explicit_errors(reported, kwargs):
    with pytest.raises(ValueError):
        recompute.check_p_match(reported, 0.05, **kwargs)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, "NaN", "Infinity", True])
def test_nonfinite_or_boolean_p_values_are_rejected(value):
    with pytest.raises(ValueError):
        recompute.check_p_match(value, 0.05)
    with pytest.raises(ValueError):
        recompute.check_p_match(0.05, value)


@pytest.mark.parametrize("reported,recomputed", [(-0.01, 0), (0, -0.01), (1.01, 1), (1, 1.01)])
def test_p_domain_endpoints_do_not_admit_out_of_domain_values(reported, recomputed):
    with pytest.raises(ValueError):
        recompute.check_p_match(reported, recomputed)


def test_count_cannot_exceed_denominator_even_if_rounding_would_hide_it():
    with pytest.raises(ValueError, match="count"):
        recompute.check_percentage(1001, 100, denominator=1000)


@pytest.mark.parametrize("run", [
    lambda: recompute.check_percentage(1.5, 50, denominator=3),
    lambda: recompute.check_percentage(1, 50, denominator=2.5),
    lambda: recompute.check_percentage(True, 50, denominator=2),
    lambda: recompute.check_percentage(1, 50, max_denominator=100.5),
    lambda: recompute.cohens_d(5, 2, 10.5, 3, 2, 10),
    lambda: recompute.achieved_power_ttest(0.5, 10.5),
    lambda: recompute.or_rr_from_2x2(0.5, 20, 5, 25),
    lambda: recompute.check_sd_possible(1, 0, 5, n=10.5),
    lambda: recompute.check_sample_size_from_df(28, 30.5),
    lambda: recompute.check_sample_size_from_df(28, 30, kind="regression", n_params=2.5),
    lambda: recompute.check_sample_size_from_df(28.5, 30, kind="ttest_paired"),
])
def test_counts_and_sample_sizes_are_not_silently_truncated(run):
    with pytest.raises(ValueError):
        run()


@pytest.mark.parametrize("level", [0, 1, -0.1, 1.5, math.nan, math.inf, True])
def test_confidence_level_domain_is_shared_by_ci_and_ratio_functions(level):
    with pytest.raises(ValueError):
        recompute.or_rr_from_2x2(10, 20, 5, 25, level=level)
    with pytest.raises(ValueError):
        recompute.check_ci_consistency(1, 0.5, 1.5, level=level)


@pytest.mark.parametrize("df", [0, -1, math.nan, math.inf, True])
def test_invalid_degrees_of_freedom_are_rejected(df):
    for run in (lambda: recompute.p_from_t(1, df),
                lambda: recompute.p_from_f(1, df, 30),
                lambda: recompute.p_from_chi2(1, df)):
        with pytest.raises(ValueError):
            run()


def test_positive_noninteger_welch_df_remains_valid():
    assert 0 < recompute.p_from_t(1, 14.5)["recomputed"] < 1
    assert 0 < recompute.p_from_t(1, 0.5)["recomputed"] < 1
    assert recompute.p_from_t(1, 1)["recomputed"] == pytest.approx(0.5)
    assert recompute.check_sample_size_from_df(14.5, 20)["consistent"] is None
    assert recompute.check_sample_size_from_df(14.5, 20, kind="ttest_2sample_welch")["consistent"] is None


@pytest.mark.parametrize("run", [
    lambda: recompute.p_from_t(json.loads("1e309"), 30),
    lambda: recompute.p_from_f(math.inf, 1, 30),
    lambda: recompute.p_from_chi2(math.inf, 1),
    lambda: recompute.z_from_beta_se(math.inf, 1),
    lambda: recompute.cohens_d(math.inf, 1, 10, 2, 1, 10),
    lambda: recompute.check_percentage(1, math.inf, denominator=10),
    lambda: recompute.or_rr_from_2x2(1, 2, 3, math.inf),
    lambda: recompute.achieved_power_ttest(math.inf, 10),
    lambda: recompute.required_n_ttest(math.nan),
    lambda: recompute.check_sd_possible(1, 0, math.inf),
    lambda: recompute.values_agree(1, math.inf),
    lambda: recompute.check_ci_consistency(1, 0, 2, rel_tol=math.inf),
])
def test_all_production_families_reject_nonfinite_inputs(run):
    with pytest.raises(ValueError):
        run()


def test_output_finiteness_guard_rejects_solver_failure(monkeypatch):
    monkeypatch.setattr(recompute.stats.t, "sf", lambda *args: math.nan)
    with pytest.raises(ValueError, match="有限"):
        recompute.p_from_t(1, 30)
    with pytest.raises(ValueError, match="有限"):
        recompute.values_agree(1e308, -1e308)


def test_percentage_rounding_boundaries_and_legal_zero_cells():
    assert recompute.check_percentage(1, "0", denominator=200)["consistent"] is False
    assert recompute.check_percentage(1, "0", denominator=201)["consistent"] is True
    assert recompute.check_percentage(1, "0", max_denominator=200)["consistent"] is False
    possible = recompute.check_percentage(1, "0", max_denominator=201)
    assert possible["consistent"] is None
    assert possible["min_possible_denominator"] == 201
    assert recompute.check_percentage(0, "0.00", denominator=10)["consistent"] is True
    assert recompute.check_percentage(10, "100.00", denominator=10)["consistent"] is True
    corrected = recompute.or_rr_from_2x2(0, 50, 10, 40)
    assert corrected["recomputed"]["zero_cell_correction"] is True
    json.dumps(corrected, allow_nan=False)
