# -*- coding: utf-8 -*-
"""Five workload profiles for the first-round A/B experiment.

Each profile defines a reference implementation and per-backend candidate
implementations, deterministic inputs from a fixed seed, three scale levels
and a parity contract. Parity is numerical equivalence: element-wise
relative tolerance for deterministic ops (matmul, fft, autodiff), and
statistical tolerance for stochastic ops (monte carlo, bootstrap). A
candidate that cannot meet the parity contract is never admitted, no
matter how fast it is.
"""

import numpy as np

SCALES = {
    "matmul_eig": {"small": 128, "medium": 512, "large": 1024},
    "fft": {"small": 256, "medium": 1024, "large": 2048},
    "monte_carlo": {"small": 10_000, "medium": 1_000_000, "large": 10_000_000},
    "bootstrap": {"small": (200, 1_000), "medium": (1_000, 10_000),
                  "large": (2_000, 50_000)},
    "autodiff": {"small": 1_000, "medium": 10_000, "large": 100_000},
}

PARITY_TOL = {
    # deterministic ops: element-wise relative tolerance, sized by scale
    # because floating-point accumulation error grows with problem size.
    "matmul_eig": {"small": 1e-10, "medium": 5e-10, "large": 2e-9},
    "fft": {"small": 1e-10, "medium": 1e-9, "large": 3e-9},
    "autodiff": {"small": 1e-10, "medium": 1e-10, "large": 1e-10},
    # statistical ops: absolute tolerance for the reported statistics.
    # Different backends draw from different RNG streams; two independent
    # draws of the same distribution must agree within a few standard
    # errors, so the tolerance is set at several SE for the smallest scale.
    "monte_carlo": {"small": 0.05, "medium": 0.02, "large": 0.01},
    "bootstrap": {"small": 0.05, "medium": 0.02, "large": 0.01},
}


def _torch_device(name):
    if name == "torch_cpu":
        return "cpu"
    if name == "torch_cuda":
        return "cuda"
    if name == "torch_mps":
        return "mps"
    raise ValueError(name)


def make_input(workload, scale, dtype, seed=0):
    n = SCALES[workload][scale]
    rng = np.random.default_rng(seed)
    if workload == "matmul_eig":
        a = rng.standard_normal((n, n)).astype(dtype)
        b = rng.standard_normal((n, n)).astype(dtype)
        sym = a + a.T
        return {"a": a, "b": b, "sym": sym}
    if workload == "fft":
        return {"x": (rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n))).astype(np.complex128)}
    if workload == "monte_carlo":
        return {"n": n}
    if workload == "bootstrap":
        resamples, sample_n = SCALES[workload][scale]
        return {"data": rng.standard_normal(sample_n).astype(dtype), "resamples": resamples}
    if workload == "autodiff":
        return {"x": rng.standard_normal(n).astype(dtype)}
    raise ValueError(workload)


# ---------------------------------------------------------------- references

def reference(workload, inputs):
    if workload == "matmul_eig":
        c = inputs["a"] @ inputs["b"]
        w = np.linalg.eigvalsh(inputs["sym"])
        return {"c": c, "eigvals": w}
    if workload == "fft":
        return {"y": np.fft.fft2(inputs["x"])}
    if workload == "monte_carlo":
        rng = np.random.default_rng(0)
        n = inputs["n"]
        u1 = rng.uniform(-1.0, 1.0, n)
        u2 = rng.uniform(-1.0, 1.0, n)
        inside = (u1 ** 2 + u2 ** 2) <= 1.0
        pi_est = 4.0 * inside.mean()
        return {"pi_mean": float(pi_est), "pi_std": float(4.0 * inside.std(ddof=1) / np.sqrt(n))}
    if workload == "bootstrap":
        data = inputs["data"]
        rng = np.random.default_rng(1)
        idx = rng.integers(0, len(data), size=(inputs["resamples"], len(data)))
        means = data[idx].mean(axis=1)
        return {"ci_lo": float(np.quantile(means, 0.025)),
                "ci_hi": float(np.quantile(means, 0.975)),
                "mean_of_means": float(means.mean())}
    if workload == "autodiff":
        x = inputs["x"]
        # loss = 0.5 * mean((x - 0.25)^2); analytic gradient = (x - 0.25) / n
        grad = (x - 0.25) / x.size
        return {"grad": grad}
    raise ValueError(workload)


# --------------------------------------------------------------- candidates

def candidate(workload, backend, inputs, dtype):
    device = _torch_device(backend) if backend.startswith("torch_") else None
    if backend == "cupy_cuda":
        return _candidate_cupy(workload, inputs, dtype)
    if backend.startswith("torch_"):
        import torch
        return _candidate_torch(workload, inputs, dtype, device)
    raise ValueError(backend)


