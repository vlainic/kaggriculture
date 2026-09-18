"""Board layout and worker zones — single source for tile geometry and routes."""

from __future__ import annotations

import os
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
            preamble=("PICKUP_WHEAT", "PICKUP_ANIMALS", "WEST", "WEST"),
            start_hour=2,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire4",
            tiles=(20, 21, 22, 23, 24),
            preamble=("PICKUP_WHEAT", "PICKUP_ANIMALS", "WEST"),
            start_hour=2,
            net_tile_ops=13,
            is_hand=True,
        ),
    ),
    shed_door=_SHED_DOOR,
    shed_adjacent=_SHED_ADJACENT,
)

# Tile grid (x, y) — land 1 = FIVE; land 2 = NE columns x=5..9 (50 tiles total)
#  25 20 15 10  5 30 35 40 45 50
#  24 19 14  9  4 29 34 39 44 49
#  23 18 13  8  3 28 33 38 43 48
#  22 17 12  7  2 27 32 37 42 47
#  21 16 11  6  1 26 31 36 41 46
TWO = Layout(
    coords=FIVE.coords + (
        (5, 4), (5, 3), (5, 2), (5, 1), (5, 0),  # 26-30 hire5 / zone VI
        (6, 4), (6, 3), (6, 2), (6, 1), (6, 0),  # 31-35 hire6 / VII
        (7, 4), (7, 3), (7, 2), (7, 1), (7, 0),  # 36-40 hire7 / VIII
        (8, 4), (8, 3), (8, 2), (8, 1), (8, 0),  # 41-45 hire8 / IX
        (9, 4), (9, 3), (9, 2), (9, 1), (9, 0),  # 46-50 hire9 / X
    ),
    zones=FIVE.zones + (
        Zone(
            name="hire5",
            tiles=(25, 26, 27, 28, 29),
            preamble=("PICKUP_WHEAT", "PICKUP_ANIMALS"),
            start_hour=2,
            net_tile_ops=16,
            is_hand=True,
        ),
        Zone(
            name="hire6",
            tiles=(30, 31, 32, 33, 34),
            preamble=("PICKUP_WHEAT", "PICKUP_ANIMALS", "EAST"),
            start_hour=2,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire7",
            tiles=(35, 36, 37, 38, 39),
            preamble=("PICKUP_WHEAT", "PICKUP_ANIMALS", "EAST", "EAST"),
            start_hour=2,
            net_tile_ops=13,
            is_hand=True,
        ),
        Zone(
            name="hire8",
            tiles=(40, 41, 42, 43, 44),
            preamble=("PICKUP_WHEAT", "PICKUP_ANIMALS", "EAST", "EAST", "EAST"),
            start_hour=2,
            net_tile_ops=12,
            is_hand=True,
        ),
        Zone(
            name="hire9",
            tiles=(45, 46, 47, 48, 49),
            preamble=(
                "PICKUP_WHEAT",
                "PICKUP_ANIMALS",
                "EAST",
                "EAST",
                "EAST",
                "EAST",
            ),
            start_hour=2,
            net_tile_ops=11,
            is_hand=True,
        ),
    ),
    shed_door=_SHED_DOOR,
    shed_adjacent=_SHED_ADJACENT,
)

