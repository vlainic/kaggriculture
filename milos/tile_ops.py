"""Tile-level ops driven by rollout JSON tapes."""

from __future__ import annotations

from milos import animal_rollouts, rollouts, script, workers
from milos.script import QueueItem, TILE_QUEUES

STRAWBERRY_LAST_AGE = 16
ONE_TIME_CROPS = frozenset({"WHEAT", "CARROT", "MELON"})


def _tile_at(me: dict, idx: int):
    x, y = workers.TILE_COORDS[idx]
    return me["tiles"][y][x]


def _inv_at(private: dict, inv_idx: int) -> dict:
    invs = private["inventories"]
    return invs[inv_idx] if inv_idx < len(invs) else {}


def tile_needs_feed(tile: dict | None, day: int) -> bool:
    """True if tile has a live animal that still needs feeding today."""
    if not isinstance(tile, dict):
        return False
    if tile.get("kind") not in ("COOP", "PASTURE"):
        return False
    if not tile.get("animal"):
        return False
    return not tile.get("fed_today")


def zone_has_animal(me: dict, tile_idx: int) -> bool:
    """Check if the zone containing tile_idx has any animal."""
    for tiles in workers.WORKER_TILES.values():
        if tile_idx in tiles:
            for idx in tiles:
                tile = _tile_at(me, idx)
                if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
                    if tile.get("animal"):
                        return True
            return False
    return False


def crop_needs_fertilize_by_age(tile: dict, day: int) -> bool:
    """Check if crop needs fertilization based on age."""
    if tile.get("crop") == "MELON":
        return False
    crop = tile.get("crop")
    if "with_fert" not in rollouts.profiles_for(crop):
        return False
    age = day - tile["planted_day"]
    fert_ages = rollouts.fertilize_ages(crop, "with_fert")
    if age not in fert_ages:
        return False
    return tile.get("fertilized_until_day", -1) < day


def _may_fertilize_today(
    tile: dict,
    day: int,
    me: dict,
    tile_idx: int,
    private: dict,
    inv_idx: int,
    *,
    fert_today: bool,
    zone_ops_remaining: int,
) -> bool:
    if fert_today or zone_ops_remaining <= 0:
        return False
    inv = _inv_at(private, inv_idx)
    if inv.get("FERTILIZER", 0) <= 0:
        return False
    if not zone_has_animal(me, tile_idx):
        return False
    return crop_needs_fertilize_by_age(tile, day)


def current_queue_item(idx: int, queue_idx: int) -> QueueItem | None:
    queue = TILE_QUEUES.get(idx, [])
    if queue_idx >= len(queue):
        return None
    return queue[queue_idx]


def can_start_today(
    idx: int,
    empty_at_dawn: set[int],
    dig_plant_ok: bool,
) -> bool:
    return idx in empty_at_dawn or dig_plant_ok


def tile_has_harvestable(idx: int, me: dict, day: int) -> bool:
    tile = _tile_at(me, idx)
    if not isinstance(tile, dict):
        return False
    if tile.get("kind") == "PLANT" and tile.get("yield_units", 0) > 0:
        return True
    if tile.get("kind") in ("COOP", "PASTURE"):
        if tile.get("yield_units", 0) > 0:
            return True
        if tile.get("fertilizer_available"):
            return True
    return False


def _harvest_only_fallback(idx: int, me: dict, day: int) -> list | None:
    tile = _tile_at(me, idx)
    if not isinstance(tile, dict):
        return None
    if tile.get("kind") == "PLANT" and tile.get("yield_units", 0) > 0:
        return ["HARVEST"]
    if tile.get("kind") in ("COOP", "PASTURE"):
        if tile.get("yield_units", 0) > 0:
            return ["HARVEST"]
        if tile.get("fertilizer_available"):
            return ["COLLECT_FERTILIZER"]
    return None


