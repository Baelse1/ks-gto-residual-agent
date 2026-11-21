# 阶段 2 研究智能体

## 安装与启动

在 Windows PowerShell 中，从项目根目录运行以下命令。需要 Python 3.13（当前已验）、到公开文献站点的网络、Git 和已经通过账号验证的 Codex CLI。PDF 工具还需要 pdftotext；没有该命令时可读 HTML 公开稿。数值命令的示例用 Ubuntu WSL，科学依赖见 [环境](environment.md)。首次创建环境时设置 D 盘暂存目录，已有环境可直接运行。

```powershell
Set-Location D:\ksagent
New-Item -ItemType Directory -Force .scratch | Out-Null
$env:TEMP="$PWD\.scratch"
$env:TMP=$env:TEMP
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip --no-cache-dir install -r requirements-agent.txt
codex login status
.\.venv\Scripts\python.exe -m ksagent --config config/agent.example.json --run-dir runs/my-literature --steps 1
.\.venv\Scripts\python.exe -m ksagent --config config/agent.example.json --run-dir runs/my-literature --resume --steps 2
```

新运行使用一个新的运行目录。续跑重新加载目标、证据、下一问题和近期工具结果，并核对配置文件哈希。步数、真实模型调用数和运行时长是每次调用的上限；检查点另累计总步数和调用数。单次模型请求设有超时。ChatGPT 登录路径使用账号现有额度，样例预算按调用次数计；CLI 能报告 token 用量时写入日志。观察到传输降级和约两分钟的首步延迟，默认单请求上限为 185 秒。

`--transport https` 使用同一 ChatGPT 登录直接走 HTTPS，在阶段 4 已实测。读取大 JSON 时，文件名可追加 `#json=/path/to/section` 选择所需子树。

## 上游和项目扩展

- [smolagents v1.26.0](https://github.com/huggingface/smolagents/tree/v1.26.0)，Apache-2.0，tag 指向 12c1bc820eca50ace6f80a21d90426d41d74f845。本项目使用 ToolCallingAgent 消化观察并逐步执行，新增了 CodexModel 适配器、项目研究工具、JSON 配置、检查点和 JSONL 日志。上游包按版本安装。
- [Codex CLI](https://github.com/openai/codex)，Apache-2.0，实际运行版本 0.171.0-alpha.13。适配器将 smolagents 消息和工具 JSON Schema 发给 Codex CLI，由外层执行一个模型提出的结构化动作。模型调用在 D 盘临时目录用 read-only、ephemeral 启动，忽略用户配置，检查事件中是否出现内层工具调用。样例使用 gpt-6.2-sol。
- 研究循环是识别知识缺口、请求证据、执行、读取反馈并更新下一问题。检索从 Crossref works 获取题录。正文工具记录最终 URL、提取范围和摘录哈希；模型可用来源 ID 分别写下论文主张、项目推断和未决条件。网页、论文、命令结果作为研究数据传入。
- 文件变更限定在配置列出的目录，返回统一 diff 和文件哈希。命令工具运行配置中的固定 argv，记录退出状态、输出尾部和工件哈希；数值 alias 是该机器 D 盘 WSL 路径示例。可编辑区和可执行 alias 由项目所有者核对，命令进程以本机用户权限运行。若配置执行研究脚本，脚本本身可调用该用户可访问的系统资源。密钥来自现有登录或环境，Git 忽略本地环境文件、运行目录和缓存。公开样例只放可分享材料。
- 使用真实模型的记录在 runs/ 或显式选择的 evidence/ 下。events.jsonl 依时间记录请求、理由、工具参数、观测、状态。checkpoint.json 保存最新状态。作者稿的正文提取仅在 D 盘本地缓存，运行记录保留读取范围和哈希。正文字节变动可能改变同一 URL 的哈希。

## 集成核对

```powershell
$env:PYTHONPATH="$PWD"
.\.venv\Scripts\python.exe scripts/stage2_check.py
```

这是本地工具的直接调用检查。覆盖写入、读取、差异、越界拒绝、命令退出码 0 和 7、工件哈希、调用预算及检查点。见 [集成检查结果](../evidence/stage2-tool-check.json)。维护者另用同一工具层执行了 WSL LiH 冒烟、公开 PDF 提取和来源笔记持久化。见 [本机命令日志](../evidence/stage2-local-command.json)、[本机数值产物](../evidence/stage2-smoke.json) 和 [本机正文与笔记检查](../evidence/stage2-local-source.json)。

真实模型的搜索与恢复见 [事件日志](../evidence/stage2/events.jsonl) 和 [检查点](../evidence/stage2/checkpoint.json)。开始运行使用 `--steps 1`，随后用同一个目录先 `--resume --steps 2`，再 `--resume --steps 1`。模型发起的首轮题录检索和末轮预印本线索检索均返回 HTTP 200 和五条记录。中间两次正文请求都遇到站点限制。维护者在第三次启动前补充 RSC 主机支持，并完善了拒绝反馈。末轮仍停在题录和预印本线索，作者公开 PDF 提取由维护者独立验证。四次模型调用均经历 HTTPS 降级，耗时约 119–129 秒。
