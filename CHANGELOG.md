# 变更日志与版本发布清单 (CHANGELOG & Release Manifest)

本文件记录 `hermes-academic-skills` 仓库各版本的接口变更与迁移规范，列明输入输出形态变化以及发布身份清单。

---

## 2026-09-17（HEAD / work/cross-review-five-v2-20260917）

本次更新包含对五人交叉评审 v2（Sparse Deliberation）的完整重构，以及全仓 41 项重审缺陷治理与科学计算执行层（`scfabric`）的引入。

### 1. 接口与返回值变更 (Migration Guide)

| 模块 / 脚本 | 原行为 (旧接口) | 现行规范 (新接口) | 迁移与兼容性说明 |
| :--- | :--- | :--- | :--- |
| `cross-review-five/orchestrate_v2.py` | 轮转互审两阶段模式；粗粒度按 target 聚类；单断言反驳清除整项 | v2 四阶段流：盲审生成 -> 断言级聚类合并 -> 定向匿名质询 -> 对账与未决保护账本 | 旧命令兼容执行，`stage_synthesize_v2` 产出 `unresolved-ledger.json` 与结构化收敛状态 |
| `retraction-watch/watch.py` | `check_doi` 仅读首批 100 条 Crossref 记录；404 时将旧值直接覆盖回当前状态 | 引入 `truncated` 状态指示；快照如实记录 `current_observation` 与 `verification_status='retained_prior'` | 状态快照向后兼容，下游解析器可直接读取 `current_observation` 判断本轮是否真实触网 |
| `retraction-watch/watch.py` | `update-to` 信号绑定 target DOI（出现重复压缩） | 信号身份优先绑定通知记录自身 DOI（`update-doi=<notice_doi>`） | 历史状态中旧格式字符串平滑保留，新检测事件使用独立更正身份 |
| `literature-watch/watch.py` | OpenAlex 查无 ID 时将原论文作为引用者输出 | `fetch_citing_works` 产出 `source='crossref-fallback'`，`collect()` 过滤该种子记录 | 杜绝被监控论文自身被报告为自己的新引用者 |
| `literature-analysis/collect_corpus.py` | 仅使用线性字典别名映射；丢弃作者与摘要 | 采用并查集（DSU）两遍归并；保留 `authors`, `abstract`, `referenced_works` 等元数据 | 彻底消除输入顺序依赖；下游引文图与评审矩阵直接消费完整材料 |
| `literature-analysis/interop.py` | BibTeX 互转单向转义，往复导致 `\\&` 等符号膨胀；剥光机构作者花括号 | 增加对称的 `tex_unescape`；仅剥除单层字段定界符，保护单一机构作者不被拆分 | `to_bibtex(from_bibtex(text))` 达到幂等性 |
| `quantitative-paper-audit/recompute.py` | `percent=0` 且 `count>0`、未给分母时直接判不可能；float 丢尾随零 | 根据报告精度容差判定最小合理分母，记为欠定；支持直接传入原始字符串保留有效小数位数 | 浮点数与字符串输入同时兼容 |
| `scfabric` (科学计算执行层) | （新增模块） | 提供硬件探针与后端目录，配备五项基准负载与严格等价门禁，产出完整的 `ComputeReceipt` 回执 | 默认基于 CPU 执行，仅在实测提速超过阈值且通过数值门禁时准入加速器 |
| `literature-watch/watch.py` & `retraction-watch/watch.py` | 404 错误触发三次无谓重试导致 Crossref 兜底受阻；Token 凭证校验依赖前缀匹配 | 404 直接抛出不参与重试；凭证注入限定为 HTTPS 与官方域名权威校验；端点显式指向 `/v1` | 兼容旧版调用，消除无谓重试延迟并杜绝凭证泄露 |
| `cross-review-five/orchestrate_v2.py` | 子进程继承父进程全量环境变量；固定 15 秒轮询；依赖兼容别名 | 注入 `--ignore-rules` 参数与最小环境白名单；引入自适应轮询与规范提供方名称解析 | 隔离无关凭证并消除评审进程空等 |
| `scfabric/backends.py` & `hardware_probe.py` | ROCm 平台误标为 CUDA；缺少 Intel XPU 执行后端 | 区分 `torch.version.hip` 并标记 `rocm` 运行环境；补齐 `torch_xpu` 执行后端与类型约束 | 准确反映各硬件运行时身份 |

### 2. 发布身份清单 (Release Manifest)

- **Repository**: `xngg1021/hermes-academic-skills`
- **Protocol**: `compute-receipt-1.0` / `evidence-receipt-1.0`
- **Skills Count**: 11
  - `skills/academic-source-verification` (1.0.0)
  - `skills/academic-writing` (1.0.0)
  - `skills/literature-analysis` (1.0.0)
  - `skills/math-computation` (1.0.0)
  - `skills/quantitative-paper-audit` (1.0.0)
  - `skills/research-reproducibility` (1.0.0)
  - `skills/systematic-review-meta-analysis` (1.0.0)
  - `skills/literature-watch` (1.0.0)
  - `skills/retraction-watch` (1.0.0)
  - `skills/research-object-identity` (1.0.0)
  - `skills/cross-review-five` (1.0.0)
- **Schemas**:
  - `schemas/compute-receipt.schema.json`
  - `schemas/evidence-receipt.schema.json`
- **Verification Matrix**:
  - Unit & Regression Tests: 439 passed, 0 failures, 0 warnings
  - Static QA Fences: 38 independent executable blocks passed
  - CI Matrix Platforms: Ubuntu (Python 3.10, 3.11, 3.12, 3.13), macOS (Python 3.12), Windows (Python 3.12)
