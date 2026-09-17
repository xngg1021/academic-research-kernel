# -*- coding: utf-8 -*-
"""ComputeReceipt: the evidence layer of the scientific compute fabric.

The receipt records what was measured and what failed, never an inferred
conclusion. Fields: hardware fingerprint, backend identity, library
versions, dtype, device, thread count, timing, transfer, VRAM delta,
parity outcome, verdict and fallback reason. A receipt with no accelerator
simply records that fact; it does not reason about why.
"""

import os
import platform
from datetime import datetime, timezone

import hardware_probe as hp

PROTOCOL = "compute-receipt-1.0"


def _thread_fingerprint():
    """采集当前进程关联的 BLAS 与 PyTorch 线程数指纹。"""
    out = {
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
    }
    try:
        import torch
        out["torch_num_threads"] = torch.get_num_threads()
    except Exception:
        pass
    return out


def _lib_versions():
    out = {}
    for mod in ("numpy", "scipy", "torch", "cupy"):
        try:
            m = __import__(mod)
            out[mod] = getattr(m, "__version__", "unknown")
        except Exception:  # noqa: BLE001
            out[mod] = "not_available"
    return out


def build_receipt(workload, scale, dtype, gain_threshold, warmup, repeat,
                  seed, ref_timing, candidates):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "protocol": PROTOCOL,
        "timestamp": now,
        "hardware": hp.probe(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "libraries": _lib_versions(),
            "threads": _thread_fingerprint(),
        },
        "operation": workload,
        "scale": scale,
        "dtype": dtype,
        "gain_threshold": gain_threshold,
        "benchmark_parameters": {"warmup": warmup, "repeat": repeat, "seed": seed},
        "reference": {
            "backend": "numpy_cpu",
            "timing": ref_timing,
        },
        "candidates": candidates,
        "admitted_backends": [
            c["backend"] for c in candidates if c.get("verdict") == "ADMITTED"
        ],
        "fallback_backends": [
            {"backend": c["backend"], "reason": c.get("fallback_reason")}
            for c in candidates if c.get("verdict") == "REFERENCE"
        ],
    }


def receipt_headline(receipt):
    """One-line summary for humans; contains no synthesized score."""
    parts = [f"{receipt['operation']}/{receipt['scale']}/{receipt['dtype']}"]
    parts.append("ref " + receipt["reference"]["backend"])
    for c in receipt["candidates"]:
        if c.get("verdict") == "ADMITTED":
            parts.append(f"ADMITTED {c['backend']} x{c.get('speedup_vs_reference')}")
        else:
            parts.append(f"REF {c['backend']} ({c.get('fallback_reason')})")
    return " | ".join(parts)
