# Stop-Process 误杀三网关事故:独立归因评审(GLM-5.3)

评审日期 2026-09-17。材料范围:任务书及其指定的四类材料,全部实际读过,引用处附路径与行号。

## 一、归因结论

两者皆有,模型侧为主(约七成),框架侧为次(约三成)。

模型侧承担主责,理由是决策链里最关键的一环断裂在推理而非信息:Get-Process python 的语义是"按进程名匹配全机所有 Python 进程",这是 PowerShell 的公开常识语义,不需要框架额外提示才能知道。agent 在执行前已经完成了正确的第一步推理——它自己承认"逐个 blob 起子进程"是灾难级写法(任务书时间线第一条),说明它清楚自己制造了一批失控子进程;但它把"清理我自己制造的进程"这个目标,错误地绑定到了"杀掉所有 python"这个手段上,而没有走必然存在的更窄路径:记录子进程 PID、用 job object、或者直接改脚本改为单进程流式扫描。这一步错在目标绑定与手段选择,不是信息缺口能够开脱的。

框架侧承担次责,理由是防线在最后一米失效:检测规则存在且大概率触发了提示(下文二 a),但会话级放行让同会话内的第二次"Stop-Process -Force"静默通过,而这条命令的后果半径(本机三个承载家人微信服务的常驻 Python 进程)没有任何机制性提示。框架没有拦住一个已知的危险模式对无辜进程的波及,这是事实;但拦不住的前提是用户已经亲手放行过一次,所以是次责。

## 二、框架侧核查

### a. 检测是否覆盖"无差别杀全部进程"

部分覆盖,覆盖方式是"动词+强制标志"而非"后果范围"。

approval_detection.py:238 有专门规则:

  (r'\bstop-process\b[^\n]*\s-force\b', "force kill processes (Stop-Process -Force)")

事故命令 `powershell -Command "Get-Process python | Stop-Process -Force"` 中,"Stop-Process -Force"子串满足 `\bstop-process\b` 加 `\s-force`(检测用 re.IGNORECASE,见 :125 的 _RE_FLAGS),所以该命令会被判为 dangerous,进入审批流程。:237 还有 taskkill /F 的对应规则。测试 test_approval_windows.py:38 明确钉住了 `"Stop-Process -Force -Name explorer"` 必须提示,:66 钉住无 -Force 的 `Stop-Process -Name notepad` 不提示。

关键缺口有三处:

其一,规则匹配的是"强杀"这个动作,不区分"杀一个具名进程"与"杀全机同名进程"。`Stop-Process -Force -Name notepad` 与 `Get-Process python | Stop-Process -Force` 在规则眼里是同一个 pattern_key("force kill processes (Stop-Process -Force)"),前者后果半径是一个应用,后者是包括三个网关在内的全部 Python 服务。

其二,POSIX 侧的无差别杀有更细的分级先例可参照:approval_detection.py:116 的硬线规则 `kill -1` 单列(硬线,永不可放行),:278-284 对 pkill -9、killall -KILL、killall -r 单列。而 Windows 侧的 Stop-Process -Force 只有一档危险级,`Get-Process <name> | Stop-Process` 这种"管道全量"形态没有被识别为比"杀具名 PID"更危险的一档。

其三,它不在硬线名单里。HARDLINE_PATTERNS(:88-121)只收了 kill -1、shutdown、mkfs、dd 到裸设备等"无恢复路径"项;按注释 :56-57 的设计哲学,可恢复操作留在 DANGEROUS_PATTERNS。杀网关确实可恢复(看门狗拉起),这个分类自洽,但结果是它可被会话级放行绕过。

### b. "会话级放行"的语义与风险

approval.py:326-332 的 is_approved 显示,放行按 (session_key, pattern_key) 二元组记账:会话内批准过某个 pattern_key,本会话内所有命中同一 pattern_key 的命令都不再提示。_persist_choice(:356-368)里选 "session" 就调 approve_session 把 key 加进集合。

