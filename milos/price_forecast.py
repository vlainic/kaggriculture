"""Conservative per-day market quotes for dawn replan (inventory walk)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from milos import animal_rollouts, pricing, rollouts
from milos.replan_lock import (
    ANIMAL_PROFILE,
    CROP_PROFILE,
    _parse_profile_key,
    _queue_suffix_to_chain,
    _rollout_spec,
    replan_eligible,
)
from milos.workers import TILE_COORDS
from milos.zoning import NUM_TILES

SHOP_INTERVAL = 4
TOWN_CENTER_INTERVAL = 12
SELL_PRODUCTS: tuple[str, ...] = (
    "MELON",
    "STRAWBERRY",
    "MILK",
    "WOOL",
    "WHEAT",
    "CARROT",
    "TOMATO",
    "EGG",
    "FERTILIZER",
)
_TOWN_CENTER_PRODUCTS = tuple(p for p in SELL_PRODUCTS if p != "FERTILIZER")


def _town_center_units(abs_day: int) -> int:
    if abs_day >= 20:
        return 4
    if abs_day >= 10:
        return 2
    return 1

OPP_CROP_PROFILE = "with_fert"
OPP_ANIMAL_PROFILE = "with_care"


def _tile_at(me: dict, idx: int):
    x, y = TILE_COORDS[idx]
    return me["tiles"][y][x]


def _product_for_label(label: str, kind: str) -> str:
    if kind == "animal":
        return animal_rollouts.product_for(label)
    return label


def _resolve_profile(
    label: str,
    profile_name: str,
    crops_data: dict,
    animals_data: dict,
) -> str | None:
    spec = crops_data.get("crops", {}).get(label) or animals_data.get(
        "animals", {}
    ).get(label)
    if spec is None:
        return None
    if profile_name in spec:
        return profile_name
    for alt in ("with_fert", "no_fert", "with_care", "no_care"):
        if alt in spec:
            return alt
    return None


def _add_profile_harvests(
    label: str,
    profile_name: str,
    rel_start: int,
    min_age: int,
    horizon: int,
    supply: dict[str, list[int]],
    crops_data: dict,
    animals_data: dict,
) -> None:
    resolved = _resolve_profile(label, profile_name, crops_data, animals_data)
    if resolved is None:
        return
    kind, _spec, profile = _rollout_spec(label, resolved, crops_data, animals_data)
    product = _product_for_label(label, kind)
    if product not in supply:
        return
    for age, yld in zip(profile["harvest_ages"], profile["yield_per_harvest"]):
        if age < min_age:
            continue
        hday = rel_start + (age - min_age)
        if 0 <= hday < horizon:
            supply[product][hday] += yld


def _empty_supply(horizon: int) -> dict[str, list[int]]:
    return {p: [0] * horizon for p in pricing.MARKET_PARAMS}


def _inv_after_sells(product: str, inv: int, units: int) -> int:
    cur = inv
    for _ in range(units):
        if pricing.quoted(product, cur) > 1:
            cur += 1
    return cur


def shop_drain_per_day(unlocked_shops: list[str]) -> dict[str, float]:
    per_tick = rollouts.shop_demand_by_product(unlocked_shops)
    scale = 24 / SHOP_INTERVAL
    return {p: per_tick.get(p, 0) * scale for p in SELL_PRODUCTS}


def town_drain_per_day(abs_day: int) -> dict[str, float]:
    units = _town_center_units(abs_day)
    scale = 24 / TOWN_CENTER_INTERVAL
    return {p: units * scale for p in _TOWN_CENTER_PRODUCTS}


def _stamp_live_tile_harvests(
    tile: dict,
    day: int,
    horizon: int,
    supply: dict[str, list[int]],
    crops_data: dict,
    animals_data: dict,
    *,
    crop_profile: str,
    animal_profile: str,
) -> None:
    if tile.get("kind") == "PLANT":
        crop = tile["crop"]
        current_age = day - tile["planted_day"]
        _add_profile_harvests(
            crop, crop_profile, 0, current_age, horizon, supply, crops_data, animals_data
        )
    elif tile.get("kind") in ("COOP", "PASTURE") and tile.get("animal"):
        animal = tile["animal"]
        current_age = day - tile["placed_day"]
        _add_profile_harvests(
            animal,
            animal_profile,
            0,
            current_age,
            horizon,
            supply,
            crops_data,
            animals_data,
        )


def _collect_frozen_supply(
    me: dict,
    day: int,
    horizon: int,
    tile_queues: dict,
    st_map: dict,
    supply: dict[str, list[int]],
    crops_data: dict,
    animals_data: dict,
) -> None:
    for idx in range(NUM_TILES):
        tile = _tile_at(me, idx)
        st = st_map.get(idx, {})
        if replan_eligible(idx, tile, st, tile_queues):
            continue
        if isinstance(tile, dict):
            _stamp_live_tile_harvests(
                tile,
                day,
                horizon,
                supply,
                crops_data,
                animals_data,
                crop_profile=CROP_PROFILE,
                animal_profile=ANIMAL_PROFILE,
            )
        qi = st.get("queue_idx", 0)
        lag = st.get("lag", 0)
        gap = st.get("gap", 0)
        queue = tile_queues.get(idx, [])
        chain = _queue_suffix_to_chain(queue, qi, lag, gap, day, horizon, me, idx)
        for profile_key, rel_start in chain:
            label, profile_name = _parse_profile_key(profile_key)
            _add_profile_harvests(
                label,
                profile_name,
                rel_start,
                0,
                horizon,
                supply,
                crops_data,
                animals_data,
            )


def _collect_opponent_supply(
    opp_farm: dict,
    day: int,
    horizon: int,
    supply: dict[str, list[int]],
    crops_data: dict,
    animals_data: dict,
) -> None:
    for row in opp_farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            _stamp_live_tile_harvests(
                tile,
                day,
                horizon,
                supply,
                crops_data,
                animals_data,
                crop_profile=OPP_CROP_PROFILE,
                animal_profile=OPP_ANIMAL_PROFILE,
            )


def _add_shed_day0(obs: dict, supply: dict[str, list[int]]) -> None:
    if not supply:
        return
    shed = (obs.get("private") or {}).get("shed", {})
    for product in supply:
        n = int(shed.get(product, 0) or 0)
        if n > 0:
            supply[product][0] += n


def walk_prices(
    start_inv: dict[str, int],
    supply: dict[str, list[int]],
    drain_by_day: list[dict[str, float]],
    horizon: int,
) -> list[dict[str, int]]:
    inv = {p: int(start_inv.get(p, pricing.I0_DEFAULT)) for p in pricing.MARKET_PARAMS}
    out: list[dict[str, int]] = []
    for rel in range(horizon):
        for product in pricing.MARKET_PARAMS:
            units = supply.get(product, [0] * horizon)[rel]
            if units > 0:
                inv[product] = _inv_after_sells(product, inv[product], units)
        day_prices = {
            p: pricing.quoted(p, inv[p]) for p in pricing.MARKET_PARAMS
        }
        out.append(day_prices)
        drain = drain_by_day[rel] if rel < len(drain_by_day) else {}
        for product in pricing.MARKET_PARAMS:
            inv[product] = max(0, int(round(inv[product] - drain.get(product, 0.0))))
    return out


def build_drain_by_day(obs: dict, horizon: int) -> list[dict[str, float]]:
    day = obs["day"]
    unlocked = list(obs.get("town", {}).get("unlocked_shops", []))
    shop = shop_drain_per_day(unlocked)
    rows: list[dict[str, float]] = []
    for rel in range(horizon):
        abs_day = day + rel
        row = dict(shop)
        tc = town_drain_per_day(abs_day)
        for p in _TOWN_CENTER_PRODUCTS:
            row[p] = row.get(p, 0.0) + tc.get(p, 0.0)
        rows.append({p: row.get(p, 0.0) for p in SELL_PRODUCTS})
    return rows


def build_supply(
    obs: dict,
    tile_queues: dict,
    tile_state: dict,
    horizon: int,
) -> dict[str, list[int]]:
    from milos.wsp import data as wsp_data

    day = obs["day"]
    player = obs["player"]
    me = obs["farms"][player]
    opp = obs["farms"][1 - player]
    crops_data = wsp_data.crops()
    animals_data = wsp_data.animals()
    supply = _empty_supply(horizon)
    _collect_frozen_supply(
        me, day, horizon, tile_queues, tile_state, supply, crops_data, animals_data
    )
    _collect_opponent_supply(opp, day, horizon, supply, crops_data, animals_data)
    _add_shed_day0(obs, supply)
    return supply


def make_price_forecast(
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None = None,
) -> Callable[[str, int], int]:
    day = obs["day"]
    horizon = rollouts.SEASON_DAYS - day
    if horizon <= 0:

        def flat(product: str, rel_day: int = 0) -> int:
            i0 = pricing.I0_DEFAULT
            return pricing.quoted(product, i0)

        return flat

    st_map = tile_state or {}
    market_inv = obs.get("market", {}).get("inventory", {})
    supply = build_supply(obs, tile_queues, st_map, horizon)
    drain = build_drain_by_day(obs, horizon)
    table = walk_prices(market_inv, supply, drain, horizon)

    def price_of(product: str, rel_day: int = 0) -> int:
        if rel_day < 0:
            rel_day = 0
        if rel_day >= len(table):
            rel_day = len(table) - 1
        return table[rel_day].get(
            product,
            pricing.quoted(product, int(market_inv.get(product, pricing.I0_DEFAULT))),
        )

    return price_of


def assert_shop_sink_sanity() -> None:
    wool = shop_drain_per_day(["YARN_STORE"])["WOOL"]
    carrot = shop_drain_per_day(["PET_CAFE"])["CARROT"]
    wheat = shop_drain_per_day(["BAKERY"])["WHEAT"]
    assert wool == 12.0, f"Yarn Store wool drain expected 12/day, got {wool}"
    assert carrot == 12.0, f"Pet Cafe carrot drain expected 12/day, got {carrot}"
    assert wheat == 6.0, f"Bakery wheat drain expected 6/day, got {wheat}"


def compare_to_observed_quotes(
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None = None,
) -> dict[str, Any]:
    """Band-check: day-0 forecast vs obs market prices (same dawn)."""
    price_of = make_price_forecast(obs, tile_queues, tile_state)
    market_prices = obs.get("market", {}).get("prices", {})
    rows = []
    for product in SELL_PRODUCTS:
        forecast = price_of(product, 0)
        observed = int(market_prices.get(product, 0) or 0)
        rows.append({"product": product, "forecast_d0": forecast, "observed": observed})
    return {"day": obs["day"], "rows": rows}
