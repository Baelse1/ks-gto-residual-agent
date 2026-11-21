# 阶段 4 智能体研究运行

## 实际运行和判据

在固定几何的中性闭壳层 LiH（3.0 Bohr）、全电子 RKS/LDA_X,VWN 上筛选增广。沿用 STO-3G、阶段 3 的候选指数和同网格 cc-pVQZ 比较值。每个实际候选增广一枚 \(s\) 壳，成本为 +1 AO，当前基组为 6 AO，增广后为 7 AO。各条件下同时比较原子局部筛选、全候选 Schur 排序和固定顺序，另穷举当步合格的 \(s\) 壳。

测量量为以下四项，后三项以 Ha 表示。

1. 候选壳层在旧 Galerkin 空间 \(G\)-正交补中的 Schur 残差分数，\(G=2T+S\)。
2. 在试验基组中固定旧密度组装 \(F[D_B]\)，以新试验空间的低端占据本征值和与旧占据迹之差乘 2，得到冻结谱降幅。
3. 用冻结算符得到的轨道构造新密度，计算该密度处完整 RKS 总能量相对原自洽能量的下降。
4. 在相同试验基组重新收敛 SCF 后测总能量下降，并对同网格的有限 cc-pVQZ 记录绝对偏差。

三条能量路径的度量不同。阶段 4 的谱比较和排序证据来自所测有限候选空间。非线性能量误差认证所需的稳定性常数与连续尾项仍待验证。

## 有因果联系的运行轨迹

表中编号见 [审计表](../evidence/stage4/audit.json)。[原始事件](../evidence/stage4/agent/events.jsonl) 还保存模型理由、工具实参、写入差异、命令、退出状态和工件哈希。论文正文摘录实际转交模型，在本地缓存中以哈希核对。

