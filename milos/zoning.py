"""Milos layouts — farmer-only sandbox and live five-zone OneLand."""

from __future__ import annotations

import os
from dataclasses import dataclass

from milos.wsp.config import EST_OPS_ANIMAL, EST_OPS_CROP, FARMER_NET_TILE_OPS

_SHED_DOOR = (4, 4)
_SHED_ADJACENT = frozenset({(4, 4), (5, 4), (4, 5), (5, 5)})

# Spawn corner → hire zone (identity at dawn, not HIRE order).
SPAWN_TO_HIRE: dict[tuple[int, int], str] = {
    (4, 4): "hire1",
    (5, 4): "hire2",
    (4, 5): "hire3",
    (5, 5): "hire4",
}

# Fifth hand re-uses an occupied corner (env _spawn_hand least-occupancy rule).
TWOFOLD_HIRE: str | None = "hire5"


@dataclass(frozen=True)
class Zone:
    name: str
    tiles: tuple[int, ...]
    preamble: tuple[str, ...]
    start_hour: int
    net_tile_ops: int
    is_hand: bool


@dataclass(frozen=True)
class Layout:
    coords: tuple[tuple[int, int], ...]
    zones: tuple[Zone, ...]
    shed_door: tuple[int, int]
    shed_adjacent: frozenset[tuple[int, int]]


def _column(x: int, t0: int) -> tuple[tuple[int, int], ...]:
    return tuple((x, y) for y in range(4, -1, -1))


def _column_south(x: int) -> tuple[tuple[int, int], ...]:
    return tuple((x, y) for y in range(5, 10))


MILOS_FARMER = Layout(
    coords=(
        (4, 4),
        (4, 3),
        (4, 2),
        (4, 1),
        (4, 0),
    ),
    zones=(
        Zone(
            name="farmer",
            tiles=(0, 1, 2, 3, 4),
            preamble=(),
            start_hour=0,
            net_tile_ops=FARMER_NET_TILE_OPS,
            is_hand=False,
        ),
    ),
    shed_door=_SHED_DOOR,
    shed_adjacent=_SHED_ADJACENT,
)

MILOS_ONELAND = Layout(
    coords=(
        *_column(4, 0),
        *_column(0, 5),
        *_column(1, 10),
        *_column(2, 15),
        *_column(3, 20),
    ),
    zones=(
        Zone(
            name="farmer",
            tiles=(0, 1, 2, 3, 4),
            preamble=(),
            start_hour=0,
            net_tile_ops=18,
            is_hand=False,
        ),
        Zone(
            name="hire1",
            tiles=(5, 6, 7, 8, 9),
            preamble=("PICKUP", "WEST", "WEST", "WEST", "WEST"),
            start_hour=0,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire2",
            tiles=(10, 11, 12, 13, 14),
            preamble=("WEST", "PICKUP", "WEST", "WEST", "WEST"),
            start_hour=0,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire3",
            tiles=(15, 16, 17, 18, 19),
            preamble=("NORTH", "PICKUP", "WEST", "WEST"),
            start_hour=0,
            net_tile_ops=15,
            is_hand=True,
        ),
        Zone(
            name="hire4",
            tiles=(20, 21, 22, 23, 24),
            preamble=("WEST", "NORTH", "PICKUP", "WEST"),
            start_hour=0,
            net_tile_ops=15,
            is_hand=True,
        ),
    ),
    shed_door=_SHED_DOOR,
    shed_adjacent=_SHED_ADJACENT,
)

_ONELAND_COORDS = MILOS_ONELAND.coords

MILOS_ONELAND6 = Layout(
    coords=_ONELAND_COORDS,
    zones=(
        Zone(
            name="farmer",
            tiles=(0, 1, 2, 3, 4),
            preamble=(),
            start_hour=0,
            net_tile_ops=19,
            is_hand=False,
        ),
        Zone(
            name="hire1",
            tiles=(5, 6, 7, 8),
            preamble=("PICKUP", "WEST", "WEST", "WEST", "WEST"),
            start_hour=0,
            net_tile_ops=16,
            is_hand=True,
        ),
        Zone(
            name="hire2",
            tiles=(10, 11, 12, 13),
            preamble=("WEST", "PICKUP", "WEST", "WEST", "WEST"),
            start_hour=0,
            net_tile_ops=16,
            is_hand=True,
        ),
        Zone(
            name="hire3",
            tiles=(15, 16, 17, 18),
            preamble=("NORTH", "PICKUP", "WEST", "WEST"),
            start_hour=0,
            net_tile_ops=17,
            is_hand=True,
        ),
        Zone(
            name="hire4",
            tiles=(20, 21, 22, 23),
            preamble=("WEST", "NORTH", "PICKUP", "WEST"),
            start_hour=0,
            net_tile_ops=17,
            is_hand=True,
        ),
        Zone(
            name="hire5",
            tiles=(24, 19, 14, 9),
            preamble=("PICKUP",),
            start_hour=0,
            net_tile_ops=14,
            is_hand=True,
        ),
    ),
    shed_door=_SHED_DOOR,
    shed_adjacent=_SHED_ADJACENT,
)

