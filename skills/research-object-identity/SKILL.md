---
name: research-object-identity
description: 研究对象身份归一、聚合五态判定与生产谱系内核 (Provenance Kernel v1).
version: 1.1.0
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms:
- linux
- macos
- windows
tags:
- identity
- lineage
- provenance
- research-object
- deterministic
metadata:
  tags: identity, lineage, provenance, research-object, deterministic
  related_skills: academic-source-verification, literature-analysis, quantitative-paper-audit
---


# research-object-identity

Research Object Identity & Provenance Kernel v1：研究对象身份判定与科研生产谱系的**确定性公共骨架**。本技能包含两大核心子系统：
1. **身份与版本关系层**（[`scripts/identity.py`](scripts/identity.py)）：标识符归一（normalize）、候选记录聚合判定（resolve）、关系与版本谱系建边（link）。
2. **生产谱系内核（Provenance Kernel v1）**（[`scripts/provenance.py`](scripts/provenance.py)）：借鉴 W3C PROV-DM 规范，确立计算活动（Activity）与产物实体（Entity）为一等公民，提供严格因果 DAG 校验与毫秒级脱机反向溯源，产出符合 [`../../schemas/lineage-receipt.schema.json`](../../schemas/lineage-receipt.schema.json) 的确定性存证回执。

纯标准库、无网络依赖、无外部大模型调用。判定与验证结论一律为离散字段，**严禁任何置信分数与模糊打分**。

## When to Use

- 同一篇论文、数据集或代码仓库来自多个来源，需要判定是否为同一对象；
- 需要把 preprint、正式发表版、更正和撤稿串接成版本谱系链条；
- 需要追踪数据清洗、统计分析、表格提取全过程，明确“某个论文表格数据项究竟由哪份原始数据、哪个 commit 的代码、哪次计算活动与哪些参数产生”；
- 需要对研究生产链条执行因果 DAG 无环性校验与基于 SHA256 的防篡改完整性验证。

## 对象与实体模型

### 1. Research Object (身份层)
五类对象：Work、Person、Dataset、CodeRepository、Artifact。每个对象八个顶层字段：object_id、object_type、identifiers、manifestations、relations、lineage、source_observations、uncertainty。

### 2. Provenance Kernel (生产谱系层)
- **Entity（实体）**：`data_snapshot`, `code_file`, `environment_spec`, `statistic_artifact`, `table_cell`, `figure_artifact`, `generic_entity`。包含唯一标识 `id`、类型 `type`、内容哈希 `sha256`（64位小写十六进制）、定位符 `locator` 及元数据。
- **Activity（活动）**：`data_cleaning`, `computation_run`, `statistical_analysis`, `table_extraction`, `render_run`, `generic_activity`。记录具体执行命令 `command`、脚本实体引用 `script_id`、代码版本 `commit_sha`、参数映射字典 `parameters` 及环境指纹 `environment`。
- **LineageEdge（因果关系边）**：
  - `used`: 活动消费输入实体（Activity -> Entity）；
  - `generated`: 活动产出实体（Activity -> Entity，遵循单产生者约束）；
  - `derived_from`: 实体间因果派生（Derived Entity -> Source Entity，可选绑定媒介 Activity）。

## 工作流一：标识符归一（normalize）

`normalize(kind, value) -> str`，每类标识符一套确定性规则：

| kind | 规则 | 示例 |
| --- | --- | --- |
| doi | 去 `https://doi.org/`、`doi:` 前缀并小写 | `https://doi.org/10.1038/Nature12373` → `10.1038/nature12373` |
| arxiv_id | 去 URL 与 `arXiv:` 前缀、去版本号 | `2310.15264v2` → `2310.15264` |
| pmid | 只保留数字 | `PMID: 38123654` → `38123654` |
| openalex_id | 从 URL 取末段 ID | `https://openalex.org/W123` → `W123` |
| orcid | 去 URL 与连字符取纯数字 | `https://orcid.org/0000-0002-1825-0097` → `0000000218250097` |

## 工作流二：聚合判定（resolve）

`resolve(records)` 输入若干同一对象的候选记录，输出 object_type、merged_identifiers、verdict、match_fields、conflict_fields、sources 与 human_confirmed。按优先级判定：

| verdict | 含义 | 触发条件 |
| --- | --- | --- |
| CONFLICT | 候选记录互相冲突 | 同一标识符类型出现两个不同归一值 |
| EXACT | 确认同一对象 | 至少一个规范标识符跨记录一致 |
| STRONG_MATCH | 强匹配 | 无共享标识符，但规范标题与作者全部一致 |
| CANDIDATE | 疑似同一对象 | 无共享标识符，标题 Jaccard 相似度 ≥ 0.5，或作者重叠 |
| UNRESOLVED | 无法判断 | 信息不足（空记录或单记录且无标识符） |

