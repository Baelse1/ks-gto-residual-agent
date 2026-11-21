#!/usr/bin/env bash
set -euo pipefail
step="${1:?Provide an archived revision number}"
output="${2:?Provide a fresh output JSON path}"
[[ "$step" =~ ^[0-9]+$ ]]
root="$PWD"
python="${KSAGENT_SCIENCE_PYTHON:-.venv-science/bin/python}"
if [[ "$python" != /* ]]; then python="$root/$python"; fi
if [[ "$output" != /* ]]; then output="$root/$output"; fi
if [[ -e "$output" ]]; then
  echo "Choose a fresh output path." >&2
  exit 2
fi
mkdir -p "$root/.scratch"
trial="$(mktemp -d "$root/.scratch/stage4-step-$step.XXXXXX")"
mkdir -p "$trial/experiments" "$trial/config"
cp experiments/__init__.py experiments/gaussian_rks.py "$trial/experiments/"
cp config/stage3.json "$trial/config/"
cp "evidence/stage4/versions/$step-stage4_probe.py" "$trial/experiments/stage4_probe.py"
cd "$trial"
export PYSCF_TMPDIR="$root/.scratch" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
"$python" -m experiments.stage4_probe --output "$output"
