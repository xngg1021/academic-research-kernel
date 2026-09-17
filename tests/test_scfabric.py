"""Tests for the scientific compute fabric (scripts/scfabric).

CPU-only by design: CI runners have no GPU, so every test must pass with
numpy/scipy/torch CPU backends. Accelerator code paths are exercised only
through the dtype gate and probe logic, not through real device calls.
"""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
SCF = ROOT / "scripts" / "scfabric"
sys.path.insert(0, str(SCF))

import backends as be  # noqa: E402
import hardware_probe as hp  # noqa: E402
import workload_profiles as wp  # noqa: E402


def test_probe_runs_without_accelerators():
    p = hp.probe()
    assert p["os"]
    assert p["architecture"]
    assert isinstance(p["accelerators"], list)
    for acc in p["accelerators"]:
        assert "kind" in acc
        assert "available" in acc


def test_probe_field_values_are_sane():
    p = hp.probe()
    assert p["os_visible_cpus"] in ("unknown",) or isinstance(p["os_visible_cpus"], int)
    assert p["ram_total_bytes"] in ("unknown",) or isinstance(p["ram_total_bytes"], int)
    assert p["isa_hint"] in ("unknown",) or isinstance(p["isa_hint"], str)


def test_backend_catalog_declares_dtype_gates():
    # MPS must never declare float64: double precision stays on CPU.
    mps = be.BACKENDS["torch_mps"]
    assert not mps.supports_dtype("float64")
    assert mps.supports_dtype("float32")
    cuda = be.BACKENDS["torch_cuda"]
    assert cuda.supports_dtype("float64")
    # numpy and scipy are CPU reference backends
    assert be.BACKENDS["numpy_cpu"].kind == "cpu"


def test_select_candidates_filters_by_dtype_and_executability():
    names = be.select_candidates("float64")
    assert "torch_mps" not in names  # dtype gate
    assert "numpy_cpu" in names
    names32 = be.select_candidates("float32")
    assert "numpy_cpu" in names32


def test_matmul_reference_and_parity():
    inputs = wp.make_input("matmul_eig", "small", "float64", seed=7)
    ref = wp.reference("matmul_eig", inputs)
    expect_c = inputs["a"] @ inputs["b"]
    assert np.allclose(ref["c"], expect_c, rtol=1e-12)
    # a second reference computation is identical: parity against itself
    ref2 = wp.reference("matmul_eig", inputs)
    assert wp.check_parity("matmul_eig", "small", ref, ref2)


def test_fft_reference_and_parity():
    inputs = wp.make_input("fft", "small", "float64", seed=7)
    ref = wp.reference("fft", inputs)
    assert np.allclose(ref["y"], np.fft.fft2(inputs["x"]), rtol=1e-12)
    assert wp.check_parity("fft", "small", ref, wp.reference("fft", inputs))


def test_autodiff_reference_gradient_is_analytic():
    inputs = wp.make_input("autodiff", "small", "float64", seed=7)
    ref = wp.reference("autodiff", inputs)
    expect = (inputs["x"] - 0.25) / inputs["x"].size
    assert np.allclose(ref["grad"], expect, rtol=1e-12)


def test_monte_carlo_statistical_parity():
    inputs = wp.make_input("monte_carlo", "small", "float64", seed=0)
    ref = wp.reference("monte_carlo", inputs)
    # 4 sigma bound: two independent runs must agree statistically
    assert abs(ref["pi_mean"] - np.pi) < 4 * ref["pi_std"]


def test_bootstrap_reference_shape():
    inputs = wp.make_input("bootstrap", "small", "float64", seed=0)
    ref = wp.reference("bootstrap", inputs)
    assert ref["ci_lo"] <= ref["mean_of_means"] <= ref["ci_hi"]


def test_parity_kinds():
    assert wp.parity_kind("matmul_eig") == "deterministic"
    assert wp.parity_kind("monte_carlo") == "statistical"
    assert wp.parity_kind("bootstrap") == "statistical"


def test_parity_detects_divergence():
    inputs = wp.make_input("matmul_eig", "small", "float64", seed=7)
    ref = wp.reference("matmul_eig", inputs)
    bad = {"c": ref["c"] * 2.0, "eigvals": ref["eigvals"]}
    assert not wp.check_parity("matmul_eig", "small", ref, bad)


@pytest.mark.skipif(not importlib.util.find_spec("torch"),
                    reason="torch not installed")
def test_torch_cpu_candidate_matches_reference():
    inputs = wp.make_input("matmul_eig", "small", "float64", seed=7)
    ref = wp.reference("matmul_eig", inputs)
    cand = wp.candidate("matmul_eig", "torch_cpu", inputs, "float64")
    assert wp.check_parity("matmul_eig", "small", ref, cand)


@pytest.mark.skipif(not importlib.util.find_spec("torch"),
                    reason="torch not installed")
def test_torch_cpu_autodiff_matches_analytic():
    inputs = wp.make_input("autodiff", "small", "float64", seed=7)
    ref = wp.reference("autodiff", inputs)
    cand = wp.candidate("autodiff", "torch_cpu", inputs, "float64")
    assert wp.check_parity("autodiff", "small", ref, cand)