# Tile grid — land 1+2 = TWO; land 3 = SW columns y=5..9 (75 tiles total)
#   XV XIV XIII XII  XI
#   75  70  65  60  55
#   74  69  64  59  54
#   73  68  63  58  53
#   72  67  62  57  52
#   71  66  61  56  51
# ops = daily_tile_ops only + hire animal preamble; do not side-charge PICKUP
THREE = Layout(
    coords=TWO.coords + (
        (4, 5), (4, 6), (4, 7), (4, 8), (4, 9),  # 51-55 hire10 / zone XI
        (3, 5), (3, 6), (3, 7), (3, 8), (3, 9),  # 56-60 hire11 / XII
        (2, 5), (2, 6), (2, 7), (2, 8), (2, 9),  # 61-65 hire12 / XIII
        (1, 5), (1, 6), (1, 7), (1, 8), (1, 9),  # 66-70 hire13 / XIV
        (0, 5), (0, 6), (0, 7), (0, 8), (0, 9),  # 71-75 hire14 / XV
    ),
    zones=TWO.zones + (
        Zone(
            name="hire10",
            tiles=(50, 51, 52, 53, 54),
            preamble=("PICKUP_WHEAT", "PICKUP_ANIMALS"),
            start_hour=2,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire11",
            tiles=(55, 56, 57, 58, 59),
            preamble=("PICKUP_WHEAT", "PICKUP_ANIMALS", "WEST"),
            start_hour=2,
            net_tile_ops=14,
            is_hand=True,
        ),
        Zone(
            name="hire12",
            tiles=(60, 61, 62, 63, 64),
            preamble=("PICKUP_WHEAT", "PICKUP_ANIMALS", "WEST", "WEST"),
            start_hour=2,
            net_tile_ops=13,
            is_hand=True,
        ),
        Zone(
            name="hire13",
            tiles=(65, 66, 67, 68, 69),
            preamble=("PICKUP_WHEAT", "PICKUP_ANIMALS", "WEST", "WEST", "WEST"),
            start_hour=2,
            net_tile_ops=12,
            is_hand=True,
        ),
        Zone(
            name="hire14",
            tiles=(70, 71, 72, 73, 74),
            preamble=(
                "PICKUP_WHEAT",
                "PICKUP_ANIMALS",
                "WEST",
                "WEST",
                "WEST",
                "WEST",
            ),
            start_hour=2,
            net_tile_ops=12,
            is_hand=True,
        ),
    ),
    shed_door=_SHED_DOOR,
    shed_adjacent=_SHED_ADJACENT,
)

CURRENT: Layout = TWO  # overwritten below from KAGGRI_LANDS

LAND2_BUY_COST = 1000
LAND3_BUY_COST = 2000
LAND1_TILE_COUNT = len(FIVE.coords)
LAND2_TILE_COUNT = len(TWO.coords)
LAND1_WORKERS: tuple[str, ...] = tuple(z.name for z in FIVE.zones)
LAND2_WORKERS: tuple[str, ...] = tuple(
    z.name for z in TWO.zones if z.name not in LAND1_WORKERS
)
LAND3_WORKERS: tuple[str, ...] = tuple(
    z.name for z in THREE.zones if z.name not in LAND1_WORKERS + LAND2_WORKERS
)

# KAGGRI_LANDS=3 → ThreeLand; default / anything else → TwoLand
USE_THREE: bool = os.environ.get("KAGGRI_LANDS", "2") == "3"
CURRENT = THREE if USE_THREE else TWO

# Wave 2: dawn rebalance of WORKER_TILES by animal/crop est_ops (default off).
ZONE_OPS_BUDGET: bool = os.environ.get("ZONE_OPS_BUDGET", "0") == "1"
# Construction-time mix pack on first queue write (fixed snakes; default on).
ZONE_OPS_MIX: bool = os.environ.get("ZONE_OPS_MIX", "1") == "1"
# Wave 4: replace done/tile-done PASS with park/CARE filler (default off).
ZONE_IDLE_FILLER: bool = os.environ.get("ZONE_IDLE_FILLER", "0") == "1"
# Construction-time tile-count resize toward est_ops 20–22 (default off).
ZONE_TILE_RESIZE: bool = os.environ.get("ZONE_TILE_RESIZE", "0") == "1"
EST_OPS_ANIMAL = 4.0
EST_OPS_CROP = 1.5
EST_OPS_TARGET_LO = 20.0
EST_OPS_TARGET_HI = 22.0
# Relative load gap to allow a transfer (below one animal weight so animal moves matter).
_EST_OPS_GAP = 3.0


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
    for name, tiles in WORKER_TILES.items():
        if idx in tiles:
            return name
    return WORKERS[0] if WORKERS else "farmer"


