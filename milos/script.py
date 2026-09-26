"""Hardcoded one-land plan from data/handmade_pseudoplan.md (1-based tiles in docs)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from milos import planner, workers, rollouts, animal_rollouts, zoning
from milos.zoning import (
    HAND_WORKERS,
    NUM_TILES,
    TILE_COORDS,
    WORKER_TILES,
    WORKERS,
)

Kind = Literal["crop", "animal"]
SEASON_LAST_DAY = 29
WHEAT_RESERVE_CAP = 10
FERT_RESERVE_CAP = 10
WHEAT_PICKUP_PER_HAND = 2

CROP_PROFILE = "no_fert"
ANIMAL_PROFILE = "with_care"


@dataclass(frozen=True)
class QueueItem:
    kind: Kind
    label: str
    profile: str = CROP_PROFILE
    start_lag: int = 0
    replant_gap: int = 0
    dig_before: bool = False


def _repeat(kind: Kind, label: str, n: int, **kw) -> list[QueueItem]:
    return [QueueItem(kind, label, **kw) for _ in range(n)]


def _wheat(n: int = 1, **kw) -> list[QueueItem]:
    return _repeat("crop", "WHEAT", n, profile=CROP_PROFILE, **kw)


def _carrot(n: int = 1, **kw) -> list[QueueItem]:
    return _repeat("crop", "CARROT", n, profile=CROP_PROFILE, **kw)


def _melon(n: int = 1, **kw) -> list[QueueItem]:
    return _repeat("crop", "MELON", n, profile=CROP_PROFILE, **kw)


def _animal(label: str, **kw) -> QueueItem:
    return QueueItem("animal", label, profile=ANIMAL_PROFILE, **kw)


def _build_tile_queues() -> dict[int, list[QueueItem]]:
    return {idx: [] for idx in range(NUM_TILES)}


from milos.planner import get_tile_queues

TILE_QUEUES: dict[int, list[QueueItem]] = get_tile_queues(_build_tile_queues)


def _tile_at(me: dict, idx: int):
    x, y = TILE_COORDS[idx]
    return me["tiles"][y][x]


def zone_animal_feed_count(
    me: dict, worker: str, tile_state: dict, *, day: int | None = None
) -> int:
    """Live animals plus animals queued for place today in this zone."""
    count = 0
    for idx in WORKER_TILES[worker]:
        tile = _tile_at(me, idx)
        if isinstance(tile, dict) and tile.get("animal"):
            count += 1
            continue
        st = tile_state.get(idx, {})
        if st.get("lag", 0) > 0 or st.get("gap", 0) > 0:
            continue
        qi = st.get("queue_idx", 0)
        queue = TILE_QUEUES.get(idx, [])
        if qi >= len(queue):
            continue
        item = queue[qi]
        if item.kind != "animal":
            continue
        emptyish = tile is None or (
            day is not None and planner.is_buy_morning_locked(tile, idx, day, me)
        )
        if emptyish:
            count += 1
            continue
        if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
            if not tile.get("animal"):
                count += 1
    return count


def zone_needs_feed_wheat(me: dict, worker: str, tile_state: dict) -> bool:
    """True if zone has live animals or is placing one today (needs FEED wheat)."""
    return zone_animal_feed_count(me, worker, tile_state) > 0


def _count_zones_with_animals(
    me: dict, tile_state: dict, *, day: int | None = None
) -> int:
    """Count how many worker zones have at least one animal (live or queued for today)."""
    count = 0
    for worker in WORKERS:
        if zone_animal_feed_count(me, worker, tile_state, day=day) > 0:
            count += 1
    return count


def wheat_pickup_needed(
    me: dict, worker: str, tile_state: dict, inv: dict, *, day: int | None = None
) -> int:
    need = zone_animal_feed_count(me, worker, tile_state, day=day)
    if need <= 0:
        return 0
    return max(0, need - inv.get("WHEAT", 0))


def _animals_needed_for_zone(
    me: dict, worker: str, tile_state: dict, *, day: int | None = None
) -> dict[str, int]:
    needed: dict[str, int] = {}
    for idx in WORKER_TILES[worker]:
        st = tile_state.get(idx, {})
        if st.get("lag", 0) > 0 or st.get("gap", 0) > 0:
            continue
        qi = st.get("queue_idx", 0)
        queue = TILE_QUEUES.get(idx, [])
        if qi >= len(queue):
            continue
        item = queue[qi]
        if item.kind != "animal":
            continue
        tile = _tile_at(me, idx)
        emptyish = tile is None or (
            day is not None and planner.is_buy_morning_locked(tile, idx, day, me)
        )
        if emptyish:
            needed[item.label] = needed.get(item.label, 0) + 1
            continue
        if not isinstance(tile, dict):
            continue
        if tile.get("kind") not in ("COOP", "PASTURE"):
            continue
        if tile.get("animal"):
            continue
        needed[item.label] = needed.get(item.label, 0) + 1
    return needed


def next_animal_pickup(
    me: dict, worker: str, tile_state: dict, private: dict, inv_idx: int
) -> str | None:
    inv = (
        private["inventories"][inv_idx]
        if inv_idx < len(private["inventories"])
        else {}
    )
    needed = _animals_needed_for_zone(me, worker, tile_state)
    shed = private.get("shed", {})
    for label in sorted(needed):
        if inv.get(label, 0) < needed[label] and shed.get(label, 0) > 0:
            return label
    return None


def zone_fert_pickup_needed(
    me: dict, worker: str, tile_state: dict, inv: dict, *, day: int | None = None
) -> int:
    if inv.get("FERTILIZER", 0) > 0:
        return 0
    uses = 0
    for idx in WORKER_TILES[worker]:
        st = tile_state.get(idx, {})
        if st.get("lag", 0) > 0 or st.get("gap", 0) > 0:
            continue
        tile = _tile_at(me, idx)
        if not isinstance(tile, dict):
            continue
        if tile.get("kind") == "PLANT":
            crop = tile.get("crop")
            age = (day if day is not None else 0) - tile.get("planted_day", day or 0)
            qi = st.get("queue_idx", 0)
            queue = TILE_QUEUES.get(idx, [])
            profile = queue[qi].profile if qi < len(queue) else "no_fert"
            acts = rollouts.actions_at_age(crop, age, profile) if crop else []
            if "FERTILIZE" in acts:
                uses += 1
        elif tile.get("animal"):
            animal = tile["animal"]
            age = (day if day is not None else 0) - tile.get("placed_day", day or 0)
            qi = st.get("queue_idx", 0)
            queue = TILE_QUEUES.get(idx, [])
            profile = queue[qi].profile if qi < len(queue) else "with_care"
            acts = animal_rollouts.actions_at_age(animal, age, profile)
            if "FERTILIZE" in acts:
                uses += 1
    return uses


def _inventory_index(worker: str, *, hand_slot: int | None = None) -> int:
    return workers.inventory_index(worker, hand_slot=hand_slot)


def total_wheat_feed_need(
    me: dict, tile_state: dict, private: dict, *, day: int | None = None
) -> int:
    del private
    total_need = sum(
        zone_animal_feed_count(me, worker, tile_state, day=day) for worker in WORKERS
    )
    if total_need <= 0:
        return 0
    zones_with_animals = _count_zones_with_animals(me, tile_state, day=day)
    buffer = (zones_with_animals + 1) // 2
    return total_need + buffer