风险在于 pattern_key 的粒度是"危险描述"而非"命令本体"。批一次 `Stop-Process -Force -Name notepad`(合理操作),同会话再来 `Get-Process python | Stop-Process -Force`(无差别屠杀)会静默放行,因为二者共享 "force kill processes (Stop-Process -Force)" 这个 key。时间线里 "allowed for session" 标记(任务书 :17)说明此前同会话确实批准过同 key 命令。这是把"我信任这个人在这个场景做这类事"错误外推成了"我信任这个人本会话做一切此类事"。永久放行(approve_permanent,:342)跨会话同构地放大这个问题,好在 Tirith 类发现已被 :357-359 注释明确限制为 session-max,说明作者意识到了粒度问题,只是没有推到命令级。

### c. CLI 会话与 gateway worker 的进程隔离/归属识别

不存在隔离,也不存在归属识别。这台机器上 CLI agent 的 terminal 与三个 gateway worker 同跑在一个 Windows 用户下,agent 的子进程与网关 worker 同为 python.exe。approval_detection.py 的全部规则里没有任何"进程归属"概念——它有 self-termination 保护(:358 `\b(pkill|killall)\b.*\b(hermes|gateway|cli\.py)\b`),也就是"别杀自己",但没有"别杀自家兄弟进程"的保护。讽刺的是这条 self-termination 规则如果移植到 Windows 形态(Stop-Process 波及 gateway),恰好能覆盖本次事故:三个 worker 的 argv 是 `main.py gateway run`(gateway-exit-diag.log:96),按命令行特征识别 Hermes 进程在 Windows 上用 WMI/CIM 完全可行。框架对"CLI 会话可能殃及 gateway"这个同机共存的部署形态,检测层面是空白。

### d. 后果范围是否告知模型

没有。approval_detection.py 是纯命令分类(文件头注释 :3-4 自述),产出只有一个 description 字符串如 "force kill processes (Stop-Process -Force)",不含后果范围。terminal 工具描述层面(本次材料范围内未见,不越权断言),至少在检测与审批这条链上,没有任何文字告诉模型"本机有常驻 Hermes gateway 进程也是 python.exe,按名杀 python 会杀死它们"。模型对"杀了 python 会发生什么"的认知完全依赖它自己的世界知识,而它显然没有把"Hermes 网关是 Python 进程"这件事纳入推理。

## 三、模型侧批评

### a. 决策错在哪一层

三层都有伤,主伤在目标绑定错误。

后果枚举不全:它没有枚举"全机还有哪些 python 进程"。一个部署着三个 Python 常驻服务的机器上,按名杀 python 必然波及无辜,这层它没想到或者没想。

目标绑定错误(主因):目标是"停掉我起的扫描子进程"。这批子进程是它自己 fork 的,git cat-file 每次调用都是它在 scan_history.py:44 的 subprocess.run 里亲手创建的。要停自己创建的进程,PID 是可得的(改脚本记录 PID 即可),甚至把 blob_lines 改成 git cat-file --batch 单进程流式读(:43-48 每个 blob 一次进程创建,这是性能灾难的根因)。它选了唯一一个后果半径不可控的手段。

工具语义误用:Get-Process python 是选择器,Stop-Process 是执行器,管道组合的语义就是"全量匹配后全杀"。它可能把这条管道理解成了"清理我的子进程"的等价写法,这是对工具语义的粗糙匹配——名字对上了(python),语义没对上(全部 python 而非我的 python)。

还有一层前置失误值得记:scan_history.py 本身。:75-79 对每个 blob 起一个 git 子进程,大仓库几千 blob 就是几千次进程创建,Windows 上进程创建成本高,这直接导致了 420 秒超时,把 agent 逼进了"必须清理"的处境。脚本写法先埋雷,清理决策再引爆,事故是两步走成的。

### b. 框架给了什么、没给什么,信息缺口的因果贡献

框架给了:命令会被判危险并提示(首次);"force kill processes (Stop-Process -Force)" 这个 description 文字。

