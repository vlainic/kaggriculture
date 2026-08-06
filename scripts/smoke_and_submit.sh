#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Activate conda env
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate kaggle

# Optional submit message: arg > git short SHA > fallback
if [[ $# -gt 0 ]]; then
  MSG="$1"
elif git rev-parse --short HEAD >/dev/null 2>&1; then
  MSG="$(git rev-parse --short HEAD)"
else
  MSG="submit"
fi

echo "==> Smoke test: main.py vs random (720 steps)"
python -c "
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

echo "==> Submitting main.py (message: ${MSG})"
kaggle competitions submit kaggriculture -f main.py -m "$MSG"

echo "==> Recent submissions"
kaggle competitions submissions kaggriculture