def tile_needs_work(
    idx: int,
    me: dict,
    private: dict,
    day: int,
    inv_idx: int,
    queue_idx: int,
    lag: int,
    gap: int,
    pending_dig: bool,
    *,
    harvest_only: bool,
    empty_at_dawn: set[int] | None = None,
    dig_plant_ok: bool = False,
) -> bool:
    tile = _tile_at(me, idx)
    dawn = empty_at_dawn if empty_at_dawn is not None else set()
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return True
    if pending_dig:
        return True
    if harvest_only and tile_has_harvestable(idx, me, day):
        return True
    if lag > 0 or gap > 0:
        return False
    item = current_queue_item(idx, queue_idx)
    if item is None:
        return False
    # Buy-morning expand tiles stay "LOCKED" until market runs; dawn set treats them empty.
    if tile is None or (tile == "LOCKED" and idx in dawn):
        return can_start_today(idx, dawn, dig_plant_ok) and (
            _start_lifecycle(item, private, inv_idx, harvest_only, idx, dawn, dig_plant_ok)
            is not None
        )
    if not isinstance(tile, dict):
        return False
    if tile.get("kind") in ("COOP", "PASTURE"):
        if tile_needs_feed(tile, day):
            return True
    return _lifecycle_pending(
        tile, day, item, inv_idx, private, harvest_only, idx, me
    )


def _lifecycle_pending(
    tile: dict,
    day: int,
    item: QueueItem,
    inv_idx: int,
    private: dict,
    harvest_only: bool,
    tile_idx: int = -1,
    me: dict | None = None,
) -> bool:
    if tile.get("kind") == "PLANT":
        return (
            _crop_action(
                tile,
                day,
                item,
                harvest_only,
                tile_idx=tile_idx,
                me=me,
                private=private,
                inv_idx=inv_idx,
            )
            is not None
        )
    if tile.get("kind") in ("COOP", "PASTURE"):
        if tile_needs_feed(tile, day):
            return True
        return _animal_action(tile, day, item, private, inv_idx, harvest_only) is not None
    return False


def next_tile_action(
    idx: int,
    me: dict,
    private: dict,
    day: int,
    inv_idx: int,
    queue_idx: int,
    lag: int,
    gap: int,
    pending_dig: bool,
    *,
    harvest_only: bool,
    empty_at_dawn: set[int] | None = None,
    dig_plant_ok: bool = False,
    fert_today: bool = False,
    zone_ops_remaining: int = 999,
) -> list | None:
    tile = _tile_at(me, idx)
    dawn = empty_at_dawn if empty_at_dawn is not None else set()

    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return ["DIG"]

    if pending_dig:
        if tile is None or isinstance(tile, dict):
            return ["DIG"]

    if lag > 0 or gap > 0:
        if harvest_only:
            return _harvest_only_fallback(idx, me, day)
        return None

    item = current_queue_item(idx, queue_idx)
    if item is None:
        if harvest_only:
            return _harvest_only_fallback(idx, me, day)
        # Leftover animal product / fert with no queue item — still collect.
        if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
            return _harvest_only_fallback(idx, me, day)
        return None

    if tile is None or (tile == "LOCKED" and idx in dawn):
        return _start_lifecycle(
            item, private, inv_idx, harvest_only, idx, dawn, dig_plant_ok
        )

    if isinstance(tile, dict):
        if tile.get("kind") == "PLANT":
            act = _crop_action(
                tile,
                day,
                item,
                harvest_only,
                tile_idx=idx,
                me=me,
                private=private,
                inv_idx=inv_idx,
                fert_today=fert_today,
                zone_ops_remaining=zone_ops_remaining,
            )
            if act:
                return act
            if harvest_only:
                return _harvest_only_fallback(idx, me, day)
        if tile.get("kind") in ("COOP", "PASTURE"):
            act = _animal_action(tile, day, item, private, inv_idx, harvest_only)
            if act:
                return act
            # Don't leave eggs/milk/fert sitting when the age tape omitted HARVEST.
            if harvest_only or tile_has_harvestable(idx, me, day):
                return _harvest_only_fallback(idx, me, day)

    if harvest_only:
        return _harvest_only_fallback(idx, me, day)

    return None


def _start_lifecycle(
    item: QueueItem,
    private: dict,
    inv_idx: int,
    harvest_only: bool,
    idx: int,
    empty_at_dawn: set[int],
    dig_plant_ok: bool,
) -> list | None:
    if harvest_only:
        return None
    if not can_start_today(idx, empty_at_dawn, dig_plant_ok):
        return None
    if item.kind == "crop":
        if private["seeds"].get(item.label, 0) <= 0:
            return None
        return ["PLANT", item.label]
    inv = _inv_at(private, inv_idx)
    if inv.get(item.label, 0) <= 0:
        return None
    if item.kind == "animal" and inv.get("WHEAT", 0) <= 0:
        return None
    return [animal_rollouts.build_action_for(item.label)]


