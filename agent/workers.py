"""Worker zones, routes, hire-order mapping for scripted one-land agent."""

from __future__ import annotations

from agent import script

WORKERS = script.WORKERS
HAND_WORKERS = script.HAND_WORKERS
TILE_COORDS = script.TILE_COORDS
NUM_TILES = script.NUM_TILES
WORKER_TILES = script.WORKER_TILES
WORKER_ROUTES = script.WORKER_ROUTES
PREAMBLE = script.PREAMBLE
HAND_START_HOUR = script.HAND_START_HOUR
SHED_DOOR = script.SHED_DOOR
SHED_ADJACENT = script.SHED_ADJACENT
NUM_HIRES = script.NUM_HIRES

# hands[0]=top (hire1), hands[1]=left (hire2), hands[2]=corner (hire3)
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