_NE_PICKUP = ("PICKUP",)

MILOS_TWOLAND12 = Layout(
    coords=(
        *_ONELAND_COORDS,
        *_column(5, 25),
        *_column(6, 30),
        *_column(7, 35),
        *_column(8, 40),
        *_column(9, 45),
    ),
    zones=(
        Zone(
            name="farmer",
            tiles=(0, 1, 2, 3, 4),
            preamble=(),
            start_hour=0,
            net_tile_ops=19,
            is_hand=False,
        ),
        Zone(
            name="hire1",
            tiles=(5, 6, 7, 8),
            preamble=("PICKUP", "WEST", "WEST", "WEST", "WEST"),
            start_hour=0,
            net_tile_ops=16,
            is_hand=True,
        ),
        Zone(
            name="hire2",
            tiles=(10, 11, 12, 13),
            preamble=("WEST", "PICKUP", "WEST", "WEST", "WEST"),
            start_hour=0,
            net_tile_ops=16,
            is_hand=True,
        ),
        Zone(
            name="hire3",
            tiles=(15, 16, 17, 18),
            preamble=("NORTH", "PICKUP", "WEST", "WEST"),
            start_hour=0,
            net_tile_ops=17,
            is_hand=True,
        ),
        Zone(
            name="hire4",
            tiles=(20, 21, 22, 23),
            preamble=("WEST", "NORTH", "PICKUP", "WEST"),
            start_hour=0,
            net_tile_ops=17,
            is_hand=True,
        ),
        Zone(
            name="hire5",
            tiles=(24, 19, 14, 9),
            preamble=("PICKUP",),
            start_hour=0,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire6",
            tiles=(25, 26, 27, 28, 29),
            preamble=_NE_PICKUP,
            start_hour=1,
            net_tile_ops=17,
            is_hand=True,
        ),
        Zone(
            name="hire10",
            tiles=(30, 31, 32, 33),
            preamble=_NE_PICKUP,
            start_hour=1,
            net_tile_ops=15,
            is_hand=True,
        ),
        Zone(
            name="hire9",
            tiles=(35, 36, 37, 38),
            preamble=_NE_PICKUP,
            start_hour=1,
            net_tile_ops=15,
            is_hand=True,
        ),
        Zone(
            name="hire8",
            tiles=(40, 41, 42, 43),
            preamble=_NE_PICKUP,
            start_hour=1,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire7",
            tiles=(45, 46, 47, 48),
            preamble=_NE_PICKUP,
            start_hour=1,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire11",
            tiles=(34, 39, 44, 49),
            preamble=_NE_PICKUP,
            start_hour=1,
            net_tile_ops=12,
            is_hand=True,
        ),
    ),
    shed_door=_SHED_DOOR,
    shed_adjacent=_SHED_ADJACENT,
)

_SW_PICKUP = ("PICKUP",)

MILOS_THREELAND18 = Layout(
    coords=(
        *_ONELAND_COORDS,
        *_column(5, 25),
        *_column(6, 30),
        *_column(7, 35),
        *_column(8, 40),
        *_column(9, 45),
        *_column_south(4),
        *_column_south(3),
        *_column_south(2),
        *_column_south(1),
        *_column_south(0),
    ),
    zones=(
        *MILOS_TWOLAND12.zones,
        Zone(
            name="hire12",
            tiles=(50, 51, 52, 53, 54),
            preamble=_SW_PICKUP,
            start_hour=2,
            net_tile_ops=16,
            is_hand=True,
        ),
        Zone(
            name="hire16",
            tiles=(55, 56, 57, 58),
            preamble=_SW_PICKUP,
            start_hour=2,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire15",
            tiles=(60, 61, 62, 63),
            preamble=_SW_PICKUP,
            start_hour=2,
            net_tile_ops=13,
            is_hand=True,
        ),
        Zone(
            name="hire14",
            tiles=(65, 66, 67, 68),
            preamble=_SW_PICKUP,
            start_hour=2,
            net_tile_ops=13,
            is_hand=True,
        ),
        Zone(
            name="hire13",
            tiles=(70, 71, 72, 73),
            preamble=_SW_PICKUP,
            start_hour=2,
            net_tile_ops=12,
            is_hand=True,
        ),
        Zone(
            name="hire17",
            tiles=(59, 64, 69, 74),
            preamble=_SW_PICKUP,
            start_hour=2,
            net_tile_ops=11,
            is_hand=True,
        ),
    ),
    shed_door=_SHED_DOOR,
    shed_adjacent=_SHED_ADJACENT,
)

