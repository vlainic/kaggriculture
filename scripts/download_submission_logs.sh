#!/usr/bin/env bash
# Download replays for every episode of a Kaggle submission (--with-logs optional).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  echo "Usage: $0 [--with-logs] <submission_id> [output_dir]"
  echo ""
  echo "  --with-logs    Also fetch agent stdout logs (often 403 on ladder episodes)"
  echo "  submission_id  From: kaggle competitions submissions kaggriculture"
  echo "  output_dir     Default: ${ROOT}/kaggle_logs/<submission_id>"
  echo ""
  echo "Example:"
  echo "  $0 12345678"
  echo "  $0 --with-logs 12345678"
  exit 1
}

WITH_LOGS=0
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --with-logs) WITH_LOGS=1 ;;
    -h | --help) usage ;;
    *)
      if [[ "$arg" == --* ]]; then
        echo "error: unknown option ${arg}" >&2
        usage
      fi
      ARGS+=("$arg")
      ;;
  esac
done

[[ ${#ARGS[@]} -ge 1 ]] || usage

SUBMISSION_ID="${ARGS[0]}"
OUT="${ARGS[1]:-${ROOT}/kaggle_logs/${SUBMISSION_ID}}"

if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate kaggle 2>/dev/null || true
fi

if ! command -v kaggle >/dev/null 2>&1; then
  echo "error: kaggle CLI not found (pip install kaggle)" >&2
  exit 1
fi

mkdir -p "$OUT/replays"
if [[ "$WITH_LOGS" -eq 1 ]]; then
  mkdir -p "$OUT/logs"
fi
EPISODES_CSV="$OUT/episodes.csv"

echo "==> Listing episodes for submission ${SUBMISSION_ID}"
kaggle competitions episodes "$SUBMISSION_ID" -v > "$EPISODES_CSV"

_episode_ids() {
  tail -n +2 "$EPISODES_CSV" | cut -d, -f1 | tr -d '"' | grep -E '^[0-9]+$' || true
}

episode_ids="$(_episode_ids)"
count="$(printf '%s\n' "$episode_ids" | sed '/^$/d' | wc -l | tr -d ' ')"

if [[ "$count" -eq 0 ]]; then
  echo "==> No episodes yet (submission may still be queued or running)"
  exit 0
fi

mode="replays"
if [[ "$WITH_LOGS" -eq 1 ]]; then
  mode="replays + logs"
fi
echo "==> Found ${count} episode(s); downloading ${mode} to ${OUT}"
while IFS= read -r ep; do
  [[ -n "$ep" ]] || continue

  echo "    episode ${ep}"
  kaggle competitions replay "$ep" -p "$OUT/replays"
  if [[ "$WITH_LOGS" -eq 1 ]]; then
    kaggle competitions logs "$ep" 0 -p "$OUT/logs"
    if ! kaggle competitions logs "$ep" 1 -p "$OUT/logs"; then
      echo "    (no logs for agent 1 on episode ${ep})"
    fi
  fi
done <<< "$episode_ids"

echo "==> Done: ${OUT}"
