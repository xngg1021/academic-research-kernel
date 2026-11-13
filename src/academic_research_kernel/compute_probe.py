"""Degradation-tolerant hardware capability probe and deterministic ComputeReceipt builder.

Produces structured environment diagnostics and `compute-receipt-1.0` records compliant with
`schemas/compute-receipt.schema.json` without claiming unmeasured kernel dispatch.
"""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Optional

PROTOCOL = "compute-receipt-1.0"
UNKNOWN = "unknown"
NOT_AVAILABLE = "not_available"


def _has(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def _sysconf_ram_bytes() -> int | str:
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        return int(page * pages)
    except (AttributeError, ValueError, OSError):
        return UNKNOWN


def _windows_ram_bytes() -> int | str:
    if sys.platform != "win32":
        return UNKNOWN
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys)
    except (AttributeError, OSError):
        pass
    return UNKNOWN


def _darwin_ram_bytes() -> int | str:
    if sys.platform != "darwin":
        return UNKNOWN
    try:
        import subprocess

        r = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=3, check=False)
        if r.returncode == 0 and r.stdout.strip().isdigit():
            return int(r.stdout.strip())
    except Exception:
        pass
    return _sysconf_ram_bytes()


def _process_affinity_count() -> int | str:
    try:
        if hasattr(os, "sched_getaffinity"):
            return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        pass
    return UNKNOWN


def _cgroup_cpu_quota(proc_cgroup_path: Path = Path("/proc/self/cgroup"), cgroup_root: Path = Path("/sys/fs/cgroup")) -> float | str:
    if sys.platform != "linux" and proc_cgroup_path == Path("/proc/self/cgroup"):
        return UNKNOWN
    try:
        quotas: list[float] = []
        saw_cgroup_files = False
        subpaths_v2: list[str] = [""]
        subpaths_v1: list[str] = [""]
        if proc_cgroup_path.is_file():
            for line in proc_cgroup_path.read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.strip().split(":", 2)
                if len(parts) != 3:
                    continue
                _, controllers, rel = parts
                rel_clean = rel.lstrip("/")
                if controllers == "":
                    cur = Path(rel_clean)
                    while str(cur) not in ("", "."):
                        subpaths_v2.append(cur.as_posix())
                        cur = cur.parent
                elif "cpu" in controllers.split(","):
                    cur = Path(rel_clean)
                    while str(cur) not in ("", "."):
                        subpaths_v1.append(cur.as_posix())
                        cur = cur.parent

        for sub in dict.fromkeys(subpaths_v2):
            p_max = (cgroup_root / sub / "cpu.max") if sub else (cgroup_root / "cpu.max")
            if p_max.is_file():
                saw_cgroup_files = True
                toks = p_max.read_text(encoding="utf-8").strip().split()
                if len(toks) == 2 and toks[0] != "max":
                    q, per = float(toks[0]), float(toks[1])
                    if q > 0 and per > 0:
                        quotas.append(q / per)

        for sub in dict.fromkeys(subpaths_v1):
            base_v1 = (cgroup_root / "cpu" / sub) if sub else (cgroup_root / "cpu")
            q_p = base_v1 / "cpu.cfs_quota_us"
            per_p = base_v1 / "cpu.cfs_period_us"
            if q_p.is_file() and per_p.is_file():
                saw_cgroup_files = True
                q = float(q_p.read_text(encoding="utf-8").strip())
                per = float(per_p.read_text(encoding="utf-8").strip())
                if q > 0 and per > 0:
                    quotas.append(q / per)

        if quotas:
            return min(quotas)
        return NOT_AVAILABLE if saw_cgroup_files or cgroup_root.exists() else UNKNOWN
    except (OSError, ValueError):
        return UNKNOWN


def _accelerators() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if _has("torch"):
        try:
            import torch  # type: ignore[import-not-found]

            if torch.cuda.is_available():
                is_rocm = bool(getattr(torch.version, "hip", None))
                kind = "rocm" if is_rocm else "cuda"
                out.append({
                    "kind": kind,
                    "runtime": kind,
                    "available": True,
                    "device_name": torch.cuda.get_device_name(0),
                    "device_count": int(torch.cuda.device_count()),
                })
            else:
                out.append({"kind": "cuda", "available": False})
            mps = getattr(torch.backends, "mps", None)
            if mps is not None:
                out.append({"kind": "mps", "available": bool(mps.is_available())})
        except Exception:
            out.append({"kind": "torch_accelerators", "available": UNKNOWN})
    else:
        out.append({"kind": "torch_accelerators", "available": NOT_AVAILABLE})
    if _has("cupy"):
        try:
            import cupy  # type: ignore[import-not-found]

            dev_cnt = int(cupy.cuda.runtime.getDeviceCount())
            out.append({"kind": "cupy", "available": dev_cnt > 0, "device_count": dev_cnt})
        except Exception:
            out.append({"kind": "cupy", "available": False})
    else:
        out.append({"kind": "cupy", "available": NOT_AVAILABLE})
    return out


