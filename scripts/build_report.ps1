param([string] $Python = "")
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $build = Join-Path $root '.scratch/report'
    $output = Join-Path $root 'output/pdf'
    New-Item -ItemType Directory -Force -Path $build,$output | Out-Null
    $env:TEMP = $build
    $env:TMP = $build
    if (-not $Python) {
        $candidate = Join-Path $root '.venv/Scripts/python.exe'
        $Python = if (Test-Path -LiteralPath $candidate) { $candidate } else { 'python' }
    }
    & $Python report/generate_data.py $build
    if ($LASTEXITCODE -ne 0) { throw 'Report data validation failed.' }

    for ($pass = 1; $pass -le 2; $pass++) {
        & xelatex -interaction=nonstopmode -halt-on-error -file-line-error "-output-directory=$build" -jobname=ksagent-report report/main.tex *> (Join-Path $build "pass-$pass.log")
        if ($LASTEXITCODE -ne 0) {
            Get-Content -LiteralPath (Join-Path $build "pass-$pass.log") -Tail 35
            throw "XeLaTeX pass $pass failed."
        }
    }
    $pdf = Join-Path $output 'ksagent-report.pdf'
    Copy-Item -LiteralPath (Join-Path $build 'ksagent-report.pdf') -Destination $pdf -Force
    Write-Output $pdf
} finally {
    Pop-Location
}
