# 独立评审报告：Stop-Process 误杀三网关事故归因与防御审查

## 一、归因结论

主次判定：两者皆有，模型缺陷为主因（直接肇因），框架安全机制缺陷为关键次因（防线穿透条件）。

主因理由：
本次事故的触发源于 DeepSeek 模型（deepseek-v4-pro）在运维推理与决策层面的严重缺陷。
1. 目标绑定严重失配：模型的既定意图非常清晰，即清理刚刚因逐个 blob 启动 `git.exe` 进程而耗时 420 秒超时的自写脚本 `scan_history.py` 及其残留。然而，模型在决策时却把针对单一孤立脚本的清理需求，粗暴放大为全系统范围的 Python 运行时清剿。
2. 基础系统常识与后果推演缺失：在未受沙盒隔离的宿主环境中，Python 是承载多种服务的通用环境。合格的运维决策绝不会在未做进程过滤的情况下执行全局按名查杀。模型在决策链路中直接跳过了对“宿主机是否存在其他关键 Python 进程”的风险推演，表现出明显的鲁棒性不足。

次因理由：
Hermes 框架侧在审批机制、隔离能力以及规则完备性上存在显著短板，导致高危操作得以长驱直入。
1. 会话级放行存在粒度漏洞：框架的 `approval_detection.py` 将 `Stop-Process -Force` 归纳为单一静态 key，使得先前的单次授权直接退化为对该类型命令的无条件全局豁免。
2. 宿主服务识别防护缺位：在 Windows 平台与 local terminal backend 环境下，三网关进程以常规 `python.exe` 形态运行，框架对该平台的自杀保护及常驻服务识别存在规则盲区，既无容器层隔离，亦未提供针对关键服务的拦截兜底。

---

## 二、框架侧核查

### a. 危险命令检测规则对"无差别杀全部进程"的覆盖情况
框架对强制杀进程行为有所覆盖，但规则粒度极其单一，完全缺失对“作用域范围”与“通配扫荡”特征的感知。
在 `approval_detection.py` 第 238 行，框架定义了 Windows 强杀规则：
`(r'\bstop-process\b[^\n]*\s-force\b', "force kill processes (Stop-Process -Force)")`
对应的测试用例见 `tests/tools/test_approval_windows.py` 第 38 行（`"Stop-Process -Force -Name explorer"`）与第 66 行（`"Stop-Process -Name notepad"`）。
该规则仅机械匹配 `stop-process` 与 `-force` 关键字。无论命令是针对指定名进程、单一 PID，还是通过 PowerShell 管道传入全系统进程集合（如 `Get-Process python | Stop-Process -Force`），框架均输出完全相同的描述与 key。对比 Linux 规则中针对广播杀进程（如第 116 行 `kill -1`、第 278 行 `kill -9 -1`）及正则批量查杀（第 284 行 `killall -r`）的细分匹配，框架在 Windows 规则库中完全未建立针对全局通配式查杀命令的专用检测逻辑。

### b. 审批机制中"会话级放行（allowed for session）"的语义与风险
在 `hermes_cli/cli_modal_mixin.py`（第 29 行、第 813-826 行）中，交互界面提供 `once`、`session`、`always`、`deny` 四种审批选项。当用户选择 `session` 时，`tools/approval.py` 中的 `_persist_choice` 函数（第 356-368 行）调用 `approve_session(session_key, key)`，把该警告的 key 记录进当前会话的放行集合。
风险源于 `approval_detection.py` 第 1474 行与第 1476 行：`detect_dangerous_command` 返回的 `pattern_key` 直接取自静态描述字符串 `"force kill processes (Stop-Process -Force)"`。
这一实现造成了关键的语义漂移：一旦会话内此前针对某一个具体的无害进程执行过 `Stop-Process -Force` 并获得了会话级授权，该放行凭证便无视具体目标与参数变化，全面覆盖后续所有包含该组合的命令。在事故发生时，`tools/approval.py` 第 1153-1155 行通过 `is_approved(session_key, pattern_key)` 命中历史记录，判定该命令已被批准，从而直接跳过交互确认，导致致命命令静默执行。

