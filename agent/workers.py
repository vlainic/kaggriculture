"""Worker zones, tile map, routes, and per-worker budgets for 5×5 NW farm."""

from __future__ import annotations

WORKERS = ("farmer", "hire1", "hire2", "hire3")
HAND_WORKERS = ("hire1", "hire2", "hire3")

_FARMER_COORDS: list[tuple[int, int]] = [
    (4, 4),
    (3, 4),
    (2, 4),
    (2, 3),
    (3, 3),
    (4, 3),
    (4, 2),
    (3, 2),
    (2, 2),
]

_HIRE1_COORDS: list[tuple[int, int]] = [
    (1, 4),
    (0, 4),
    (0, 3),
    (1, 3),
    (0, 2),
    (1, 2),
]

_HIRE2_COORDS: list[tuple[int, int]] = [
    (2, 0),
    (3, 0),
    (4, 0),
    (4, 1),
    (3, 1),
    (2, 1),
]

_HIRE3_COORDS: list[tuple[int, int]] = [
    (1, 1),
    (0, 1),
    (0, 0),
    (1, 0),
]

TILE_COORDS: list[tuple[int, int]] = (
    _FARMER_COORDS + _HIRE1_COORDS + _HIRE2_COORDS + _HIRE3_COORDS
)
NUM_TILES = len(TILE_COORDS)

TILE_WORKER: list[str] = (
    ["farmer"] * len(_FARMER_COORDS)
    + ["hire1"] * len(_HIRE1_COORDS)
    + ["hire2"] * len(_HIRE2_COORDS)
    + ["hire3"] * len(_HIRE3_COORDS)
)

WORKER_TILES: dict[str, list[int]] = {
    "farmer": list(range(0, 9)),
    "hire1": list(range(9, 15)),
    "hire2": list(range(15, 21)),
    "hire3": list(range(21, 25)),
}

WORKER_ROUTES: dict[str, list[int]] = {
    "farmer": list(range(len(_FARMER_COORDS))),
    "hire1": list(range(len(_HIRE1_COORDS))),
    "hire2": list(range(len(_HIRE2_COORDS))),
    "hire3": list(range(len(_HIRE3_COORDS))),
}

WORKER_ROUTE_GLOBAL: dict[str, list[int]] = {
    w: [WORKER_TILES[w][local] for local in WORKER_ROUTES[w]] for w in WORKERS
}

DAILY_TURN_BUDGET: dict[str, int] = {
    "farmer": 24,
    "hire1": 23,
    "hire2": 23,
    "hire3": 23,
}

NET_TILE_OPS: dict[str, int] = {
    "farmer": 15,
    "hire1": 15,
    "hire2": 15,
    "hire3": 14,
}

# Fixed cardinal sneak before snake (from typical spawn adjacent to shed).
PREAMBLE: dict[str, list[str]] = {
    "farmer": [],
    "hire1": ["WEST", "WEST", "WEST"],
    "hire2": ["NORTH", "NORTH", "NORTH"],
    "hire3": ["WEST", "WEST", "WEST", "NORTH", "NORTH", "NORTH"],
}

SHED_ADJACENT: frozenset[tuple[int, int]] = frozenset(
    {(4, 4), (5, 4), (4, 5), (5, 5)}
)

# Only unlocked shed-adjacent tile in NW quadrant (matches engine _default_spawn).
SHED_DOOR: tuple[int, int] = (4, 4)

# Typical hand spawn positions (NWSE from shed) → worker zone.
SPAWN_TO_WORKER: dict[tuple[int, int], str] = {
    (5, 4): "hire1",
    (4, 5): "hire2",
    (5, 5): "hire3",
}

NUM_HIRES = len(HAND_WORKERS)


def worker_for_tile(idx: int) -> str:
    return TILE_WORKER[idx]


def net_tile_ops(worker: str) -> int:
    return NET_TILE_OPS[worker]


def daily_turn_budget(worker: str) -> int:
    return DAILY_TURN_BUDGET[worker]


def hand_index(worker: str) -> int:
    return HAND_WORKERS.index(worker)


def assign_hand_workers(hands: list) -> dict[str, int]:
    """Map hire1/2/3 → hand list index from spawn position."""
    mapping = {w: hand_index(w) for w in HAND_WORKERS}
    used: set[str] = set()
    for i, hand in enumerate(hands):
        pos = (hand[0], hand[1])
        worker = SPAWN_TO_WORKER.get(pos)
        if worker and worker not in used:
            mapping[worker] = i
            used.add(worker)
    return mapping


def worker_for_hand_idx(hand_idx: int, hand_for_worker: dict[str, int]) -> str:
    for worker, idx in hand_for_worker.items():
        if idx == hand_idx:
            return worker
    if hand_idx < len(HAND_WORKERS):
        return HAND_WORKERS[hand_idx]
    return HAND_WORKERS[-1]


def inventory_index(worker: str) -> int:
    if worker == "farmer":
        return 0
    return hand_index(worker) + 1


def route_len(worker: str) -> int:
    return len(WORKER_ROUTE_GLOBAL[worker])
