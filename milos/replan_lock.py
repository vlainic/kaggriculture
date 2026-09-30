"""Dawn replan eligibility + locked-tile commitment stamp (farmer-only, no agent/)."""

from __future__ import annotations

from collections.abc import Callable

from milos import animal_rollouts, rollouts
from milos.wsp import data as wsp_data
from milos.wsp.config import ANIMAL_NAMES, PROFILE_SUFFIXES
from milos.wsp.mip import harvest_price_for_cash
from milos.workers import TILE_COORDS
from milos.zoning import NUM_TILES, WORKERS, worker_for_tile

CROP_PROFILE = "no_fert"
ANIMAL_PROFILE = "with_care"

LOCKED_DAILY_KEYS = (
    "daily_tile_ops",
    "daily_animal_active",
    "daily_feed",
    "daily_fert",
    "daily_collect",
    "daily_wheat",
)


def _parse_profile_key(profile_key: str) -> tuple[str, str]:
    for suffix in PROFILE_SUFFIXES:
        token = f"_{suffix}"
        if profile_key.endswith(token):
            return profile_key[: -len(token)], suffix
    raise ValueError(f"unknown profile key: {profile_key}")


def _tile_at(me: dict, idx: int):
    x, y = TILE_COORDS[idx]
    return me["tiles"][y][x]


def _zero_daily(horizon: int) -> dict[str, list[int]]:
    return {key: [0] * horizon for key in LOCKED_DAILY_KEYS}


def _add_daily(dst: list[int], src: list[int], horizon: int) -> None:
    for i in range(horizon):
        dst[i] += src[i]


def _on_tile_ops_count(acts: list) -> int:
    return len([a for a in acts if a != "PICKUP"])


def _empty_daily_place(horizon: int) -> dict[str, list[int]]:
    from milos.wsp.config import ANIMAL_NAMES

    return {name: [0] * horizon for name in ANIMAL_NAMES}


def _merge_daily_place(dst: dict, src: dict, horizon: int) -> None:
    for an, arr in src.items():
        for i in range(horizon):
            dst[an][i] = max(dst[an][i], arr[i])


def empty_locked(horizon: int) -> dict:
    return _zero_daily(horizon) | {
        "cash_by_day": [0] * horizon,
        "spend_by_day": [0] * horizon,
        "daily_place": _empty_daily_place(horizon),
    }


def _rollout_spec(label: str, profile_name: str, crops_data: dict, animals_data: dict):
    if label in crops_data["crops"]:
        spec = crops_data["crops"][label]
        return "crop", spec, spec[profile_name]
    if label in animals_data["animals"]:
        spec = animals_data["animals"][label]
        return "animal", spec, spec[profile_name]
    raise KeyError(label)


def _parse_age_maps(profile, label, kind):
    harvest_map = dict(zip(profile["harvest_ages"], profile["yield_per_harvest"]))
    feed_by_age = {}
    fert_use_by_age = {}
    collect_by_age = {}
    wheat_gain_by_age = {}
    for day in profile["days"]:
        age = day["age"]
        acts = day["actions"]
        feed_by_age[age] = 1 if "FEED" in acts else 0
        fert_use_by_age[age] = 1 if "FERTILIZE" in acts else 0
        collect_by_age[age] = 1 if "COLLECT_FERTILIZER" in acts else 0
        wheat_gain_by_age[age] = (
            harvest_map[age]
            if kind == "crop" and label == "WHEAT" and age in harvest_map
            else 0
        )
    return feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age


def _product_for_label(label: str, kind: str) -> str:
    if kind == "animal":
        return animal_rollouts.product_for(label)
    return label


def _build_cash_and_spend(
    start_day: int,
    setup_cost: int,
    product: str,
    profile,
    horizon: int,
    price_of: Callable[..., int],
    *,
    min_age: int = 0,
    charge_setup: bool = True,
) -> tuple[list[int], list[int]]:
    cash = [0] * horizon
    spend = [0] * horizon
    if charge_setup and start_day < horizon:
        cash[start_day] -= setup_cost
        spend[start_day] -= setup_cost
    for age, yld in zip(profile["harvest_ages"], profile["yield_per_harvest"]):
        if age < min_age:
            continue
        hday = start_day + (age - min_age)
        if hday < horizon:
            cash[hday] += yld * harvest_price_for_cash(product, hday, price_of)
    return cash, spend


