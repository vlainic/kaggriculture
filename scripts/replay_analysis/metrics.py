"""Farm / economy metrics from replay steps."""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import animal_rollouts, rollouts  # noqa: E402

from replay_analysis.load import SEASON_DAYS, Replay, StepRecord

SELLABLE = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)


def _tile_kind(tile: Any) -> str:
    if tile is None:
        return "empty"
    if tile == "LOCKED":
        return "locked"
    if isinstance(tile, dict):
        kind = tile.get("kind")
        if kind == "WEED":
            return "weed"
        if kind == "PLANT":
            return "occupied"
        if kind in ("COOP", "PASTURE"):
            if tile.get("animal"):
                return "occupied"
            return "empty_structure"
    return "other"


def _count_tiles(farm: dict[str, Any]) -> dict[str, int]:
    counts = Counter()
    for row in farm.get("tiles") or []:
        for tile in row:
            counts[_tile_kind(tile)] += 1
    return dict(counts)


def _worker_positions(rec: StepRecord) -> list[tuple[str, list[Any]]]:
    obs = rec.observation
    player = rec.player
    farm = obs["farms"][player]
    fx, fy = farm["farmer"]
    out: list[tuple[str, list[Any]]] = [("farmer", [fx, fy])]
    for hi, pos in enumerate(farm.get("hands") or []):
        out.append((f"hand{hi}", pos))
    return out


def _tile_at(farm: dict[str, Any], x: int, y: int) -> Any:
    return farm["tiles"][y][x]


def _iter_unit_actions(rec: StepRecord) -> list[tuple[str, list[Any]]]:
    act = rec.action
    out: list[tuple[str, list[Any]]] = []
    farmer = act.get("farmer") or ["PASS"]
    if isinstance(farmer, list) and farmer:
        out.append(("farmer", farmer))
    for hi, hand in enumerate(act.get("hands") or []):
        if isinstance(hand, list) and hand:
            out.append((f"hand{hi}", hand))
    return out


def _merge_inv(target: Counter[str], source: dict[str, int] | Counter[str]) -> None:
    for k, v in source.items():
        if v:
            target[k] += int(v)


def _inventory_totals(private: dict[str, Any]) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for inv in private.get("inventories") or []:
        if isinstance(inv, dict):
            _merge_inv(totals, inv)
    return dict(totals)


def daily_tile_counts(replay: Replay) -> dict[int, list[dict[str, dict[str, int]]]]:
    """player -> list[day] -> tile count dict (hour 0 snapshots)."""
    out: dict[int, list[dict[str, dict[str, int]]]] = {
        p: [{} for _ in range(SEASON_DAYS)] for p in range(len(replay.team_names))
    }
    seen_day: dict[int, set[int]] = {p: set() for p in out}

    for rec in _all_records(replay):
        obs = rec.observation
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        if hour != 0 or day >= SEASON_DAYS:
            continue
        if day in seen_day[rec.player]:
            continue
        seen_day[rec.player].add(day)
        farm = obs["farms"][rec.player]
        out[rec.player][day] = _count_tiles(farm)

    for p in out:
        for day in range(SEASON_DAYS):
            if day not in seen_day[p]:
                # fill from nearest prior day or zeros
                prior = next(
                    (out[p][d] for d in range(day, -1, -1) if out[p][d]),
                    None,
                )
                out[p][day] = prior or {
                    "occupied": 0,
                    "empty": 0,
                    "weed": 0,
                    "empty_structure": 0,
                    "locked": 0,
                    "other": 0,
                }

    return [out[p] for p in sorted(out)]


