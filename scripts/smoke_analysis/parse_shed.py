"""Parse dawn [snap] shed_total for cap streak KPIs."""

from __future__ import annotations

import re
from typing import Any

SNAP_SHED_RE = re.compile(
    r"\[snap\] d=(\d+) h=(\d+) money=\d+ shed_total=(\d+)"
)
SHED_COMP_RE = re.compile(
    r"\[shed\] d=(\d+) h=(\d+) total=(\d+)(?: (.+))?"
)
SHED_DROP_RE = re.compile(
    r"\[shed_drop\] d=(\d+) hand_inv=(\d+) room=(\d+) est_dropped=(\d+)"
)


def parse_shed_cap(lines: list[str], *, season_days: int = 30, cap: int = 100) -> dict[str, Any]:
    at_cap_days: list[int] = []
    streak = 0
    max_streak = 0
    dawn_totals: list[int | None] = [None] * season_days

    for line in lines:
        m = SNAP_SHED_RE.search(line)
        if not m:
            continue
        day = int(m.group(1))
        hour = int(m.group(2))
        total = int(m.group(3))
        if day < 0 or day >= season_days:
            continue
        if hour != 0:
            continue
        dawn_totals[day] = total
        if total >= cap:
            at_cap_days.append(day)
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    return {
        "shed_cap": cap,
        "days_at_cap": len(at_cap_days),
        "at_cap_days": at_cap_days,
        "max_cap_streak": max_streak,
        "dawn_shed_total_by_day": dawn_totals,
        **parse_shed_diagnostics(lines, season_days=season_days),
    }


def parse_shed_diagnostics(
    lines: list[str], *, season_days: int = 30
) -> dict[str, Any]:
    dawn_totals: list[int] = []
    est_dropped_total = 0
    for line in lines:
        m = SHED_DROP_RE.search(line)
        if m:
            est_dropped_total += int(m.group(4))
        m = SHED_COMP_RE.search(line)
        if m and int(m.group(2)) == 0:
            dawn_totals.append(int(m.group(3)))
    mean_dawn = (
        sum(dawn_totals) / len(dawn_totals) if dawn_totals else None
    )
    return {
        "mean_dawn_shed": mean_dawn,
        "est_dropped_total": est_dropped_total,
    }


def parse_disposal_events(lines: list[str]) -> dict[str, Any]:
    room = 0
    animal_cap = 0
    sell_lead = 0
    room_reasons: dict[str, int] = {}
    animal_reasons: dict[str, int] = {}

    for line in lines:
        if line.startswith("[room]"):
            room += 1
            if "defer_steep=" in line:
                room_reasons["defer_steep"] = room_reasons.get("defer_steep", 0) + 1
            if "opp_skip=" in line:
                room_reasons["opp_skip"] = room_reasons.get("opp_skip", 0) + 1
        elif line.startswith("[animal_cap]"):
            animal_cap += 1
            if "skip=wool_glut" in line:
                animal_reasons["wool_glut"] = animal_reasons.get("wool_glut", 0) + 1
            elif "skip=shed_full" in line:
                animal_reasons["shed_full"] = animal_reasons.get("shed_full", 0) + 1
            elif "skip=pressure" in line:
                animal_reasons["pressure"] = animal_reasons.get("pressure", 0) + 1
            elif "skip=product" in line:
                animal_reasons["product"] = animal_reasons.get("product", 0) + 1
        elif line.startswith("[sell_lead]"):
            sell_lead += 1

    return {
        "room_events": room,
        "animal_cap_events": animal_cap,
        "sell_lead_events": sell_lead,
        "room_reasons": room_reasons,
        "animal_cap_reasons": animal_reasons,
    }
