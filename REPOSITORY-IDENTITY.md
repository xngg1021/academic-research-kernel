# Repository Identity Continuity Record (仓库身份连续性存证)

本文件记录本仓库在 GitHub 上的持久性身份标识、更名历史及其与历史许可证事实的不可篡改映射。

---

## 1. 持久性标识 (Persistent Identity)

| 属性 | 事实记录 |
| :--- | :--- |
| **GitHub Repository ID** | `1358731364` (官方不可变整型标识) |
| **Current Canonical Name** | `xngg1021/academic-research-kernel` |
| **Current Web URL** | https://github.com/xngg1021/academic-research-kernel |
| **Current Git Remote** | `https://github.com/xngg1021/academic-research-kernel.git` |
| **Former Canonical Name** | `xngg1021/hermes-academic-skills` |
| **Identity Transition Event** | PR #7 (`chore/repo-identity-migration`) |
| **Transition Merge Commit** | `fb2cf3a2050f0b43d57c9ed52dc9fb9f6c3fd47e` |

---

## 2. 身份迁移原因与定位跃迁

随着 **PR #5**（Harness-neutral 中立传输契约、stdio MCP 工具服务、Agent Plugins v1 规范支持）与 **PR #6**（W3C PROV 风格的生产谱系内核与可重放 `LineageReceipt`）先后通过全架构严格 CI 合入 `main`：
1. 本仓库已经从“服务于 Hermes 单一智能体的技能包”，彻底演进为**跨智能体生态中立的科研基础设施公共内核**；
2. 消除旧名称对外部智能体（Claude Code、Cursor、Gemini CLI 等）科研用户的认知壁垒；
3. 现行 JSON Schemas `$id`、多语言安装指南与 MCP 服务名称已完整对齐新命名。

---

## 3. 历史法律记录不可篡改性 (Immutability of Historical Legal Boundaries)

依据 Source Lineage License (SLL) 溯源原则与软件工程证据纪律，以下文件记录的是历史时刻的真实法律审计事实，**绝不回溯重命名**：
- `SOURCE-LINEAGE.md`
- `LICENSE-APPLICATION.md`
- `LICENSE-HISTORY.md`
- `SLL-APPLICATION.json`
- `tests/test_license_application.py`

上述历史文件中所引用的 `xngg1021/hermes-academic-skills` 及其对应的不可变 Commit SHA，保持历史字面一致性，作为可被机械核验的合规证据链。
