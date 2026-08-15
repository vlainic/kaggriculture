#!/usr/bin/env bash
# Safe for Cursor agents: build submission bundle + local smoke test only (no Kaggle upload).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
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
cp data/crop_rollouts.json data/animal_rollouts.json data/handmade_dp_candidates.json "$BUILD/data/"
cp -a vendor/. "$BUILD/"
find "$BUILD" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$BUILD" -name '*.pyc' -delete 2>/dev/null || true

tar -czf "$SUBMISSION" -C "$BUILD" .
ls -lh "$SUBMISSION"

echo "==> Smoke test: main.py vs random (720 steps) [local env]"
python3 -c "
from kaggle_environments import make

env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True)
env.run(['main.py', 'random'])
final = env.steps[-1]
for i, s in enumerate(final):
    print(f'Player {i}: reward={s.reward}, status={s.status}')
    if s.status != 'DONE':
        raise SystemExit(f'Smoke test failed: player {i} status={s.status!r}')
print('Smoke test passed.')
"

echo "==> Done (no Kaggle upload). To submit: scripts/smoke_and_submit.sh --submit \"message\""
