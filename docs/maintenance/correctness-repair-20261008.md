# 本地正确性修复与有限任务链回归 — 2026-10-08

施工基线为当前远端 `37462f8d25f3842d753d258804c5549ac6e6b548`，tree
`fff6a1bcf9525751f10f2affd50cf11af20a897a`。开始时无开放 PR，使用
`work/correctness-repair-20261008`。未提供审查附件，按请求原反例重建正式测试。
Windows 11 x86_64 / Python 3.12.6，依赖来自仓库声明范围的 PyPI 包及官方
PyTorch CPU 索引，使用仓库外专用环境。原样基线在 UTF-8 环境下为
1001 passed、3 skipped；三项跳过均为可选 torch 后端，最终本机已安装补测。
最初的沙箱临时目录权限错误、默认 GBK 解码错误保留在本地日志；测试显式使用
可写临时目录，两个既有文本读取测试补充 UTF-8 编码，正确性断言保持原状。

| ID | 根因／触发条件 | 修改文件 | 正式回归与状态 |
| --- | --- | --- | --- |
| P1-01 | float 字符串未正确处理指数与精度；报告尾零丢失 | `recompute.py`、`mcp_server.py`、定量产物 schema | `test_statistics_correctness.py`、`test_correctness_stdio.py`、链 A；已修复。原 `.00001` 与约 `.3253086154` 不一致，普通 `.3253` 一致；字面量、冲突、半开区间两端均覆盖 |
| P1-02 | run 将查询前整份旧快照覆盖更新后的其他 DOI | `retraction-watch/scripts/watch.py` | `test_retraction_correctness.py`；已修复。DOI 增量、查询前单调版本、真实 spawn 多进程、同 DOI 新旧观测、锁归属／死持有者回收、唯一临时文件和写入恢复 |
| P2-01 | 未拒绝非有限值、非法统计输入域和 count 超分母 | `recompute.py`、`mcp_server.py` | 统计与 stdio 正式回归；已修复。保留合法零计数与 Welch 分数自由度；非法水平、NaN/Infinity、1e309 不作为成功结果 |
| P2-02 | 成功 HTTP 畸形字段被 bool 转成 False；未知抹除历史 | `watch.py`、撤稿 schema | 撤稿正式回归和链 B；已修复。测试数据故障注入覆盖缺失/null/错误类型、超时/限流、来源分歧、恢复；本轮观测与 last-known 分离 |
| P2-03 | ping 未实现，通知／畸形输入未区分 | `mcp_server.py` | `test_correctness_stdio.py` 的真实子进程；已修复。通知静默、ping 同 id 空 result、错误后会话继续、EOF 退出；同步任务未声明抢占取消 |
| P2-04 | 不完整统计输入返回空对象或 isError=false | `mcp_server.py`、README | stdio 回归；已修复。失败／部分失败为工具错误；统计不一致及成功验证 valid=false 保持正常结果。公开描述限于当前 t/p 与 Cohen's d/Hedges' g |
| P2-05 | sdist 清单漏 examples、CHANGELOG、REPOSITORY-IDENTITY | `pyproject.toml`、`package_acceptance.py`、`distribution_smoke.py` | 原样候选 sdist 仓库外全量／QA 与独立 wheel/sdist doctor、发现、stdio；修复清单，实际验收结果随候选交接保存。仅验证本地候选，uvx 使用独立缓存 |
| P2-06 | schedule 排除上游 canary；外部异常只影响退出码 | `qa.yml`、`live-contract.yml`、监测脚本 | `test_monitoring.py` 及真实 pinned/latest loader 检查；已修复。两通道各记 SHA，JSON/summary/产物显式三态；本地断言失败与网络退化分开 |
| P3-01 | 当前 README 混入旧候选数量、缺本轮精度／分发入口 | 英文／简体 README、CHANGELOG、i18n manifest | README 简体别名一致、i18n --check；同步本轮内容，旧译文保持 stale/queued，历史数字保留历史语境 |
| P3-02 | live-contract 使用落后 action 代际 | 直接相关 workflows | 官方 tag 与固定 SHA/action.yml 核对，复用已用 checkout v7.0.1、setup-python v7.0.0（Node24，runner >=2.327.1）；监测回归验证实际工作流条件 |

链 A 使用真实 t 重算与独立 60 位 mpmath 不完全 beta 判据，包含小 p 反例及普通正例。
产物经真实适配、入库回执、DOI 对象身份与来源定位、CEG、明确选择的 Ledger basis、
JSON 导出和完整回放验证。链 B 只替换 HTTP 外部边界，使用标记为测试数据的响应，
经过真实三态解析、并发提交、差异事件、再读与再次运行。没有 mock 数值、适配、入库或写入器。

PR #14 的种子、30 场景配额和覆盖定义未修改。两条任务链不代表全部 13 技能链、
未选任务目标或普通因子缺口已覆盖。LICENSE/SLL、产品版本 2.0.0、公共工具名称、
receipt/schema v1、既有 identity/lineage/CEG/Ledger 语义保持原有契约。

## 可复现验收入口

本次源码 checkout 全量 **1165 passed、零跳过**，包含 **161 项新增回归**；
静态 QA、40 个独立可执行代码块、i18n --check、schema／版本一致性、编译和 diff 检查通过。
真实 Hermes loader 检查 pinned `245e48008fa814b3251f50755eb656bd9fb86cb1` 与
latest `167e9fdb84248cd0fff80762dc57b6a914b6e930` 均为 healthy。
匿名外部探测为 degraded：可选 Unpaywall 缺少邮箱配置，literature-analysis 探测 healthy。
本地覆盖 Windows x86_64；Linux、macOS、ARM64 的候选验收由现有 CI 矩阵记录。

在独立环境安装 `requirements-qa.txt`、`build`、`twine`；按需从官方 CPU 索引
安装 `torch>=2.5,<3`。临时目录放在可写的仓库外目录。执行：

```bash
python -m pytest -q -rs tests
python scripts/qa.py
python scripts/i18n_sync.py --check
python -m compileall -q src scripts skills
git diff --check
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --cpu-torch --report package-acceptance.json
python scripts/release_manifest.py --output dist/release-manifest.json
```

`package_acceptance.py` 为源码包验收显式设置 `ARK_REPO` / `ARK_SDIST`，不从 checkout
补夹具，不使用 PYTHONPATH、全局同名包或用户已有环境。候选 commit/tree、分发 SHA-256、
实际导入路径和最终命令日志随本地交接目录保存；冻结后远端结果写入 Draft PR 描述和
本地 WORK_STATE，不为追加报告改 HEAD。主 CI 只由 Draft 的 `full-ci` 标签触发一轮，
不转 Ready，不请求额外 review。