def _stamp_profile_segment(
    label: str,
    profile_name: str,
    rel_start: int,
    min_age: int,
    horizon: int,
    price_of: Callable[..., int],
    crops_data: dict,
    animals_data: dict,
    *,
    charge_setup: bool,
):
    kind, spec, profile = _rollout_spec(label, profile_name, crops_data, animals_data)
    setup_cost = spec["seed_cost"] if kind == "crop" else spec["animal_cost"]
    product = _product_for_label(label, kind)
    feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age = _parse_age_maps(
        profile, label, kind
    )

    out = _zero_daily(horizon)
    daily_place = _empty_daily_place(horizon)
    cash_by_day = [0] * horizon
    spend_by_day = [0] * horizon

    if kind == "crop":
        for day in profile["days"]:
            age = day["age"]
            if age < min_age:
                continue
            rel = rel_start + (age - min_age)
            if rel >= horizon:
                continue
            acts = day["actions"]
            out["daily_tile_ops"][rel] += _on_tile_ops_count(acts)
            out["daily_feed"][rel] += feed_by_age.get(age, 0)
            out["daily_fert"][rel] += fert_use_by_age.get(age, 0)
            out["daily_collect"][rel] += collect_by_age.get(age, 0)
            out["daily_wheat"][rel] += wheat_gain_by_age.get(age, 0)
    else:
        occupied = False
        for day in profile["days"]:
            age = day["age"]
            if age < min_age:
                continue
            rel = rel_start + (age - min_age)
            if rel >= horizon:
                break
            occupied = True
            acts = day["actions"]
            out["daily_tile_ops"][rel] += _on_tile_ops_count(acts)
            if "PLACE" in acts:
                daily_place[label][rel] = 1
            out["daily_animal_active"][rel] = 1
            out["daily_feed"][rel] += feed_by_age.get(age, 0)
            out["daily_fert"][rel] += fert_use_by_age.get(age, 0)
            out["daily_collect"][rel] += collect_by_age.get(age, 0)
            out["daily_wheat"][rel] += wheat_gain_by_age.get(age, 0)
        if not occupied:
            return None

    cash_by_day, spend_by_day = _build_cash_and_spend(
        rel_start,
        setup_cost,
        product,
        profile,
        horizon,
        price_of,
        min_age=min_age,
        charge_setup=charge_setup,
    )
    return {
        "weight": sum(cash_by_day),
        "cash_by_day": cash_by_day,
        "spend_by_day": spend_by_day,
        "daily_place": daily_place,
        **out,
    }


def _stamp_placement(
    profile_key: str,
    start_day: int,
    horizon: int,
    price_of: Callable[..., int],
    crops_data: dict,
    animals_data: dict,
):
    label, profile_name = _parse_profile_key(profile_key)
    return _stamp_profile_segment(
        label,
        profile_name,
        start_day,
        0,
        horizon,
        price_of,
        crops_data,
        animals_data,
        charge_setup=True,
    )


def _stamp_chain(
    chain,
    horizon: int,
    price_of: Callable[..., int],
    crops_data: dict,
    animals_data: dict,
):
    out = _zero_daily(horizon)
    daily_place = _empty_daily_place(horizon)
    cash_by_day = [0] * horizon
    spend_by_day = [0] * horizon
    for profile_key, start_day in chain:
        seg = _stamp_placement(
            profile_key, start_day, horizon, price_of, crops_data, animals_data
        )
        if seg is None:
            continue
        for key in LOCKED_DAILY_KEYS:
            _add_daily(out[key], seg[key], horizon)
        _merge_daily_place(daily_place, seg.get("daily_place", {}), horizon)
        _add_daily(cash_by_day, seg["cash_by_day"], horizon)
        _add_daily(spend_by_day, seg["spend_by_day"], horizon)
    return {
        "weight": sum(cash_by_day),
        "cash_by_day": cash_by_day,
        "spend_by_day": spend_by_day,
        "daily_place": daily_place,
        **out,
    }