def tile_est_ops_weight(tile) -> float:
    """Wave-1/2 daily-ops weight for a board tile (empty/WEED/LOCKED → 0)."""
    if not isinstance(tile, dict):
        return 0.0
    kind = tile.get("kind")
    if kind in ("COOP", "PASTURE"):
        return EST_OPS_ANIMAL
    if kind == "PLANT":
        return EST_OPS_CROP
    return 0.0


def _board_tile(me: dict, idx: int):
    x, y = TILE_COORDS[idx]
    return me["tiles"][y][x]


def _sort_route_tiles(tiles: list[int]) -> list[int]:
    """Column-major snake: ascending x, then descending y within a column."""
    return sorted(tiles, key=lambda i: (TILE_COORDS[i][0], -TILE_COORDS[i][1]))


def _move_rank(tile) -> tuple[int, float]:
    """Prefer empty, then crop, then animal."""
    w = tile_est_ops_weight(tile)
    if not isinstance(tile, dict) or tile.get("kind") == "WEED":
        return (0, w)
    if tile.get("kind") == "PLANT":
        return (1, w)
    if tile.get("kind") in ("COOP", "PASTURE"):
        return (2, w)
    return (5, w)


def _is_emptyish(tile) -> bool:
    return tile is None or (isinstance(tile, dict) and tile.get("kind") == "WEED")


def _tile_blocked(tile, day: int) -> bool:
    """Skip mid-fert window or currently harvestable / fert-ready tiles."""
    if not isinstance(tile, dict):
        return False
    fert_until = tile.get("fertilized_until_day")
    if fert_until is not None and int(fert_until) >= day:
        return True
    if int(tile.get("yield_units") or 0) > 0:
        return True
    if tile.get("kind") in ("COOP", "PASTURE") and tile.get("fertilizer_available"):
        return True
    return False


def _rebalance_land(me: dict, group: tuple[str, ...], day: int) -> list[str]:
    """Move spare empties toward low-est_ops hands; occupied tiles stay put (halt)."""
    workers = [w for w in group if w in WORKER_TILES and w != "farmer"]
    if len(workers) < 2:
        return []

    max_tiles = max(5, int(EST_OPS_TARGET_HI / EST_OPS_CROP))
    min_tiles = 2

    locked_kept: dict[str, list[int]] = {w: [] for w in workers}
    assignment: dict[str, list[int]] = {w: [] for w in workers}
    for w in workers:
        for idx in WORKER_TILES[w]:
            tile = _board_tile(me, idx)
            if tile == "LOCKED":
                locked_kept[w].append(idx)
            else:
                assignment[w].append(idx)

    owned = [idx for w in workers for idx in assignment[w]]
    if not owned:
        return []
    if not any(tile_est_ops_weight(_board_tile(me, i)) > 0 for i in owned):
        return []

    notes: list[str] = []
    # Cap transfers per dawn to limit cascade thrash (52k/60k lesson).
    max_moves = max(4, len(workers))
    for _ in range(max_moves):
        loads = {
            w: sum(tile_est_ops_weight(_board_tile(me, i)) for i in assignment[w])
            for w in workers
        }
        donors = [w for w in workers if len(assignment[w]) > min_tiles]
        if not donors:
            break
        donor = max(donors, key=lambda w: (loads[w], len(assignment[w])))
        recvs = [w for w in workers if w != donor and len(assignment[w]) < max_tiles]
        if not recvs:
            break
        recv = min(recvs, key=lambda w: (loads[w], len(assignment[w])))
        spread = loads[donor] - loads[recv]
        if spread <= _EST_OPS_GAP:
            break

        ranked = sorted(
            assignment[donor],
            key=lambda i: _move_rank(_board_tile(me, i)),
        )
        moved = False
        for idx in ranked:
            if len(assignment[donor]) <= min_tiles:
                break
            tile = _board_tile(me, idx)
            rank, weight = _move_rank(tile)
            if rank >= 5:
                continue
            # Halt occupied transfers (Wave 2b regression): empties only.
            if weight > 0:
                continue
            if not _is_emptyish(tile):
                continue
            # Empty handoff: only when donor has strictly more empties (anti-thrash).
            n_empty_d = sum(
                1 for i in assignment[donor] if _is_emptyish(_board_tile(me, i))
            )
            n_empty_r = sum(
                1 for i in assignment[recv] if _is_emptyish(_board_tile(me, i))
            )
            if n_empty_d <= n_empty_r:
                continue
            assignment[donor].remove(idx)
            assignment[recv].append(idx)
            notes.append(f"t{idx + 1}:{donor}->{recv}(empty)")
            moved = True
            break
        if not moved:
            break

    if not notes:
        return []

    for w in workers:
        merged = locked_kept[w] + _sort_route_tiles(assignment[w])
        seen: set[int] = set()
        ordered: list[int] = []
        for idx in merged:
            if idx not in seen:
                seen.add(idx)
                ordered.append(idx)
        WORKER_TILES[w] = ordered
        WORKER_ROUTES[w] = list(ordered)
    return notes


