"""Board layout and worker zones — single source for tile geometry and routes."""

from __future__ import annotations

from dataclasses import dataclass

_SHED_DOOR = (4, 4)
_SHED_ADJACENT = frozenset({(4, 4), (5, 4), (4, 5), (5, 5)})


@dataclass(frozen=True)
class Zone:
    name: str
    tiles: tuple[int, ...]  # visit order (route)
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


# Tile grid (x, y) — tile 1 = (4, 4) = shed door
#  24 23 13 14 15
#  25 22 12 11 10
#  19 18  9  8  7
#  20 17  4  5  6
#  21 16  3  2  1
FOUR = Layout(
    coords=(
        (4, 4), (3, 4), (2, 4), (2, 3), (3, 3), (4, 3), (4, 2), (3, 2), (2, 2),  # 1-9 farmer
        (4, 1), (3, 1), (2, 1), (2, 0), (3, 0), (4, 0),  # 10-15 top
        (1, 4), (1, 3), (1, 2), (0, 2), (0, 3), (0, 4),  # 16-21 left
        (1, 1), (1, 0), (0, 0), (0, 1),  # 22-25 corner
    ),
    zones=(
        Zone(
            name="farmer",
            tiles=(0, 1, 2, 3, 4, 5, 6, 7, 8),
            preamble=(),
            start_hour=0,
            net_tile_ops=14,
            is_hand=False,
        ),
        Zone(
            name="hire1",
            tiles=(9, 10, 11, 12, 13, 14),
            preamble=("WEST", "PICKUP_WHEAT", "PICKUP_ANIMALS", "NORTH", "NORTH", "NORTH"),
            start_hour=1,
            net_tile_ops=12,
            is_hand=True,
        ),
        Zone(
            name="hire2",
            tiles=(15, 16, 17, 18, 19, 20),
            preamble=("NORTH", "PICKUP_WHEAT", "PICKUP_ANIMALS", "WEST", "WEST", "WEST"),
            start_hour=1,
            net_tile_ops=12,
            is_hand=True,
        ),
        Zone(
            name="hire3",
            tiles=(21, 22, 23, 24),
            preamble=(
                "WEST",
                "PICKUP_WHEAT",
                "PICKUP_ANIMALS",
                "WEST",
                "WEST",
                "NORTH",
                "NORTH",
                "NORTH",
            ),
            start_hour=1,
            net_tile_ops=10,
            is_hand=True,
        ),
    ),
    shed_door=_SHED_DOOR,
    shed_adjacent=_SHED_ADJACENT,
)

# Tile grid (x, y) — tile 1 = (4, 4) = shed door
#  10 15 20 25  5
#   9 14 19 24  4
#   8 13 18 23  3
#   7 12 17 22  2
#   6 11 16 21  1
FIVE = Layout(
    coords=(
        (4, 4), (4, 3), (4, 2), (4, 1), (4, 0),  # 1-5 farmer
        (0, 4), (0, 3), (0, 2), (0, 1), (0, 0),  # 6-10 hire1
        (1, 4), (1, 3), (1, 2), (1, 1), (1, 0),  # 11-15 hire2
        (2, 4), (2, 3), (2, 2), (2, 1), (2, 0),  # 16-20 hire3
        (3, 4), (3, 3), (3, 2), (3, 1), (3, 0),  # 21-25 hire4
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
            preamble=(
                "WEST",
                "PICKUP_WHEAT",
                "PICKUP_ANIMALS",
                "WEST",
                "WEST",
                "WEST",
                "WEST",
            ),
            start_hour=1,
            net_tile_ops=17,
            is_hand=True,
        ),
        Zone(
            name="hire2",
            tiles=(10, 11, 12, 13, 14),
            preamble=(
                "NORTH",
                "PICKUP_WHEAT",
                "PICKUP_ANIMALS",
                "WEST",
                "WEST",
                "WEST",
            ),
            start_hour=1,
            net_tile_ops=16,
            is_hand=True,
        ),
        Zone(
            name="hire3",
            tiles=(15, 16, 17, 18, 19),
            preamble=("WEST", "PICKUP_WHEAT", "PICKUP_ANIMALS", "WEST", "WEST"),
            start_hour=2,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire4",
            tiles=(20, 21, 22, 23, 24),
            preamble=("NORTH", "PICKUP_WHEAT", "PICKUP_ANIMALS", "WEST"),
            start_hour=2,
            net_tile_ops=13,
            is_hand=True,
        ),
    ),
    shed_door=_SHED_DOOR,
    shed_adjacent=_SHED_ADJACENT,
)

CURRENT: Layout = FIVE


def _fib_hire_cost(n: int) -> int:
    """Daily hire cost: sum of fib(0..n-1) with fib = 1,1,2,3,5,..."""
    if n <= 0:
        return 0
    a, b = 1, 1
    total = 0
    for _ in range(n):
        total += a
        a, b = b, a + b
    return total


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


def bind(layout: Layout) -> None:
    """Populate module-level tables from a layout."""
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
    for zone in CURRENT.zones:
        if idx in zone.tiles:
            return zone.name
    return WORKERS[0] if WORKERS else "farmer"


bind(CURRENT)