def _crop_action(
    tile: dict,
    day: int,
    item: QueueItem,
    harvest_only: bool,
    *,
    tile_idx: int = -1,
    me: dict | None = None,
    private: dict | None = None,
    inv_idx: int = 0,
    fert_today: bool = False,
    zone_ops_remaining: int = 999,
) -> list | None:
    crop = tile["crop"]
    profile = item.profile if item.kind == "crop" else script.CROP_PROFILE
    age = day - tile["planted_day"]
    actions = rollouts.actions_at_age(crop, age, profile)

    if crop == "STRAWBERRY" and age == STRAWBERRY_LAST_AGE:
        actions = [a for a in actions if a != "DIG"]

    if not harvest_only:
        if "WATER" in actions and not tile.get("watered_today"):
            return ["WATER"]
        if me is not None and private is not None and tile_idx >= 0:
            if _may_fertilize_today(
                tile,
                day,
                me,
                tile_idx,
                private,
                inv_idx,
                fert_today=fert_today,
                zone_ops_remaining=zone_ops_remaining,
            ):
                return ["FERTILIZE"]

    for act in actions:
        if harvest_only:
            if act == "WATER":
                if crop not in ONE_TIME_CROPS or tile.get("watered_today"):
                    continue
            elif act != "HARVEST":
                continue
        if act == "WATER" and tile.get("watered_today"):
            continue
        if act == "PLANT":
            continue
        if act == "FERTILIZE":
            continue
        if act == "HARVEST" and tile.get("yield_units", 0) <= 0:
            continue
        return [act] + ([crop] if act == "PLANT" else [])
    return None


def _animal_action(
    tile: dict,
    day: int,
    item: QueueItem,
    private: dict,
    inv_idx: int,
    harvest_only: bool,
) -> list | None:
    animal = tile.get("animal")
    profile = item.profile if item.kind == "animal" else script.ANIMAL_PROFILE

    if not animal:
        if harvest_only:
            return None
        inv = _inv_at(private, inv_idx)
        if inv.get(item.label, 0) <= 0:
            return None
        if inv.get("WHEAT", 0) <= 0:
            return None
        return ["PLACE", item.label]

    age = day - tile["placed_day"]
    actions = animal_rollouts.actions_at_age(animal, age, profile)

    for act in actions:
        if harvest_only and act not in ("HARVEST", "COLLECT_FERTILIZER"):
            continue
        if act == "FEED" and tile.get("fed_today"):
            continue
        if act == "FEED":
            inv = _inv_at(private, inv_idx)
            if inv.get("WHEAT", 0) <= 0:
                continue  # don't swallow HARVEST / COLLECT_FERTILIZER
        if act == "CARE" and tile.get("cared_today"):
            continue
        if act == "COLLECT_FERTILIZER" and not tile.get("fertilizer_available"):
            continue
        if act == "HARVEST" and tile.get("yield_units", 0) <= 0:
            continue
        if act in ("PLACE", "PICKUP", "BUILD_COOP", "BUILD_PASTURE"):
            continue
        return [act] + ([animal] if act == "PLACE" else [])
    return None


def on_lifecycle_end(
    idx: int,
    queue_idx: int,
    item: QueueItem | None,
    pending_dig: bool,
) -> tuple[int, int, int, bool]:
    """Return (new_queue_idx, lag, gap, pending_dig) after tile freed."""
    if item is None:
        return queue_idx, 0, 0, pending_dig
    new_idx = queue_idx + 1
    queue = TILE_QUEUES.get(idx, [])
    lag = 0
    gap = item.replant_gap
    if new_idx < len(queue):
        lag = queue[new_idx].start_lag
    dig = pending_dig
    if item.kind == "crop" and item.label == "STRAWBERRY":
        dig = True
    if item.dig_before:
        dig = False
    return new_idx, lag, gap, dig