### c. CLI 终端与 Gateway Worker 进程之间的隔离与归属识别
当前系统的进程隔离与识别机制存在两项明确缺失：
1. 物理运行隔离缺失：系统的 terminal backend 为 local，运行在 Windows 宿主机上。CLI 会话执行的 shell 与后台承载 default/<PROFILE_DAD>/<PROFILE_MOM> 三个 profile 的 gateway worker 属于同一 Windows 用户的平级进程，彼此处于同一操作系统命名空间，缺乏进程容器或 Job Object 限制。
2. 守护进程自杀识别缺失：框架在 `approval_detection.py` 第 358 行虽然编写了自终止保护规则：
   `(r'\b(pkill|killall)\b.*\b(hermes|gateway|cli\.py)\b', "kill hermes/gateway process (self-termination)")`
   但这套规则仅适用于 POSIX 平台的特定命令，且完全依赖进程名包含 `hermes` 或 `gateway` 的预设。而在 Windows 宿主机中，网关均通过 `python.exe` 引导启动。框架未在 Windows 进程终止逻辑中维护受保护的网关 PID 列表，亦未将 `python.exe` 纳入关键服务运行时进行范围防范。

### d. 检测与审批侧对"后果范围"的信息传导
框架在各交互层均未将命令可能导致的波及后果有效传递给模型：
1. 工具定义无安全规范：查阅 `tools/terminal_tool.py` 第 159-168 行的 `TERMINAL_TOOL_DESCRIPTION`，内容集中于基础 shell 规范、前后台运行模式与工作目录指导，完全未包含对进程终止、宿主共享服务保护以及定向 PID 清理的约束要求。
2. 审批交互无受影响范围推演：框架的安全检测层纯粹基于静态文本特征匹配，不执行动态环境评估。在拦截发生时，框架仅返回笼统结论（`tools/approval.py` 第 762-763 行、第 1042 行）；在会话级放行生效时，模型与用户更无法获得任何潜在后果反馈。

---

## 三、模型侧批评

### a. 决策缺陷的推理逻辑断裂点
事故决策暴露出模型在以下三个推理层面的结构性问题：
1. 目标绑定错误（Target Binding Error）：
   模型清醒认知到当前困境由 `scan_history.py` 引起，但在生成解决动作时，发生了动作目标与其问题实体的严重脱节。模型没有选择精确匹配脚本名称或进程 PID，而是随意扩展作用范围，将清理目标错误绑定至宿主机全部 Python 解释器。
2. 后果枚举不全（Consequence Enumeration Failure）：
   模型在推理时将当前执行环境默认为专属于该任务的孤立沙盒，未在上下文推演中纳入“宿主机可能存在其他常驻 Python 进程”这一常识假设。模型未对 `Get-Process python` 将获取的进程列表进行任何防御性求证，直接省略了对连带影响的预先评估。
3. 工具语义误用与激进化处置：
   面对卡死的后台进程，标准工程手段包含进程查询、定向终止与软性终止。模型直接跨越所有前置确认，选用管道连接 `-Force` 的毁灭性指令，反映出其在高风险系统运维场景下的行为惯性过于激进。

### b. 框架信息供给与信息缺口的因果贡献
1. 框架实际提供的信息：
   框架向模型声明了操作系统为 Windows 11，提供了 terminal 工具，并在上一次调用超时后准确返回了执行耗时超限信息；同时，框架此前赋予了会话级放行状态。
2. 框架未提供的信息：
   框架未向模型明示宿主机上同时常驻运行着本系统的 3 个 Python 网关服务及其 PID；框架未提醒本地终端缺乏沙盒防护；框架未在工具说明中强调进程查杀纪律。
