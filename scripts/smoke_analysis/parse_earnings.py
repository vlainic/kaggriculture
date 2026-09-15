"""Daily earnings from smoke exec + snap logs."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from smoke_analysis.parse_snap import dawn_snaps

EXEC_RE = re.compile(r"\[exec\] d=(\d+) h=(\d+)")
SELL_REV_RE = re.compile(r"\bsell_rev=(\d+)\b")
EARN_RE = re.compile(r"\bearn=(\d+)\b")
TILE_RE = re.compile(r"\bt(\d+)\b")
FERTILIZER_BASE = 100
_COLLECT_VERBS = frozenset({"COLLECT_FERTILIZER"})


def _worker_for_hand(hand_idx: int, hand_workers: tuple[str, ...]) -> str:
    if 0 <= hand_idx < len(hand_workers):
        return hand_workers[hand_idx]
    return hand_workers[-1] if hand_workers else f"hand{hand_idx}"


def _tile_worker(tile_idx: int, worker_tiles: dict[str, tuple[int, ...]]) -> str | None:
    for worker, tiles in worker_tiles.items():
        if tile_idx in tiles:
            return worker
    return None


def _parse_actor(line: str, hand_workers: tuple[str, ...]) -> tuple[str, str] | None:
    if " farmer " in line:
        return "farmer", line.split(" farmer ", 1)[1].strip()
    hm = re.search(r" hand(\d+) ", line)
    if hm:
        hand_idx = int(hm.group(1))
        rest = line.split(f" hand{hand_idx} ", 1)[1].strip()
        return _worker_for_hand(hand_idx, hand_workers), rest
    return None


def parse_earnings(
    lines: list[str],
    snaps: list[dict[str, Any]],
    *,
    season_days: int = 30,
    hand_workers: tuple[str, ...] = (),
    worker_tiles: dict[str, tuple[int, ...]] | None = None,
) -> dict[str, Any]:
    """Sell revenue from sell_rev logs; harvest/collect from earn= on exec lines."""
    dawn = {int(s["day"]): s for s in dawn_snaps(snaps)}
    sell_by_day = [0.0] * season_days
    net_by_day = [0.0] * season_days
    harvest_by_worker: dict[str, list[float]] = defaultdict(
        lambda: [0.0] * season_days
    )
    harvest_events_by_worker: dict[str, int] = defaultdict(int)
    sell_rev_logged = False
    earn_logged = False
    worker_tiles = worker_tiles or {}

    dawn_money = [
        float(dawn.get(d, {}).get("money", 0)) if d in dawn else None
        for d in range(season_days)
    ]
    for d in range(1, season_days):
        if dawn_money[d] is not None and dawn_money[d - 1] is not None:
            net_by_day[d] = dawn_money[d] - dawn_money[d - 1]

    for line in lines:
        if "[exec]" not in line:
            continue
        m = EXEC_RE.search(line)
        if not m:
            continue
        day, hour = int(m.group(1)), int(m.group(2))
        if not (0 <= day < season_days):
            continue

        if " market " in line:
            rm = SELL_REV_RE.search(line)
            if rm:
                sell_rev_logged = True
                sell_by_day[day] += int(rm.group(1))
            continue

        parsed = _parse_actor(line, hand_workers)
        if not parsed:
            continue
        actor, rest = parsed
        verb = rest.split()[0] if rest else ""
        if verb != "HARVEST" and verb not in _COLLECT_VERBS:
            continue

        tm = TILE_RE.search(rest)
        worker = actor
        if tm is not None and worker_tiles:
            worker = _tile_worker(int(tm.group(1)) - 1, worker_tiles) or actor

        em = EARN_RE.search(line)
        if em:
            earn_logged = True
            earn = int(em.group(1))
        elif verb in _COLLECT_VERBS:
            earn = FERTILIZER_BASE
        else:
            earn = 0

        if earn <= 0:
            continue

        harvest_by_worker[worker][day] += earn
        harvest_events_by_worker[worker] += 1

    harvest_total = [0.0] * season_days
    for series in harvest_by_worker.values():
        for d in range(season_days):
            harvest_total[d] += series[d]

    return {
        "sell_revenue_by_day": sell_by_day,
        "sell_rev_logged": sell_rev_logged,
        "earn_logged": earn_logged,
        "net_cash_by_day": net_by_day,
        "harvest_by_worker_by_day": dict(harvest_by_worker),
        "harvest_events_by_worker": dict(harvest_events_by_worker),
        "harvest_total_by_day": harvest_total,
    }
