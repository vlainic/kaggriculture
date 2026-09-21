#!/usr/bin/env bash
# Run smoke_test.sh N times into scripts/smoke_runs/ (no Kaggle upload).
# Usage: SMOKE_RUNS=8 bash scripts/smoke_multi_run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNS_DIR="$SCRIPT_DIR/smoke_runs"
N="${SMOKE_RUNS:-5}"

mkdir -p "$RUNS_DIR"
echo "==> Multi-run smoke: N=${N} -> ${RUNS_DIR}/"

for i in $(seq 1 "$N"); do
  pad=$(printf "%02d" "$i")
  out="$RUNS_DIR/run_${pad}.txt"
  echo "==> Run ${i}/${N} -> ${out}"
  # Rebuild once on first run; later runs still rebuild (smoke_test always builds).
  bash "$SCRIPT_DIR/smoke_test.sh"
  cp "$SCRIPT_DIR/smoke.txt" "$out"
  echo "==> Copied smoke.txt -> ${out}"
done

echo "==> Done: ${N} logs in ${RUNS_DIR}/ (no Kaggle upload)"
