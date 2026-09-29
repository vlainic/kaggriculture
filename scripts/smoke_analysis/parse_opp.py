"""Parse [opp] / [opp_snap] lines from logged V55 wrapper."""

from __future__ import annotations

import re
from typing import Any

from smoke_analysis.parse_actions import classify_action

OPP_UNIT_RE = re.compile(
    r"\[opp\] d=(\d+) h=(\d+) (farmer|hand\d+) (\S+)"
)
OPP_SNAP_RE = re.compile(
    r"\[opp_snap\] d=(\d+) h=(\d+) money=(-?\d+)(?: (.+))?"
)
PLAYER_RE = re.compile(
    r"Player (\d+) \((us|opp)\): reward=([^,\s]+)"
)
MARGIN_RE = re.compile(r"margin_us_minus_opp=(-?\d+(?:\.\d+)?)")

_NON_TILE = frozenset({"MOVE", "PASS", "OTHER"})


def parse_opp(lines: list[str], *, season_days: int = 30) -> dict[str, Any]:
    tile_ops = [0] * season_days
    move = [0] * season_days
    passthrough = [0] * season_days
    market = [0] * season_days
    n_unit_lines = 0

    for line in lines:
        if line.startswith("[opp] ") and " market " in line:
            m = re.search(r"\[opp\] d=(\d+) h=(\d+) market ", line)
            if m:
                day = int(m.group(1))
                if 0 <= day < season_days:
                    market[day] += 1
            continue
        m = OPP_UNIT_RE.search(line)
        if not m:
            continue
        day = int(m.group(1))
        if not (0 <= day < season_days):
            continue
        verb = m.group(4)
        bucket = classify_action(verb)
        n_unit_lines += 1
        if bucket == "MOVE":
            move[day] += 1
        elif bucket == "PASS":
            passthrough[day] += 1
        elif bucket not in _NON_TILE:
            tile_ops[day] += 1

    money_by_day: list[float | None] = [None] * season_days
    for line in lines:
        sm = OPP_SNAP_RE.search(line)
        if not sm:
            continue
        day, hour = int(sm.group(1)), int(sm.group(2))
        if hour != 0 or not (0 <= day < season_days):
            continue
        money_by_day[day] = float(sm.group(3))

    net_cash = [0.0] * season_days
    for d in range(1, season_days):
        if money_by_day[d] is not None and money_by_day[d - 1] is not None:
            net_cash[d] = money_by_day[d] - money_by_day[d - 1]

    rewards: dict[str, float | None] = {"us": None, "opp": None}
    for line in lines:
        pm = PLAYER_RE.search(line)
        if pm:
            role = pm.group(2)
            try:
                rewards[role] = float(pm.group(3))
            except ValueError:
                pass
    margin = None
    for line in lines:
        mm = MARGIN_RE.search(line)
        if mm:
            margin = float(mm.group(1))
            break

    return {
        "present": n_unit_lines > 0 or any(v is not None for v in money_by_day),
        "tile_ops_by_day": tile_ops,
        "move_by_day": move,
        "pass_by_day": passthrough,
        "market_turns_by_day": market,
        "money_by_day": money_by_day,
        "net_cash_by_day": net_cash,
        "reward_us": rewards["us"],
        "reward_opp": rewards["opp"],
        "margin": margin,
    }


def us_tile_ops_by_day(
    actions: dict[str, Any] | None, *, season_days: int = 30
) -> list[int]:
    """Sum tile_ops across workers from parse_actions.by_worker_by_day."""
    out = [0] * season_days
    by_w = (actions or {}).get("by_worker_by_day") or {}
    for daily in by_w.values():
        for d in range(min(season_days, len(daily))):
            out[d] += int((daily[d] or {}).get("tile_ops", 0))
    return out
