"""Parse [planner] twoland_wsp and replan lines."""

from __future__ import annotations

import ast
import re
from typing import Any

ZONE_OK_RE = re.compile(
    r"\[planner\] twoland_wsp zone=(\w+) (OPTIMAL|FEASIBLE) "
    r"obj=([\d.]+) time=([\d.]+)s close0=(-?\d+) cons0=(-?\d+) "
    r"open0=(-?\d+) empty=(\d+) picks=(\d+)"
)
ZONE_STARTS_RE = re.compile(
    r"\[planner\] twoland_wsp zone=(\w+) starts=(\{.+?\}) "
    r"min=(-?\d+|None) picks=(\d+) day0=(\d+)"
)
ZONE_INFEASIBLE_RE = re.compile(
    r"\[planner\] twoland_wsp zone=(\w+) status=(\w+) "
    r"time=([\d.]+)s empty=(\d+) open0=(-?\d+|N/A)"
    r"(?: locked_peak=(\d+)@(\d+) cap=(\d+)(?: over_days=(\d+))?)?"
)
SKIP_RE = re.compile(
    r"\[planner\] twoland_wsp zone=(\w+) skip cascade \((INFEASIBLE|picks=0)\)"
)
THIN_RE = re.compile(
    r"\[planner\] twoland_wsp zone=(\w+) thin day0=(\d+) "
    r"need>=(\d+) \(write anyway\)"
)
PROBE_OK_RE = re.compile(
    r"\[planner\] twoland_wsp probe hire5 ok day0=(\d+) buy_land tomorrow"
)
PROBE_THIN_RE = re.compile(
    r"\[planner\] twoland_wsp probe hire5 thin day0=(\d+) defer buy past d=(\d+)"
)
REPLAN_DAY_RE = re.compile(r"\[planner\] replan d=(\d+)")
REPLAN_META_RE = re.compile(
    r"\[planner\] replan d=(\d+) solver=\w+ shops=\d+ catalog=\d+ "
    r"assign=(\d+) locked=(\d+)"
)
REPLAN_BUY_RE = re.compile(
    r"\[planner\] replan d=(\d+) land2 probe ok BUY_LAND_DAY=(\d+)"
)
ASSIGN_RE = re.compile(r"\[planner\] replan assign (.+?)(?: partial=(\d+))?$")
ASSIGN_TILE_RE = re.compile(r"t(\d+):(\w+)(?:@(-?\d+))?")
ZONE_STREAK_STUCK_RE = re.compile(
    r"\[planner\] zone_streak worker=(\w+) d=(\d+) streak=(\d+) status=stuck"
)
ZONE_STREAK_RECOVERED_RE = re.compile(
    r"\[planner\] zone_streak worker=(\w+) d=(\d+) status=recovered"
)
ZONE_OUTCOMES_RE = re.compile(
    r"\[planner\] zone_outcomes d=(\d+) solved=([\w,]+) outcomes=(\{[^}]+\})"
)
STALE_UNLOCK_RE = re.compile(
    r"\[planner\] stale_unlock t=(\d+) worker=(\w+) d=(\d+) "
    r"age=(\d+) item=(\w+)"
)


