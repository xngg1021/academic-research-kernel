# 任务书:Stop-Process 误杀三网关事故归因评审

## 一、归因结论

**结论：事故由框架缺陷与模型缺陷共同导致，但主因在于框架侧的审批机制缺陷。**

**理由：**
1. **主因（框架侧）**：危险命令的“会话级放行（allowed for session）”机制粒度过粗。当模型触发无差别的 `Stop-Process -Force` 时，框架实际上正确地识别到了这是高危操作，但仅仅因为在此前的会话中批准过同规则键值（rule key）的精准查杀命令，系统便自动放行了这次具有全局毁灭性的命令，剥夺了最后的防线。同时，CLI 的运行环境缺乏沙箱隔离，默认给予了足以摧毁宿主基础设施的权限。
2. **次因（模型侧）**：模型在解决“子进程过多导致卡死”的问题时，推理能力存在明显短板，在没有排查和限制目标影响范围的情况下，粗暴地采用按进程名无差别杀伤（`Get-Process python`）的做法，犯了“后果枚举不全”和“目标绑定错误”的错误。

## 二、框架侧核查

**a. 危险命令检测是否覆盖"无差别杀全部进程"这类模式?具体规则是什么?**
覆盖了，但未区分“无差别全杀”和“精准查杀”。
*证据*：在 `<HERMES_HOME>\hermes-agent\tools\approval_detection.py` 第 238 行明确存在匹配模式：`(r'\bstop-process\b[^\n]*\s-force\b', "force kill processes (Stop-Process -Force)")`。
在 `<HERMES_HOME>\hermes-agent\tests\tools\test_approval_windows.py` 第 38 行，用例 `"Stop-Process -Force -Name explorer"` 也证实了只要带有 `-Force` 标志的 `Stop-Process` 都会被检测。然而，规则基于正则字符串匹配，并没有提取管道输入（`Get-Process python | ...`）的语义，将无差别杀全部与查杀单个全混在同一个分类标签下。

**b. 审批机制中"会话级放行"的语义与风险**
*语义*：在当前会话中，某一类规则（通过固定的描述字符串 / pattern_key 映射）只要被人工放行一次，系统就将其记为会话白名单，后续该规则再次命中即自动通过。
*风险*：规则的分类描述只关注“动作类型”（如 `"force kill processes (Stop-Process -Force)"`），不关注“目标范围”。这导致如果用户曾放行过杀单一个无害进程，模型后续执行清空全系统所有 Python 进程的相同类型命令时，系统将不再拦截。这一设计在面对具有毁灭性破坏能力的系统级命令时，形同虚设。

**c. CLI 会话的 agent 终端与 gateway worker 进程之间是否存在进程隔离或归属识别缺失**
存在严重的隔离与识别缺失。
*证据*：`<HERMES_HOME>\profiles\<PROFILE_DAD>\logs\gateway-stdio.log` 第 664 行显示系统曾明确警告过：`API server is network-accessible (<IP>) AND the terminal backend is 'local' (unsandboxed). Agent work dispatched through this endpoint runs as the host user with full terminal/file access.`
这表明当前的 agent 环境与三大 gateway 进程处于同一宿主环境及相同的用户权限下，毫无沙箱隔离。同时，`approval_detection.py` 中虽然在第 358 行设有 `kill hermes/gateway process (self-termination)` 的防御，但它只拦截直接指名杀 `hermes` 或 `gateway` 的命令。面对泛指 `python` 的管道过滤，归属识别彻底失效。

**d. 检测/审批侧是否把"后果范围"告知模型**
没有。
*证据*：在 `approval_detection.py` 代码逻辑中，硬编码的只有纯文本字符串形式的危险类型描述（如 `"force kill processes (Stop-Process -Force)"`）。没有任何解析逻辑会去计算影响多少个实际进程或者提醒模型“这将影响除你自己以外的其他重要组件”，模型完全在缺乏环境后果感知的情况下盲目执行。

## 三、模型侧批评

