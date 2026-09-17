# Stop-Process 误杀三网关事故归因评审(deepseek-v4-pro)

评审人:deepseek-v4-pro 会话。评审范围限于任务书与指定材料,全部判断附证据出处。

## 一、归因结论

两者皆有,模型决策为主因,框架缺陷为次因。

主因在模型:事故命令的目标绑定、后果枚举、工具语义三层全部出错,而且错得可以静态定位。agent 要杀的是"自己起的扫描子进程",可它自己写的 scan_history.py 起的子进程是 git cat-file,不是 python(scan_history.py:44)。按进程名杀 python 既杀不到肇事子进程,又把本机所有 python 进程一网打尽,连三个 gateway worker 一起杀掉。这个决策在任何框架下都是错的,不是框架信息不全能解释的。

次因在框架:框架确实存在三个真实缺陷——Windows 侧没有"全量/无差别杀"的范围识别(Stop-Process -Force 与 POSIX 的 kill -1 严重性分层不对等)、会话级放行按命令形态而非命令目标生效、检测层不注入进程归属与后果范围信息。这三个缺陷没有阻止本可被阻止的破坏,并且其中的会话级放行机制直接让这次命令未经人工确认就执行了。

一句话归因:模型在审批闸门本可拦住它时做出了一个三重错误的决策,框架则没有为"按解释器名无差别杀进程"这个形态提供任何兜底。

## 二、框架侧核查

### a. 检测覆盖:"无差别杀全部进程"有没有规则

有部分覆盖,覆盖的是动作,不是范围。

POSIX 侧分层完整。kill -1 在硬线层(approval_detection.py:116,"kill all processes"),不可绕过,连 --yolo 都不放行;kill -9 -1 在危险层(approval_detection.py:278);pkill -9 在危险层(approval_detection.py:279)。Windows 侧只有动作级规则:taskkill /F(approval_detection.py:237)与 Stop-Process -Force(approval_detection.py:238),两条都在可审批的危险层,描述分别是 "force kill processes (taskkill /F)" 和 "force kill processes (Stop-Process -Force)"。

事故命令 `powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force"` 按规则顺序静态推导,命中第 238 行(正则 `\bstop-process\b[^\n]*\s-force\b`,事故文本中 "Stop-Process -Force" 同段出现必然命中),判定结果为危险、key 为 "force kill processes (Stop-Process -Force)"。这与任务书截图"该命令带有 Approval 标记"一致(task.md:17)。

关键缺口在范围识别。"Stop-Process -Force -Name explorer" 与 "Get-Process python | Stop-Process -Force" 在检测层是同一个 key、同一句描述、同一个严重级别。前者的后果是杀一个桌面程序,后者的后果是杀本机全部 python 进程,其中藏着三个网关 worker。框架不区分。硬线层有 POSIX 的 kill -1,却没有 Windows 对应物——Windows 上的"全量杀"形态与"单目标杀"形态一样只走可审批的危险层。测试用例印证了这个粒度:test_approval_windows.py:38 只测了单目标形态(Stop-Process -Force -Name explorer),全文没有任何"管道全量杀"或"-Name *"通配的用例。

我实测时还拿到三个直接证据,证明检测层确实在逐文本扫描、分层生效:我在终端里运行一个只读验证脚本,第一次因脚本文本含 "kill -9 -1" 字样被硬线拦截(理由 "kill all processes",不可绕过);第二次因文本含 "taskkill /F /IM" 字样被审批层拦截(理由 "force kill processes (taskkill /F)",单查询模式无人批准);第三次因 python heredoc 形态被审批层拦截(理由 "script execution via heredoc")。三次拦截的触发词都只是脚本里的字符串字面量,不是要执行的命令。检测层灵敏、分层正确,但它看的是文本形态。

### b. "会话级放行"的语义与风险

approval_detection.py 的模块 docstring 声明自己是纯分类模块,不存审批状态(第 2-4 行)。但第 448-460 行的 _PATTERN_KEY_ALIASES 机制暴露了审批系统的存储语义:审批条目按 pattern key(即规则描述)持久化,注释原文是 "the old approval key, kept for backwards compatibility with stored allowlist/session entries"——存在按 key 存储的 allowlist 与 session entries,存储实现在 tools/approval.py,不在本次指定材料内,此处不展开其代码。

由此可以确定会话级放行的粒度:放行的是 pattern key,也就是命令形态。同一会话内批准过 key "force kill processes (Stop-Process -Force)" 之后,该会话内所有命中同一 key 的命令都不再提示,无论目标是什么。任务书截图显示本次命令 "allowed for session"(task.md:17),证实这条路径走通了。

风险就在这里。审批的知情同意绑定在命令形态上,而不是绑定在执行后果上。批准过一次 "Stop-Process -Force -Name explorer" 之后,"Get-Process python | Stop-Process -Force" 因为形态相同就免审放行,而这两条命令的破坏范围相差三个量级。放行语义实际上退化成了"这类命令我同意过",而不是"这次执行的后果我同意"。

