"""Worker zones, routes, hire-order mapping for scripted one-land agent."""

from __future__ import annotations

from agent import zoning

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

# Hand order follows HAND_WORKERS in the active layout (see zoning.CURRENT).
HAND_ORDER = HAND_WORKERS


def hand_index(worker: str) -> int:
    return HAND_WORKERS.index(worker)


def worker_for_hand_idx(hand_idx: int) -> str:
    if hand_idx < len(HAND_WORKERS):
        return HAND_WORKERS[hand_idx]
    return HAND_WORKERS[-1]


def inventory_index(worker: str) -> int:
    if worker == "farmer":
        return 0
    return hand_index(worker) + 1
