# -*- coding: utf-8 -*-
"""Paired benchmark and evidence-based admission.

For one workload + scale + dtype: run the reference, then every executable
candidate backend, with warmup and repeated timing, numeric parity check,
dtype gate and a mechanical material-gain gate. The verdict is ADMITTED
only when parity passes AND the candidate's steady-state time beats the
reference by at least the gain threshold. Everything else is REFERENCE
with a recorded fallback reason. No scores are synthesized.
"""

import statistics
import time

import backends as be
import compute_receipt as cr
import workload_profiles as wp


def time_call(fn, warmup=2, repeat=5):
    """startup = first-call wall time; warmup iterations (C04); steady = median of repeats."""
    start = time.perf_counter()
    fn()
    startup = time.perf_counter() - start
    for _ in range(max(0, warmup - 1)):
        fn()
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return {"startup": startup, "median": statistics.median(times),
            "times": times}


def measure_transfer(backend, inputs, dtype):
    """CPU->device copy wall time for accelerator backends (C05 / C11)."""
    if backend in ("torch_cuda", "torch_mps"):
        import torch
        import numpy as np
        device = "cuda" if backend == "torch_cuda" else "mps"
        t0 = time.perf_counter()
        transferred = 0
        for val in inputs.values():
            if isinstance(val, np.ndarray):
                if np.iscomplexobj(val):
                    c_t = torch.complex64 if dtype == "float32" else torch.complex128
                    torch.tensor(val, dtype=c_t, device=device)
                else:
                    r_t = torch.float32 if dtype == "float32" else torch.float64
                    torch.tensor(val, dtype=r_t, device=device)
                transferred += 1
        if transferred == 0:
            return None
        if device == "cuda" and torch.cuda.is_available():
            torch.cuda.synchronize()
        return time.perf_counter() - t0
    return None


def measure_vram_delta(backend, fn):
    if backend != "torch_cuda":
        return None
    try:
        import torch
        torch.cuda.reset_peak_memory_stats()
        before = torch.cuda.max_memory_allocated()
        fn()
        after = torch.cuda.max_memory_allocated()
        return int(after - before)
    except Exception:
        return None


def run_admission(workload, scale, dtype="float64", gain_threshold=1.5,
                  warmup=2, repeat=5, seed=0):
    inputs = wp.make_input(workload, scale, dtype, seed=seed)
    ref_result = wp.reference(workload, inputs)

    ref_timing = time_call(lambda: wp.reference(workload, inputs),
                           warmup=warmup, repeat=repeat)

    candidates = []
    for name in be.select_candidates(dtype):
        if name in ("numpy_cpu", "scipy_cpu"):
            continue  # reference side; cross-library CPU comparison is separate
        spec = be.BACKENDS[name]
        try:
            cand_result = wp.candidate(workload, name, inputs, dtype)
        except Exception as exc:  # noqa: BLE001
            candidates.append({
                "backend": name,
                "device": spec.device_name(),
                "kind": spec.kind,
                "dtype": dtype,
                "verdict": "REFERENCE",
                "fallback_reason": f"execution_failed: {type(exc).__name__}: {exc}",
            })
            continue

        parity_ok = wp.check_parity(workload, scale, ref_result, cand_result)
        if not parity_ok:
            candidates.append({
                "backend": name,
                "device": spec.device_name(),
                "kind": spec.kind,
                "dtype": dtype,
                "verdict": "REFERENCE",
                "fallback_reason": "parity_failed",
            })
            continue

        try:
            cand_timing = time_call(
                lambda: wp.candidate(workload, name, inputs, dtype),
                warmup=warmup, repeat=repeat)
            transfer = measure_transfer(name, inputs, dtype)
            vram = measure_vram_delta(
                name, lambda: wp.candidate(workload, name, inputs, dtype))
        except Exception as exc:  # C09: 计时与测量异常受控降级为 REFERENCE
            candidates.append({
                "backend": name,
                "device": spec.device_name(),
                "kind": spec.kind,
                "dtype": dtype,
                "verdict": "REFERENCE",
                "fallback_reason": f"timing_failed: {type(exc).__name__}: {exc}",
            })
            continue

        speedup = ref_timing["median"] / max(cand_timing["median"], 1e-12)
        if speedup >= gain_threshold:
            verdict = "ADMITTED"
            reason = None
        else:
            verdict = "REFERENCE"
            reason = "no_material_gain"
        candidates.append({
            "backend": name,
            "device": spec.device_name(),
            "kind": spec.kind,
            "dtype": dtype,
            "verdict": verdict,
            "fallback_reason": reason,
            "speedup_vs_reference": round(speedup, 4),
            "timing": cand_timing,
            "transfer_seconds": transfer,
            "vram_delta_bytes": vram,
        })

    return cr.build_receipt(
        workload=workload,
        scale=scale,
        dtype=dtype,
        gain_threshold=gain_threshold,
        warmup=warmup,
        repeat=repeat,
        seed=seed,
        ref_timing=ref_timing,
        candidates=candidates,
    )


def run_matrix(workloads=None, scales=("small", "medium", "large"),
               dtype="float64", gain_threshold=1.5):
    rows = []
    for workload in (workloads or list(wp.SCALES)):
        for scale in scales:
            receipt = run_admission(workload, scale, dtype=dtype,
                                    gain_threshold=gain_threshold)
            rows.append(receipt)
    return rows


if __name__ == "__main__":
    import json
    rows = run_matrix()
    print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
