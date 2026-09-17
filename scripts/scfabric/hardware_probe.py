# -*- coding: utf-8 -*-
"""Hardware probe: a thin, optional-dependency, degradation-tolerant subset.

Every probe degrades to "unknown" or "not_available" instead of raising, so
the probe can run on CI runners, containers, phones and offline machines.
The probe reports what is observable; it never claims kernel dispatch.
"""

import ctypes
import importlib.util
import os
import platform
import sys
from pathlib import Path

UNKNOWN = "unknown"
NOT_AVAILABLE = "not_available"


def _has(module):
    return importlib.util.find_spec(module) is not None


def _sysconf_ram_bytes():
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        return page * pages
    except (ValueError, OSError):
        return UNKNOWN


def _windows_ram_bytes():
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


def _process_affinity_count():
    try:
        aff = os.process_cpu_affinity()
        return len(aff)
    except (AttributeError, OSError):
        return UNKNOWN


def _cgroup_cpu_quota():
    if sys.platform != "linux":
        return UNKNOWN
    try:
        root = Path("/sys/fs/cgroup")
        if (root / "cpu.max").exists():
            parts = (root / "cpu.max").read_text().strip().split()
            if len(parts) == 2 and parts[0] != "max":
                quota = float(parts[0])
                period = float(parts[1])
                return quota / period if period > 0 else UNKNOWN
        if (root / "cpu" / "cpu.cfs_quota_us").exists():
            quota = float((root / "cpu" / "cpu.cfs_quota_us").read_text().strip())
            period = float((root / "cpu" / "cpu.cfs_period_us").read_text().strip())
            if quota > 0 and period > 0:
                return quota / period
        return NOT_AVAILABLE
    except (OSError, ValueError):
        return UNKNOWN


def _torch_isa():
    try:
        import torch  # noqa: PLC0415
        return torch.backends.cpu.get_cpu_capability() or UNKNOWN
    except Exception:  # noqa: BLE001
        return UNKNOWN


def _accelerators():
    out = []
    if _has("torch"):
        try:
            import torch  # noqa: PLC0415
            if torch.cuda.is_available():
                out.append({
                    "kind": "cuda",
                    "available": True,
                    "device_name": torch.cuda.get_device_name(0),
                    "device_count": torch.cuda.device_count(),
                })
            else:
                out.append({"kind": "cuda", "available": False})
            mps = getattr(torch.backends, "mps", None)
            if mps is not None:
                try:
                    out.append({"kind": "mps", "available": bool(mps.is_available())})
                except Exception:  # noqa: BLE001
                    out.append({"kind": "mps", "available": False})
            xpu = getattr(torch, "xpu", None)
            if xpu is not None:
                try:
                    out.append({"kind": "xpu", "available": bool(xpu.is_available())})
                except Exception:  # noqa: BLE001
                    out.append({"kind": "xpu", "available": False})
        except Exception:  # noqa: BLE001
            out.append({"kind": "torch_accelerators", "available": UNKNOWN})
    else:
        out.append({"kind": "torch_accelerators", "available": NOT_AVAILABLE})
    if _has("cupy"):
        out.append({"kind": "cupy", "available": True})
    else:
        out.append({"kind": "cupy", "available": NOT_AVAILABLE})
    return out


def probe():
    """Return a hardware fingerprint dict. All fields degrade gracefully."""
    return {
        "os": platform.system(),
        "architecture": platform.machine(),
        "cpu_model": platform.processor() or UNKNOWN,
        "python": platform.python_version(),
        "os_visible_cpus": os.cpu_count() or UNKNOWN,
        "process_affinity_cpus": _process_affinity_count(),
        "cgroup_cpu_quota": _cgroup_cpu_quota(),
        "ram_total_bytes": (_windows_ram_bytes() if sys.platform == "win32"
                            else _sysconf_ram_bytes()),
        "isa_hint": _torch_isa(),
        "accelerators": _accelerators(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(probe(), ensure_ascii=False, indent=2))
