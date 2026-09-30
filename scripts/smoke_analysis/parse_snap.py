"""Parse [snap] dawn lines from smoke stdout."""

from __future__ import annotations

import re
from typing import Any

SNAP_RE = re.compile(r"\[snap\] d=(\d+) h=(\d+) money=(\d+)(?: (.+))?")

# Populated at import from agent.workers when available.
ZONE_WORKERS: tuple[str, ...] = ()
ZONE_EMPTY_COLS: tuple[str, ...] = ()


def bind_workers(workers: tuple[str, ...]) -> None:
    global ZONE_WORKERS, ZONE_EMPTY_COLS
    ZONE_WORKERS = workers
    ZONE_EMPTY_COLS = tuple(f"{w}_empty" for w in workers)


def parse_snaps(lines: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in lines:
        m = SNAP_RE.search(line)
        if not m:
            continue
        row: dict[str, Any] = {
            "day": int(m.group(1)),
            "hour": int(m.group(2)),
            "money": int(m.group(3)),
        }
        tail = m.group(4) or ""
        for part in tail.split():
            if "=" not in part:
                continue
            key, val = part.split("=", 1)
            try:
                row[key] = int(val)
            except ValueError:
                row[key] = val
        rows.append(row)
    return rows


def dawn_snaps(snaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in snaps if int(s.get("hour", -1)) == 0]


def empty_by_worker_by_day(
    snaps: list[dict[str, Any]], *, season_days: int = 30
) -> dict[str, list[int | None]]:
    dawn = dawn_snaps(snaps)
    by_day: dict[int, dict[str, Any]] = {int(s["day"]): s for s in dawn}
    out: dict[str, list[int | None]] = {}
    cols = ZONE_EMPTY_COLS or tuple(
        k for k in next(iter(by_day.values()), {}) if k.endswith("_empty")
    )
    for col in cols:
        worker = col.removesuffix("_empty")
        series: list[int | None] = []
        for day in range(season_days):
            row = by_day.get(day)
            series.append(int(row[col]) if row and col in row else None)
        out[worker] = series
    return out


def us_farm_dawn_by_day(
    snaps: list[dict[str, Any]], *, season_days: int = 30
) -> tuple[list[int | None], list[int | None]]:
    """Dawn live PLANT/COOP/PASTURE count and workers (hands + farmer) from [snap]."""
    live: list[int | None] = [None] * season_days
    workers: list[int | None] = [None] * season_days
    for s in dawn_snaps(snaps):
        day = int(s["day"])
        if not (0 <= day < season_days):
            continue
        if "live" in s:
            live[day] = int(s["live"])
        if "hands" in s:
            workers[day] = int(s["hands"]) + 1
    return live, workers


def combine_us_daily_farm_metrics(
    us_tiles: list[int],
    us_workers: list[int],
    snaps: list[dict[str, Any]],
    exec_workers: list[int],
    *,
    season_days: int = 30,
) -> tuple[list[int], list[int]]:
    """Merge qtiles, dawn [snap] live=/hands+, and per-day [exec] actor counts."""
    live, snap_wk = us_farm_dawn_by_day(snaps, season_days=season_days)
    tiles = list(us_tiles)
    workers = list(us_workers)
    for d in range(season_days):
        q_t = int(tiles[d]) if d < len(tiles) else 0
        q_w = int(workers[d]) if d < len(workers) else 0
        lv = live[d]
        sw = snap_wk[d]
        ew = int(exec_workers[d]) if d < len(exec_workers) else 0
        if lv is not None:
            tiles[d] = max(q_t, int(lv))
        else:
            tiles[d] = q_t
        merged = max(q_w, ew, int(sw or 0))
        if merged <= 0 and (tiles[d] > 0 or ew > 0):
            merged = max(ew, 1)
        workers[d] = merged
    return tiles, workers


def money_by_day(
    snaps: list[dict[str, Any]], *, season_days: int = 30
) -> list[float | None]:
    dawn = dawn_snaps(snaps)
    by_day = {int(s["day"]): float(s["money"]) for s in dawn}
    return [by_day.get(d) for d in range(season_days)]


def money_by_turn(
    snaps: list[dict[str, Any]],
    *,
    season_days: int = 30,
    hours_per_day: int = 24,
) -> list[float | None]:
    """Money at each logged [snap] turn (day×24+hour); None where unlogged."""
    n = season_days * hours_per_day
    out: list[float | None] = [None] * n
    for s in snaps:
        day = int(s["day"])
        hour = int(s.get("hour", 0))
        if not (0 <= day < season_days and 0 <= hour < hours_per_day):
            continue
        out[day * hours_per_day + hour] = float(s["money"])
    return out
