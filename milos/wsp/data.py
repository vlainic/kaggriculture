"""Load crop/animal rollout JSON from repo data/ (not agent/)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_REPO_DATA = Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=1)
def crops() -> dict:
    with (_REPO_DATA / "crop_rollouts.json").open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def animals() -> dict:
    with (_REPO_DATA / "animal_with_pickups.json").open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def i0_base_prices() -> dict[str, int]:
    prices = {crop: spec["base_price"] for crop, spec in crops()["crops"].items()}
    for spec in animals()["animals"].values():
        prices[spec["product"]] = spec["base_price"]
    return prices


def tile_free_age(crop: str, profile: str) -> int:
    from milos.wsp.config import CROP_FREE_AGE

    spec = crops()["crops"].get(crop, {})
    if profile in spec and "tile_free_age" in spec[profile]:
        return int(spec[profile]["tile_free_age"])
    return int(CROP_FREE_AGE.get((crop, profile), 7))
