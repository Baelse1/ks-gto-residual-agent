#!/usr/bin/env bash
set -euo pipefail
output="${1:?Provide a fresh result directory}"
python="${KSAGENT_SCIENCE_PYTHON:-.venv-science/bin/python}"
mkdir -p "$output" .scratch
export PYSCF_TMPDIR="$PWD/.scratch" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1

"$python" -m pip check
"$python" -m pip freeze > "$output/science-freeze.txt"
"$python" -m experiments.run_baseline --mode baseline --case lih --level 3 --output "$output/lih-baseline.json"
for level in 3 4 5; do
  "$python" -m experiments.run_baseline --mode comparison --case lih --level "$level" \
    --output "$output/lih-level$level.json"
done
"$python" -m experiments.run_baseline --mode baseline --case h2 --level 3 --output "$output/h2-symmetry.json"

if "$python" -m experiments.run_baseline --mode baseline --case lih --level 3 --max-cycle 1 \
  --output "$output/lih-low-max-cycle.json"; then
  echo "Expected a failed one-cycle SCF control." >&2
  exit 1
fi

"$python" - "$output/near-linear-config.json" <<'PY'
import json
from pathlib import Path
import sys

config = json.loads(Path("config/stage3.json").read_text(encoding="utf-8"))
config["molecules"]["lih"]["candidates"].append(["Li_s32_near_duplicate", 0, 0, 0.3200000001])
Path(sys.argv[1]).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
if "$python" -m experiments.run_baseline --mode baseline --case lih --level 3 \
  --config "$output/near-linear-config.json" --output "$output/lih-near-linear.json"; then
  echo "Expected a rejected near-duplicate union." >&2
  exit 1
fi

"$python" -m experiments.summarize_stage3 "$output"
