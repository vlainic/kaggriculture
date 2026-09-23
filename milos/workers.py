"""Worker zones, routes, spawn-tile hire binding for scripted OneLand agent."""

from __future__ import annotations

from milos import zoning

WORKERS = zoning.WORKERS
HAND_WORKERS = zoning.HAND_WORKERS
TILE_COORDS = zoning.TILE_COORDS
NUM_TILES = zoning.NUM_TILES
WORKER_TILES = zoning.WORKER_TILES
WORKER_ROUTES = zoning.WORKER_ROUTES
PREAMBLE = zoning.PREAMBLE
HAND_START_HOUR = zoning.HAND_START_HOUR
SHED_DOOR = zoning.SHED_DOOR
SHED_ADJACENT = zoning.SHED_ADJACENT
NUM_HIRES = zoning.NUM_HIRES
SPAWN_TO_HIRE = zoning.SPAWN_TO_HIRE

HAND_ORDER = HAND_WORKERS


def hand_index(worker: str) -> int:
    return HAND_WORKERS.index(worker)


def worker_for_hand_idx(hand_idx: int) -> str:
    if hand_idx < len(HAND_WORKERS):
        return HAND_WORKERS[hand_idx]
    return HAND_WORKERS[-1]


def hire_worker_for_hand_pos(pos: tuple[int, int]) -> str | None:
    return SPAWN_TO_HIRE.get(pos)


def inventory_index(worker: str, *, hand_slot: int | None = None) -> int:
    if worker == "farmer":
        return 0
    if hand_slot is not None:
        return hand_slot + 1
    return hand_index(worker) + 1
