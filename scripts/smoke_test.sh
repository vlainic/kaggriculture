#!/usr/bin/env bash
# Safe for Cursor agents: build submission bundle + local smoke test only (no Kaggle upload).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SMOKE_LOG="$SCRIPT_DIR/smoke.txt"
cd "$ROOT"

SUBMISSION="submission.tar.gz"
BUILD="$ROOT/build/submission"

if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate kaggle 2>/dev/null || true
fi

if [[ ! -d vendor/ortools ]]; then
  echo "==> vendor/ missing — running scripts/vendor_ortools.sh"
  bash "$ROOT/scripts/vendor_ortools.sh"
fi

echo "==> Building ${SUBMISSION} (main.py + agent/ + data/ + vendored ortools)"
rm -rf "$BUILD"
mkdir -p "$BUILD"
cp main.py "$BUILD/"
cp -a agent "$BUILD/"
mkdir -p "$BUILD/data"
cp data/crop_rollouts.json data/animal_with_pickups.json data/handmade_dp_candidates.json "$BUILD/data/"
cp -a vendor/. "$BUILD/"
find "$BUILD" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$BUILD" -name '*.pyc' -delete 2>/dev/null || true

tar -czf "$SUBMISSION" -C "$BUILD" .
ls -lh "$SUBMISSION"

echo "==> Smoke test: main.py vs random (720 steps) [local env]"
export KAGGRI_VERBOSE=1
{
echo "==> Log: ${SMOKE_LOG}"
python3 -c "
import io
import re
import sys
from collections import defaultdict
from contextlib import redirect_stdout

from kaggle_environments import make

env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True)
log_buf = io.StringIO()
with redirect_stdout(log_buf):
    env.run(['main.py', 'random'])
run_log = log_buf.getvalue()
sys.stdout.write(run_log)

final = env.steps[-1]
for i, s in enumerate(final):
    print(f'Player {i}: reward={s.reward}, status={s.status}')
    if s.status != 'DONE':
        raise SystemExit(f'Smoke test failed: player {i} status={s.status!r}')

lines = run_log.splitlines()

SEASON_LAST_DAY = 29

exec_re = re.compile(r'\[exec\] d=(\d+) h=(\d+)')
by_day_hand2 = defaultdict(list)
early_wheat_sells = []
for line in lines:
    m = exec_re.search(line)
    if not m:
        continue
    day, hour = int(m.group(1)), int(m.group(2))
    if (
        day < SEASON_LAST_DAY
        and ' market ' in line
        and 'SELL WHEAT' in line
        and hour < 5
    ):
        early_wheat_sells.append(line.strip())
    if ' hand2 ' in line:
        act = line.split(' hand2 ', 1)[1].split(' farmer')[0].strip()
        by_day_hand2[day].append((hour, act))

build = sum(
    1 for acts in by_day_hand2.values() for _, a in acts
    if a.startswith('BUILD_COOP') or a.startswith('BUILD_PASTURE')
)
place = sum(
    1 for acts in by_day_hand2.values() for _, a in acts
    if a.startswith('PLACE')
)
# Empty pasture/coop persists after harvest; replan PLACE reuses structure (no new BUILD).
if place > 0 and build == 0:
    print(
        f'FAIL: hand2 PLACE={place} with BUILD_COOP/BUILD_PASTURE=0 (need at least one build)',
        file=sys.stderr,
    )
    raise SystemExit(1)

for day, acts in sorted(by_day_hand2.items()):
    place_hours = [h for h, a in acts if a.startswith('PLACE')]
    if not place_hours:
        continue
    feed_hours = [h for h, a in acts if a.startswith('FEED')]
    if not feed_hours:
        print(f'FAIL: d={day} hand2 PLACE without same-day FEED', file=sys.stderr)
        raise SystemExit(1)

if early_wheat_sells:
    print('FAIL: SELL WHEAT during hours 0-4:', file=sys.stderr)
    for line in early_wheat_sells[:5]:
        print(f'  {line}', file=sys.stderr)
    raise SystemExit(1)

day0_buy_seed = any(
    ' market ' in line and 'BUY_SEED' in line
    for line in lines
    if line.startswith('[exec] d=0 ')
)
day0_plant = any(
    (' farmer PLANT' in line or ' hand' in line and ' PLANT' in line)
    for line in lines
    if line.startswith('[exec] d=0 ')
)
if not day0_buy_seed and not day0_plant:
    print('FAIL: day-0 had zero BUY_SEED and zero PLANT', file=sys.stderr)
    raise SystemExit(1)

print(f'Smoke checks passed: hand2 BUILD_COOP/BUILD_PASTURE={build} PLACE={place}, no early SELL WHEAT, day-0 productive')
print('Smoke test passed.')
"
} 2>&1 | tee "$SMOKE_LOG"

echo "==> Done (no Kaggle upload). To submit: scripts/smoke_and_submit.sh --submit \"message\""
