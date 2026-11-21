# 跨阶段进度

- 当前阶段为阶段 6 发布交付。2026-11-21（上海）。
- 项目根目录为 D:\ksagent。阶段 2 使用 Windows PowerShell 驱动智能体，科学计算使用 D 盘 WSL 环境。
- 阶段 1 已核验。完成原始论文定向查阅、Crossref 查询、实际 ChatGPT CLI 请求和 LiH 有限候选残差冒烟。主问题固定为 LiH/RKS/LDA 的同 AO 预算比较。详见 [阶段 1 环境](docs/environment.md)、[文献](docs/literature.md)、[设计](docs/design.md) 和 [原始证据](evidence/stage1/)。
- 阶段 2 已实现。CLI 为 python -m ksagent；smolagents v1.26.0 ToolCallingAgent 使用 CodexModel 适配器，运行工具由 config/agent.example.json 授权。参见 [启动和上游说明](docs/agent.md)、[真实模型事件](evidence/stage2/events.jsonl)、[检查点](evidence/stage2/checkpoint.json)。操作员直接工具验证包含读写与 diff、命令退出状态、真实 LiH 重算和公开 PDF 提取。参见 [读写与流程检查](evidence/stage2-tool-check.json)、[数值命令](evidence/stage2-local-command.json)、[文献工具](evidence/stage2-local-source.json)。
- 真实运行两次续跑，累计 4 次模型调用和 4 次工具行动。Crossref 两次返回 HTTP 200；两次正文访问受站点范围限制。后续模型行动尝试检索预印本，检查点保留了这个待查问题。维护者独立验证作者公开 PDF 及来源笔记工具。自主从题录定位可访问正文、写代码并根据数值反馈继续的证据在阶段 4 取得。
- 阶段 3 已验证。独立 WSL 科学环境位于项目 .venv-science。LiH 在网格 3/4/5 的原子筛选和全候选路径相同；新增 5 AO 时，两者相对固定顺序的偏差少约 4.705 mHa。两套有限参考替换后排序一致。首步两个中间候选的残差排序与实际能降对调。H₂ 原子对称性、SCF 失败控制和近线性拒绝均已核查。见 [基线与复现](docs/numerics.md)、[表格](evidence/stage3/matched-budget.csv)、[敏感性](evidence/stage3/sensitivity-summary.json) 和 [原始记录](evidence/stage3/)。
- 阶段 4 已完成。37 次真实工具行动覆盖公开论文查找与阅读、代码写入、语法失败与自行修复、LiH +1 AO 实验与两次受控追问。H_s20 和 Li_s08 的名次在冻结谱步骤已互换。删壳和权重扫描中三种策略仍选 Li_s08，穷举中 H_s20 的重新自洽总能量约低 0.202 mHa。适用范围为固定 LiH、两个网格及有限参考和候选集。见 [研究运行](docs/research-run.md)、[审计表](evidence/stage4/audit.json)、[检查点](evidence/stage4/agent/checkpoint.json)、[排名图](evidence/stage4/ranking.png)。
- 阶段 5 已完成。7 页中文报告保留指定题目，按行动号说明证据如何改变决策，给出冻结有限维子空间界、证明、两组矩阵核查与实际局限。核对了 20 个源文件哈希，逐页检查中文、表格、公式、图和链接。见 [PDF](output/pdf/ksagent-report.pdf)、[源与构建](report/README.md)、[逐页质检](evidence/stage5/pdf-qa.json)。
- 阶段 6 交付。[个人公开仓库](https://github.com/Baelse1/ks-gto-residual-agent) 使用 GitHub API 认证身份创建。干净环境复核了真实文献工具调用、阶段 3 全基线和两个负对照、阶段 4 的权重扫描以及 PDF 重建。见 [复现记录](evidence/stage6/clean-reproduction.json) 和 [第三方材料与许可](THIRD_PARTY_NOTICES.md)。连续对偶尾、自洽稳定性和一般可靠界仍为研究问题。
- 后续复核时可读取本文件并检查 Git 状态。

```powershell
Get-Content -Encoding UTF8 D:\ksagent\PROGRESS.md
git -C D:\ksagent status --short --branch
```
