"""Batch replay analysis CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from replay_analysis import analyze, summarize_dir  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze Kaggle kaggriculture replay JSON files.",
    )
    parser.add_argument(
        "path",
        help="Replay file, replays/ dir, or kaggle_logs/<submission_id>/ dir",
    )
    parser.add_argument(
        "--us-name",
        default=None,
        help="Your team name (matches info.TeamNames) for us_index / aggregates",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output JSON path (batch mode only; default: <dir>/summary.json)",
    )
    args = parser.parse_args(argv)

    path = Path(args.path)
    if path.is_file():
        report = analyze(path, us_name=args.us_name)
        out = args.output or path.with_suffix(".analysis.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Wrote {out}")
        return 0

    summary = summarize_dir(path, us_name=args.us_name, out_path=args.output)
    print(
        f"Analyzed {summary['n_episodes']} episode(s) → {summary.get('summary_path')}"
    )
    agg = summary.get("aggregate") or {}
    if agg:
        print(f"  win_rate={agg.get('win_rate'):.3f}  reward_us={agg.get('reward_us')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
