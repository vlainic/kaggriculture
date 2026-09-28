"""Load crop rollout templates from data/crop_rollouts.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CROP_NAMES = ("WHEAT", "CARROT", "TOMATO", "MELON", "STRAWBERRY")
ANIMAL_PRODUCTS = ("EGG", "MILK", "WOOL")
PRODUCT_NAMES = CROP_NAMES + ANIMAL_PRODUCTS
SEASON_DAYS = 30  # full season: calendar days 0..29
PLAN_HORIZON = 28  # packing grid + plant_day cap (half-open −1, sell lag −1)
DAILY_OP_BUDGET = 16
FIRST_DAY_OP_RESERVE = 1  # day 0: one turn reserved for BUY_SEED market orders

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "crop_rollouts.json"

# Product demand units per unlocked shop (docs/project_overview.md town table).
SHOP_PRODUCT_DEMAND: dict[str, dict[str, int]] = {
    "BAKERY": {"WHEAT": 1, "EGG": 1},
    "PIZZA_SHOP": {"TOMATO": 1, "WHEAT": 1, "MILK": 1},
    "BRUNCH_SPOT": {"STRAWBERRY": 1, "WHEAT": 1, "EGG": 1},
    "ICE_CREAM_SHOP": {"STRAWBERRY": 1, "WHEAT": 1, "MILK": 1},
    "YARN_STORE": {"WOOL": 2},
    "SMOOTHIE_SHOP": {"STRAWBERRY": 1, "MILK": 1},
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


def profiles_for(crop: str) -> tuple[str, ...]:
    """Melon has no with_fert profile; others expose both."""
    keys = tuple(k for k in _load()["crops"][crop] if k in ("no_fert", "with_fert"))
    return keys if keys else ("no_fert",)


def plant_options() -> list[tuple[str, str]]:
    return [(crop, profile) for crop in CROP_NAMES for profile in profiles_for(crop)]


def _profile_data(crop: str, profile: str) -> dict:
    return _load()["crops"][crop][profile]


def shop_demand_by_product(unlocked_shops: list[str]) -> dict[str, int]:
    """Sum product demand units from currently unlocked town shops.

    Iterates the raw list (not deduped): duplicate shop entries double demand,
    matching competition behavior when the same shop unlocks more than once.
    """
    demand = dict.fromkeys(PRODUCT_NAMES, 0)
    for shop in unlocked_shops:
        for product, units in SHOP_PRODUCT_DEMAND.get(shop, {}).items():
            demand[product] = demand.get(product, 0) + units
    return demand


def shop_demand_by_crop(unlocked_shops: list[str]) -> dict[str, int]:
    """Backward-compatible crop-only view."""
    full = shop_demand_by_product(unlocked_shops)
    return {crop: full.get(crop, 0) for crop in CROP_NAMES}


def seed_cost(crop: str) -> int:
    return _load()["crops"][crop]["seed_cost"]


def expected_yield(crop: str, profile: str = "no_fert") -> int:
    return _profile_data(crop, profile)["expected_yield"]


def harvest_ages(crop: str, profile: str = "no_fert") -> list[int]:
    return list(_profile_data(crop, profile)["harvest_ages"])


def yield_per_harvest(crop: str, profile: str = "no_fert") -> list[int]:
    return list(_profile_data(crop, profile)["yield_per_harvest"])


def tile_free_age(crop: str, profile: str = "no_fert") -> int:
    return _profile_data(crop, profile)["tile_free_age"]


def fertilize_ages(crop: str, profile: str = "no_fert") -> list[int]:
    return list(_profile_data(crop, profile).get("fertilize_ages", []))


def fert_count(crop: str, profile: str = "no_fert") -> int:
    return len(fertilize_ages(crop, profile))


def actions_at_age(crop: str, age: int, profile: str = "no_fert") -> list[str]:
    for day in _profile_data(crop, profile)["days"]:
        if day["age"] == age:
            return list(day["actions"])
    return []


def ops_count_at_age(crop: str, age: int, profile: str = "no_fert") -> int:
    return len(actions_at_age(crop, age, profile))


def covered_days(
    crop: str, plant_day: int, horizon: int, profile: str = "no_fert"
) -> set[int]:
    """Calendar days this lifecycle occupies on its tile (half-open: excludes free day)."""
    days: set[int] = set()
    for age in range(tile_free_age(crop, profile)):
        cal = plant_day + age
        if cal < horizon:
            days.add(cal)
    return days


def ops_by_calendar_day(
    crop: str, plant_day: int, horizon: int, profile: str = "no_fert"
) -> dict[int, int]:
    """Tile ops per calendar day, plus +1 PICKUP per fert unit on fertilize days."""
    return executor_ops_by_day(crop, plant_day, horizon, profile)


def executor_ops_by_day(
    crop: str, plant_day: int, horizon: int, profile: str = "no_fert"
) -> dict[int, int]:
    """All farmer turns per calendar day (tile actions + fert PICKUP)."""
    out: dict[int, int] = {}
    for day in _profile_data(crop, profile)["days"]:
        cal = plant_day + day["age"]
        if cal < horizon:
            out[cal] = len(day["actions"])
    for age in fertilize_ages(crop, profile):
        cal = plant_day + age
        if cal < horizon:
            out[cal] = out.get(cal, 0) + 1
    return out


def lifecycle_fits(
    crop: str, plant_day: int, horizon: int, profile: str = "no_fert"
) -> bool:
    for day in _profile_data(crop, profile)["days"]:
        if plant_day + day["age"] >= horizon:
            return False
    return True


def profile_days(crop: str, profile: str = "no_fert") -> list[dict]:
    return list(_profile_data(crop, profile)["days"])
