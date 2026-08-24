"""Board layout and worker zones — single source for tile geometry and routes."""

from __future__ import annotations

from dataclasses import dataclass


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
CURRENT = Layout(
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
    shed_door=(4, 4),
    shed_adjacent=frozenset({(4, 4), (5, 4), (4, 5), (5, 5)}),
)


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


TILE_COORDS = CURRENT.coords
NUM_TILES = len(CURRENT.coords)
SHED_DOOR = CURRENT.shed_door
SHED_ADJACENT = CURRENT.shed_adjacent

WORKERS = tuple(z.name for z in CURRENT.zones)
HAND_WORKERS = tuple(z.name for z in CURRENT.zones if z.is_hand)
NUM_HIRES = len(HAND_WORKERS)

WORKER_TILES = {z.name: list(z.tiles) for z in CURRENT.zones}
WORKER_ROUTES = {z.name: list(z.tiles) for z in CURRENT.zones}
PREAMBLE = {z.name: list(z.preamble) for z in CURRENT.zones}
HAND_START_HOUR = {z.name: z.start_hour for z in CURRENT.zones if z.is_hand}
NET_TILE_OPS = {z.name: z.net_tile_ops for z in CURRENT.zones}
HIRE_DAILY_COST = _fib_hire_cost(NUM_HIRES)


def worker_for_tile(idx: int) -> str:
    for zone in CURRENT.zones:
        if idx in zone.tiles:
            return zone.name
    return WORKERS[0]