**a. 决策错在推理的哪一层？**
*目标绑定错误*：根据阅读 `<WORKSPACE>\audit-mirrors\scan_history.py` 源码，其 75-89 行中的扫描循环（对数以千计的 blobs 依次调用 `subprocess.run(["git", "cat-file", "blob", ...])`）确实是一种极耗资源的阻塞式/密集调用写法。当该脚本失控卡死时，模型的真正目标本应是终止其发起的 `git` 或这个脚本的实例，但模型却把目标绑定成了更大集合的 `Get-Process python`。
*后果枚举不全*：模型没有执行环境边界意识，未去核验宿主机是否还有其他非自己启动的 Python 服务，直接把清理自己的烂摊子粗暴等同于清空主机所有的同名进程。

**b. 框架给了模型什么信息，没给什么信息，信息缺口对决策的因果贡献。**
*给了什么*：执行工具（Powershell 和 Terminal 交互能力），并且它通过报错或者卡死知道脚本在疯狂生成进程。
*没给什么*：没有强调这是“在裸机上与其他常驻服务共用的宿主环境”，未给出沙箱隔离，同时在危险执行前的最后关口（会话级审批放行那一刻），未向终端反射该命令具体将杀掉哪些 PID。
*因果贡献*：由于模型处于“单机假想空间”（以为系统只有自己），再加之审批由于旧缓存直接滑行通过，这种信息盲区和拦截机制的缺位直接让“灾难级的脚本失控”升级成了“灾难级的基础服务误杀事故”。

## 四、改进建议

**框架侧改进（择一执行即可防范）：**
1. **收紧“会话级放行”判定逻辑**：不能单纯依据 `pattern_key` 放行。在涉及批量删除、杀死进程等高危规则上，必须将目标参数或管道输入（如含通配符、或者未明确指名具体 PID）作为上下文哈希的一部分。若检测到泛型过滤器（例如 `Get-Process python`），应强制脱离会话免审批缓存，直接要求人工重新核对。
2. **强化自保规则（`approval_detection.py`）**：在防自我终止的规则中（当前第 358 行），对于未隔离的 `local` 模式环境，应当补充拦截对解释器基座无差别屠杀的模式，例如：拦截所有不带特定 ID 或特定精确脚本名的 `Stop-Process *python*` 或类似形式的范围性查杀。

**使用侧改进：**
1. **启用独立沙箱隔离（工作纪律/配置）**：根据 `gateway-stdio.log` 第 664 行的警告，应立刻修改 `config.yaml`，将用于执行代理测试和扫描等高危作业的会话配置为 `terminal.backend: docker`，在容器内执行不可靠的 Python 脚本。隔离后即便执行 `Stop-Process python` 也只会清空容器内的自身进程，不可能波及宿主机的 `default/<PROFILE_DAD>/<PROFILE_MOM>` 三个网关。

## 五、证据引用汇总

- `<WORKSPACE>\audit-mirrors\scan_history.py`，75-80 行，证实该脚本在循环内对每个 blob 执行同步的 subprocess.run 派生子进程，容易造成进程积压和超时卡死。
- `<HERMES_HOME>\hermes-agent\tools\approval_detection.py`，237-238 行，证实 `Stop-Process -Force` 被列为危险检测模式，且以 `"force kill processes (Stop-Process -Force)"` 作为固定标识。
- `<HERMES_HOME>\hermes-agent\tools\approval_detection.py`，358-362 行，证实当前的自我防御仅能识别针对 `hermes|gateway|cli.py` 关键词的误杀，未囊括泛滥目标匹配。
- `<HERMES_HOME>\profiles\<PROFILE_DAD>\logs\gateway-stdio.log`，664 行，明确指出该终端运行在 `local` 无沙盒环境，拥有宿主机的完整权限。
- `<HERMES_HOME>\profiles\<PROFILE_DAD>\logs\gateway-stdio.log`，662 行，日志确认了先前的 gateway 进程 `pid=66824` 因未能正常退出（SIGKILL）而死亡，在时间线上与 15:10 的屠杀高度吻合。
- `<HERMES_HOME>\logs\gateway-exit-diag.log`，96-97 行，验证网关服务通过看门狗被重新拉起恢复。