def _library_versions() -> dict[str, str]:
    libs: dict[str, str] = {}
    for mod_name in ("numpy", "scipy", "statsmodels", "sympy", "mpmath", "pandas", "networkx", "torch", "cupy"):
        if not _has(mod_name):
            libs[mod_name] = NOT_AVAILABLE
            continue
        try:
            from importlib import metadata

            libs[mod_name] = metadata.version(mod_name)
        except Exception:
            libs[mod_name] = "available"
    return libs


def _thread_fingerprint() -> dict[str, Any]:
    return {
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
        "numexpr_max_threads": os.environ.get("NUMEXPR_MAX_THREADS"),
    }


def probe() -> dict[str, Any]:
    """Return a degradation-tolerant hardware and numerical library fingerprint."""
    if sys.platform == "win32":
        ram = _windows_ram_bytes()
    elif sys.platform == "darwin":
        ram = _darwin_ram_bytes()
    else:
        ram = _sysconf_ram_bytes()

    isa = UNKNOWN
    if _has("numpy"):
        try:
            import numpy as np

            show_cfg = getattr(np, "__config__", None)
            if show_cfg is not None and hasattr(show_cfg, "show"):
                isa = platform.machine() or UNKNOWN
        except Exception:
            pass

    return {
        "os": platform.system(),
        "architecture": platform.machine(),
        "cpu_model": platform.processor() or UNKNOWN,
        "python": platform.python_version(),
        "os_visible_cpus": os.cpu_count() or UNKNOWN,
        "process_affinity_cpus": _process_affinity_count(),
        "cgroup_cpu_quota": _cgroup_cpu_quota(),
        "ram_total_bytes": ram,
        "isa_hint": isa,
        "accelerators": _accelerators(),
        "libraries": _library_versions(),
        "threads": _thread_fingerprint(),
    }


def build_compute_receipt(
    *,
    operation: str = "matmul_f64",
    scale: str = "small",
    dtype: str = "float64",
    gain_threshold: float = 1.25,
    warmup: int = 1,
    repeat: int = 3,
    seed: int = 42,
    candidates: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Execute a bounded NumPy reference timing probe and emit a schema-valid ComputeReceipt."""
    allowed_ops = ("matmul_f64", "matmul_f32", "dot", "svd", "svd_f64", "fft_1d")
    if operation not in allowed_ops:
        raise ValueError(f"Unsupported operation {operation!r}; allowed={list(allowed_ops)}")
    if scale not in ("small", "medium", "large"):
        raise ValueError(f"Invalid scale {scale!r}; expected small, medium, or large")
    if dtype not in ("float32", "float64"):
        raise ValueError(f"Invalid dtype {dtype!r}; expected float32 or float64")

    import numpy as np

    dim = {"small": 64, "medium": 192, "large": 384}[scale]
    np_dtype = np.float32 if (dtype == "float32" or operation == "matmul_f32") else np.float64
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((dim, dim)).astype(np_dtype)
    b = rng.standard_normal((dim, dim)).astype(np_dtype)

    def _exec_op() -> Any:
        if operation in ("matmul_f64", "matmul_f32"):
            return a @ b
        if operation == "dot":
            return float(np.dot(a.ravel(), b.ravel()))
        if operation in ("svd", "svd_f64"):
            return np.linalg.svd(a, compute_uv=False)
        return np.fft.rfft(a.ravel())

    t_start0 = time.perf_counter()
    for _ in range(max(1, warmup)):
        _ = _exec_op()
    startup = round(time.perf_counter() - t_start0, 6)

    times: list[float] = []
    for _ in range(max(1, repeat)):
        t0 = time.perf_counter()
        _ = _exec_op()
        times.append(round(time.perf_counter() - t0, 6))

    hw = probe()
    hw_schema = {
        k: hw[k]
        for k in (
            "os",
            "architecture",
            "cpu_model",
            "python",
            "os_visible_cpus",
            "process_affinity_cpus",
            "cgroup_cpu_quota",
            "ram_total_bytes",
            "isa_hint",
            "accelerators",
        )
    }
    cand_list = list(candidates or [])
    return {
        "protocol": PROTOCOL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hardware": hw_schema,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "libraries": hw["libraries"],
            "threads": hw["threads"],
        },
        "operation": operation,
        "scale": scale,
        "dtype": dtype,
        "gain_threshold": float(gain_threshold),
        "benchmark_parameters": {"warmup": int(warmup), "repeat": int(repeat), "seed": int(seed)},
        "reference": {
            "backend": "numpy_cpu",
            "timing": {
                "startup": startup,
                "median": round(float(statistics.median(times)), 6),
                "times": times,
            },
        },
        "candidates": cand_list,
        "admitted_backends": [c["backend"] for c in cand_list if c.get("verdict") == "ADMITTED"],
        "fallback_backends": [
            {"backend": c["backend"], "reason": c.get("fallback_reason")}
            for c in cand_list
            if c.get("verdict") == "REFERENCE"
        ],
    }
