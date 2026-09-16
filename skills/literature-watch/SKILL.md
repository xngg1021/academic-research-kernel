---
name: literature-watch
description: "每周监控新文献：按主题、作者、DOI 清单查 OpenAlex 与 Crossref，只报新增."
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
    tags: [blueprint, literature, openalex, crossref, monitoring]
    related_skills: [literature-analysis, academic-source-verification, retraction-watch]
    config:
      - key: literature_watch.watchlist
        description: 监控清单 JSON 路径（含 topics/authors/dois 三个数组）
        default: "~/.hermes/literature-watch.json"
        prompt: literature-watch 监控清单文件路径
      - key: literature_watch.state
        description: 已见作品去重状态文件路径（自动维护，勿手改）
        default: "~/.hermes/literature-watch.seen.json"
        prompt: literature-watch 去重状态文件路径
    blueprint:
      schedule: "0 9 * * 1"
      deliver: origin
      prompt: "运行 literature-watch：读取监控清单（topics/authors/dois），用 scripts/watch.py --run 查 OpenAlex 与 Crossref 窗口内的新作品，与去重状态比对后只报告新增条目；无新增则明确说无新增。更新状态文件后结束。"
      no_agent: false
---

# literature-watch

定时文献监控 blueprint：每周按用户给定的主题、作者、DOI 清单查询 OpenAlex 与 Crossref，跨周去重后只报告新增作品。配套脚本 `scripts/watch.py` 负责网络查询与状态管理。

## When to Use

- 用户要求"每周帮我盯一下某主题的新论文"
- 用户要求跟踪某位作者（OpenAlex author id）的新作
- 用户要求盯某几篇论文的新引用者
- 安装后 Hermes 把它登记为建议排程（suggested cron），用户接受后每周自动运行

## 安装与排程配置

本技能 frontmatter 带 `metadata.hermes.blueprint`，安装时 **不会** 静默创建定时任务，而是进入建议队列：

```bash
hermes skills install xngg1021/hermes-academic-skills/skills/literature-watch
# 然后在会话中：
/suggestions             # 查看待处理建议
/suggestions accept N    # 接受并创建 cron 任务
/suggestions dismiss N   # 不再提示
```

默认排程 `"0 9 * * 1"`（每周一 09:00），`deliver: origin`（结果送回触发会话）。接受建议时可用任意 cron 表达式、`"every 2h"` 式间隔或 ISO 时间戳覆盖 schedule。

## 监控清单（watchlist）配置

清单是一个 JSON 文件，默认路径 `~/.hermes/literature-watch.json`，可用 `hermes config set skills.config.literature_watch.watchlist <路径>` 改。结构：

```json
{
  "topics": ["retrieval augmented generation"],
  "authors": ["A5023888391"],
  "dois": ["10.1038/nature12373"]
}
```

- `topics`：主题词，走 OpenAlex `search=` 检索；
- `authors`：OpenAlex author id（形如 `A...`，先用 literature-analysis 工作流 D 查到）；
- `dois`：论文 DOI，监控它们的**新引用者**（OpenAlex `cites:` 过滤）。

去重状态文件默认 `~/.hermes/literature-watch.seen.json`，由脚本自动维护；换机器或重新统计时可删除，删除后下一轮把窗口内结果全部当作新增。

## 每次运行的流程

1. 读取 watchlist 与状态文件；窗口默认最近 7 天（`--days` 可调）。
2. 逐来源查询（全部是 `scripts/watch.py` 里标注 live 的函数，真实 HTTPS）：
   - 主题 → `fetch_topic_works`；作者 → `fetch_author_works`；DOI → `fetch_citing_works`。
3. `filter_unseen` 按 DOI → OpenAlex id → 归一化标题的优先级去重（本轮内部与历史状态双重去重）。
4. 只输出新增条目（年份、标题、DOI）；无新增明确说"无新增"。
5. 写回状态文件。

手动跑一次（等同 blueprint 每轮做的事）：

```bash
python ${HERMES_SKILL_DIR}/scripts/watch.py --run --watchlist ~/.hermes/literature-watch.json
```

## 数据源与限制

- OpenAlex 匿名查询有日预算（2026-09 核查为 $0.10/日，免费 key $1/日）与 100 req/s 上限；key 放 `OPENALEX_API_KEY` 环境变量，只发给 api.openalex.org。429 时有界退避，最多 3 次。
- `from_publication_date` 按出版日期过滤，数据库收录有延迟，边界日可能漏收或重复；去重机制吸收重复，漏收不补偿。
- Crossref 仅作 DOI 元数据兜底（`fetch_crossref_record`），无 key，遵守公共节流。
- 无 DOI 无 OpenAlex id 的条目靠标题去重，同名不同文会被误判为已见；报告里保留 id 便于复核。

## Verification

离线自检不触网，验证去重与清单解析；live 查询明确 SKIP：

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