def _profile_key_for_item(item) -> str:
    return f"{item.label}_{item.profile}"


def _queue_suffix_to_chain(
    queue: list,
    qi: int,
    lag: int,
    gap: int,
    from_day: int,
    horizon: int,
    me: dict,
    idx: int,
) -> list:
    end_day = from_day + horizon
    cal = from_day
    tile = _tile_at(me, idx)
    chain: list = []

    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        crop = tile["crop"]
        item = queue[qi] if qi < len(queue) else None
        profile = item.profile if item and item.kind == "crop" else CROP_PROFILE
        free_day = tile["planted_day"] + rollouts.tile_free_age(crop, profile)
        cal = max(cal, free_day)
        if item is not None:
            from milos import tile_ops

            qi, lag, gap, _ = tile_ops.on_lifecycle_end(idx, qi, item, False)
    elif isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
        if tile.get("animal"):
            return []

    while qi < len(queue) and cal < end_day:
        while lag > 0 and cal < end_day:
            cal += 1
            lag -= 1
        while gap > 0 and cal < end_day:
            cal += 1
            gap -= 1
        if cal >= end_day:
            break

        item = queue[qi]
        rel = cal - from_day
        if rel >= horizon:
            break
        chain.append([_profile_key_for_item(item), rel])
        if item.kind == "crop":
            cal += rollouts.tile_free_age(item.label, item.profile)
            qi += 1
            lag = queue[qi].start_lag if qi < len(queue) else 0
            gap = item.replant_gap
        else:
            break

    return chain


def _stamp_locked_tile(
    tile: dict,
    day: int,
    horizon: int,
    price_of: Callable[..., int],
    crops_data: dict,
    animals_data: dict,
):
    if tile.get("kind") == "PLANT":
        crop = tile["crop"]
        current_age = day - tile["planted_day"]
        return _stamp_profile_segment(
            crop,
            CROP_PROFILE,
            0,
            current_age,
            horizon,
            price_of,
            crops_data,
            animals_data,
            charge_setup=False,
        )
    if tile.get("kind") in ("COOP", "PASTURE"):
        animal = tile.get("animal")
        if not animal:
            empty = _zero_daily(horizon)
            return {
                "weight": 0,
                "cash_by_day": [0] * horizon,
                "spend_by_day": [0] * horizon,
                **empty,
            }
        current_age = day - tile["placed_day"]
        return _stamp_profile_segment(
            animal,
            ANIMAL_PROFILE,
            0,
            current_age,
            horizon,
            price_of,
            crops_data,
            animals_data,
            charge_setup=False,
        )
    empty = _zero_daily(horizon)
    return {
        "weight": 0,
        "cash_by_day": [0] * horizon,
        "spend_by_day": [0] * horizon,
        **empty,
    }


def _tile_occupied_for_lock(tile) -> bool:
    if not isinstance(tile, dict):
        return False
    if tile.get("kind") == "PLANT":
        return True
    if tile.get("kind") in ("COOP", "PASTURE"):
        return bool(tile.get("animal"))
    return False


def _stamp_tile_commitment(
    idx: int,
    me: dict,
    st: dict,
    queue: list,
    day: int,
    horizon: int,
    price_of: Callable[..., int],
    crops_data: dict,
    animals_data: dict,
):
    tile = _tile_at(me, idx)
    qi = st.get("queue_idx", 0)
    lag = st.get("lag", 0)
    gap = st.get("gap", 0)

    out = _zero_daily(horizon)
    daily_place = _empty_daily_place(horizon)
    cash_by_day = [0] * horizon
    spend_by_day = [0] * horizon

    if _tile_occupied_for_lock(tile):
        seg = _stamp_locked_tile(tile, day, horizon, price_of, crops_data, animals_data)
        if seg:
            for key in LOCKED_DAILY_KEYS:
                _add_daily(out[key], seg[key], horizon)
            _merge_daily_place(daily_place, seg.get("daily_place", {}), horizon)
            _add_daily(cash_by_day, seg["cash_by_day"], horizon)
            _add_daily(spend_by_day, seg["spend_by_day"], horizon)

    raw = _queue_suffix_to_chain(queue, qi, lag, gap, day, horizon, me, idx)
    if raw:
        suffix_seg = _stamp_chain(raw, horizon, price_of, crops_data, animals_data)
        for key in LOCKED_DAILY_KEYS:
            _add_daily(out[key], suffix_seg[key], horizon)
        _merge_daily_place(daily_place, suffix_seg.get("daily_place", {}), horizon)
        _add_daily(cash_by_day, suffix_seg["cash_by_day"], horizon)
        _add_daily(spend_by_day, suffix_seg["spend_by_day"], horizon)

    if not any(cash_by_day) and not any(sum(out[k]) for k in LOCKED_DAILY_KEYS):
        return None
    return {
        "weight": sum(cash_by_day),
        "cash_by_day": cash_by_day,
        "spend_by_day": spend_by_day,
        "daily_place": daily_place,
        **out,
    }