def parse_zone_streaks(lines: list[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in lines:
        m = ZONE_STREAK_STUCK_RE.search(line)
        if m:
            events.append(
                {
                    "worker": m.group(1),
                    "day": int(m.group(2)),
                    "streak": int(m.group(3)),
                    "status": "stuck",
                }
            )
            continue
        m = ZONE_STREAK_RECOVERED_RE.search(line)
        if m:
            events.append(
                {
                    "worker": m.group(1),
                    "day": int(m.group(2)),
                    "status": "recovered",
                }
            )
    return events


def summarize_zone_streaks(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-worker: first stuck day, max streak, recovery day or None."""
    by_worker: dict[str, dict[str, Any]] = {}
    for ev in events:
        worker = ev["worker"]
        row = by_worker.setdefault(
            worker,
            {
                "worker": worker,
                "first_stuck_day": None,
                "max_streak": 0,
                "recovered_day": None,
            },
        )
        if ev["status"] == "stuck":
            day = ev["day"]
            streak = ev.get("streak", 0)
            if row["first_stuck_day"] is None:
                row["first_stuck_day"] = day
            row["max_streak"] = max(row["max_streak"], streak)
        elif ev["status"] == "recovered":
            row["recovered_day"] = ev["day"]
    return list(by_worker.values())


def parse_planner_events(lines: list[str]) -> dict[str, Any]:
    """Parse planner lines grouped into replan blocks (zone lines precede replan d=N)."""
    blocks: list[tuple[int | None, list[str]]] = []
    current: list[str] = []

    for line in lines:
        if "[planner]" not in line:
            continue
        current.append(line)
        m = REPLAN_DAY_RE.search(line)
        if m and "replan assign" not in line:
            blocks.append((int(m.group(1)), current))
            current = []

    if current:
        blocks.append((None, current))

    replan_days: list[int] = []
    zone_solves: list[dict[str, Any]] = []
    skip_cascade: list[dict[str, Any]] = []
    infeasible: list[dict[str, Any]] = []
    probe_hire5: list[dict[str, Any]] = []
    keep_assignments: list[dict[str, Any]] = []
    buy_land_day_logged: int | None = None

    for day, block_lines in blocks:
        if day is not None and (not replan_days or replan_days[-1] != day):
            replan_days.append(day)
        parsed = _parse_replan_block(block_lines, day)
        zone_solves.extend(parsed["zone_solves"])
        skip_cascade.extend(parsed["skip_cascade"])
        infeasible.extend(parsed["infeasible"])
        probe_hire5.extend(parsed["probe_hire5"])
        keep_assignments.extend(parsed["keep_assignments"])
        if parsed.get("buy_land_day_logged") is not None:
            buy_land_day_logged = parsed["buy_land_day_logged"]

    zone_streak_events = parse_zone_streaks(lines)
    replan_meta: dict[int, dict[str, int]] = {}
    solved_by_day: dict[int, list[str]] = {}
    outcomes_by_day: dict[int, dict[str, str]] = {}
    stale_unlocks: list[dict[str, Any]] = []
    for line in lines:
        m = REPLAN_META_RE.search(line)
        if m:
            replan_meta[int(m.group(1))] = {
                "assign": int(m.group(2)),
                "locked": int(m.group(3)),
            }
        m = ZONE_OUTCOMES_RE.search(line)
        if m:
            day = int(m.group(1))
            solved_raw = m.group(2)
            solved_by_day[day] = (
                [] if solved_raw == "none" else solved_raw.split(",")
            )
            outcomes_by_day[day] = _parse_outcomes_map(m.group(3))
            continue
        m = STALE_UNLOCK_RE.search(line)
        if m:
            stale_unlocks.append(
                {
                    "tile": int(m.group(1)),
                    "worker": m.group(2),
                    "day": int(m.group(3)),
                    "age": int(m.group(4)),
                    "item": m.group(5),
                }
            )
    return {
        "replan_days": replan_days,
        "zone_solves": zone_solves,
        "skip_cascade": skip_cascade,
        "infeasible": infeasible,
        "probe_hire5": probe_hire5,
        "keep_assignments": keep_assignments,
        "buy_land_day_logged": buy_land_day_logged,
        "replan_meta": replan_meta,
        "zone_streak_events": zone_streak_events,
        "zone_streak_summary": summarize_zone_streaks(zone_streak_events),
        "solved_by_day": solved_by_day,
        "outcomes_by_day": outcomes_by_day,
        "stale_unlocks": stale_unlocks,
    }


def _parse_outcomes_map(raw: str) -> dict[str, str]:
    inner = raw.strip("{}")
    if not inner:
        return {}
    out: dict[str, str] = {}
    for part in inner.split(","):
        if ":" not in part:
            continue
        worker, status = part.split(":", 1)
        out[worker] = status
    return out


def _parse_replan_block(block_lines: list[str], day: int | None) -> dict[str, Any]:
    zone_solves: list[dict[str, Any]] = []
    skip_cascade: list[dict[str, Any]] = []
    infeasible: list[dict[str, Any]] = []
    probe_hire5: list[dict[str, Any]] = []
    keep_assignments: list[dict[str, Any]] = []
    buy_land_day_logged: int | None = None
    pending_zone: dict[str, Any] | None = None

    def flush_zone() -> None:
        nonlocal pending_zone
        if pending_zone is not None:
            pending_zone["day"] = day
            zone_solves.append(pending_zone)
            pending_zone = None

    for line in block_lines:
        m = REPLAN_BUY_RE.search(line)
        if m:
            buy_land_day_logged = int(m.group(2))
            probe_hire5.append(
                {
                    "day": int(m.group(1)),
                    "ok": True,
                    "thin": False,
                    "buy_land_day": buy_land_day_logged,
                }
            )

        m = ASSIGN_RE.search(line)
        if m:
            flush_zone()
            for tm in ASSIGN_TILE_RE.finditer(m.group(1)):
                tile_1 = int(tm.group(1))
                label = tm.group(2)
                start = int(tm.group(3)) if tm.group(3) is not None else None
                if label == "keep":
                    keep_assignments.append(
                        {
                            "day": day,
                            "tile": tile_1,
                            "tile_idx": tile_1 - 1,
                            "label": label,
                            "start": start,
                        }
                    )
            continue

        m = PROBE_OK_RE.search(line)
        if m:
            probe_hire5.append(
                {"day": day, "ok": True, "thin": False, "day0": int(m.group(1))}
            )
            continue

        m = PROBE_THIN_RE.search(line)
        if m:
            probe_hire5.append(
                {
                    "day": day,
                    "ok": False,
                    "thin": True,
                    "day0": int(m.group(1)),
                    "force_buy_day": int(m.group(2)),
                }
            )
            continue

        m = ZONE_INFEASIBLE_RE.search(line)
        if m:
            flush_zone()
            entry = {
                "day": day,
                "worker": m.group(1),
                "status": m.group(2),
                "empty": int(m.group(4)),
                "open0": m.group(5),
                "locked_peak": int(m.group(6)) if m.group(6) else None,
                "peak_day": int(m.group(7)) if m.group(7) else None,
                "cap": int(m.group(8)) if m.group(8) else None,
                "over_days": int(m.group(9)) if m.group(9) else None,
            }
            infeasible.append(entry)
            pending_zone = {**entry, "picks": 0, "skipped": False}
            continue

        m = SKIP_RE.search(line)
        if m:
            skip_cascade.append(
                {"day": day, "worker": m.group(1), "reason": m.group(2)}
            )
            if pending_zone and pending_zone.get("worker") == m.group(1):
                pending_zone["skipped"] = True
                pending_zone["skip_reason"] = m.group(2)
            continue

        m = THIN_RE.search(line)
        if m:
            if pending_zone and pending_zone.get("worker") == m.group(1):
                pending_zone["thin"] = True
                pending_zone["write_anyway"] = True
                pending_zone["day0"] = int(m.group(2))
            continue

        m = ZONE_STARTS_RE.search(line)
        if m:
            hist_raw = m.group(2)
            try:
                hist = ast.literal_eval(hist_raw)
            except (SyntaxError, ValueError):
                hist = {}
            mn = m.group(3)
            if pending_zone and pending_zone.get("worker") == m.group(1):
                pending_zone["starts_hist"] = hist
                pending_zone["min_start"] = None if mn == "None" else int(mn)
                pending_zone["picks"] = int(m.group(4))
                pending_zone["day0"] = int(m.group(5))
            continue

        m = ZONE_OK_RE.search(line)
        if m:
            flush_zone()
            pending_zone = {
                "day": day,
                "worker": m.group(1),
                "status": m.group(2),
                "obj": float(m.group(3)),
                "time_s": float(m.group(4)),
                "close0": int(m.group(5)),
                "cons0": int(m.group(6)),
                "open0": int(m.group(7)),
                "empty": int(m.group(8)),
                "picks": int(m.group(9)),
                "skipped": False,
                "thin": False,
                "write_anyway": False,
            }
            continue

    flush_zone()
    return {
        "zone_solves": zone_solves,
        "skip_cascade": skip_cascade,
        "infeasible": infeasible,
        "probe_hire5": probe_hire5,
        "keep_assignments": keep_assignments,
        "buy_land_day_logged": buy_land_day_logged,
    }
