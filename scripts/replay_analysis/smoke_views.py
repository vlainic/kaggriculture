"""Build smoke_analysis-shaped earnings/actions views from a replay (us player)."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.pricing import base_price  # noqa: E402
from smoke_analysis.parse_actions import (  # noqa: E402
    ACTION_ORDER,
    HOURS_PER_DAY,
    _aggregate_capacity,
    classify_action,
)

from replay_analysis.load import SEASON_DAYS, Replay, load_replay
from replay_analysis.metrics import _iter_unit_actions, _total_private_stock


def _layout() -> tuple[
    list[str],
    tuple[str, ...],
    dict[str, list[int]],
    dict[tuple[int, int], int],
    dict[str, int],
]:
    from smoke_analysis.layout import active_layout

    lay = active_layout()
    workers = list(lay["workers"])
    hand_workers = tuple(lay["hand_workers"])
    worker_tiles = {w: list(tiles) for w, tiles in lay["worker_tiles"].items()}
    net_tile_ops = dict(lay["net_tile_ops"])
    if lay["package"] == "milos":
        from milos import zoning
    else:
        from agent import zoning

    coord_to_idx = {xy: i for i, xy in enumerate(zoning.TILE_COORDS)}
    return workers, hand_workers, worker_tiles, coord_to_idx, net_tile_ops


def _who_to_worker(who: str, hand_workers: tuple[str, ...]) -> str:
    if who == "farmer":
        return "farmer"
    if who.startswith("hand"):
        idx = int(who[4:])
        if 0 <= idx < len(hand_workers):
            return hand_workers[idx]
        return who
    return who


def _product_from_tile(tile: Any) -> str | None:
    if not isinstance(tile, dict):
        return None
    kind = tile.get("kind")
    if kind == "PLANT":
        crop = tile.get("crop")
        return str(crop) if crop else None
    if kind in ("COOP", "PASTURE"):
        animal = tile.get("animal")
        if animal == "GOOSE":
            return "EGG"
        if animal == "COW":
            return "MILK"
        if animal == "SHEEP":
            return "WOOL"
        if kind == "COOP":
            return "EGG"
        return "MILK"
    return None


def _tile_worker(
    x: int, y: int, coord_to_idx: dict[tuple[int, int], int], worker_tiles: dict[str, list[int]]
) -> str | None:
    idx = coord_to_idx.get((x, y))
    if idx is None:
        return None
    for worker, tiles in worker_tiles.items():
        if idx in tiles:
            return worker
    return None


def build_smoke_style_report(
    replay: Replay,
    player: int,
    *,
    stem: str | None = None,
) -> dict[str, Any]:
    """Smoke-compatible dict for plot_earnings_* / plot_worker_actions / plot_zone_capacity."""
    workers, hand_workers, worker_tiles, coord_to_idx, net_tile_ops = _layout()
    worker_idx = {w: i for i, w in enumerate(workers)}
    n_actions = len(ACTION_ORDER)
    action_idx = {a: i for i, a in enumerate(ACTION_ORDER)}

    sell_by_day = [0.0] * SEASON_DAYS
    net_by_day = [0.0] * SEASON_DAYS
    harvest_by_worker: dict[str, list[float]] = {
        w: [0.0] * SEASON_DAYS for w in workers
    }
    harvest_events: dict[str, int] = defaultdict(int)
    buy_land_day: int | None = None

    grid = np.full(
        (len(workers) * n_actions, SEASON_DAYS * HOURS_PER_DAY),
        np.nan,
        dtype=float,
    )

    records = list(replay.iter_player(player))
    money_start: dict[int, float] = {}
    money_end: dict[int, float] = {}
    cap_events: list[dict[str, Any]] = []

    for i, rec in enumerate(records):
        obs = rec.observation
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        if day < 0 or day >= SEASON_DAYS:
            continue
        farm = obs["farms"][player]
        money = float(farm.get("money") or 0)
        if hour == 0 and day not in money_start:
            money_start[day] = money
        money_end[day] = money

        pre = records[i - 1].observation if i > 0 else obs
        pre_farm = pre["farms"][player]

        for order in rec.action.get("market") or []:
            if not isinstance(order, list) or not order:
                continue
            if order[0] == "BUY_LAND" and buy_land_day is None:
                buy_land_day = day
            if len(order) >= 3 and order[0] == "SELL":
                # filled revenue approximated later from stock; skip here
                pass

        for who, action in _iter_unit_actions(rec):
            if not action:
                continue
            worker = _who_to_worker(who, hand_workers)
            if worker not in worker_idx:
                continue
            verb = str(action[0])
            bucket = classify_action(verb)
            wi = worker_idx[worker]
            ai = action_idx[bucket]
            row = wi * n_actions + ai
            col = day * HOURS_PER_DAY + hour
            grid[row, col] = ai + 1
            cap_events.append(
                {
                    "worker": worker,
                    "day": day,
                    "hour": hour,
                    "verb": verb,
                    "bucket": bucket,
                    "note": "",
                }
            )

            if verb in ("HARVEST", "COLLECT_FERTILIZER") and i > 0 and 0 <= hour < HOURS_PER_DAY:
                if who == "farmer":
                    pos = list(pre_farm.get("farmer") or [0, 0])
                else:
                    hi = int(who[4:])
                    hands = pre_farm.get("hands") or []
                    pos = list(hands[hi]) if hi < len(hands) else [0, 0]
                x, y = int(pos[0]), int(pos[1])
                tile = pre_farm["tiles"][y][x]
                zone = _tile_worker(x, y, coord_to_idx, worker_tiles) or worker
                if verb == "COLLECT_FERTILIZER":
                    earn = float(base_price("FERTILIZER"))
                    harvest_by_worker.setdefault(zone, [0.0] * SEASON_DAYS)
                    harvest_by_worker[zone][day] += earn
                    harvest_events[zone] += 1
                elif isinstance(tile, dict):
                    units = int(tile.get("yield_units") or 0)
                    product = _product_from_tile(tile)
                    if units > 0 and product:
                        try:
                            earn = float(units * base_price(product))
                        except KeyError:
                            earn = float(units * 25)
                        harvest_by_worker.setdefault(zone, [0.0] * SEASON_DAYS)
                        harvest_by_worker[zone][day] += earn
                        harvest_events[zone] += 1

        if i > 0:
            prev_stock = _total_private_stock(pre.get("private") or {})
            curr_stock = _total_private_stock(obs.get("private") or {})
            sell_qty: dict[str, int] = {}
            for order in rec.action.get("market") or []:
                if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                    sell_qty[str(order[1])] = sell_qty.get(str(order[1]), 0) + int(
                        order[2]
                    )
            for prod, qty in sell_qty.items():
                dec = int(prev_stock.get(prod, 0)) - int(curr_stock.get(prod, 0))
                filled = max(0, min(dec, qty))
                if filled <= 0:
                    continue
                try:
                    sell_by_day[day] += filled * float(base_price(prod))
                except KeyError:
                    sell_by_day[day] += filled * 25.0
    for d in range(SEASON_DAYS):
        s = money_start.get(d)
        e = money_end.get(d)
        if s is not None and e is not None:
            net_by_day[d] = e - s

    by_worker_by_day = _aggregate_capacity(cap_events, workers, SEASON_DAYS)

    return {
        "replay_stem": stem or replay.path.stem,
        "log_stem": stem or replay.path.stem,
        "workers": workers,
        "net_tile_ops": net_tile_ops,
        "buy_land_day": buy_land_day,
        "earnings": {
            "sell_revenue_by_day": sell_by_day,
            "net_cash_by_day": net_by_day,
            "harvest_by_worker_by_day": harvest_by_worker,
            "harvest_events_by_worker": dict(harvest_events),
            "sell_rev_logged": True,
            "earn_logged": False,
            "harv_inferred": True,
        },
        "actions": {
            "grid": grid,
            "action_order": list(ACTION_ORDER),
            "hours_per_day": HOURS_PER_DAY,
            "events": cap_events,
            "by_worker_by_day": by_worker_by_day,
        },
    }


def smoke_style_from_report(report: dict[str, Any]) -> dict[str, Any]:
    """If report already has smoke earnings/actions, return it; else load replay."""
    if report.get("earnings") and report.get("actions"):
        return report
    path = report.get("replay_path")
    if not path:
        raise ValueError("report missing replay_path (and no smoke earnings/actions)")
    replay = load_replay(path)
    us = report.get("us_index")
    if us is None:
        us = 0
    return build_smoke_style_report(
        replay, int(us), stem=report.get("replay_stem")
    )
