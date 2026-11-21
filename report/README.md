# 中文课程报告

报告以 report/main.tex 为可编辑源。最终 PDF 位于 output/pdf/ksagent-report.pdf，图由阶段 4 的真实首壳对照数据绘制。生成程序读取归档数值、检查点和审计，核对哈希与结果，然后生成表格和数字。构建使用 Python 3、XeLaTeX、ctex 与 Fandol，阶段 5 实测为 Python 3.13.16 和 TeX Live 2023。

在仓库根目录执行下列 PowerShell 命令。默认使用项目 .venv 中的 Python，也可通过 -Python 指定解释器。

```powershell
pwsh -File scripts/build_report.ps1
```

生成脚本执行两遍 XeLaTeX，临时文件位于 .scratch/report。若修改阶段 4 的图，可先按 docs/research-run.md 中的绘图命令重建原始图。最终 PDF 的逐页检查命令如下，使用 Poppler。

```powershell
New-Item -ItemType Directory -Force .scratch/report/preview | Out-Null
pdftoppm -r 133 -png output/pdf/ksagent-report.pdf .scratch/report/preview/page
pdftotext -layout -enc UTF-8 output/pdf/ksagent-report.pdf .scratch/report/extracted.txt
pdfinfo -url output/pdf/ksagent-report.pdf
pdffonts output/pdf/ksagent-report.pdf
```

[成品](../output/pdf/ksagent-report.pdf) · [逐页检查与成品哈希](../evidence/stage5/pdf-qa.json) · [实际输入哈希与排版数值](../evidence/stage5/report-inputs.json)
