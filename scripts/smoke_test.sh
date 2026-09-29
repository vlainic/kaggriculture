#!/usr/bin/env bash
# Safe for Cursor agents: build submission bundle + local smoke test only (no Kaggle upload).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SMOKE_LOG="$SCRIPT_DIR/smoke.txt"
cd "$ROOT"

SUBMISSION="submission.tar.gz"
BUILD="$ROOT/build/submission"

V55_MAIN="$ROOT/opponents/v55/main.py"
V55_LOGGED="$ROOT/scripts/v55_logged_opponent.py"
# Default: logged V55 wrapper ([opp]/[opp_snap] exec+money). Raw: opponents/v55/main.py
SMOKE_OPPONENT="${SMOKE_OPPONENT:-$V55_LOGGED}"
SMOKE_US_SEAT="${SMOKE_US_SEAT:-0}"
SMOKE_OPP_VERBOSE="${SMOKE_OPP_VERBOSE:-1}"

if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate kaggle 2>/dev/null || true
fi

if [[ ! -d vendor/ortools ]]; then
  echo "==> vendor/ missing — running scripts/vendor_ortools.sh"
  bash "$ROOT/scripts/vendor_ortools.sh"
fi

# Explicit copy list only — never opponents/ (second main.py would break submission).
echo "==> Building ${SUBMISSION} (main.py + milos/ + data/ + vendored ortools)"
rm -rf "$BUILD"
mkdir -p "$BUILD"
cp main.py "$BUILD/"
cp -a milos "$BUILD/"
mkdir -p "$BUILD/data"
cp data/crop_rollouts.json data/animal_with_pickups.json data/handmade_dp_candidates.json "$BUILD/data/"
cp -a vendor/. "$BUILD/"
find "$BUILD" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$BUILD" -name '*.pyc' -delete 2>/dev/null || true

tar -czf "$SUBMISSION" -C "$BUILD" .
ls -lh "$SUBMISSION"
if tar -tzf "$SUBMISSION" | grep -qi opponents; then
  echo "FAIL: submission tarball must not contain opponents/" >&2
  exit 1
fi

if [[ "$SMOKE_OPPONENT" == "$V55_MAIN" \
   || "$SMOKE_OPPONENT" == "opponents/v55/main.py" \
   || "$SMOKE_OPPONENT" == "$V55_LOGGED" \
   || "$SMOKE_OPPONENT" == *"v55_logged_opponent.py" ]]; then
  if [[ ! -f "$V55_MAIN" ]]; then
    echo "==> Extracting V55 opponent"
    python3 "$ROOT/scripts/extract_v55_opponent.py"
  fi
fi

echo "==> Smoke test: main.py vs ${SMOKE_OPPONENT} us_seat=${SMOKE_US_SEAT} (720 steps, default config)"
export KAGGRI_VERBOSE=1
export SMOKE_ROOT="$ROOT"
export SMOKE_OPPONENT
export SMOKE_US_SEAT
export SMOKE_OPP_VERBOSE
{
  echo "==> Log: ${SMOKE_LOG}"
  python3 "$ROOT/scripts/smoke_episode.py"
} 2>&1 | tee "$SMOKE_LOG"

echo "==> Done (no Kaggle upload). To submit: scripts/smoke_and_submit.sh --submit \"message\""
