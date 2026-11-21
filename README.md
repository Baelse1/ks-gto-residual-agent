# 原子中心高斯轨道基下 Kohn–Sham 方程局部残差可靠误差估计与自适应基组增广研究

课程项目当前聚焦中性 LiH 的有限候选空间。固定几何和限制性 LDA，检验原子局部残差能否在相同新增 AO 数下帮助选择增广壳层，并以冻结算符的有限维子空间界验证残差计算。重新自洽的总能量偏差通过实验评估。

## 安装与启动

安装依赖、确认 CLI 登录并启动一个新的文献运行。以下为 Windows PowerShell。

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-agent.txt
codex login status
.\.venv\Scripts\python.exe -m ksagent --run-dir runs/my-literature --steps 1 --transport https
```

智能体基于 [smolagents v1.26.0](https://github.com/huggingface/smolagents/tree/v1.26.0)。项目扩展、检查点续跑和工具权限见[智能体说明](docs/agent.md)。数值研究配置 [agent.stage4.json](config/agent.stage4.json) 保存了原试验的 WSL 路径，其他机器按本机工作目录和科学解释器调整命令别名后开启新运行。

## 复现实验与 PDF

从 Linux 或 WSL 的仓库根目录运行，使用 Python 3.14。

```bash
python3 -m venv .venv-science
.venv-science/bin/python -m pip install -r requirements-numerics.txt
bash scripts/run_stage3.sh runs/stage3-recheck
bash scripts/reproduce_stage4.sh 31 runs/stage4-recheck/partition-sweep.json
```

使用 PowerShell 和 XeLaTeX 生成报告。

```powershell
pwsh -File scripts/build_report.ps1
```

## 材料与证据

- [阶段进度](PROGRESS.md)
- [文献核查](docs/literature.md)
- [子问题与试验协议](docs/design.md)
- [环境、真实命令和阶段 2 入口](docs/environment.md)
- [阶段 1 机器输出](evidence/stage1/)
- [研究智能体安装、启动和日志](docs/agent.md)
- [数值基线、同预算对照及复现](docs/numerics.md)
- [智能体研究轨迹、结果和复现](docs/research-run.md)
- [阶段 4 原始事件与检查点](evidence/stage4/agent/) · [行动、代码与产物审计](evidence/stage4/audit.json)
- [中文 PDF 报告](output/pdf/ksagent-report.pdf) · [报告源文件与构建](report/README.md)
- [第三方材料与许可](THIRD_PARTY_NOTICES.md) · [发布复现检查](evidence/stage6/clean-reproduction.json)
