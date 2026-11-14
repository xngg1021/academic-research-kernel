---
name: compute-math
description: "Probe compute hardware and route scientific math tasks."
version: 3.0.0
author: Junfu Shi (SJF, xngg1021)
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, math, symbolic, scipy, sympy, statsmodels, compute-receipt]
    related_skills: [audit-paper, meta-analysis]
---

# Scientific Computation & Hardware Probe (`compute-math`)

Degradation-tolerant hardware/library capability probing, schema-validated `ComputeReceipt` benchmarking (`compute-receipt-1.0`), and multi-domain scientific computation routing via `academic-research-kernel` (`3.0.0`). Consolidates `math-computation` and `scfabric` probe/receipt contracts.

## When to Use

- Probing observable CPU/GPU hardware, OS process affinity, Linux cgroup quotas, RAM bytes, BLAS/OMP thread environment variables, and installed versions of `numpy`, `scipy`, `statsmodels`, `sympy`, `mpmath`, `pandas`, `networkx`, and `torch` (`compute-probe`).
- Emitting a deterministic `compute-receipt-1.0` JSON artifact (`compute-probe --receipt`) recording actual startup/median reference timings without claiming unmeasured accelerator speedups.
- Routing symbolic algebra (`sympy`), numerical integration/optimization/ODE/FFT (`scipy`/`numpy`), arbitrary-precision arithmetic (`mpmath`), econometric/biostatistical modeling (`statsmodels`), graph algorithms (`networkx`), and headless plotting (`matplotlib.use("Agg")`; see `references/domain-recipes.md`).

## Quick CLI Commands

```bash
# 1. Probe CPU/GPU accelerators, RAM, thread env vars, and installed scientific Python packages
academic-research-kernel compute-probe

# 2. Emit a schema-validated compute-receipt-1.0 JSON record
academic-research-kernel compute-probe --receipt --operation matmul_f64 --scale small --dtype float64 --output ./compute-receipt.json
```

## MCP Tools

- `academic_scfabric_hardware_probe` (alias `academic_compute_probe`)

## Execution Discipline

1. Always verify `sys.executable` before installing or importing optional scientific libraries (`sympy`, `mpmath`, `torch`, `networkx`, `matplotlib`).
2. For headless figures, call `import matplotlib; matplotlib.use("Agg")` before importing ` matplotlib.pyplot`, verify installed CJK fonts before rendering non-ASCII labels, and save outputs explicitly with `fig.savefig(..., dpi=300, bbox_inches="tight")`.
3. Consult `references/domain-recipes.md` for library routing and numerical conditioning checks.