def pass_counts(replay: Replay) -> dict[int, dict[str, Any]]:
    per_player: dict[int, dict[str, Any]] = {}
    for p in range(len(replay.team_names)):
        per_turn: list[int] = []
        per_day: Counter[int] = Counter()
        workers_by_day: dict[int, int] = {}
        for rec in replay.iter_player(p):
            obs = rec.observation
            day = int(obs.get("day", 0))
            hour = int(obs.get("hour", 0))
            if hour == 0 and day < SEASON_DAYS:
                farm = obs["farms"][p]
                workers_by_day[day] = 1 + len(farm.get("hands") or [])
            n_pass = 0
            for _who, action in _iter_unit_actions(rec):
                if action and action[0] == "PASS":
                    n_pass += 1
            per_turn.append(n_pass)
            per_day[day] += n_pass
        total = sum(per_turn)
        workers_series = [
            int(workers_by_day.get(d, workers_by_day.get(d - 1, 1)))
            for d in range(SEASON_DAYS)
        ]
        per_worker = [
            (per_day[d] / workers_series[d]) if workers_series[d] else 0.0
            for d in range(SEASON_DAYS)
        ]
        per_player[p] = {
            "per_turn": per_turn,
            "per_day": [int(per_day[d]) for d in range(SEASON_DAYS)],
            "workers_by_day": workers_series,
            "per_worker_by_day": per_worker,
            "total": total,
            "mean_per_turn": total / len(per_turn) if per_turn else 0.0,
            "mean_per_worker": (
                sum(per_worker) / len([x for x in per_worker if x > 0])
                if any(x > 0 for x in per_worker)
                else 0.0
            ),
        }
    return per_player


def _total_private_stock(private: dict[str, Any]) -> Counter[str]:
    stock: Counter[str] = Counter()
    _merge_inv(stock, private.get("shed") or {})
    for inv in private.get("inventories") or []:
        if isinstance(inv, dict):
            _merge_inv(stock, inv)
    return stock


def _submitted_sell_qty(rec: StepRecord) -> Counter[str]:
    qty: Counter[str] = Counter()
    for order in (rec.action.get("market") or []):
        if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
            qty[str(order[1])] += int(order[2])
    return qty


def _feed_count(rec: StepRecord) -> int:
    return sum(
        1
        for _who, action in _iter_unit_actions(rec)
        if action and action[0] == "FEED"
    )


def sold_units(replay: Replay) -> dict[int, dict[str, int]]:
    """Units that actually left shed+inventory via market SELL (replay stock outflow)."""
    sold: dict[int, Counter[str]] = {
        p: Counter() for p in range(len(replay.team_names))
    }

    for p in range(len(replay.team_names)):
        records = list(replay.iter_player(p))
        for i in range(1, len(records)):
            prev_rec, rec = records[i - 1], records[i]
            prev_stock = _total_private_stock(prev_rec.observation.get("private") or {})
            curr_stock = _total_private_stock(rec.observation.get("private") or {})
            sell_qty = _submitted_sell_qty(rec)

            for prod in SELLABLE:
                dec = int(prev_stock.get(prod, 0)) - int(curr_stock.get(prod, 0))
                if prod == "WHEAT":
                    dec = max(0, dec - _feed_count(rec))
                if dec <= 0 or sell_qty.get(prod, 0) <= 0:
                    continue
                sold[p][prod] += min(dec, int(sell_qty[prod]))

    return {p: dict(sold[p]) for p in sold}


def harvest_yield(replay: Replay) -> dict[int, dict[str, int]]:
    """Units harvested/collected — positive shed+inventory delta per turn."""
    yields: dict[int, Counter[str]] = {
        p: Counter() for p in range(len(replay.team_names))
    }

    for p in range(len(replay.team_names)):
        records = list(replay.iter_player(p))
        if not records:
            continue
        prev_stock = _total_private_stock(records[0].observation.get("private") or {})
        for i in range(1, len(records)):
            rec = records[i]
            curr_stock = _total_private_stock(rec.observation.get("private") or {})
            delta: Counter[str] = Counter(curr_stock)
            for prod, qty in prev_stock.items():
                delta[prod] -= qty

            for order in (rec.action.get("market") or []):
                if isinstance(order, list) and len(order) >= 3 and order[0] == "BUY_PRODUCT":
                    delta[str(order[1])] -= int(order[2])

            for prod, qty in delta.items():
                if prod in SELLABLE and qty > 0:
                    yields[p][prod] += qty

            prev_stock = curr_stock

    return {p: dict(yields[p]) for p in yields}


def _crop_profile(crop: str) -> str:
    return "no_fert" if crop == "MELON" else "with_fert"


def _clip_harvest_total(
    harvest_ages: list[int],
    yields_per: list[int],
    start_day: int,
) -> int:
    total = 0
    for age, units in zip(harvest_ages, yields_per):
        if start_day + age < SEASON_DAYS:
            total += units
    return total


