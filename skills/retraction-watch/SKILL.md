---
name: retraction-watch
description: "每周核查 DOI 清单的撤稿信号：OpenAlex 与 Crossref 双源比对，只在状态变化时报告."
version: 1.0.0
author: SJF, Hermes Agent
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
required_environment_variables:
  - name: OPENALEX_API_KEY
    prompt: "OpenAlex API key（可跳过，使用匿名查询）"
    help: "在 OpenAlex 官方账户中获取免费 key；不要把 key 写进技能或聊天。"
    required_for: "Authenticated OpenAlex requests; anonymous queries remain available."
metadata:
  hermes:
    tags: [blueprint, retraction, crossref, openalex, monitoring]
    related_skills: [academic-source-verification, literature-watch]
    config:
      - key: retraction_watch.watchlist
        description: DOI 监控清单 JSON 路径（含 dois 数组）
        default: "~/.hermes/retraction-watch.json"
        prompt: retraction-watch 监控清单文件路径
      - key: retraction_watch.state
        description: 各 DOI 状态快照文件路径（自动维护，勿手改）
        default: "~/.hermes/retraction-watch.state.json"
        prompt: retraction-watch 状态快照文件路径
    blueprint:
      schedule: "0 9 * * 1"
      deliver: origin
      prompt: "运行 retraction-watch：读取 DOI 监控清单，用 scripts/watch.py --run 逐条查 OpenAlex is_retracted 与 Crossref updates 反向查询的 update-to 撤稿信号，与状态快照比对；只有发生变化（含首次建档）的 DOI 才报告，全部无变化则明确说无变化。写回状态文件后结束。"
      no_agent: false
---

# retraction-watch

定时撤稿监控 blueprint：每周对用户维护的 DOI 清单核查撤稿/更动信号，与历史状态快照比对，**只有状态变化才报告**，无变化保持静默。配套脚本 `scripts/watch.py` 负责网络查询与状态管理。

## When to Use

- 用户维护一份参考文献/已发表论文清单，要求"有人被撤稿就告诉我"
- 用户要求在综述定稿前持续盯清单内文献的撤稿与更动信号
- 安装后 Hermes 把它登记为建议排程（suggested cron），用户接受后每周自动运行

## 安装与排程配置

本技能 frontmatter 带 `metadata.hermes.blueprint`，安装时 **不会** 静默创建定时任务，而是进入建议队列：

```bash
hermes skills install xngg1021/hermes-academic-skills/skills/retraction-watch
# 然后在会话中：
/suggestions             # 查看待处理建议
/suggestions accept N    # 接受并创建 cron 任务
/suggestions dismiss N   # 不再提示
```

默认排程 `"0 9 * * 1"`（每周一 09:00），`deliver: origin`。接受建议时可用任意 cron 表达式、`"every 2h"` 式间隔或 ISO 时间戳覆盖 schedule。

## 监控清单（watchlist）配置

清单是一个 JSON 文件，默认路径 `~/.hermes/retraction-watch.json`，可用 `hermes config set skills.config.retraction_watch.watchlist <路径>` 改。结构：

```json
{
  "dois": ["10.1038/nature12373", "10.1126/science.1234567"]
}
```

状态快照文件默认 `~/.hermes/retraction-watch.state.json`，记录每个 DOI 上次的 `is_retracted` 与 Crossref 更新信号集合，由脚本自动维护；删除后下一轮全部按"首次建档"报告一次。

## 信号来源与判定

两个独立信号，合并为状态快照（`snapshot_from_signals`）：

1. **OpenAlex**：`works/https://doi.org/<doi>?select=is_retracted` 的布尔字段；
2. **Crossref**：`works?filter=updates:<doi>` 反向查询，命中记录的 `update-to` 条目中指向目标 DOI 的撤稿/撤回/更正/表达关注信号（`type` 与 `source` 双字段，与 academic-source-verification 的 check_updates 语义一致）。

变化检测（`diff_snapshots`）：`is_retracted` 翻转、Crossref 更新信号新增或消失，都构成一次报告；首次建档的 DOI 也报告一次（作为基线）。完全相同则该 DOI 静默。

手动跑一次：

```bash
python ${HERMES_SKILL_DIR}/scripts/watch.py --run --watchlist ~/.hermes/retraction-watch.json
```

## 数据源与限制

- OpenAlex 匿名查询有日预算与 100 req/s 上限；key 放 `OPENALEX_API_KEY` 环境变量，只发给 api.openalex.org。429 有界退避，最多 3 次；OpenAlex 404 时继续用 Crossref 单源判定。
- Crossref 的撤稿标注依赖出版商与 Retraction Watch 数据登记；update 记录缺失不证明未撤稿，本技能只报告已登记的更新信号，不推断未登记的事实。
- 两个信号可能不一致（一方先更新）：报告按快照逐字段列出，由用户判断，不做多数表决。
- DOI 大小写与前缀形式先归一化再比对，状态文件以归一化 DOI 为键。

## Verification

离线自检不触网，验证信号合并与变化检测；live 查询明确 SKIP：

```python
# smoke-test: true
import os, subprocess, sys
from pathlib import Path
base = Path(os.environ.get('SKILL_DIR', '.')).expanduser().resolve()
result = subprocess.run([sys.executable, str(base / 'scripts' / 'watch.py'), '--self-test'],
                        capture_output=True, text=True, timeout=60)
assert result.returncode == 0, result.stderr
assert 'SKIP live OpenAlex/Crossref checks' in result.stdout
print(result.stdout.strip().splitlines()[-1])
```
