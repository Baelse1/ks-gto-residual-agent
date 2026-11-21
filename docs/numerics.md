# 阶段 3 数值基线与同预算对照

## 对象、误差与空间

两个固定几何、中性、闭壳层全电子算例均用球谐原子中心 GTO 和 RKS/LDA_X,VWN。主算例 LiH 的 Li 坐标为原点，H 位于 z=3 Bohr。H₂ 的两原子在 z=±0.7 Bohr，仅用于对称性核对。原子标签 Li1、H2 中的数字是原子序号。每步从 MINAO 初猜，SCF 能量阈值 \(10^{-11}\) Ha、轨道梯度阈值 \(10^{-8}\)，最多 100 步。各条件重复求解，没有随机选取。

- 主量 \( |E(B)-E_\mathrm{ref}| \) 是同几何同泛函下，重新自洽的总能量绝对偏差，包含核间排斥。计算同时保存有符号差。主参考 \(E_\mathrm{ref}\) 是同积分网格的 cc-pVQZ，强度检查改用 cc-pV5Z。两者的差是有限参考敏感性，连续基组极限仍待确定。另求选取字典全部壳层的自洽能量。
- \(B\) 是当前求解的 Galerkin 空间，\(U\) 是初始 STO-3G 与固定候选壳层的并空间。组装 \(F_U[D_B]\) 时嵌入当前占据系数，保存原子中心、角动量、指数、收缩系数和交叉重叠映射的检查。SCF 与冻结算符使用相同的格点和权重，其 AO 筛选表分别按各自基组构造。
- 由 \(M=C^TF_UC\) 构造矩残差 \(r=F_UC-S_UCM\)。旧空间报告最终重建 Fock 的广义本征残差、SCF 梯度和 \(B\) 上的 \(G=2T+S\) 对偶范数。候选量计算于 \(U\cap B^{\perp_G}\)。用 Schur 投影去掉 \(B\) 分量，再以相应 Riesz 向量能量密度和高斯单位分解积分，得到各原子的平方局部指标。记录局部积分、解析 \(G\) 范数、占据旋转不变性、\(S\)-正交性及电子数检查。
- 整个候选补空间的分量可诊断字典可见方向。单壳层的 Schur 范数用于排序。留出壳层在 \(U\) 之外作额外探测，未参与选取。另在满足 \(\delta>0\) 的有限冻结矩阵上检查 [子问题中的占据子空间界](design.md#冻结算符有限维核查)。一般自洽误差上界需要连续空间尾项和非线性稳定性信息。
- 候选选择以完整壳层为单位，落实固定的 \(s,p,s\) 增广序列，各步实际新增 1、3、1 个球谐 AO。固定策略每次选配置中首个合格壳层。全候选策略在当步角动量内选最大 Schur 分数。局部策略先在有合格候选的原子中选最大原子分数，再选该原子的最佳壳层。相对并列容差为 \(10^{-10}\)，用配置顺序确定选择。每一步重新自洽，并保留首步每个 s 壳层的实际能量下降。各策略均计算同一组诊断，计时用于复核每次运行。
- 规范化 \(S\) 的最小/最大本征值比须大于 \(10^{-9}\)。候选 Schur 块用原候选 Gram 对角归一，丢弃小于等于 \(10^{-9}\max(1,\lambda_{\max})\) 的方向。壳层增广必须全部方向合格和试验 AO 重叠合格。近相关控制在 Li 上加入指数为 0.3200000001 的 s 壳，检验投影截秩和拒绝联合基组。另将 SCF 限为 1 步检查失败数据留存。

## 复现

在 Linux 或 WSL 的项目根目录运行。使用 Python 3.14.4 与 [依赖](../requirements-numerics.txt)。本机最终结果来自新的 D 盘 .venv-science，版本见 [冻结列表](../evidence/stage3/science-freeze.txt)。

```bash
python3 -m venv .venv-science
.venv-science/bin/python -m pip install -r requirements-numerics.txt
bash scripts/run_stage3.sh runs/stage3-recheck
```

本机 WSL 的 venv/ensurepip 启动失败，WSL 访问 PyPI 报网络不可达。实际恢复途径是在 Windows 用现有 pip 下载 Linux x86_64 的 CPython 3.14 wheel 到 D 盘，再用本机旧科学环境的 pip 向新 venv 安装 wheel；最终科学运行只调用新环境。已验证的命令如下。

```powershell
Set-Location D:\ksagent
$env:TEMP="$PWD\.scratch"
$env:TMP=$env:TEMP
.\.venv\Scripts\python.exe -m pip --no-cache-dir download --only-binary=:all: --platform manylinux_2_28_x86_64 --platform manylinux_2_27_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 --python-version 3.14 --implementation cp --abi cp314 --dest .scratch/wheels-linux -r requirements-numerics.txt pip
wsl -d Ubuntu --cd /mnt/d/ksagent -- python3 -m venv --without-pip .venv-science
wsl -d Ubuntu --cd /mnt/d/ksagent -- env TMPDIR=/mnt/d/ksagent/.scratch /mnt/d/ks_research/.venv-pyscf/bin/python -m pip --python .venv-science/bin/python --no-index --find-links .scratch/wheels-linux -r requirements-numerics.txt pip
wsl -d Ubuntu --cd /mnt/d/ksagent -- bash scripts/run_stage3.sh runs/stage3-recheck
```

单个基线可运行下列命令，将 mode 切换为 comparison 可得到三种策略。每个运行使用新的输出名，同级 .jsonl 为时间序列。JSON 保存配置副本、源码哈希、逐步数值、SCF 状态、资源和积分协议。已保存的阶段结果见 [机器数据](../evidence/stage3/)。

```bash
mkdir -p .scratch
PYSCF_TMPDIR="$PWD/.scratch" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv-science/bin/python -m experiments.run_baseline --mode baseline --case lih \
  --level 3 --output runs/stage3-single/lih.json
```

## 已核查结果

网格 3 的 LiH 初始能量为 −7.7922850789 Ha。有限参考 cc-pVQZ（85 AO）和 cc-pV5Z（146 AO）分别为 −7.9189278697 Ha 和 −7.9195024470 Ha，相差约 0.575 mHa。字典全空间（22 AO）能量为 −7.8163843987 Ha，相对 cc-pVQZ 仍偏离 102.543 mHa，显示该候选集覆盖范围有限。

| 累计新增 AO | 原子局部筛选 | 全候选 Schur 排序 | 固定顺序 |
| ---: | ---: | ---: | ---: |
| 0 | 126.643 | 126.643 | 126.643 |
| 1 | 109.843 | 109.843 | 109.843 |
| 4 | 109.257 | 109.257 | 109.273 |
| 5 | 104.461 | 104.461 | 109.167 |

表中单位为 mHa，采用网格 3 的 cc-pVQZ 有限参考。两个残差策略都选出 Li_s32 → H_p35 → H_s20；固定策略选出 Li_s32 → Li_p35 → Li_s08。网格 3/4/5 和两套有限参考下选择与能量偏差排序一致。新增 5 AO 时两种残差方法相对固定顺序的改善为 4.7050–4.7052 mHa。原子筛选与全候选排序本次完全重合，原子筛选的独立收益仍待能区分两者的算例检验。首步穷举中，Schur 分数和实际能量下降都把 Li_s32 排第一，Li_s08 与 H_s20 的中间名次发生对调。

LiH 网格 3 初始旧空间对偶残差为 \(4.41\times10^{-11}\)，候选补空间为 \(8.59\times10^{-2}\)，在候选字典之外的留出探针为 \(1.88\times10^{-2}\)。有限冻结矩阵的子空间误差为 0.11065，上界为 1.47719，约束较松。网格 3–5 的正常 LiH 拟合全部收敛，最大的旧空间广义本征残差对偶范数为 \(5.69\times10^{-9}\)。归一化重叠最小/最大本征值比的最小值为 \(2.70\times10^{-5}\)。原子积分相对闭合误差最大为 \(2.33\times10^{-5}\)。H₂ 两个原子的平方指标相对差约 \(1.07\times10^{-14}\)。

单循环控制实际未收敛，旧空间对偶残差约 0.12846，保留了失败能量与残差。近线性控制把候选投影从 17 维截为 16 维，并在 SCF 前拒绝 23 AO 的联合字典。

- [同预算 CSV](../evidence/stage3/matched-budget.csv) 和 [参考/网格配对比较](../evidence/stage3/sensitivity-summary.json)
- [LiH 最小基线](../evidence/stage3/lih-baseline.json)、[网格 3](../evidence/stage3/lih-level3.json)、[网格 4](../evidence/stage3/lih-level4.json) 和 [网格 5](../evidence/stage3/lih-level5.json)
- [H₂ 对称性](../evidence/stage3/h2-symmetry.json)、[SCF 负对照](../evidence/stage3/lih-low-max-cycle.json) 和 [近线性负对照](../evidence/stage3/lih-near-linear.json)

阶段 4 可从 [智能体数值配置示例](../config/agent.numerics.example.json) 接手。它包含 LiH 基线、同预算对照和由智能体在项目内写入独立配置的变体命令，输出进入 runs/stage4/。