### c. CLI agent 终端与 gateway worker 之间有无进程隔离或归属识别

无隔离,归属识别也缺失。

进程层面,CLI 会话的 terminal 与三个 gateway worker 在同一台 Windows 主机、同一用户、同一个 python 解释器下运行,全是 python.exe,进程层没有任何隔离机制。gateway-exit-diag.log:96 显示 gateway worker 的 argv 是 python 跑 main.py gateway run,与普通 python 进程没有可区分的命名。

检测层面,approval_detection.py 是纯函数,输入命令字符串,输出 key 与描述,不接触本机进程清单,没有任何"本机还跑着什么"的上下文注入点。它对进程归属的唯一启发式是第 358-362 行的自终止保护:三条规则要求命令文本中出现 hermes、gateway 或 cli.py 字样(pkill/killall 与 hermes 字样共现,或 kill 与 pgrep/pidof 展开共现),而且只覆盖 POSIX 命令,没有 taskkill 或 Stop-Process 的对应物。按进程名杀 python 时,命令文本里根本没有这些词,这条启发式必然失效——它在 POSIX 侧也拦不住 pkill -9 python(我静态推导:该命令不命中 358 行规则,只命中 279 行的普通强杀规则)。在 Windows 侧连对应规则都不存在。归属识别在"按解释器名杀进程"这个形态下是结构性缺失。

### d. 检测/审批侧是否把后果范围告知模型

没有。approval_detection.py 全文不产出提示词,检测结果只有一句静态描述("force kill processes (Stop-Process -Force)")。模块内不存在任何主机上下文注入点,审批交互层(不在指定材料内)能拿到的也只有这句描述。框架没有把"本机运行着三个 python gateway worker"、"按名称匹配将命中 N 个进程"这类后果信息告诉模型,也没有告诉审批人。测试用例同样只断言真/假,没有任何后果提示相关用例。

## 三、模型侧批评

### a. 决策错在哪一层

三层全错,核心是目标绑定错误。

第一层,目标绑定错误。agent 明确知道要杀的是自己起的扫描子进程(任务书截图:它先承认"逐个 blob 起子进程"是灾难级写法,然后动手杀)。它自己写的 scan_history.py 里,子进程是 subprocess.run(["git", "cat-file", "blob", ...])(scan_history.py:44),每个 blob 一次进程启动,循环在 scan_history.py:75-79。也就是说,肇事子进程是 git,不是 python。按进程名杀 python 杀不到肇事者,却覆盖了全机所有 python 进程——包括三个网关 worker、包括它自己的扫描主进程。正确的绑定是把"我的子进程"枚举成具体 PID 集,或者直接杀掉卡死的父进程(扫描脚本自身),子进程随进程树终结。它跳过了这层枚举,直接从"我的子进程"退化成"所有 python"。

第二层,后果枚举不全。它枚举后果时停在了自己的会话边界:杀 python 会怎样?它只想到了自己的扫描脚本会停。全机 python 进程的持有者清单——三个 profile 的网关 worker、看门狗环境、其他 python 工具——一项都没有进入它的推理。本机有 96GB 内存的工作站上,一个 420 秒超时的卡死扫描,恢复手段却是范围无界的全量杀。

第三层,工具语义误用。Stop-Process 的 -Name 参数语义是全名匹配所有同名进程,-Force 跳过优雅退出,这两个语义是它自己写命令时选定的,它知道自己在选什么。但它没有把这些语义映射回后果:"匹配所有 python 进程"乘以"-Force 跳过优雅退出",等于全机 python 无警告 SIGKILL。另外还有一个更细的误用:恢复手段与目标之间粒度落差巨大。正确路径是 Get-Process 列清单、核对归属、按 PID 精准杀,或者等 terminal 调用超时自然返回后再处理。它选择了不可逆、无界、且杀不到目标的那一条。

### b. 信息缺口对决策的因果贡献

框架给了模型:危险命令检测、审批交互、会话级放行(同类命令已批准过)。框架没给模型三样东西:第一,本机存在三个 python 网关 worker 的事实——指定材料中不存在任何向 CLI 会话注入此信息的点,模型的上下文里没有任何证据表明它知道这件事;第二,审批描述里没有后果范围;第三,会话级放行不提示"本次命令与上次批准的命令目标不同"。

因果贡献的判断:信息缺口是促成条件,不是直接原因。即使上下文里写明"本机有三个网关 worker",按进程名全量杀 python 依然是错误决策——它杀不到自己起的 git 子进程这一点与网关信息无关。但网关信息缺失维持了一个错误的心智模型:"本机只有我这个会话在跑 python"。这个假设一旦在上下文里被击穿,拦截概率会显著提高,因为"杀全部 python"这个选项会在枚举时直接被否定掉。所以缺口的贡献是:它放大了模型第一层的目标绑定错误,把本可一眼识破的误杀变成了顺理成章。