def rebalance_zones_for_ops(me: dict, day: int = 0) -> None:
    """Dawn reassignment of owned tiles so est_ops load equalizes within each land."""
    if not ZONE_OPS_BUDGET:
        return
    groups: list[tuple[str, ...]] = [LAND1_WORKERS]
    if LAND2_WORKERS:
        groups.append(LAND2_WORKERS)
    if USE_THREE and LAND3_WORKERS:
        groups.append(LAND3_WORKERS)
    all_notes: list[str] = []
    for group in groups:
        all_notes.extend(_rebalance_land(me, group, day))
    if all_notes:
        print(
            f"[zoning] ZONE_OPS_BUDGET rebalance moves={len(all_notes)} "
            f"{','.join(all_notes[:12])}"
            + ("..." if len(all_notes) > 12 else ""),
            flush=True,
        )


def _register_land3_catalog() -> None:
    """Expose LAND3 tile/ops/cost tables while CURRENT stays TWO."""
    global WORKER_TILES, WORKER_ROUTES, PREAMBLE, HAND_START_HOUR, NET_TILE_OPS
    global HAND_DAILY_COST
    if not LAND3_WORKERS:
        return
    vals = list(HAND_DAILY_COST.values())
    if len(vals) >= 2:
        a, b = vals[-1] + vals[-2], vals[-1] + vals[-2] + vals[-1]
    elif len(vals) == 1:
        a, b = vals[0], vals[0]
    else:
        a, b = 1, 1
    for z in THREE.zones:
        if z.name not in LAND3_WORKERS:
            continue
        WORKER_TILES[z.name] = list(z.tiles)
        WORKER_ROUTES[z.name] = list(z.tiles)
        PREAMBLE[z.name] = list(z.preamble)
        HAND_START_HOUR[z.name] = z.start_hour
        NET_TILE_OPS[z.name] = z.net_tile_ops
        HAND_DAILY_COST[z.name] = a
        a, b = b, a + b


bind(CURRENT)
if CURRENT is TWO:
    _register_land3_catalog()
_layout_name = (
    "THREE" if CURRENT is THREE else "TWO" if CURRENT is TWO else "FIVE" if CURRENT is FIVE else "FOUR"
)
print(
    f"[zoning] CURRENT={_layout_name} tiles={NUM_TILES} hands={NUM_HIRES} "
    f"KAGGRI_LANDS={os.environ.get('KAGGRI_LANDS', '2')} "
    f"ZONE_OPS_BUDGET={int(ZONE_OPS_BUDGET)} "
    f"ZONE_OPS_MIX={int(ZONE_OPS_MIX)} "
    f"ZONE_IDLE_FILLER={int(ZONE_IDLE_FILLER)} "
    f"ZONE_TILE_RESIZE={int(ZONE_TILE_RESIZE)}",
    flush=True,
)
