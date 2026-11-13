"""论文配套 GitHub 代码仓库结构核验工具：按路径启发式区分自研核心代码、拷入第三方库与单元测试密度。

支持三种模式：
1. --local-repo / --repo-dir <dir>：扫描本地代码仓库目录（若存在 .git 则优先通过 git ls-files 仅统计受跟踪文件）
2. --tree-json <file>：解析已保存的 GitHub git/trees?recursive=1 JSON
3. --github-repo <owner/repo>：调用本地 gh api 获取远端目录树
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

UNCONDITIONAL_VENDORED_DIRS = {
    "third_party", "3rdparty", "vendor", "vendored", "external", "externals",
    "baselines", "memory_toolkits", "node_modules", "site-packages",
}
NESTED_VENDORED_PACKAGES = {"vendor_pkg", "bundled_lib", "copied_sdk", "ext_toolkit"}
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "build", "dist", ".egg-info", "node_modules", "site-packages",
}
TEST_MARKERS = {"test", "tests", "testing"}
EXAMPLE_MARKERS = {"example", "examples", "demo", "demos", "notebooks", "experiments", "benchmark", "benchmarks"}
REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _is_excluded_part(part: str) -> bool:
    low = part.lower()
    return low in EXCLUDED_DIRS or low.endswith(".egg-info")


def classify_py_path(rel_posix: str, sole_top_pkg: str | None = None) -> str:
    parts = [p.lower() for p in PurePosixPath(rel_posix).parts]
    if not parts or any(_is_excluded_part(p) for p in parts):
        return "excluded"
    fname = parts[-1]
    dir_parts = parts[:-1]
    if any(p in UNCONDITIONAL_VENDORED_DIRS for p in dir_parts):
        return "vendored_or_third_party"
    # Nested third-party memory packages (unless it is the repository's own sole top-level package)
    for idx, p in enumerate(dir_parts):
        if p in NESTED_VENDORED_PACKAGES:
            if idx == 0 and sole_top_pkg and p == sole_top_pkg.lower():
                continue
            if idx == 1 and dir_parts[0] == "src" and sole_top_pkg and p == sole_top_pkg.lower():
                continue
            return "vendored_or_third_party"
    if any(p in TEST_MARKERS for p in dir_parts):
        return "unit_tests"
    if any(p in EXAMPLE_MARKERS for p in dir_parts):
        return "examples_or_experiments"
    if fname.startswith("test_") or fname.endswith("_test.py") or fname == "conftest.py":
        return "unit_tests"
    return "first_party_core"


def analyze_entries(entries: list[dict], truncated: bool = False) -> dict:
    """entries: list of {'path': posix_str, 'size': int}."""
    if not isinstance(entries, list):
        raise ValueError("entries must be a list of file objects")
    buckets = {
        "first_party_core": {"file_count": 0, "bytes": 0, "files": []},
        "vendored_or_third_party": {"file_count": 0, "bytes": 0, "files": []},
        "unit_tests": {"file_count": 0, "bytes": 0, "files": []},
        "examples_or_experiments": {"file_count": 0, "bytes": 0, "files": []},
    }
    # Detect whether the repository has a single top-level Python package (e.g. mypkg/ or src/mypkg/)
    top_pkgs = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        p_str = str(item.get("path", "")).replace("\\", "/").strip("/")
        if not p_str.endswith(".py"):
            continue
        ps = [p.lower() for p in PurePosixPath(p_str).parts]
        if len(ps) >= 2 and ps[0] not in TEST_MARKERS and ps[0] not in EXAMPLE_MARKERS and ps[0] not in UNCONDITIONAL_VENDORED_DIRS:
            if ps[0] == "src" and len(ps) >= 3:
                top_pkgs.add(ps[1])
            else:
                top_pkgs.add(ps[0])
    sole_top_pkg = next(iter(top_pkgs)) if len(top_pkgs) == 1 else None

    total_blobs = 0
    total_py = 0
    seen_paths = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        path_str = str(item.get("path", "")).replace("\\", "/").strip("/")
        if not path_str or path_str in seen_paths:
            continue
        raw_size = item.get("size", 0)
        if isinstance(raw_size, bool) or not isinstance(raw_size, int) or raw_size < 0:
            raise ValueError(f"Invalid file size for {path_str!r}: {raw_size!r}")
        size = int(raw_size)
        parts = [p.lower() for p in PurePosixPath(path_str).parts]
        if any(_is_excluded_part(p) for p in parts):
            continue
        seen_paths.add(path_str)
        total_blobs += 1
        if not path_str.endswith(".py"):
            continue
        cat = classify_py_path(path_str, sole_top_pkg=sole_top_pkg)
        if cat == "excluded":
            continue
        total_py += 1
        b = buckets[cat]
        b["file_count"] += 1
        b["bytes"] += size
        if len(b["files"]) < 25:
            b["files"].append({"path": path_str, "bytes": size})

    core_bytes = buckets["first_party_core"]["bytes"]
    vend_bytes = buckets["vendored_or_third_party"]["bytes"]
    test_bytes = buckets["unit_tests"]["bytes"]
    all_py_bytes = sum(v["bytes"] for v in buckets.values())

    return {
        "classification_method": "path_heuristic",
        "truncated": bool(truncated),
        "total_tracked_files": total_blobs,
        "total_python_files": total_py,
        "total_python_bytes": all_py_bytes,
        "estimated_total_python_lines": all_py_bytes // 38,
        "first_party_core": {
            "file_count": buckets["first_party_core"]["file_count"],
            "bytes": core_bytes,
            "estimated_lines": core_bytes // 38,
            "sample_files": buckets["first_party_core"]["files"],
        },
        "vendored_or_third_party": {
            "file_count": buckets["vendored_or_third_party"]["file_count"],
            "bytes": vend_bytes,
            "estimated_lines": vend_bytes // 38,
            "share_of_python_bytes": float(vend_bytes / all_py_bytes) if all_py_bytes > 0 else 0.0,
            "sample_files": buckets["vendored_or_third_party"]["files"],
        },
        "unit_tests": {
            "file_count": buckets["unit_tests"]["file_count"],
            "bytes": test_bytes,
            "estimated_lines": test_bytes // 38,
            "test_to_core_byte_ratio": float(test_bytes / core_bytes) if core_bytes > 0 else None,
            "sample_files": buckets["unit_tests"]["files"],
        },
        "examples_or_experiments": {
            "file_count": buckets["examples_or_experiments"]["file_count"],
            "bytes": buckets["examples_or_experiments"]["bytes"],
            "estimated_lines": buckets["examples_or_experiments"]["bytes"] // 38,
        },
    }


def scan_local_repo(root: Path) -> list[dict]:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Local repository directory does not exist: {root}")
    root = root.resolve()
    if (root / ".git").exists():
        try:
            r = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z"],
                capture_output=True,
                check=True,
                timeout=15,
            )
            rel_paths = [p.decode("utf-8", errors="replace") for p in r.stdout.split(b"\x00") if p]
            if rel_paths:
                entries = []
                for rel in sorted(rel_paths):
                    full_p = root / rel
                    if full_p.is_symlink() or not full_p.is_file():
                        continue
                    entries.append({"path": rel.replace("\\", "/"), "size": full_p.stat().st_size})
                return entries
        except Exception:
            pass

    entries = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not _is_excluded_part(d))
        rel_dir = Path(dirpath).relative_to(root)
        for fn in sorted(filenames):
            if _is_excluded_part(fn):
                continue
            full_p = Path(dirpath) / fn
            if full_p.is_symlink() or not full_p.is_file():
                continue
            rel_posix = (rel_dir / fn).as_posix() if rel_dir.parts else fn
            entries.append({"path": rel_posix, "size": full_p.stat().st_size})
    return entries
