#!/usr/bin/env bash
# Analyze all replays for a Kaggle submission → kaggle_logs/<id>/<id>.json
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="${ROOT}/scripts"

usage() {
  echo "Usage: $0 <submission_id> [--us-name \"Your Name\"] [--include-events] [-o path]"
  echo ""
  echo "  submission_id    Kaggle submission ID (replays under kaggle_logs/<id>/replays/)"
  echo "  --us-name        Team name for us_index / aggregates (matches info.TeamNames)"
  echo "  --include-events Include per-unit sell events (large JSON; for violin charts)"
  echo "  -o, --output     Override output path (default: kaggle_logs/<id>/<id>.json)"
  echo ""
  echo "Example:"
  echo "  $0 55934103 --us-name \"Milos Vlainic\""
  echo "  $0 55934103 --include-events -o /tmp/out.json"
  exit 1
}

SUBMISSION_ID=""
US_NAME=""
INCLUDE_EVENTS=0
OUTPUT=""
EXTRA=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h | --help) usage ;;
    --us-name)
      [[ $# -ge 2 ]] || usage
      US_NAME="$2"
      shift 2
      ;;
    --include-events)
      INCLUDE_EVENTS=1
      shift
      ;;
    -o | --output)
      [[ $# -ge 2 ]] || usage
      OUTPUT="$2"
      shift 2
      ;;
    -*)
      echo "error: unknown option $1" >&2
      usage
      ;;
    *)
      if [[ -z "$SUBMISSION_ID" ]]; then
        SUBMISSION_ID="$1"
      else
        echo "error: unexpected argument $1" >&2
        usage
      fi
      shift
      ;;
  esac
done

[[ -n "$SUBMISSION_ID" ]] || usage

LOG_DIR="${ROOT}/kaggle_logs/${SUBMISSION_ID}"
if [[ ! -d "${LOG_DIR}/replays" ]]; then
  echo "error: ${LOG_DIR}/replays not found (run scripts/download_submission_logs.sh first)" >&2
  exit 1
fi

CMD=(python3 -m replay_analysis "$LOG_DIR")
if [[ -n "$US_NAME" ]]; then
  CMD+=(--us-name "$US_NAME")
fi
if [[ "$INCLUDE_EVENTS" -eq 1 ]]; then
  CMD+=(--include-events)
fi
if [[ -n "$OUTPUT" ]]; then
  CMD+=(-o "$OUTPUT")
fi

echo "==> Summarizing ${LOG_DIR}/replays → ${OUTPUT:-${LOG_DIR}/${SUBMISSION_ID}.json}"
(cd "$SCRIPTS" && "${CMD[@]}")