| 工具行动 | 触发与智能体动作 | 观察与下一步 |
| --- | --- | --- |
| 1–8 | 阶段 3 的两名候选在 Schur 分数和自洽能降之间互换。智能体生成并收窄 Crossref 查询。闭壳层稳定性论文的出版社请求返回 403，随后智能体从项目文献清单找到公开稿并开始阅读。 | 实际读取 Cancès 等的 arXiv 公开稿 HTML 偏移 0–14000，保存来源 ID 32c8700cdcb7 和分开的来源主张、项目推断、未核验条件。依据文章关于逆 Jacobian 的讨论，选择拆分冻结算符和重新自洽的比较。第二次正文读取返回同一摘录。 [实际阅读原稿](https://arxiv.org/html/2111.01470) |
| 9–16 | 查阅数值后端、配置和阶段 3 设计，编写第一版 Python 探针。代理配置文件的一次读取超出权限。调用编译和实际数值命令并读取 JSON。 | 编译和执行均返回 0。四个候选的重新自洽均成功。H_s20 与 Li_s08 的名次翻转首见于冻结谱降幅。三种策略均选 Li_s32。 [第一版代码](../evidence/stage4/versions/13-stage4_probe.py) · [原始数据](../evidence/stage4/results/15/stage4_probe.json) |
| 17–22 | 第一次后续调用再次跑了同一设置。智能体读回文件，识别这只是重复，并改写程序以移除共同优胜壳 Li_s32，重算原子局部积分，并用网格 3 和 4 对照。 | 原设置和删壳设置均成功求解。删壳后二级网格上三种策略仍选择 Li_s08，而 H_s20 的自洽总能量更低。原子局部分数接近，促使模型提出权重参数敏感性分析。 [同设置复跑](../evidence/stage4/results/17/stage4_followup.json) · [第二版代码](../evidence/stage4/versions/20-stage4_probe.py) · [两级网格与删壳结果](../evidence/stage4/results/21/stage4_followup.json) |
| 23–37 | 智能体取回大型 JSON 中缺失的网格 4 结果。它只改变删壳设置下的局部化参数 \(\gamma\)，并复用各网格的单壳 SCF 结果。两次编译均定位到第 131 行未闭合的字符串。智能体将换行写法改为 chr(10)，复检和执行均返回 0。 | 两个网格与三个 \(\gamma\) 值下，三种策略都选 Li_s08。智能体随后读回参数子树和局部化实现，留下可复用原 Riesz 向量的更宽扫描问题。 [失败版](../evidence/stage4/versions/27-stage4_probe.py) · [修复版](../evidence/stage4/versions/31-stage4_probe.py) · [权重扫描结果](../evidence/stage4/results/33/stage4_probe.json) |

## 同预算结果

所有表项都是同网格、同参考、同新增成本下的自洽结果。三个实现的选择在以下条件中一致。

| 候选字典 | 网格 | 局部 / 全局 / 固定选择 | 该选择的参考偏差（mHa） | 穷举最优候选及偏差（mHa） |
| --- | ---: | --- | ---: | --- |
| 原字典 | 3 | Li_s32 / Li_s32 / Li_s32 | 109.843 | Li_s32，109.843 |
| 原字典 | 4 | Li_s32 / Li_s32 / Li_s32 | 109.844 | Li_s32，109.844 |
| 移除 Li_s32 | 3 | Li_s08 / Li_s08 / Li_s08 | 120.614 | H_s20，120.413 |
| 移除 Li_s32 | 4 | Li_s08 / Li_s08 / Li_s08 | 120.615 | H_s20，120.413 |

在网格 3 下，H_s20 较 Li_s08 的冻结谱降幅大 0.147 mHa，冻结算符所得密度处的总能量降幅大 0.054 mHa，自洽总能量降幅大 0.202 mHa。网格 4 中后者的差约 0.202 mHa。排序翻转在固定旧密度的线性求解中已经出现。此结果确认了 Schur 分数与能量降幅的排序存在实测差别，并把进一步区分曲率因素的研究限定在后续检验。

删壳后，权重取 \(\gamma=0.25,\ 0.5,\ 1.0\) 时，Li 与 H 的原子平方指标差保持为正，六次观测在 \(1.872\times10^{-6}\) 至 \(4.655\times10^{-6}\) 之间。局部选择由此保持在 Li，且三种策略都选 Li_s08。这个范围内未发现原子筛选带来的额外收益。它也给出了一个可定位的排序误差，即三种策略均没有挑中穷举中总能量更低的 H_s20。上述结果限于这一个固定几何、小候选字典、+1 AO 和两个网格。

第一版程序只含网格 3。第二版在网格 3 和 4 共享相同单壳试验空间的 SCF 结果。第一版命令工具记录 4.685 秒，第二版删壳与两级网格的命令记录约 8.065 秒，权重扫描为 6.221 秒，含进程启动与 I/O。首步候选 SCF 为 8–9 次迭代。完整运行数据保留每个候选的时间、收敛、格点指纹和条件诊断。

[排序图](../evidence/stage4/ranking.png) 用第一版的观测数据绘制。图左是四种度量的名次，图右是 H_s20 相对 Li_s08 的三条能量降幅差。数值与版本关联见审计表。

## 复现与检查点

从项目根目录启动研究 CLI。新运行使用新目录，已有数值结果可单用下方 Bash 命令重算。

```powershell
.\.venv\Scripts\python.exe -m ksagent --config config/agent.stage4.json --run-dir runs/stage4-new --transport https --steps 12
.\.venv\Scripts\python.exe -m ksagent --config config/agent.stage4.json --run-dir runs/stage4-new --resume --transport https --steps 9
```

实际运行保留在 evidence/stage4/agent。首段默认传输完成一次工具行动，下一次模型请求由维护者中止，随后改用 HTTPS。其余各段使用同一检查点，步数上限依次为 12、9、5、8 和 2。累计 38 次模型请求、37 次工具行动，最后按步数预算暂停。 [检查点](../evidence/stage4/agent/checkpoint.json) · [维护者干预记录](../evidence/stage4/supervision.md)

以下命令在 Linux 或 WSL 的项目根目录执行，使用阶段 3 的科学环境。绘图另需 matplotlib 3.11.2。

```bash
bash scripts/reproduce_stage4.sh 13 runs/stage4-recheck/original.json
bash scripts/reproduce_stage4.sh 20 runs/stage4-recheck/ablation.json
bash scripts/reproduce_stage4.sh 31 runs/stage4-recheck/partition-sweep.json
python scripts/plot_stage4.py evidence/stage4/results/15/stage4_probe.json runs/stage4-recheck/ranking.png
```

归档工具通过统一 diff 恢复每个版本并验证 SHA-256，再把验证命令和对应数据配对。维护者在隔离的暂存目录重跑了三个成功版本，三个结果的非计时字段都与归档数据逐项相同。该重算独立于智能体轨迹。 [复现核对记录](../evidence/stage4/reproduction-check.json)

