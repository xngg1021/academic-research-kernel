# 先验记录：Scientific Compute Fabric 提案（2026-09-17）

来源：ChatGPT 外部提案，经主线程评审后采纳薄层方案。本文件在动手前记录主线程的先验预期，用于事后对照外部影响。

## 采纳范围

- 在 hermes-academic-skills 内建 scripts/scfabric/ 薄层：硬件探针通用子集、ComputeBackendSpec、workload fingerprint、paired benchmark 加 parity admission、ComputeReceipt。
- 第一版实验：五个 workload(dense matmul/eigensolver、FFT、Monte Carlo、bootstrap/permutation、torch autodiff）乘可用后端乘三档规模，跑 paired benchmark。
- dtype 语义优先于 device 可用性；MPS 与 float64 组合直接 REFERENCE。
- 不建仓库间依赖，不搬 THM provider catalog、storage fabric、optimizer 存储、inference/index providers，不拆第三个仓库。
- admission 规则机械化：数值等价加实测提速比超过阈值（默认 1.5 倍）才 ADMITTED，否则 REFERENCE 并记录 fallback_reason。不合成分数。

## 先验预期（动手前）

1. 小规模统计负载（t 检验、meta 分析、定量审计反算）GPU 无益，overhead 主导，预期全部 REFERENCE。
2. 大规模 matmul、FFT、Monte Carlo 在 GPU 上有益。
3. 消费级 GPU 的 FP64 吞吐普遍被大幅阉割（约 FP32 的 1/64），而工作站级多核 CPU 加 AVX-512 的浮点吞吐不弱。所以在实测机上 float64 的 matmul 与 Monte Carlo 存在 CPU 反超 GPU 的真实可能。若实测如此，它将推翻"GPU 优先"直觉，这是本实验最有价值的可能结果。
4. parity 是 admission 的硬前提；dtype 不一致的候选一律 REFERENCE，不做静默降精度。
5. CI 无 GPU，测试必须全 CPU 可跑；真 GPU 实测在各自机器本地完成，receipt 留在本地（gitignore），公开仓库不存任何机器的硬件指纹快照；结论表以匿名单机快照形式记录，架构本身可移植到任意机器。
6. ComputeReceipt 同时服务复现证据，字段设计与 Evidence Receipt 哲学一致：记录查无与失败，不推断不在场的结论。

## 被拒绝的部分

- hermes-academic-skills 依赖 thm-tiered-hot-memory：拒绝（THM 是重运行时项目，academic-skills 保持薄）。
- 移植 THM native BLAS wrappers：拒绝（NumPy/SciPy/PyTorch 已自带优化 BLAS，二次包装只增加开销）。
- 一步到位做函数级 capability matrix：第一版只做 workload 级候选表，函数级矩阵留待有实测证据后。
