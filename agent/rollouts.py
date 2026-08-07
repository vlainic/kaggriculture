"""Load crop rollout templates from data/crop_rollouts.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PROFILE = "no_fert"
CROP_NAMES = ("WHEAT", "CARROT", "TOMATO", "MELON", "STRAWBERRY")
SEASON_DAYS = 30  # full season: calendar days 0..29
PLAN_HORIZON = 28  # packing grid + plant_day cap (half-open −1, sell lag −1)
DAILY_OP_BUDGET = 16
FIRST_DAY_OP_RESERVE = 1  # day 0: one turn reserved for BUY_SEED market orders

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "crop_rollouts.json"

# Crop demand units per unlocked shop (from docs/README.md town table).
SHOP_CROP_DEMAND: dict[str, dict[str, int]] = {
    "BAKERY": {"WHEAT": 1},
    "PIZZA_SHOP": {"TOMATO": 1, "WHEAT": 1},
    "BRUNCH_SPOT": {"STRAWBERRY": 1, "WHEAT": 1},
    "ICE_CREAM_SHOP": {"STRAWBERRY": 1, "WHEAT": 1},
    "PET_CAFE": {"CARROT": 2},
    "FARMERS_MARKET": {
        "WHEAT": 1,
        "CARROT": 1,
        "TOMATO": 1,
        "STRAWBERRY": 1,
    },
}


@lru_cache(maxsize=1)
def _load() -> dict:
    with _DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def daily_op_budget(day: int) -> int:
    """Farmer tile-op capacity for a calendar day (day 0 reserves one turn for buying)."""
    if day == 0:
        return DAILY_OP_BUDGET - FIRST_DAY_OP_RESERVE
    return DAILY_OP_BUDGET


def crop_names() -> tuple[str, ...]:
    return CROP_NAMES


def shop_demand_by_crop(unlocked_shops: list[str]) -> dict[str, int]:
    """Sum crop demand units from currently unlocked town shops."""
    demand = dict.fromkeys(CROP_NAMES, 0)
    for shop in unlocked_shops:
        for crop, units in SHOP_CROP_DEMAND.get(shop, {}).items():
            demand[crop] += units
    return demand


def seed_cost(crop: str) -> int:
    return _load()["crops"][crop]["seed_cost"]


def expected_yield(crop: str) -> int:
    return _load()["crops"][crop][PROFILE]["expected_yield"]


def harvest_ages(crop: str) -> list[int]:
    return list(_load()["crops"][crop][PROFILE]["harvest_ages"])


def tile_free_age(crop: str) -> int:
    return _load()["crops"][crop][PROFILE]["tile_free_age"]


def actions_at_age(crop: str, age: int) -> list[str]:
    for day in _load()["crops"][crop][PROFILE]["days"]:
        if day["age"] == age:
            return list(day["actions"])
    return []


def ops_count_at_age(crop: str, age: int) -> int:
    return len(actions_at_age(crop, age))


def covered_days(crop: str, plant_day: int, horizon: int) -> set[int]:
    """Calendar days this lifecycle occupies on its tile (half-open: excludes free day)."""
    days = set()
    for age in range(tile_free_age(crop)):
        cal = plant_day + age
        if cal < horizon:
            days.add(cal)
    return days


def ops_by_calendar_day(crop: str, plant_day: int, horizon: int) -> dict[int, int]:
    out: dict[int, int] = {}
    for day in _load()["crops"][crop][PROFILE]["days"]:
        cal = plant_day + day["age"]
        if cal < horizon:
            out[cal] = len(day["actions"])
    return out


def lifecycle_fits(crop: str, plant_day: int, horizon: int) -> bool:
    for day in _load()["crops"][crop][PROFILE]["days"]:
        if plant_day + day["age"] >= horizon:
            return False
    return True


def profile_days(crop: str) -> list[dict]:
    return list(_load()["crops"][crop][PROFILE]["days"])