def _candidate_torch(workload, inputs, dtype, device):
    import torch
    t = {"float32": torch.float32, "float64": torch.float64}.get(dtype)
    if t is None:
        raise ValueError(dtype)
    if workload == "matmul_eig":
        a = torch.tensor(inputs["a"], dtype=t, device=device)
        b = torch.tensor(inputs["b"], dtype=t, device=device)
        sym = torch.tensor(inputs["sym"], dtype=t, device=device)
        c = a @ b
        w = torch.linalg.eigvalsh(sym)
        return {"c": c.cpu().numpy(), "eigvals": w.cpu().numpy()}
    if workload == "fft":
        x = torch.tensor(inputs["x"], dtype=torch.complex128, device=device)
        y = torch.fft.fft2(x)
        return {"y": y.cpu().numpy()}
    if workload == "monte_carlo":
        gen = torch.Generator(device=device).manual_seed(0)
        n = inputs["n"]
        u = 2.0 * torch.rand(n * 2, generator=gen, dtype=t, device=device) - 1.0
        inside = (u[:n] ** 2 + u[n:] ** 2) <= 1.0
        pi_mean = 4.0 * inside.float().mean().item()
        pi_std = 4.0 * inside.float().std(unbiased=True).item() / np.sqrt(n)
        return {"pi_mean": float(pi_mean), "pi_std": float(pi_std)}
    if workload == "bootstrap":
        data = torch.tensor(inputs["data"], dtype=t, device=device)
        gen = torch.Generator(device=device).manual_seed(1)
        idx = torch.randint(0, data.numel(), (inputs["resamples"], data.numel()),
                            generator=gen, device=device)
        means = data[idx].float().mean(axis=1).cpu().numpy()
        return {"ci_lo": float(np.quantile(means, 0.025)),
                "ci_hi": float(np.quantile(means, 0.975)),
                "mean_of_means": float(means.mean())}
    if workload == "autodiff":
        x = torch.tensor(inputs["x"], dtype=t, device=device, requires_grad=True)
        loss = 0.5 * ((x - 0.25) ** 2).mean()
        loss.backward()
        return {"grad": x.grad.cpu().numpy()}
    raise ValueError(workload)


def _candidate_cupy(workload, inputs, dtype):
    import cupy as cp
    if workload == "matmul_eig":
        a = cp.asarray(inputs["a"])
        b = cp.asarray(inputs["b"])
        sym = cp.asarray(inputs["sym"])
        c = a @ b
        w = cp.linalg.eigvalsh(sym)
        return {"c": cp.asnumpy(c), "eigvals": cp.asnumpy(w)}
    if workload == "fft":
        x = cp.asarray(inputs["x"])
        y = cp.fft.fft2(x)
        return {"y": cp.asnumpy(y)}
    if workload == "monte_carlo":
        rng = cp.random.RandomState(0)
        n = inputs["n"]
        u = 2.0 * rng.uniform(low=-1.0, high=1.0, size=n * 2)
        inside = (u[:n] ** 2 + u[n:] ** 2) <= 1.0
        return {"pi_mean": float(4.0 * cp.mean(inside)),
                "pi_std": float(4.0 * cp.std(inside) / cp.sqrt(n))}
    if workload == "bootstrap":
        data = cp.asarray(inputs["data"])
        rng = cp.random.RandomState(1)
        idx = rng.randint(0, data.size, size=(inputs["resamples"], data.size))
        means = cp.asnumpy(data[idx].mean(axis=1))
        return {"ci_lo": float(np.quantile(means, 0.025)),
                "ci_hi": float(np.quantile(means, 0.975)),
                "mean_of_means": float(means.mean())}
    raise ValueError(workload)


# ------------------------------------------------------------------ parity

def parity_kind(workload):
    if workload in ("matmul_eig", "fft", "autodiff"):
        return "deterministic"
    return "statistical"


def check_parity(workload, scale, ref_result, cand_result):
    tol = PARITY_TOL[workload][scale]
    if workload == "matmul_eig":
        c_ok = _rel_err(ref_result["c"], cand_result["c"]) < tol
        e_ok = _rel_err(ref_result["eigvals"], cand_result["eigvals"]) < tol
        return bool(c_ok and e_ok)
    if workload == "fft":
        return bool(_rel_err(ref_result["y"], cand_result["y"]) < tol)
    if workload == "autodiff":
        return bool(_rel_err(ref_result["grad"], cand_result["grad"]) < tol)
    # statistical: absolute tolerance on every reported statistic
    for key in ref_result:
        if abs(ref_result[key] - cand_result[key]) > tol:
            return False
    return True


def _rel_err(a, b):
    a = np.asarray(a)
    b = np.asarray(b)
    denom = np.maximum(np.abs(a), 1e-30)
    return float(np.max(np.abs(a - b) / denom))