def test_admission_reference_only_environment():
    """Admission must run even when no accelerator exists, and every
    candidate is either ADMITTED (parity + gain) or REFERENCE with a
    recorded reason."""
    import admission as ad
    receipt = ad.run_admission("monte_carlo", "small", dtype="float64",
                               warmup=1, repeat=2)
    for cand in receipt["candidates"]:
        if cand["verdict"] == "REFERENCE":
            assert cand["fallback_reason"] is not None
        else:
            assert cand["fallback_reason"] is None
            assert cand["speedup_vs_reference"] >= receipt["gain_threshold"]


def test_receipt_validates_against_schema():
    import jsonschema
    import admission as ad
    schema = json.loads(
        (ROOT / "schemas" / "compute-receipt.schema.json").read_text(encoding="utf-8"))
    receipt = ad.run_admission("fft", "small", dtype="float64", warmup=1, repeat=2)
    jsonschema.validate(receipt, schema)


def test_receipt_headline_no_score():
    import compute_receipt as cr
    import admission as ad
    receipt = ad.run_admission("matmul_eig", "small", dtype="float64",
                               warmup=1, repeat=2)
    line = cr.receipt_headline(receipt)
    assert receipt["operation"] in line
    assert "ref numpy_cpu" in line


# ---------- C01 ~ C11 回归契约测试 ----------

def test_c01_parity_rejects_nan_and_wrong_shape():
    ref_det = {"c": np.ones((4, 4)), "eigvals": np.ones(4)}
    nan_cand = {"c": np.full((4, 4), np.nan), "eigvals": np.ones(4)}
    assert not wp.check_parity("matmul_eig", "small", ref_det, nan_cand)

    broadcast_cand = {"c": np.ones((4, 1)), "eigvals": np.ones(4)}
    assert not wp.check_parity("matmul_eig", "small", ref_det, broadcast_cand)

    assert not wp.check_parity("matmul_eig", "small", {}, {})

    ref_stat = {"pi_mean": 3.1415, "pi_std": 0.001}
    nan_stat = {"pi_mean": float("nan"), "pi_std": 0.001}
    assert not wp.check_parity("monte_carlo", "small", ref_stat, nan_stat)


@pytest.mark.skipif(not importlib.util.find_spec("torch"),
                    reason="torch not installed")
def test_c02_torch_bootstrap_preserves_float64():
    # 测试极其微小的差别在 float64 下不被截断为 float32
    inputs = {"data": np.array([1.0 + 2**-30] * 10, dtype=np.float64), "resamples": 2}
    cand = wp._candidate_torch("bootstrap", inputs, "float64", "cpu")
    # float64 精度下 1.0 + 2**-30 不等于 1.0
    assert cand["mean_of_means"] != 1.0
    assert abs(cand["mean_of_means"] - (1.0 + 2**-30)) < 1e-15


def test_c03_cupy_monte_carlo_code_inspection():
    import inspect
    src = inspect.getsource(wp._candidate_cupy)
    assert "2.0 * rng.uniform" not in src, "C03: uniform(-1, 1) 不得再乘以 2.0"


def test_c04_time_call_executes_requested_warmup():
    import admission as ad
    calls = 0

    def f():
        nonlocal calls
        calls += 1

    ad.time_call(f, warmup=5, repeat=3)
    # 1 次 startup + 4 次额外 warmup + 3 次 repeat = 8 次
    assert calls == 8


def test_c05_fft_float32_uses_complex64():
    inp32 = wp.make_input("fft", "small", "float32")
    assert inp32["x"].dtype == np.complex64
    inp64 = wp.make_input("fft", "small", "float64")
    assert inp64["x"].dtype == np.complex128


def test_c07_process_affinity_safe_on_all_platforms():
    res = hp._process_affinity_count()
    assert res == hp.UNKNOWN or isinstance(res, int)


def test_c08_cupy_probe_requires_device(monkeypatch):
    class FakeCupyNoDevice:
        class cuda:
            @staticmethod
            def is_available():
                return False

    monkeypatch.setitem(sys.modules, "cupy", FakeCupyNoDevice)
    probe = be._probe_cupy_cuda()
    assert probe["executable"] is False


def test_c09_admission_handles_timing_exception_gracefully(monkeypatch):
    import admission as ad
    inputs = wp.make_input("matmul_eig", "small", "float64")
    # 模拟候选执行正常，但在 time_call 阶段崩溃
    orig_time_call = ad.time_call
    called = 0

    def failing_time_call(fn, warmup=2, repeat=5):
        nonlocal called
        called += 1
        if called > 1:  # 第一次是 ref_timing
            raise RuntimeError("CUDA out of memory in timing")
        return orig_time_call(fn, warmup=warmup, repeat=repeat)

    monkeypatch.setattr(ad, "time_call", failing_time_call)
    receipt = ad.run_admission("matmul_eig", "small", dtype="float64", warmup=1, repeat=1)
    for c in receipt["candidates"]:
        assert c["verdict"] == "REFERENCE"
        assert "timing_failed" in c["fallback_reason"]