def potential_yield(replay: Replay) -> dict[int, dict[str, int]]:
    """Perfect-care ceiling for plantings/animals actually placed on the board."""
    potential: dict[int, Counter[str]] = {
        p: Counter() for p in range(len(replay.team_names))
    }
    seen_plants: set[tuple[int, int, int, int]] = set()
    seen_animals: set[tuple[int, int, int, int]] = set()
    animal_days: dict[tuple[int, int, int, int], set[int]] = {}

    for rec in _all_records(replay):
        obs = rec.observation
        player = rec.player
        day = int(obs.get("day", 0))
        farm = obs["farms"][player]
        for y, row in enumerate(farm.get("tiles") or []):
            for x, tile in enumerate(row):
                if not isinstance(tile, dict):
                    continue
                if tile.get("kind") == "PLANT":
                    crop = tile.get("crop")
                    planted = tile.get("planted_day")
                    if crop is None or planted is None:
                        continue
                    key = (player, x, y, int(planted))
                    if key not in seen_plants:
                        seen_plants.add(key)
                        profile = _crop_profile(crop)
                        total = _clip_harvest_total(
                            rollouts.harvest_ages(crop, profile),
                            rollouts.yield_per_harvest(crop, profile),
                            int(planted),
                        )
                        potential[player][crop] += total
                elif tile.get("kind") in ("COOP", "PASTURE") and tile.get("animal"):
                    animal = tile["animal"]
                    placed = tile.get("placed_day")
                    if placed is None:
                        continue
                    key = (player, x, y, int(placed))
                    if key not in seen_animals:
                        seen_animals.add(key)
                        product = animal_rollouts.product_for(animal)
                        total = _clip_harvest_total(
                            animal_rollouts.harvest_ages(animal, "with_care"),
                            animal_rollouts.yield_per_harvest(animal, "with_care"),
                            int(placed),
                        )
                        potential[player][product] += total
                    animal_days.setdefault(key, set()).add(day)

    for p in range(len(replay.team_names)):
        fert_days = 0
        for key, days in animal_days.items():
            if key[0] != p:
                continue
            fert_days += len(days)
        if fert_days:
            potential[p]["FERTILIZER"] += fert_days

    return {p: dict(potential[p]) for p in potential}


def end_shed(replay: Replay) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    if not replay.steps:
        return out
    last = replay.steps[-1]
    for rec in last:
        priv = rec.observation.get("private") or {}
        shed = {k: int(v) for k, v in (priv.get("shed") or {}).items() if v}
        carried = _inventory_totals(priv)
        combined: Counter[str] = Counter()
        _merge_inv(combined, shed)
        _merge_inv(combined, carried)
        out[rec.player] = {
            "shed": shed,
            "carried": carried,
            "combined": dict(combined),
        }
    return out


def daily_money(replay: Replay) -> dict[int, dict[str, Any]]:
    """Day start (h=0) and end (next h=0) bank balances per player."""
    start_by_day: dict[int, dict[int, float]] = {
        p: {} for p in range(len(replay.team_names))
    }

    for rec in _all_records(replay):
        obs = rec.observation
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        if hour != 0 or day >= SEASON_DAYS:
            continue
        money = float(obs["farms"][rec.player]["money"])
        start_by_day[rec.player][day] = money

    result: dict[int, dict[str, Any]] = {}
    for p in range(len(replay.team_names)):
        start = [
            float(start_by_day[p].get(d, float("nan"))) for d in range(SEASON_DAYS)
        ]
        end: list[float] = []
        for d in range(SEASON_DAYS):
            if d + 1 < SEASON_DAYS and d + 1 in start_by_day[p]:
                end.append(float(start_by_day[p][d + 1]))
            elif d + 1 == SEASON_DAYS:
                end.append(float(replay.rewards[p]) if p < len(replay.rewards) else float("nan"))
            else:
                end.append(float("nan"))
        result[p] = {
            "start": start,
            "end": end,
            "final_reward": float(replay.rewards[p]) if p < len(replay.rewards) else None,
        }
    return result


def submitted_sells(replay: Replay) -> dict[int, dict[str, int]]:
    sold: dict[int, Counter[str]] = {
        p: Counter() for p in range(len(replay.team_names))
    }
    for rec in _all_records(replay):
        for order in (rec.action.get("market") or []):
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                product = str(order[1])
                qty = int(order[2])
                sold[rec.player][product] += qty
    return {p: dict(sold[p]) for p in sold}


def _all_records(replay: Replay):
    for step in replay.steps:
        for rec in step:
            yield rec