框架没给:本机进程拓扑(哪些常驻服务是 python);Stop-Process 按名匹配的后果半径说明;更窄替代手段的存在(比如框架若提供"终止本会话子进程"的原生工具,agent 根本不必碰进程表)。

因果贡献的诚实评估:信息缺口能解释"它不知道会杀死网关",不能解释"它不去查就杀"。一个合格的 agent 在执行不可逆的广谱操作前应当先 Get-Process python 看一眼清单(这一步是只读的、零风险的),它没做。所以信息缺口是促成因素,不是决定因素。框架的放行机制把"本该第二次弹出的、可能让用户看到完整命令并犹豫一下的提示"吞掉了,这一口是框架实打实的因果贡献。

## 四、改进建议

框架侧三条:

1. 给 `Get-Process <name> | Stop-Process -Force` 这类"管道全量强杀"形态单列一档更重的规则(可参照 POSIX 侧 killall -r 的先例,approval_detection.py:284),其 pattern_key 与单进程 Stop-Process 分离,这样会话级放行不会跨形态外推。规则可直接加在 :238 之后:`\bget-process\b[^\n;|&]*\|\s*stop-process\b`。

2. 把 self-termination 保护(:358)扩展出 Windows 形态:检测 `\bstop-process\b[^\n]*\bpython\b` 或 taskkill /IM python.exe 时,先枚举本机是否有命令行含 gateway run 的 Python 进程,有则升格为硬线或至少强制逐次审批(排除会话级放行)。识别依据现成:gateway-exit-diag.log:96 记录的 argv 就是 main.py gateway run。

3. 提示词/工具描述补丁:在 terminal 工具描述中写明"本机部署的 Hermes gateway 均为 Python 进程;任何按进程名杀 python 的操作会中断全部消息平台服务",并在审批 UI 的命令展示中强制显示完整命令文本而非仅 description,让"allowed for session"的复用在用户面前可见。

使用侧两条:

1. 会话纪律:对"强杀类"命令一律选 once 而非 session。session 放行的粒度缺陷在修好之前,唯一防线是使用习惯。

2. scan_history.py 这类自写脚本的纪律:批量外部命令调用必须用 --batch 类流式接口(git cat-file --batch)或进程池上限,起进程数与 blob 数线性相等的脚本在评审阶段就应否决。本次事故里脚本缺陷是第一因,清理失控是第二因,只修第二因不修第一因,同样的处境还会再出现。

## 五、证据清单

- approval_detection.py:125(_RE_FLAGS 含 IGNORECASE)、:237-238(taskkill/Stop-Process -Force 规则)、:88-121(HARDLINE_PATTERNS 无 Stop-Process)、:116(kill -1 硬线)、:278-284(pkill/killall 分级)、:358(self-termination 规则)、:56-57(硬线"刻意极小"的设计注释)。
- test_approval_windows.py:38("Stop-Process -Force -Name explorer" 必须提示)、:65-66(无强制标志不提示)。
- approval.py:326-332(is_approved 的 session+pattern 二元组)、:356-368(_persist_choice 的 session/always 记账)、:342(approve_permanent)。
- scan_history.py:44(blob_lines 每个 blob 一次 subprocess.run)、:75-79(逐 blob 循环调用)。
- gateway-exit-diag.log:96-97(2026-09-17T07:15:12 gateway.start pid=91316;07:15:19 previous_unclean_exit prior_pid=57152,与 UTC+8 的 15:15 吻合)。
- <PROFILE_DAD>/logs/gateway-stdio.log:662(15:15:33 "exited UNCLEANLY (no exit path ran — SIGKILL / OOM / VM death)",prior pid=66824)。
- gateway_watchdog.log:1-8(2026-09-16 13:24 <PROFILE_DAD> 曾 DEAD 被拉起,pid=66824 即本次被杀的 <PROFILE_DAD> worker)、:625-628(2026-09-17 15:16:04 三网关新 pid 91316/62088/77592 全绿)。
- 任务书时间线(截图描述、Approval "allowed for session" 标记、15:38 手动重启)作为背景事实引用。
