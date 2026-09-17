# -*- coding: utf-8 -*-
"""Backend catalog: capability discovery, dispatch and data transfer as
separate concerns, mirroring THM's provider contract in miniature.

A backend spec declares what it SUPPORTS (declared), what is actually
EXECUTABLE right now (probed), and what has a receipt (measured). Support
claims alone never admit a backend.
"""

import importlib.util


class BackendSpec:
    def __init__(self, name, kind, dtypes, description, probe_fn):
        self.name = name
        self.kind = kind  # "cpu" or "accelerator"
        self.declared_dtypes = tuple(dtypes)
        self.description = description
        self._probe_fn = probe_fn
        self._cache = None

    def probe(self):
        """Lazy capability probe; results are cached per process."""
        if self._cache is None:
            self._cache = self._probe_fn()
        return self._cache

    def executable(self):
        return self.probe().get("executable", False)

    def supports_dtype(self, dtype):
        return dtype in self.declared_dtypes

    def device_name(self):
        return self.probe().get("device_name", None)


def _probe_numpy_cpu():
    return {"executable": importlib.util.find_spec("numpy") is not None}


def _probe_scipy_cpu():
    return {"executable": importlib.util.find_spec("scipy") is not None}


def _probe_torch_cpu():
    try:
        import torch
        return {"executable": True, "device_name": "cpu",
                "version": torch.__version__}
    except Exception:
        return {"executable": False}


def _probe_torch_cuda():
    try:
        import torch
        if not torch.cuda.is_available():
            return {"executable": False, "reason": "torch.cuda.is_available() == False"}
        is_rocm = bool(getattr(torch.version, "hip", None))
        runtime = "rocm" if is_rocm else "cuda"
        return {
            "executable": True,
            "device_name": torch.cuda.get_device_name(0),
            "version": torch.__version__,
            "runtime": runtime,
            "hip_version": getattr(torch.version, "hip", None),
        }
    except Exception as exc:
        return {"executable": False, "reason": str(exc)}


def _probe_torch_xpu():
    try:
        import torch
        xpu = getattr(torch, "xpu", None)
        if xpu is None or not xpu.is_available():
            return {"executable": False, "reason": "torch.xpu.is_available() == False"}
        dev_name = xpu.get_device_name(0) if hasattr(xpu, "get_device_name") else "Intel XPU"
        return {
            "executable": True,
            "device_name": dev_name,
            "version": torch.__version__,
            "runtime": "xpu",
        }
    except Exception as exc:
        return {"executable": False, "reason": str(exc)}


def _probe_torch_mps():
    try:
        import torch
        mps = getattr(torch.backends, "mps", None)
        if mps is None or not mps.is_available():
            return {"executable": False, "reason": "MPS backend unavailable"}
        return {"executable": True, "device_name": "mps",
                "version": torch.__version__}
    except Exception as exc:
        return {"executable": False, "reason": str(exc)}


def _probe_cupy_cuda():
    try:
        import cupy as cp
        if not hasattr(cp, "cuda") or not cp.cuda.is_available():
            return {"executable": False, "reason": "cupy.cuda.is_available() == False"}
        count = cp.cuda.runtime.getDeviceCount()
        if count <= 0:
            return {"executable": False, "reason": "no CUDA devices found"}
        dev_name = cp.cuda.runtime.getDeviceProperties(0)["name"].decode("utf-8", errors="replace")
        return {"executable": True, "device_name": dev_name}
    except Exception as exc:
        return {"executable": False, "reason": str(exc)}


BACKENDS = {
    "numpy_cpu": BackendSpec(
        "numpy_cpu", "cpu", ("float32", "float64", "complex64", "complex128"),
        "NumPy on CPU; already linked against an optimized BLAS on common wheels",
        _probe_numpy_cpu),
    "scipy_cpu": BackendSpec(
        "scipy_cpu", "cpu", ("float32", "float64", "complex64", "complex128"),
        "SciPy on CPU; solvers and transforms are CPU-centric in current releases",
        _probe_scipy_cpu),
    "torch_cpu": BackendSpec(
        "torch_cpu", "cpu", ("float32", "float64", "complex64", "complex128"),
        "PyTorch on CPU with its thread pool",
        _probe_torch_cpu),
    "torch_cuda": BackendSpec(
        "torch_cuda", "accelerator", ("float32", "float64", "complex64", "complex128"),
        "PyTorch CUDA; float64 support exists but many consumer GPUs throttle FP64",
        _probe_torch_cuda),
    "torch_mps": BackendSpec(
        "torch_mps", "accelerator", ("float32", "float16", "bfloat16"),
        "PyTorch MPS; no float64 or complex128 support, so double-precision "
        "workloads must stay on CPU",
        _probe_torch_mps),
    "cupy_cuda": BackendSpec(
        "cupy_cuda", "accelerator", ("float32", "float64", "complex64", "complex128"),
        "CuPy on CUDA when installed",
        _probe_cupy_cuda),
    "torch_xpu": BackendSpec(
        "torch_xpu", "accelerator", ("float32", "float16", "bfloat16"),
        "PyTorch on Intel XPU when installed",
        _probe_torch_xpu),
}


def executable_backends():
    """Backends whose probe says executable right now."""
    return [name for name, spec in BACKENDS.items() if spec.executable()]


def select_candidates(workload_dtype):
    """Backends that declare support for the workload dtype and are
    executable. dtype semantics come before device availability."""
    out = []
    for name, spec in BACKENDS.items():
        if not spec.supports_dtype(workload_dtype):
            continue
        if not spec.executable():
            continue
        out.append(name)
    return out


def dtype_support_report(workload_dtype):
    rows = []
    for name, spec in BACKENDS.items():
        rows.append({
            "backend": name,
            "declared_support": spec.supports_dtype(workload_dtype),
            "executable": spec.executable(),
        })
    return rows