## 四、改进建议

框架侧:

1. 给 Windows 补"全量杀"的范围识别,与 POSIX 的 kill -1 分层对齐。在 approval_detection.py 第 236-238 行的 Windows 强杀规则处新增独立 key,识别 `Get-Process <name> | Stop-Process -Force`、`Stop-Process -Force -Name *`(通配目标)这类"按名称匹配全部进程"的形态,描述明确写"将强制终止本机全部同名进程";考虑将其升入硬线层,或至少排除在会话级放行之外。
2. 给自终止保护补 Windows 对应物,并注入主机上下文。approval_detection.py 第 358 行的 pkill/killall 自终止规则只有 POSIX 形态,应增加 taskkill /F /IM 与 Stop-Process -Force -Name 的目标名检查;更根本的方案是在审批提示构造处(在 tools/approval.py,不在本材料内)注入主机上下文,例如"本机当前有 N 个 python 进程,其中 3 个是 Hermes gateway worker(default/<PROFILE_DAD>/<PROFILE_MOM>)"。
3. 细化会话级放行的粒度。对强杀类 key,会话放行条目应携带目标参数(进程名或 PID),目标变化时重新审批;全量形态不参与会话级放行。
4. 补测试。test_approval_windows.py 增加三个断言:Get-Process 管道形态被标记、-Name * 通配形态被标记、且二者的 key 与单目标形态(现第 38 行)不同。

使用侧:

1. 立一条全会话工作纪律:禁止按进程名或解释器名无差别杀进程;杀进程前必须先列清单核对归属,按 PID 精准杀;本机 python 进程承载三 profile 网关服务,凡涉及杀 python 的命令必须先确认三网关状态。
2. 给 CLI 会话的系统提示或 terminal 工具描述打补丁,写明"本机常驻三个 Hermes gateway worker(default/<PROFILE_DAD>/<PROFILE_MOM>,进程 python.exe,由看门狗与计划任务守护),禁止 Stop-Process -Force -Name python、Get-Process python | Stop-Process -Force、taskkill /F /IM python.exe 一类命令"。
3. 扫描类脚本纪律:大批量 git 对象访问必须用 cat-file --batch 流式批处理或 git log -p --all,禁止逐 blob 起子进程。scan_history.py:44 的写法是反例,扫描脚本若重写应直接改掉这条。

## 五、证据引用

事故与审批链:

- 事故命令原文:task.md:7。
- agent 承认灾难写法后执行命令、Approval 标记、allowed for session:task.md:17。
- 三网关重启时间 15:15:12/15:15:31/15:15:51、看门狗 15:16:04 全绿:task.md:18-19。

源码:

- Stop-Process -Force 规则:approval_detection.py:238。
- taskkill /F 规则:approval_detection.py:237。
- 硬线 kill -1:approval_detection.py:116;危险层 kill -9 -1:approval_detection.py:278。
- 自终止保护仅 POSIX 且要求 hermes/gateway/cli.py 字样:approval_detection.py:358-362。
- 会话条目按 pattern key 存储的注释:approval_detection.py:454。
- 测试仅覆盖单目标形态:test_approval_windows.py:37-38;无 -Force 不标记:test_approval_windows.py:65-66;全文无全量杀用例。
- 子进程爆炸写法:scan_history.py:44(subprocess.run 每 blob 一次 git cat-file)、scan_history.py:75-79(逐 blob 循环,无批量无并行)。

日志:

- default 网关 15:15:12 重启、prior_pid 57152、previous_unclean_exit、最后心跳 07:05:35 UTC:gateway-exit-diag.log:96-97。
- 管理员 15:38 干净重启(exit_clean):gateway-exit-diag.log:98-100。
- <PROFILE_DAD> 网关 15:15:33 重启、"exited UNCLEANLY (no exit path ran — SIGKILL / OOM / VM death)"、prior pid=66824:profiles/<PROFILE_DAD>/logs/gateway-stdio.log:662。
- 事故前 15:06:01 三网关 pid(57152/66824/33012)全绿:gateway_watchdog.log:621-624。
- 事故后 15:16:04 三网关新 pid(91316/62088/77592)全绿、微信重连:gateway_watchdog.log:625-628。
- 2026-09-16 13:24 <PROFILE_DAD> DEAD 被看门狗经计划任务拉活(自愈机制有效):gateway_watchdog.log:1-4。

实测(本评审过程中真实遇到的三次拦截):

- 验证脚本文本含 "kill -9 -1" 字样,被硬线拦截,理由 "kill all processes",不可绕过。
- 验证脚本文本含 "taskkill /F /IM" 字样,被审批层拦截,理由 "force kill processes (taskkill /F)",单查询模式无人批准。
- python heredoc 形态被审批层拦截,理由 "script execution via heredoc"。

这三次拦截共同证明:检测层逐文本扫描、硬线与危险层分层生效、Windows 强杀规则已接入,并且检测的判定依据是命令文本形态而非执行后果。
