# 阶段 1 文献核查

检索日期为 2026-11-21。对原始论文、期刊 DOI、作者公开稿及软件文档做定向检索。使用的关键词组包括 `Kohn Sham adaptive finite element a posteriori`、`Kohn Sham inverse Jacobian residual plane wave`、`atom-centered LCAO Schrödinger a posteriori`、`Gaussian orbital basis set incompleteness Kohn Sham Jensen`、`adaptive local basis Kohn Sham residual` 和 `Gaussian projected residual basis enrichment`。实际阅读范围列在表中。Crossref 精确题名查询的三条返回保存在 [crossref.json](../evidence/stage1/crossref.json)，后两条仅为搜索返回。

| 相关性与出处 | 研究对象、离散和误差度量 | 主要假设与阅读所见 | 可复用部分及范围 |
| --- | --- | --- | --- |
| 直接匹配 LCAO 与局部后验估计。Dupuy、Dusson、Lygatsika，[期刊 DOI](https://doi.org/10.1137/24M1700697)，[公开稿](https://arxiv.org/html/2410.04943)。查阅摘要、§3.1 的定位和 §4.1.4–4.1.5 对照。 | 全空间原子中心势的线性 Schrödinger 源问题与本征问题，LCAO 离散，误差用移位算符能量范数衡量。 | 单位分解、原子算符的正定性和谱间隙信息支撑估计。实用认证要处理局部残差对偶范数的谱尾。公开稿 1D 实验比较了自适应与均匀基组增广。 | 借鉴局部化、谱分离和截断尾项的核对。分子自洽有效势、响应稳定性及其可计算常数需另外验证。 |
| 直接匹配分子高斯 KS 基组误差。Jensen，[期刊 DOI](https://doi.org/10.1063/1.1465405)，[原文 PDF](https://lab409chem.ccu.edu.tw/var/file/80/1080/img/1707/pc-n_II_Jensen_JCP_2002.pdf)。查阅引言、pc-n 构造、外推式和结论。 | 分子核中心高斯基，逐级逼近 HF 或 KS 基组极限，比较总能、原子化能等偏差。 | 依赖指数优化、偏振分级、官能团/分子测试和外推经验。所读正文包含 BLYP 指数优化与二原子数值 HF 校准。 | 用更丰富的基系列做独立敏感性检查。本文外推和数据不足以给 LiH/LDA 参考值颁发误差证书。 |
| 理论类比。Chen 等，[期刊 DOI](https://doi.org/10.1137/130916096)，[作者稿](https://arxiv.org/html/1302.6896)。核对 §2 残差与 A3、收敛定理和收缩段。 | 非线性 KS、适形自适应有限元，单元强残差和面跳跃，轨道组距离采用 (H^1)。 | 初网格充分细和 A1 用于全局收敛结果，附加分析使用 A2、A3 等条件。A3 涉及约束切空间线性化同构。 | 分开记录 SCF 与离散误差，并考虑响应稳定性。高斯函数全局重叠，需要建立自己的局部化稳定性、可覆盖性和增广收敛条件。 |
| 理论类比。Kaye、Lin、Yang，[原文 PDF](https://math.berkeley.edu/~linlin/publications/APostKSDFT.pdf)。核对摘要、式 (3.16)–(3.17)、定理 3.5 及其后说明。 | DG 自适应局部基 KS，有效势下的本征函数 DG 能量距离和本征值误差。 | 依赖假设 3.1 中的近似与提升性质、适合的局部基以及估计中的余项。残差覆盖单元和界面。 | 借鉴局部标记、误差度量与余项分离。DG 结论的界面结构及插值性质须另行处理才能迁移到分子 GTO。 |
| 理论类比。Herbst、Levitt、Cancès，[公开稿](https://arxiv.org/abs/2004.13549)，[原文 PDF](https://michael-herbst.com/publications/2020.04.28_error_nonscf_kohn_sham.pdf)。查阅摘要、谱间隙估计段、数值验证讨论。 | 固定非自洽赝势算符、平面波离散，给出本征值误差区间。 | 使用残差与谱分离信息，分别控制基组截断、迭代求解和舍入。 | 借鉴冻结算符的可验证子实验。本文的平面波尾部界和舍入处理没有用于当前 GTO 计算。 |
| 理论类比。Cancès、Dusson、Kemlin、Levitt，[公开稿](https://arxiv.org/html/2111.01470)。核对摘要、平面波离散与逆 Jacobian 误差估计的框架。 | 周期平面波电子结构，目标量含密度矩阵、能量和力。 | 线性化误差估计取决于逆 Jacobian 的控制以及近似项。Schur 补用于提高估计精度。 | 有限维冻结谱隙与自洽切空间 Jacobian 的可逆性应分别验证。本文 Schur 补和本项目 Gram 消元用途不同。 |
| 实现依据。[PySCF SCF 开发者文档](https://pyscf.org/contributor/scf_developer.html)、[RKS API](https://pyscf.org/pyscf_api_docs/pyscf.dft.html)、[RKS 源码页](https://pyscf.org/_modules/pyscf/dft/rks.html)。查阅 `get_veff`、网格与密度输入。 | Gaussian AO、RKS 积分及 SCF 求解。 | 要以正确 AO 顺序嵌入密度，并核对同网格下的旧矩阵块。 | 在联合空间用旧密度构造冻结算符，并用真实 RKS 再自洽求能量。 |
| 检索实现依据。[Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)。查阅公开 works 查询与元数据范围。 | 文献题名、DOI、题录和可能的摘要。 | 元数据内容取决于提交者。 | 查询保存原始 URL 与题录，正文访问和阅读范围另记。 |

本次最直接的两条证据分别覆盖线性 LCAO 可靠估计和分子高斯 KS 的有限基能量偏差。在上述覆盖范围内，本课程项目可检验的增量是固定 LiH/LDA、预算和候选库，通过消融测量原子局部筛选相对全候选 Schur 排序的增益。这是针对具体设定的研究问题，优先权和一般性创新仍待系统检索。未逐式复核论文的完整证明。
