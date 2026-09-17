# 任务书:Stop-Process 误杀三网关事故归因评审

## 事故背景

2026-09-17 15:10(北京时间),本机(HP Z6 G4 工作站,Windows 11)一个 Hermes CLI 会话(主模型 deepseek-v4-pro,DeepSeek 官方 API)在审计 git 仓库时发生事故。该会话的 agent 自写脚本 scan_history.py 逐个 blob 起子进程,大仓库扫描极慢并卡死(单次 terminal 调用 420 秒超时)。agent 随后执行:

powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force"

该命令无差别强制杀死本机全部 Python 进程,导致三个 Hermes gateway worker(均为 Python 进程,承载 default/<PROFILE_DAD>/<PROFILE_MOM> 三个 profile 的微信平台服务)被 SIGKILL,微信端服务中断约 5 分钟,之后被守护机制自动拉起恢复,看门狗确认三平台重连。

## 用户的核心问题

这是 DeepSeek 模型(deepseek-v4-pro)的决策缺陷("模型弱智"),还是 Hermes 框架/源码的缺陷?请给出独立归因判断,不预设立场。

## 已核实的时间线(证据链)

- 15:10:25-15:10:53 用户连拍终端截图,其中第 1 张显示:agent 承认"逐个 blob 起子进程,每个仓库几百上千次进程启动"是灾难级写法,然后执行了上述 Stop-Process -Force 命令;该命令带有 Approval 标记且显示 "allowed for session"(会话级放行,即此前同会话已有批准)。
- 15:15:12/15:15:31/15:15:51 default/<PROFILE_DAD>/<PROFILE_MOM> 三网关分别以 previous_unclean_exit(SIGKILL / no exit path ran)记录重启,prior_pid 与死亡时间吻合。
- 15:16:04 看门狗巡逻记录三网关新 pid 全绿,微信与 api_server 重连。
- 15:38 管理员为切换辅助模型手动干净重启三网关(与事故无关的后续操作)。

## 指定材料(只读)

1. Hermes 源码 <HERMES_HOME>\hermes-agent\tools\approval_detection.py —— 危险命令检测逻辑,请特别核查其中对 Stop-Process 类命令的检测规则是否存在、覆盖面如何。
2. Hermes 源码 <HERMES_HOME>\hermes-agent\tests\tools\test_approval_windows.py —— 危险命令检测规则的测试用例。
3. 事故脚本 <WORKSPACE>\audit-mirrors\scan_history.py —— 肇事会话自写的扫描脚本,评估其子进程爆炸写法。
4. 日志抽查(用 read_file 带 offset/limit 或 search_files 切片,勿整文件读入):
   - <HERMES_HOME>\logs\gateway-exit-diag.log(时间戳为 UTC,北京 = UTC+8,查 2026-09-17T07:15 附近)
   - <HERMES_HOME>\profiles\<PROFILE_DAD>\logs\gateway-stdio.log(查 2026-09-17 15:15:33 行)
   - <WORKSPACE>\tools\logs\gateway_watchdog.log(查 2026-09-17 15:16 与 2026-09-16 13:24 两处)

## 评审要求(每份产出,写入指定输出文件)

一、归因结论:模型缺陷 / 框架缺陷 / 两者皆有(请说明主次与理由)。

二、框架侧核查(基于 approval_detection.py 与测试用例的实读):
   a. 危险命令检测是否覆盖"无差别杀全部进程"这类模式?具体规则是什么?
   b. 审批机制中"会话级放行"的语义与风险;
   c. CLI 会话的 agent 终端与 gateway worker 进程之间是否存在进程隔离或归属识别缺失;
   d. 检测/审批侧是否把"后果范围"告知模型(如提示词、工具描述里有无相关警告)。

三、模型侧批评(基于事故决策本身):
   a. agent 明确知道要杀的是"自己起的扫描子进程",却选择按进程名杀全部 python,这个决策错在推理的哪一层(后果枚举不全、目标绑定错误、工具语义误用,还是其他);
   b. 用同一逻辑衡量:框架给了模型什么信息,没给什么信息,信息缺口对决策的因果贡献。

四、改进建议:框架侧、使用侧各至少一条,必须具体可执行(可指向代码位置、配置项、提示词补丁、工作纪律)。

五、证据引用:产出中每条关键判断附实际读到的证据(文件路径 + 行号或关键行原文),不得虚构文件或接口。

## 纪律

只读任务书与指定材料,不得修改任何其他文件;不得修改其他评审者的产出文件;输出用简体中文,按您自然的文风写作;产出必须基于实际读到的内容。