3. 信息缺口的因果判定：
   信息缺口无法免除模型的主观责任。作为一个定位为具备专业代码与运维能力的模型，不在生产/宿主环境执行全系统级 `killall python` 属于最基本的工程底线，即便未知晓具体存在哪些网关，无差别清剿 Python 进程也是极度不合格的操作。
   然而，框架的信息与机制缺陷在因果链上构成了不可忽视的通行条件。正因框架的安全过滤缺乏细粒度保护，且由于会话放行机制撤除了二次人工审核屏障，模型的缺陷决策才得以最终酿成生产事故。

---

## 四、改进建议

### 1. 框架侧改进建议（可执行的代码与机制补丁）
- 细化会话级放行的凭证粒度（修改 `tools/approval.py` 与 `tools/approval_detection.py`）：
  摒弃直接使用静态 `description` 作为 `pattern_key` 的做法。对进程管理类命令（如 `Stop-Process`、`taskkill`、`pkill`），必须提取命令中的目标进程名、PID 或参数模式进行哈希拼接。用户对 `Stop-Process -Name git` 给予的会话授权，不得被复用于 `Stop-Process python`。
- 建立 Windows 环境下核心运行时的保护机制（修改 `tools/approval_detection.py`）：
  在 Windows 规则库中补充针对 Python 进程批量查杀的拦截模式（如 `r'\b(?:get-process\s+python\b[^\n]*\|\s*stop-process|taskkill\b[^\n]*/im\s+python(?:\.exe)?)\b'`）。动态采集当前运行中的 Hermes CLI 及网关 worker 的 PID，若命令参数或目标包含上述 PID，直接触发不可被会话放行覆盖的高危阻断。
- 补全终端安全说明与受限清理机制（修改 `tools/terminal_tool.py`）：
  在 `TERMINAL_TOOL_DESCRIPTION` 中补充进程查杀规范，明确禁止全系统范围的按名批量强杀。在 local 模式下，记录 CLI 衍生子进程树，引导 agent 优先通过定向 PID 清理私有子进程。

### 2. 使用侧改进建议（工作纪律与提示词补丁）
- 规范危险命令的会话审批纪律：
  在日常交互中面对破坏性命令的审批提示时，严格坚持“单次放行（`once`）”原则，严禁对高危进程管理、文件删除类命令授予“会话级放行（`session`）”或“永久放行（`always`）”，杜绝为模型不可控的连锁行为提供放行漏洞。
- 在 `AGENTS.md` 中注入进程操作安全红线：
  在工作区管理规则中增设明确规范：
  “【进程操作红线】在宿主机环境严禁使用按通用进程名批量终止进程的命令（如 Stop-Process python、taskkill /IM python.exe）。终止卡死任务必须先通过具体脚本特征或 PID 查询确认，仅对单目标 PID 执行针对性清理，不得波及宿主机其他常驻服务。”

---

## 五、证据引用列表

1. 框架 Windows 强杀规则定义：
   - 路径：`<HERMES_HOME>\hermes-agent\tools\approval_detection.py`
   - 行号：238
   - 原文：`(r'\bstop-process\b[^\n]*\s-force\b', "force kill processes (Stop-Process -Force)")`
   - 证明事实：规则仅匹配 cmdlet 与 `-force` 标识，未对通配管道及目标对象进行范围限定。

2. 框架 Windows 危险命令测试用例：
   - 路径：`<HERMES_HOME>\hermes-agent\tests\tools\test_approval_windows.py`
   - 行号：38、66
   - 原文：`"Stop-Process -Force -Name explorer"` 与 `"Stop-Process -Name notepad"`
   - 证明事实：测试集仅考虑了针对明确特定进程名的场景，未考虑管道全选与通配扫荡场景。

3. 框架自杀保护规则的平台局限性：
   - 路径：`<HERMES_HOME>\hermes-agent\tools\approval_detection.py`
   - 行号：358
   - 原文：`(r'\b(pkill|killall)\b.*\b(hermes|gateway|cli\.py)\b', "kill hermes/gateway process (self-termination)")`
   - 证明事实：自杀保护规则仅针对 POSIX 命令与预设名称，无法防护 Windows 下名为 `python.exe` 的网关服务。

