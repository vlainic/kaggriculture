#!/usr/bin/env bash
# Run dual-track smoke: N vs random (regression) + N vs V55 with seat swap (benchmark).
# Usage: SMOKE_RUNS=6 bash scripts/smoke_multi_run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNS_DIR="$SCRIPT_DIR/smoke_runs"
N="${SMOKE_RUNS:-6}"
V55_MAIN="$ROOT/scripts/v55_logged_opponent.py"

mkdir -p "$RUNS_DIR"
SUMMARY="$RUNS_DIR/summary.txt"

echo "==> Extract V55 opponent (if needed)"
python3 "$ROOT/scripts/extract_v55_opponent.py"

echo "==> Multi-run smoke: N=${N} per track -> ${RUNS_DIR}/"

for i in $(seq 1 "$N"); do
  pad=$(printf "%02d" "$i")
  out="$RUNS_DIR/random_${pad}.txt"
  echo "==> Random regression ${i}/${N} -> ${out}"
  SMOKE_OPPONENT=random SMOKE_US_SEAT=0 bash "$SCRIPT_DIR/smoke_test.sh" > "$out" 2>&1 || true
done

for i in $(seq 1 "$N"); do
  pad=$(printf "%02d" "$i")
  seat=$(( (i - 1) % 2 ))
  out="$RUNS_DIR/v55_seat${seat}_${pad}.txt"
  echo "==> V55 benchmark ${i}/${N} us_seat=${seat} -> ${out}"
  SMOKE_OPPONENT="$V55_MAIN" SMOKE_US_SEAT="$seat" bash "$SCRIPT_DIR/smoke_test.sh" > "$out" 2>&1 || true
done

python3 - "$RUNS_DIR" "$N" << 'PY'
import re
import statistics as stats
import sys
from pathlib import Path

runs_dir = Path(sys.argv[1])
n = int(sys.argv[2])

random_rewards = []
for i in range(1, n + 1):
    p = runs_dir / f"random_{i:02d}.txt"
    if not p.is_file():
        continue
    m = re.search(r"Player 0 \(us\): reward=([^,]+)", p.read_text())
    if m:
        random_rewards.append(float(m.group(1)))

margins, us_rewards = [], []
seat0 = seat1 = 0
for i in range(1, n + 1):
    seat = (i - 1) % 2
    if seat == 0:
        seat0 += 1
    else:
        seat1 += 1
    p = runs_dir / f"v55_seat{seat}_{i:02d}.txt"
    if not p.is_file():
        continue
    text = p.read_text()
    mm = re.search(r"margin_us_minus_opp=(-?\d+(?:\.\d+)?)", text)
    um = re.search(rf"Player {seat} \(us\): reward=([^,]+)", text)
    if mm:
        margins.append(float(mm.group(1)))
    if um:
        us_rewards.append(float(um.group(1)))

wins = sum(1 for m in margins if m > 0)
losses = sum(1 for m in margins if m < 0)
ties = sum(1 for m in margins if m == 0)

lines = [
    "== smoke_multi_run summary ==",
    f"random_track n={len(random_rewards)}",
]
if random_rewards:
    lines.append(
        f"  us_reward mean={stats.mean(random_rewards):.1f} "
        f"stdev={stats.pstdev(random_rewards):.1f}"
    )
lines.extend([
    f"v55_track n={len(margins)} seat_counts={{0: {seat0}, 1: {seat1}}}",
    f"  W/L/T = {wins}/{losses}/{ties}",
])
if margins:
    lines.append(f"  margin mean={stats.mean(margins):.1f}")
if us_rewards:
    lines.append(f"  us_reward mean={stats.mean(us_rewards):.1f}")

out = "\n".join(lines) + "\n"
print(out)
(runs_dir / "summary.txt").write_text(out)
PY

cat "$SUMMARY"
echo "==> Done: logs in ${RUNS_DIR}/ (no Kaggle upload)"
