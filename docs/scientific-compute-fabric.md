# Scientific Compute Fabric, v0.1

Status: first-round experiment, 2026-09-17. Proposal provenance and the maintainer's prior expectations are recorded in docs/external-proposal-priors-20260917-scfabric.md. This layer is thin by design: it does not replace NumPy/SciPy/PyTorch, and it never re-wraps their optimized BLAS.

## What it is

scripts/scfabric/ implements five separable concerns, mirroring the THM provider contract in miniature without any THM dependency:

- hardware_probe.py: CPU model, OS-visible cores, process affinity, cgroup quota, RAM, ISA hint, accelerators. Every probe degrades to unknown instead of raising.
- backends.py: BackendSpec catalog with declared dtype support and lazy executable probes. dtype semantics come before device availability: torch_mps declares float32/float16/bfloat16 only, so any float64 workload can never be routed to MPS.
- workload_profiles.py: five workloads (dense matmul + eigensolver, FFT, Monte Carlo, bootstrap, autodiff), deterministic inputs from a fixed seed, three scale levels, and a parity contract.
- admission.py: paired benchmark with warmup and repeated timing, numeric parity check, transfer and VRAM measurement, then a mechanical gate: ADMITTED requires parity AND a measured speedup of at least the gain threshold (default 1.5x). Everything else is REFERENCE with a recorded fallback reason. No scores are synthesized.
- compute_receipt.py: the evidence record (schemas/compute-receipt.schema.json): hardware fingerprint, backend identity, library versions, dtype, device, timing, transfer, VRAM delta, parity outcome, verdict and fallback reason. A receipt records what was measured; it never infers a conclusion.

## Parity contract

Deterministic workloads (matmul, fft, autodiff) compare element-wise relative error with a tolerance sized by scale, because floating-point accumulation error grows with problem size. Stochastic workloads (monte carlo, bootstrap) compare the reported statistics with an absolute tolerance of several standard errors, because different backends draw from different RNG streams and two independent draws of the same distribution must agree statistically, not bit-for-bit. A candidate that fails parity is never admitted, no matter how fast it is.

## First-round measurements (single-machine snapshot)

One workstation: 36 hardware threads with AVX-512, 96 GB RAM, one consumer GPU with throttled FP64, Windows, Python 3.11, float64, gain threshold 1.5x, warmup 2, repeat 5. The receipts stay local and are gitignored; this table is a snapshot of that one machine, not a repository-wide claim. Every machine that runs run_ab_matrix.py produces its own receipts, and the fabric's verdicts are always relative to the machine being measured.

| workload | scale | torch_cpu | torch_cuda |
| --- | --- | --- | --- |
| matmul_eig | small | REF (no gain) | REF (no gain) |
| matmul_eig | medium | ADMITTED x5.8 | ADMITTED x2.5 |
| matmul_eig | large | ADMITTED x5.0 | ADMITTED x2.8 |
| fft | small | ADMITTED x8.5 | ADMITTED x2.8 |
| fft | medium | ADMITTED x28.0 | ADMITTED x8.6 |
| fft | large | ADMITTED x26.0 | ADMITTED x11.6 |
| monte_carlo | small | REF (no gain) | REF (no gain) |
| monte_carlo | medium | REF (no gain) | ADMITTED x60.2 |
| monte_carlo | large | REF (no gain) | ADMITTED x25.9 |
| bootstrap | small | REF (no gain) | ADMITTED x2.8 |
| bootstrap | medium | REF (no gain) | ADMITTED x66.5 |
| bootstrap | large | REF (no gain) | ADMITTED x33.7 |
| autodiff | small | REF (no gain) | REF (no gain) |
| autodiff | medium | REF (no gain) | REF (no gain) |
| autodiff | large | REF (no gain) | REF (no gain) |

Recorded findings:

1. There is no universal fastest backend. Small workloads stay on CPU because accelerator overhead dominates. Element-wise autodiff stays on CPU at every tested scale because the computation is too light.
2. On the measured machine, the 36-thread AVX-512 CPU beats its consumer GPU for float64 dense linear algebra and FFT: consumer GPUs throttle FP64 throughput relative to FP32, while the workstation CPU's multi-threaded torch kernels win on this specific workload. This confirmed the maintainer's prior expectation on this specific hardware configuration and demonstrates that a naive GPU-first dispatch rule is invalid for double precision on systems with throttled FP64 hardware.
3. The GPU wins where the workload is wide and parallel at float32 statistics: Monte Carlo and bootstrap with large resample counts.
4. The admission gate rejected real cases that a naive router would have shipped: torch_cpu FFT at the largest scale failed the sized parity contract before a complex-dtype comparison bug was fixed; the bug itself (casting complex results to float64 and silently comparing real parts only) is exactly the class of silent semantic drift this layer exists to catch, and it is now pinned by a regression test.

## Known limitations

- CPU-only in CI: GitHub runners have no GPU, so tests exercise probe, dtype gates, CPU candidates and admission logic only. Accelerator numbers come from this machine's receipts.
- The workload set is five operations at three scales, float64 only. float32, larger scales, CuPy and XPU are not yet measured.
- Parity tolerances are recorded judgments per workload and scale, not derived from first principles.
- The fabric is not yet wired into math-computation routing; it is a standalone measurement layer with evidence receipts. Wiring requires per-operation capability evidence, which is the next round.

## Reproducibility

Re-run the matrix with: python scripts/scfabric/run_ab_matrix.py. Every receipt carries the hardware fingerprint, library versions, benchmark parameters and the fallback reasons, so the same matrix on another machine is directly comparable.
