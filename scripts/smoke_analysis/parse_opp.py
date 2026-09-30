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
OPP_SNAP_HANDS_RE = re.compile(r"\bhands=(\d+)\b")
OPP_SNAP_LIVE_RE = re.compile(r"\blive=(\d+)\b")
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
    hands_by_day: list[int | None] = [None] * season_days
    live_tiles_by_day: list[int | None] = [None] * season_days
    for line in lines:
        sm = OPP_SNAP_RE.search(line)
        if not sm:
            continue
        day, hour = int(sm.group(1)), int(sm.group(2))
        if hour != 0 or not (0 <= day < season_days):
            continue
        money_by_day[day] = float(sm.group(3))
        tail = sm.group(4) or ""
        hm = OPP_SNAP_HANDS_RE.search(tail)
        if hm:
            hands_by_day[day] = int(hm.group(1))
        lm = OPP_SNAP_LIVE_RE.search(tail)
        if lm:
            live_tiles_by_day[day] = int(lm.group(1))

    workers_by_day = opp_workers_by_day_from_lines(lines, season_days=season_days)

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
        "hands_by_day": hands_by_day,
        "live_tiles_by_day": live_tiles_by_day,
        "workers_by_day": workers_by_day,
        "net_cash_by_day": net_cash,
        "reward_us": rewards["us"],
        "reward_opp": rewards["opp"],
        "margin": margin,
    }


def opp_workers_by_day_from_lines(
    lines: list[str], *, season_days: int = 30
) -> list[int]:
    """Distinct farmer + handN actors with at least one [opp] line that day."""
    workers = [1] * season_days
    for d in range(season_days):
        actors: set[str] = set()
        for line in lines:
            if not line.startswith("[opp] "):
                continue
            m = OPP_UNIT_RE.search(line)
            if not m or int(m.group(1)) != d:
                continue
            actors.add(m.group(3))
        if actors:
            workers[d] = len(actors)
    return workers


def opp_money_by_turn(
    lines: list[str], *, season_days: int = 30, hours_per_day: int = 24
) -> list[float | None]:
    """Money from each [opp_snap] at day×24+hour."""
    n = season_days * hours_per_day
    out: list[float | None] = [None] * n
    for line in lines:
        sm = OPP_SNAP_RE.search(line)
        if not sm:
            continue
        day, hour = int(sm.group(1)), int(sm.group(2))
        if not (0 <= day < season_days and 0 <= hour < hours_per_day):
            continue
        out[day * hours_per_day + hour] = float(sm.group(3))
    return out


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


def _safe_ratio(num: float, den: float | int | None) -> float:
    if den is None or den <= 0:
        return 0.0
    return float(num) / float(den)


def us_workers_by_day_from_exec(
    lines: list[str], *, season_days: int = 30
) -> list[int]:
    """Distinct farmer + handN with at least one [exec] farmer/hand line that day."""
    workers = [0] * season_days
    for d in range(season_days):
        actors: set[str] = set()
        for line in lines:
            if "[exec]" not in line or " market " in line:
                continue
            m = re.search(r"\[exec\] d=(\d+) h=(\d+)", line)
            if not m or int(m.group(1)) != d:
                continue
            if " farmer " in line:
                actors.add("farmer")
            hm = re.search(r" hand(\d+)", line)
            if hm:
                actors.add(f"hand{hm.group(1)}")
        workers[d] = len(actors) if actors else 0
    return workers


def us_workers_and_tiles_by_day(
    qtiles_by_worker: dict[str, list[int | None]] | None,
    *,
    season_days: int = 30,
) -> tuple[list[int], list[int]]:
    workers = [0] * season_days
    tiles = [0] * season_days
    by_w = qtiles_by_worker or {}
    for d in range(season_days):
        wcount = 0
        tsum = 0
        for series in by_w.values():
            if d >= len(series):
                continue
            q = series[d]
            if q is None:
                continue
            qv = int(q)
            if qv > 0:
                wcount += 1
                tsum += qv
        workers[d] = wcount
        tiles[d] = tsum
    return workers, tiles


def derived_efficiency_series(
    *,
    tile_ops: list[int],
    workers: list[int | None],
    tiles: list[int | None],
    season_days: int = 30,
) -> tuple[list[float], list[float], list[float]]:
    ops_per_tile = [0.0] * season_days
    tiles_per_worker = [0.0] * season_days
    ops_per_worker = [0.0] * season_days
    for d in range(season_days):
        ops = float(tile_ops[d] if d < len(tile_ops) else 0)
        w = workers[d] if d < len(workers) else None
        t = tiles[d] if d < len(tiles) else None
        ops_per_tile[d] = _safe_ratio(ops, t)
        tiles_per_worker[d] = _safe_ratio(float(t or 0), w)
        ops_per_worker[d] = _safe_ratio(ops, w)
    return ops_per_tile, tiles_per_worker, ops_per_worker


def opp_live_series_present(live_tiles: list[int | None] | None) -> bool:
    return any(v is not None for v in (live_tiles or []))
