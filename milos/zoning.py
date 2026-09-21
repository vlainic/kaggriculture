"""Milos farmer-only layout (FIVE zone I) — live submission geometry."""

from __future__ import annotations

import os
from dataclasses import dataclass

from milos.wsp.config import EST_OPS_ANIMAL, EST_OPS_CROP, FARMER_NET_TILE_OPS

_SHED_DOOR = (4, 4)
_SHED_ADJACENT = frozenset({(4, 4), (5, 4), (4, 5), (5, 5)})


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

CURRENT = MILOS_FARMER

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
print(
    f"[zoning] CURRENT=milos_farmer tiles={NUM_TILES} hands={NUM_HIRES}",
    flush=True,
)
