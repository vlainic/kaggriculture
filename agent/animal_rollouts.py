"""Load animal rollout templates from data/animal_rollouts.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ANIMAL_NAMES = ("GOOSE", "COW", "SHEEP")
ANIMAL_PRODUCTS = ("EGG", "MILK", "WOOL")
WHEAT_PRICE = 25
BUILD_DAY_OFFSET = -1

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "animal_rollouts.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with _DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def animal_names() -> tuple[str, ...]:
    return ANIMAL_NAMES


def profiles_for(animal: str) -> tuple[str, ...]:
    keys = tuple(k for k in _load()["animals"][animal] if k in ("no_care", "with_care"))
    return keys if keys else ("no_care",)


def animal_options() -> list[tuple[str, str]]:
    return [(animal, profile) for animal in ANIMAL_NAMES for profile in profiles_for(animal)]


def _animal_spec(animal: str) -> dict:
    return _load()["animals"][animal]


def _profile_data(animal: str, profile: str) -> dict:
    return _animal_spec(animal)[profile]


def animal_cost(animal: str) -> int:
    return _animal_spec(animal)["animal_cost"]


def base_price(animal: str) -> int:
    return _animal_spec(animal)["base_price"]


def product_for(animal: str) -> str:
    return _animal_spec(animal)["product"]


def structure_for(animal: str) -> str:
    return _animal_spec(animal)["structure"]


def build_action_for(animal: str) -> str:
    return _animal_spec(animal)["build_action"]


def profile_days(animal: str, profile: str = "no_care") -> list[dict]:
    return list(_profile_data(animal, profile)["days"])


def harvest_ages(animal: str, profile: str = "no_care") -> list[int]:
    return list(_profile_data(animal, profile)["harvest_ages"])


def yield_per_harvest(animal: str, profile: str = "no_care") -> list[int]:
    return list(_profile_data(animal, profile)["yield_per_harvest"])


def expected_yield(animal: str, profile: str = "no_care") -> int:
    return _profile_data(animal, profile)["expected_yield"]


def actions_at_age(animal: str, age: int, profile: str = "no_care") -> list[str]:
    for day in _profile_data(animal, profile)["days"]:
        if day["age"] == age:
            return list(day["actions"])
    return []


def ops_count_at_age(animal: str, age: int, profile: str = "no_care") -> int:
    return len(actions_at_age(animal, age, profile))


def covered_days(
    animal: str, place_day: int, horizon: int, profile: str = "no_care"
) -> set[int]:
    """Calendar days this animal occupies its tile (truncated at horizon)."""
    days: set[int] = set()
    for age_day in _profile_data(animal, profile)["days"]:
        cal = place_day + age_day["age"]
        if cal < horizon:
            days.add(cal)
        else:
            break
    return days


def ops_by_calendar_day(
    animal: str, place_day: int, horizon: int, profile: str = "no_care"
) -> dict[int, int]:
    return executor_ops_by_day(animal, place_day, horizon, profile)


def executor_ops_by_day(
    animal: str,
    place_day: int,
    horizon: int,
    profile: str = "no_care",
    min_day: int = 0,
) -> dict[int, int]:
    """All farmer turns per calendar day (pickups JSON already includes shed trips)."""
    out: dict[int, int] = {}
    for day in _profile_data(animal, profile)["days"]:
        cal = place_day + day["age"]
        if cal < min_day:
            continue
        if cal >= horizon:
            break
        out[cal] = len(day["actions"])
    return out


def revenue_in_window(
    animal: str,
    place_day: int,
    horizon: int,
    profile: str = "no_care",
    unit_price: int | None = None,
) -> int:
    price = unit_price if unit_price is not None else base_price(animal)
    total = 0
    for age, units in zip(
        harvest_ages(animal, profile), yield_per_harvest(animal, profile)
    ):
        if place_day + age < horizon:
            total += units * price
    return total
