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

# §7.2: explicit hand index → worker zone (refreshed when hires change).
_HAND_ZONE_MAP: dict[int, str] = {}


def refresh_hand_zone_map(active_hand_workers: list[str] | tuple[str, ...]) -> None:
    """Bind physical hand slots to worker zone names in hire order."""
    global _HAND_ZONE_MAP
    _HAND_ZONE_MAP = {
        i: w for i, w in enumerate(active_hand_workers) if w in HAND_WORKERS
    }


def hand_index(worker: str) -> int:
    for idx, name in _HAND_ZONE_MAP.items():
        if name == worker:
            return idx
    return HAND_WORKERS.index(worker)


def worker_for_hand_idx(hand_idx: int) -> str:
    if hand_idx in _HAND_ZONE_MAP:
        return _HAND_ZONE_MAP[hand_idx]
    if hand_idx < len(HAND_WORKERS):
        return HAND_WORKERS[hand_idx]
    return HAND_WORKERS[-1]


def inventory_index(worker: str) -> int:
    if worker == "farmer":
        return 0
    return hand_index(worker) + 1


refresh_hand_zone_map(HAND_WORKERS[:4])