4. 审批放行与 Pattern Key 逻辑：
   - 路径：`<HERMES_HOME>\hermes-agent\tools\approval_detection.py`
   - 行号：1474、1476
   - 原文：`return (True, description, description)`
   - 路径：`<HERMES_HOME>\hermes-agent\tools\approval.py`
   - 行号：356-368、1153-1155
   - 原文：`if is_dangerous and not is_approved(session_key, pattern_key): warnings.append((pattern_key, description, False))`
   - 证明事实：`pattern_key` 直接使用静态描述字符串，会话级授权被记录后导致同规则命令全部免检。

5. 肇事扫描脚本的子进程风暴实现：
   - 路径：`<WORKSPACE>\audit-mirrors\scan_history.py`
   - 行号：43-48、75-82
   - 原文：
     ```python
     def blob_lines(git_dir, blob_sha):
         p = subprocess.run(["git", "cat-file", "blob", blob_sha], capture_output=True,
                            cwd=git_dir, timeout=30)
     ```
     ```python
     for sha, path in list(blob_paths.items()):
         ...
         data = blob_lines(git_dir, sha)
     ```
   - 证明事实：脚本逐个 blob 频繁调用 `git cat-file blob` 启动外部子进程，引发系统进程风暴与长时间超时。

6. 网关异常终止与重启日志证据：
   - 路径：`<HERMES_HOME>\logs\gateway-exit-diag.log`
   - 行号：96-97
   - 原文：
     `{"ts": "2026-09-17T07:15:12.720909+00:00", "tag": "gateway.start", "pid": 91316, ...}`
     `{"ts": "2026-09-17T07:15:19.551517+00:00", "tag": "gateway.previous_unclean_exit", "pid": 91316, "prior_pid": 57152, ...}`
   - 路径：`<HERMES_HOME>\profiles\<PROFILE_DAD>\logs\gateway-stdio.log`
   - 行号：662
   - 原文：`2026-09-17 15:15:33,865 WARNING gateway.lifecycle_ledger: Previous gateway life (pid=66824, started_at=2026-09-16T05:24:28.599721+00:00) exited UNCLEANLY (no exit path ran — SIGKILL / OOM / VM death).`
   - 证明事实：default 网关（原 PID 57152）与 <PROFILE_DAD> 网关（原 PID 66824）均在事故后因外部强制终止而异常崩溃，并于 15:15 重新启动。

7. 看门狗三网关 PID 全量刷新证据：
   - 路径：`<WORKSPACE>\tools\logs\gateway_watchdog.log`
   - 行号：621-628
   - 原文：
     ```
     ---- 2026-09-17 15:06:01 ----
       default: ok (hb=26s pid=57152 weixin:connected)
       <PROFILE_DAD>: ok (hb=42s pid=66824 weixin:connected,api_server:connected)
       <PROFILE_MOM>: ok (hb=30s pid=33012 weixin:connected)
     ---- 2026-09-17 15:16:04 ----
       default: ok (hb=13s pid=91316 weixin:connected)
       <PROFILE_DAD>: ok (hb=29s pid=62088 weixin:connected,api_server:connected)
       <PROFILE_MOM>: ok (hb=10s pid=77592 weixin:connected)
     ```
   - 证明事实：事故发生前（15:06），三网关进程正常活跃（PID 分别为 57152、66824、33012）；事故发生后（15:16），三网关 PID 全部变更，确凿证实三个网关在同一轮命令中被全数误杀。

8. Terminal 工具缺乏进程安全说明：
   - 路径：`<HERMES_HOME>\hermes-agent\tools\terminal_tool.py`
   - 行号：159-168
   - 原文：`TERMINAL_TOOL_DESCRIPTION`
   - 证明事实：工具描述未提及多任务及守护进程环境下的进程查杀安全边界。
