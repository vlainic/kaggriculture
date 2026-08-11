#!/usr/bin/env bash
# USER ONLY — uploads to Kaggle. Requires explicit --submit flag.
# Cursor/agents: NEVER run this script. Use scripts/smoke_test.sh instead.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" != "--submit" ]]; then
  echo "ERROR: Refusing to upload without --submit flag." >&2
  echo "  Smoke only (agents):  scripts/smoke_test.sh" >&2
  echo "  Submit (users):       scripts/smoke_and_submit.sh --submit \"message\"" >&2
  exit 1
fi
shift

SUBMISSION="submission.tar.gz"

# Optional submit message: arg > git short SHA > fallback
if [[ $# -gt 0 ]]; then
  MSG="$1"
elif git rev-parse --short HEAD >/dev/null 2>&1; then
  MSG="$(git rev-parse --short HEAD)"
else
  MSG="submit"
fi

bash "$ROOT/scripts/smoke_test.sh"

echo "==> Submitting ${SUBMISSION} (message: ${MSG})"
kaggle competitions submit kaggriculture -f "$SUBMISSION" -m "$MSG"

echo "==> Recent submissions"
kaggle competitions submissions kaggriculture
