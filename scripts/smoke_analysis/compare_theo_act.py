"""Compare dawn est_ops (theo) vs parsed act tile_ops per worker/day."""

from __future__ import annotations

import sys
from pathlib import Path

from smoke_analysis import analyze
from smoke_analysis.load import SEASON_DAYS


def main() -> None:
    log = Path(__file__).resolve().parents[1] / "smoke.txt"
    if len(sys.argv) > 1:
        log = Path(sys.argv[1])
    if not log.is_file():
        print(f"missing log: {log}", file=sys.stderr)
        raise SystemExit(1)

    report = analyze(log)
    workers = report.get("workers") or []
    est = (report.get("hands") or {}).get("est_ops_by_worker_by_day") or {}
    by_wd = (report.get("actions") or {}).get("by_worker_by_day") or {}

    mismatches: list[str] = []
    for w in workers:
        est_d = est.get(w) or [None] * SEASON_DAYS
        act_d = by_wd.get(w) or [{} for _ in range(SEASON_DAYS)]
        for day in range(1, SEASON_DAYS):  # snake + endgame day 29
            e = est_d[day] if day < len(est_d) else None
            a = act_d[day].get("tile_ops", 0) if day < len(act_d) else 0
            if e is None:
                continue
            if abs(int(round(e)) - int(a)) > 3:
                mismatches.append(f"d={day} {w} theo={int(round(e))} act={a}")

    print(f"log={log.name} workers={len(workers)} mismatches(>|3|)={len(mismatches)}")
    for line in mismatches[:40]:
        print(f"  {line}")
    if len(mismatches) > 40:
        print(f"  ... +{len(mismatches) - 40} more")
    if mismatches:
        raise SystemExit(1)
    print("theo vs act tile_ops OK (within ±3 per worker/day; sim_apply slack)")


if __name__ == "__main__":
    main()