NW_WORKERS: tuple[str, ...] = (
    "farmer",
    "hire1",
    "hire2",
    "hire3",
    "hire4",
    "hire5",
)
NE_WORKERS: tuple[str, ...] = (
    "hire6",
    "hire10",
    "hire9",
    "hire8",
    "hire7",
    "hire11",
)
NE_TILES: frozenset[int] = frozenset(range(25, 50))
SW_WORKERS: tuple[str, ...] = (
    "hire12",
    "hire16",
    "hire15",
    "hire14",
    "hire13",
    "hire17",
)
SW_TILES: frozenset[int] = frozenset(range(50, 75))

# Diagnostic spawn expectations (env least-occupancy; log only).
SW_EXPECTED_SPAWN: dict[str, tuple[tuple[int, int], ...]] = {
    "hire12": ((4, 5),),
    "hire15": ((5, 4),),
    "hire16": ((4, 4), (5, 4)),
}

SW_ENABLED = os.environ.get("KAGGRI_SW", "1") == "1"
CURRENT = MILOS_THREELAND18 if SW_ENABLED else MILOS_TWOLAND12

TILE_COORDS: tuple[tuple[int, int], ...] = ()
NUM_TILES = 0
SHED_DOOR: tuple[int, int] = _SHED_DOOR
SHED_ADJACENT: frozenset[tuple[int, int]] = _SHED_ADJACENT
WORKERS: tuple[str, ...] = ()
HAND_WORKERS: tuple[str, ...] = ()
NUM_HIRES = 0
WORKER_TILES: dict[str, list[int]] = {}
WORKER_ROUTES: dict[str, list[int]] = {}
PREAMBLE: dict[str, list[str]] = {}
HAND_START_HOUR: dict[str, int] = {}
NET_TILE_OPS: dict[str, int] = {}
HAND_DAILY_COST: dict[str, int] = {}
HIRE_DAILY_COST = 0

FARMER = "farmer"
FARMER_TILES = MILOS_FARMER.zones[0].tiles


def bind(layout: Layout) -> None:
    global TILE_COORDS, NUM_TILES, SHED_DOOR, SHED_ADJACENT
    global WORKERS, HAND_WORKERS, NUM_HIRES
    global WORKER_TILES, WORKER_ROUTES, PREAMBLE, HAND_START_HOUR, NET_TILE_OPS
    global HAND_DAILY_COST, HIRE_DAILY_COST

    TILE_COORDS = layout.coords
    NUM_TILES = len(layout.coords)
    SHED_DOOR = layout.shed_door
    SHED_ADJACENT = layout.shed_adjacent

    WORKERS = tuple(z.name for z in layout.zones)
    HAND_WORKERS = tuple(z.name for z in layout.zones if z.is_hand)
    NUM_HIRES = len(HAND_WORKERS)

    WORKER_TILES = {z.name: list(z.tiles) for z in layout.zones}
    WORKER_ROUTES = {z.name: list(z.tiles) for z in layout.zones}
    PREAMBLE = {z.name: list(z.preamble) for z in layout.zones}
    HAND_START_HOUR = {z.name: z.start_hour for z in layout.zones if z.is_hand}
    NET_TILE_OPS = {z.name: z.net_tile_ops for z in layout.zones}

    hand_costs: dict[str, int] = {}
    a, b = 1, 1
    for z in layout.zones:
        if z.is_hand:
            hand_costs[z.name] = a
            a, b = b, a + b
    HAND_DAILY_COST = hand_costs
    HIRE_DAILY_COST = sum(hand_costs.values())


def worker_for_tile(idx: int) -> str:
    for name, tiles in WORKER_TILES.items():
        if idx in tiles:
            return name
    return WORKERS[0] if WORKERS else FARMER


def tile_est_ops_weight(tile) -> float:
    if not isinstance(tile, dict):
        return 0.0
    kind = tile.get("kind")
    if kind in ("COOP", "PASTURE"):
        return EST_OPS_ANIMAL
    if kind == "PLANT":
        return EST_OPS_CROP
    return 0.0


bind(CURRENT)
if CURRENT is MILOS_THREELAND18:
    _layout_tag = "milos_threeland18"
elif CURRENT is MILOS_TWOLAND12:
    _layout_tag = "milos_twoland12"
elif CURRENT is MILOS_ONELAND6:
    _layout_tag = "milos_oneland6"
elif CURRENT is MILOS_ONELAND:
    _layout_tag = "milos_oneland"
else:
    _layout_tag = "milos_farmer"
print(
    f"[zoning] CURRENT={_layout_tag} tiles={NUM_TILES} hands={NUM_HIRES}",
    flush=True,
)