def _aggregate_locked(
    locked_by_worker: dict[str, dict],
    worker: str,
    seg: dict,
    horizon: int,
) -> None:
    for key in LOCKED_DAILY_KEYS:
        _add_daily(locked_by_worker[worker][key], seg[key], horizon)
    _merge_daily_place(
        locked_by_worker[worker]["daily_place"],
        seg.get("daily_place", {}),
        horizon,
    )
    _add_daily(locked_by_worker[worker]["cash_by_day"], seg["cash_by_day"], horizon)
    _add_daily(locked_by_worker[worker]["spend_by_day"], seg["spend_by_day"], horizon)


def _tile_empty_for_replan(tile) -> bool:
    return tile is None or (isinstance(tile, dict) and tile.get("kind") == "WEED")


def replan_eligible(
    idx: int,
    tile,
    st: dict,
    queues: dict,
    *,
    staple_bootstrap_workers: frozenset[str] | None = None,
) -> bool:
    if st.get("pending_dig"):
        return False
    if not _tile_empty_for_replan(tile):
        return False
    qi = st.get("queue_idx", 0)
    queue = queues.get(idx, [])
    if qi == 0 and queue:
        if staple_bootstrap_workers:
            worker = worker_for_tile(idx)
            if worker in staple_bootstrap_workers:
                return True
        return False
    return True


def any_replan_eligible(
    me: dict,
    st_map: dict,
    tile_queues: dict,
    *,
    staple_bootstrap_workers: frozenset[str] | None = None,
) -> bool:
    for i in range(NUM_TILES):
        if replan_eligible(
            i,
            _tile_at(me, i),
            st_map.get(i, {}),
            tile_queues,
            staple_bootstrap_workers=staple_bootstrap_workers,
        ):
            return True
    return False


def build_replan_lock(
    me: dict,
    day: int,
    horizon: int,
    tile_queues: dict,
    st_map: dict,
    price_of: Callable[..., int],
    *,
    market_inv: dict[str, int] | None = None,
    staple_bootstrap_workers: frozenset[str] | None = None,
) -> tuple[list[int], dict[str, dict], int]:
    """Return (replan_tile_indices, locked_by_worker, locked_tile_count)."""
    from milos.wsp import mip

    inv = market_inv if market_inv is not None else {}
    mip.set_quote_market_inv(inv)
    try:
        crops_data = wsp_data.crops()
        animals_data = wsp_data.animals()
        replan_tiles: list[int] = []
        locked_tiles = 0
        locked_by_worker = {w: empty_locked(horizon) for w in WORKERS}

        for idx in range(NUM_TILES):
            tile = _tile_at(me, idx)
            st = st_map.get(idx, {})
            worker = worker_for_tile(idx)
            if replan_eligible(
                idx,
                tile,
                st,
                tile_queues,
                staple_bootstrap_workers=staple_bootstrap_workers,
            ):
                replan_tiles.append(idx)
            else:
                seg = _stamp_tile_commitment(
                    idx,
                    me,
                    st,
                    tile_queues.get(idx, []),
                    day,
                    horizon,
                    price_of,
                    crops_data,
                    animals_data,
                )
                if seg:
                    _aggregate_locked(locked_by_worker, worker, seg, horizon)
                    locked_tiles += 1

        return replan_tiles, locked_by_worker, locked_tiles
    finally:
        mip.set_quote_market_inv(None)
