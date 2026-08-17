"""Hardcoded one-land plan from data/handmade_pseudoplan.md (1-based tiles in docs)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["crop", "animal"]

# Tile grid (x, y) — tile 1 = (4, 4) = shed door
#  24 23 13 14 15
#  25 22 12 11 10
#  19 18  9  8  7
#  20 17  4  5  6
#  21 16  3  2  1
TILE_COORDS: list[tuple[int, int]] = [
    (4, 4), (3, 4), (2, 4), (2, 3), (3, 3), (4, 3), (4, 2), (3, 2), (2, 2),  # 1-9 farmer
    (4, 1), (3, 1), (2, 1), (2, 0), (3, 0), (4, 0),  # 10-15 top
    (1, 4), (1, 3), (1, 2), (0, 2), (0, 3), (0, 4),  # 16-21 left
    (1, 1), (1, 0), (0, 0), (0, 1),  # 22-25 corner
]
NUM_TILES = len(TILE_COORDS)

WORKERS = ("farmer", "hire1", "hire2", "hire3")
HAND_WORKERS = ("hire1", "hire2", "hire3")

WORKER_TILES: dict[str, list[int]] = {
    "farmer": list(range(0, 9)),
    "hire1": list(range(9, 15)),
    "hire2": list(range(15, 21)),
    "hire3": list(range(21, 25)),
}

# Snake routes as tile indices (visit order)
WORKER_ROUTES: dict[str, list[int]] = {
    "farmer": [0, 1, 2, 3, 4, 5, 6, 7, 8],
    "hire1": [9, 10, 11, 12, 13, 14],
    "hire2": [15, 16, 17, 18, 19, 20],
    "hire3": [21, 22, 23, 24],
}

# Preamble: first move from spawn, optional wheat pickup, then approach zone.
PREAMBLE: dict[str, list[str]] = {
    "farmer": [],
    "hire1": ["WEST", "PICKUP_WHEAT", "PICKUP_ANIMALS", "NORTH", "NORTH", "NORTH"],
    "hire2": ["NORTH", "PICKUP_WHEAT", "PICKUP_ANIMALS", "WEST", "WEST", "WEST"],
    "hire3": ["WEST", "PICKUP_WHEAT", "PICKUP_ANIMALS", "WEST", "WEST", "NORTH", "NORTH", "NORTH"],
}

HAND_START_HOUR: dict[str, int] = {"hire1": 1, "hire2": 1, "hire3": 1}

SHED_DOOR: tuple[int, int] = (4, 4)
SHED_ADJACENT: frozenset[tuple[int, int]] = frozenset({(4, 4), (5, 4), (4, 5), (5, 5)})
NUM_HIRES = 3
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
    q: dict[int, list[QueueItem]] = {}

    for idx in range(3):
        q[idx] = _carrot(1) + _wheat(5)
    for idx in range(3, 6):
        q[idx] = _carrot(2) + _wheat(4)
    for idx in range(6, 9):
        q[idx] = _melon(2, start_lag=1) + _wheat(1)

    for idx in (9, 15):  # tiles 10, 16
        q[idx] = _wheat(1) + [_animal("SHEEP")]
    for idx in (10, 16):  # tiles 11, 17 — carrot before sheep
        q[idx] = _wheat(1) + _carrot(1) + [_animal("SHEEP")]
    for idx in (11, 12, 17, 18):  # tiles 12,13,18,19
        q[idx] = _wheat(1) + _melon(2, replant_gap=3)
    for idx in (13, 14, 19, 20):
        q[idx] = _wheat(1) + _melon(2, start_lag=1, replant_gap=1)

    q[21] = _wheat(1) + [_animal("COW")]
    q[22] = _wheat(2) + [_animal("COW")]  # tile 23: wheat, wheat, cow
    q[23] = _wheat(1) + [
        QueueItem("crop", "STRAWBERRY", profile=CROP_PROFILE),
        QueueItem("crop", "CARROT", profile=CROP_PROFILE, dig_before=True),
        QueueItem("crop", "CARROT", profile=CROP_PROFILE),
    ]
    q[24] = _wheat(1) + _melon(1, start_lag=1) + _melon(1, start_lag=1)

    return q


from agent.planner import get_tile_queues

TILE_QUEUES: dict[int, list[QueueItem]] = get_tile_queues(_build_tile_queues)


def worker_for_tile(idx: int) -> str:
    for worker, indices in WORKER_TILES.items():
        if idx in indices:
            return worker
    return "farmer"


def _tile_at(me: dict, idx: int):
    x, y = TILE_COORDS[idx]
    return me["tiles"][y][x]


def zone_needs_feed_wheat(me: dict, worker: str, tile_state: dict) -> bool:
    """True if zone has live animals or is placing one today (needs FEED wheat)."""
    for idx in WORKER_TILES[worker]:
        tile = _tile_at(me, idx)
        if isinstance(tile, dict) and tile.get("animal"):
            return True
        st = tile_state.get(idx, {})
        if st.get("lag", 0) > 0 or st.get("gap", 0) > 0:
            continue
        qi = st.get("queue_idx", 0)
        if qi >= len(TILE_QUEUES.get(idx, [])):
            continue
        item = TILE_QUEUES[idx][qi]
        if item.kind != "animal":
            continue
        if tile is None:
            continue
        if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
            if not tile.get("animal"):
                return True
    return False


def wheat_pickup_needed(
    me: dict, worker: str, tile_state: dict, inv: dict
) -> int:
    if not zone_needs_feed_wheat(me, worker, tile_state):
        return 0
    return max(0, WHEAT_PICKUP_PER_HAND - inv.get("WHEAT", 0))


def _animals_needed_for_zone(
    me: dict, worker: str, tile_state: dict
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


def _inventory_index(worker: str) -> int:
    if worker == "farmer":
        return 0
    return HAND_WORKERS.index(worker) + 1


def total_wheat_feed_need(me: dict, tile_state: dict, private: dict) -> int:
    total = 0
    for worker in WORKERS:
        inv_idx = _inventory_index(worker)
        inv = (
            private["inventories"][inv_idx]
            if inv_idx < len(private["inventories"])
            else {}
        )
        total += wheat_pickup_needed(me, worker, tile_state, inv)
    return total