## 工作流三：建边（link）

`link(a, b, kind, evidence)` 在 a 到 b 之间建立有向边：
- `relations`（cites、contradicts、replicates、derived_from）：单向记录在 a 侧；
- `lineage`（preprint_to_vor、correction、retraction、version_chain）：双向回填，保留方向。
evidence 必须包含：source、queried_at、match_fields、conflict_fields、human_confirmed 五项。

## 工作流四：生产谱系内核与可重放回执 (Provenance Kernel)

使用 `provenance` 模块构建全流程生产谱系网络：

```python
# fragment: true
from provenance import LineageGraph, validate_lineage, trace_origin

graph = LineageGraph(root_dir=".")

# 注册实体与活动 (强制互斥命名空间与幂等注册)
e_raw = graph.add_entity("raw_data", "data_snapshot", sha256="...", locator="data/raw.csv")
e_script = graph.add_entity("clean_script", "code_file", sha256="...", locator="scripts/clean.py")
e_clean = graph.add_entity("clean_data", "data_snapshot", sha256="...", locator="data/clean.csv")

act = graph.add_activity("clean_act", "data_cleaning", command="python scripts/clean.py", script_id=e_script.id)

# 记录因果关系
graph.record_used(act.id, e_raw.id)
graph.record_used(act.id, e_script.id)
graph.record_generated(act.id, e_clean.id)

# 拓扑与内容完整性校验
v_stat, t_stat, c_stat, err = validate_lineage(graph, check_on_disk_hashes=True)

# 逆向毫秒级溯源，生成不可变 LineageReceipt
receipt = trace_origin(graph, target_id=e_clean.id)
```

- **状态区分与覆盖率（拒绝将 UNKNOWN 折叠为 intact）**：`intact`（验证完整通过，所有声明哈希的本地文件物理字节一致）、`partial`（部分本地文件校验通过，存在未在本地解析的远程 URI 实体）、`unchecked`（未开启哈希检查或全为无哈希/未本地验证实体）、`missing_artifact`（声明了哈希但本地文件丢失）、`hash_mismatch`（物理文件哈希与声明不符）、`cycle_detected`（因果拓扑环路）、`missing_input` / `broken_chain`（引用不存在的实体或活动）。
- **不可变回执存证**：生成深拷贝的 `LineageReceipt`，因果图拓扑指纹（`lineage_digest`）与回执审计指纹（`receipt_digest` / `receipt_id`）清晰分离，同图同状态绝对稳定确定。
- **声称与验证边界**：所记录的代码 Commit SHA 与参数字典代表执行声明（claimed commit identity），供离线审计核对。

## 边界

- 不评分：任何字段都不是概率或置信度，判定依据只有离散字段比对；
- 不联网：归一、判定、建边与溯源全部离线可重放；
- 不伪造阴性状态：未检查或不可观测状态显式标记为 `unchecked` 或 `unobservable`，绝不冒充 `intact`。

## Verification

离线冒烟测试验证：

```python
# smoke-test: true
import os, sys
sys.path.insert(0, os.path.join(os.environ.get('SKILL_DIR', os.getcwd()), 'scripts'))
import identity as rid
import provenance as pr

# 1. 归一测试
assert rid.normalize('doi', 'https://doi.org/10.1038/Nature12373') == '10.1038/nature12373'
assert rid.normalize('arxiv_id', '2310.15264v2') == '2310.15264'

# 2. 五态判定测试
exact = rid.resolve([
    {'identifiers': [{'type': 'doi', 'value': '10.1/a'}], 'title': 'T', 'authors': ['A, B'], 'year': 2020},
    {'identifiers': [{'type': 'doi', 'value': 'doi:10.1/A'}], 'title': 'T', 'authors': ['A, B'], 'year': 2020}])
assert exact['verdict'] == 'EXACT' and exact['human_confirmed'] is False

# 3. 生产谱系内核冒烟测试
graph = pr.LineageGraph()
e_in = graph.add_entity("raw_1", "data_snapshot")
e_out = graph.add_entity("clean_1", "data_snapshot")
act = graph.add_activity("act_1", "data_cleaning")
graph.record_used(act.id, e_in.id)
graph.record_generated(act.id, e_out.id)
graph.record_derivation(e_out.id, e_in.id, activity_id=act.id)

v_stat, t_stat, c_stat, err = pr.validate_lineage(graph, check_on_disk_hashes=False)
assert v_stat == "unchecked" and t_stat == "valid_dag"

rec = pr.trace_origin(graph, target_id=e_out.id, check_on_disk_hashes=False)
assert rec.topology_status == "valid_dag"
assert rec.root_ancestors == ("raw_1",)
assert len(rec.trace_steps) == 1

print('research-object-identity smoke PASS')
```
