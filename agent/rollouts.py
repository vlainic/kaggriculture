"""Load crop rollout templates from data/crop_rollouts.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PROFILE = "no_fert"
CROP_NAMES = ("WHEAT", "CARROT", "TOMATO", "MELON", "STRAWBERRY")
SEASON_DAYS = 30
DAILY_OP_BUDGET = 16

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "crop_rollouts.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with _DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def crop_names() -> tuple[str, ...]:
    return CROP_NAMES


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
