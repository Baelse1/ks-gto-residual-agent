# 最小环境、实际命令与智能体选型

日期 2026-11-21（上海）。当前会话根目录只有未提交的 Git 元数据，项目另在 D:\ksagent 初始化。D 盘开始时约有 20.2 GB 空闲。Windows 12 逻辑核，约 16 GiB 内存，RTX 4060 Laptop GPU 约 8 GiB 显存。单线程 CPU 冒烟已经足够。Git 2.56.0.windows.4 可用，Crossref、公开论文网页、PyPI、GitHub 的 smolagents tag 可达。GitHub REST releases/latest 的一次探测得到 403 限额响应，发布身份和远端将在阶段 6 核对。XeLaTeX 和 pdftoppm 可定位，中文 PDF 尚未编译。

| 项目 | 实际验证或阶段计划 |
| --- | --- |
| 科学计算 | WSL Ubuntu 的 D 盘既有虚拟环境，Python 3.14.4，PySCF 2.15.0，NumPy 2.5.4，SciPy 1.18.1，h5py 3.16.0 列入冻结文件。Windows Python 3.13 上下载 PySCF 2.15.1 wheel 成功，安装进程以 -1073741819 异常退出。现采用 [PySCF 官方安装说明](https://pyscf.org/user/install.html) 支持的 WSL 路径。现有 WSL 提示 NAT localhost 代理未镜像，数值冒烟成功。 |
| 智能体框架 | [Hugging Face smolagents v1.26.0](https://github.com/huggingface/smolagents/releases/tag/v1.26.0)，Apache-2.0，实查 Git tag 指向 `12c1bc820eca50ace6f80a21d90426d41d74f845`。已在 Windows D 盘环境安装，`ToolCallingAgent` 和 `Model` 导入及 pip check 通过。用 [版本化 API](https://huggingface.co/docs/smolagents/v1.26.0/en/reference/agents) 的工具调用、分步及回调接口。优先使用明确工具的 ToolCallingAgent。CodeAgent 允许模型生成代码并直接执行，和本项目按配置授权具体操作的接口目标不同。 |
| 首选模型调用 | [开源 Codex CLI](https://github.com/openai/codex)（Apache-2.0），实测版本 `0.171.0-alpha.13`，模型 `gpt-6.2-sol`。当前 ChatGPT 登录可经 CLI 请求，WebSocket 尝试超时后由 CLI 切换 HTTPS 成功。核对 [非交互文档](https://learn.chatgpt.com/docs/non-interactive-mode)。建议阶段 2 先验证结构化输出，并给冷启动留至少 180 秒且限制总调用次数。 |
| 模型备选 | localhost:11434 本次拒绝连接，未发现正在服务的 Ollama，未看到模型 API 密钥环境变量。可另测 [llama.cpp](https://github.com/ggml-org/llama.cpp)（MIT）和 [Qwen3-4B-GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF)（Apache-2.0）；本次未下载权重或验证推理。 |
| 研究资料 | 首选 Crossref 公开 works 查询，再按 DOI、出版社、arXiv 公开稿解析。按所实际读取的页/节记录笔记及访问失败。核心查询可用 Python 标准库；开放 PDF 的文本提取可使用外部 pdftotext（阶段 2 测试）。 |
| 尚待实现 | smolagents 和 Codex CLI 均未修改上游源码。阶段 2 才添加模型适配、受控检索和项目读写工具、工具差异、检查点、日志和预算。命令执行由外层对具体命令校验，模型以结构化动作提出请求。模型仅接收课程仓库中审核过的输入及公开文献摘要。 |

## 已执行的命令与复现入口

PowerShell，从 D:\ksagent 运行。Linux 数值冒烟使用该机器已有的 D 盘科学环境。独立环境的重建和冻结验证在后续覆盖。

```powershell
Set-Location D:\ksagent
git status --short --branch
py -0p
wsl --list --quiet
wsl -d Ubuntu -- python3 --version
git ls-remote https://github.com/huggingface/smolagents.git refs/tags/v1.26.0
py -3.13 -m venv .venv
$env:TEMP = "$PWD\.scratch"
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m pip --disable-pip-version-check --no-cache-dir install --only-binary=:all: pyscf==2.15.1
.\.venv\Scripts\python.exe -m pip --disable-pip-version-check --no-cache-dir install smolagents==1.26.0
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "from smolagents import ToolCallingAgent, Model; print(ToolCallingAgent.__name__, Model.__name__)"
codex login status
codex exec --ephemeral --sandbox read-only "Return exactly KS_STAGE1_MODEL_OK. Do not use tools."
wsl -d Ubuntu --cd /mnt/d/ksagent -- env PYSCF_TMPDIR=/mnt/d/ksagent/.scratch OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /mnt/d/ks_research/.venv-pyscf/bin/python scripts/stage1_smoke.py --output evidence/stage1/numerics.json
```

创建独立数值环境时从 WSL 在项目内执行 `python3 -m venv .venv-science`，将 `TMPDIR` 和 `PYSCF_TMPDIR` 指向此项目的 `.scratch`，以该环境的 Python 安装 `requirements-numerics.txt` 并重跑冒烟。安装和运行工具可分别选 Windows/WSL。

模型结果与重试过程见 [脱敏摘要](../evidence/stage1/model-probe.txt)。实测阶段 1 的 Crossref URL 和输出见 [题录日志](../evidence/stage1/crossref.json)，数值见 [结果 JSON](../evidence/stage1/numerics.json)。可行性脚本为当前协作会话编写并调用。阶段 2 验收必须由新 CLI 启动，真实模型自主构造一次文献查询、调用工具、记录退出状态及引用，并用检查点重启。之后验证失败反馈、文件差异、预算耗尽和回放标识。
