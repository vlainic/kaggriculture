"""Derive land1/land2/land3 partitions from live agent.zoning.CURRENT."""

from __future__ import annotations

from typing import Any


def active_layout() -> dict[str, Any]:
    """Read agent workers/zoning and return layout-aware partitions.

    Land1 = FIVE zone names (always the NW 25-tile catalog).
    Land2 = LAND2_WORKERS when present on CURRENT.
    Land3 = LAND3_WORKERS when CURRENT is THREE.
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from agent import zoning

    layout = zoning.CURRENT
    workers_tuple = tuple(z.name for z in layout.zones)
    hand_workers = tuple(z.name for z in layout.zones if z.is_hand)
    worker_tiles = {z.name: list(z.tiles) for z in layout.zones}

    land1_names = frozenset(z.name for z in zoning.FIVE.zones)
    land2_names = frozenset(zoning.LAND2_WORKERS)
    land3_names = frozenset(zoning.LAND3_WORKERS)
    land2_workers = tuple(w for w in workers_tuple if w in land2_names)
    land3_workers = tuple(w for w in workers_tuple if w in land3_names)
    land1_tile_count = len(zoning.FIVE.coords)
    if zoning.CURRENT is zoning.THREE:
        layout_name = "THREE"
    elif zoning.CURRENT is zoning.TWO:
        layout_name = "TWO"
    elif zoning.CURRENT is zoning.FIVE:
        layout_name = "FIVE"
    elif zoning.CURRENT is zoning.FOUR:
        layout_name = "FOUR"
    else:
        layout_name = "CUSTOM"
    return {
        "workers": workers_tuple,
        "hand_workers": hand_workers,
        "worker_tiles": worker_tiles,
        "land1_workers": tuple(w for w in workers_tuple if w in land1_names),
        "land2_workers": land2_workers,
        "land3_workers": land3_workers,
        "land2_probe_worker": land2_workers[0] if land2_workers else None,
        "land3_probe_worker": land3_workers[0] if land3_workers else None,
        "land1_tile_count": land1_tile_count,
        "land2_tile_min": land1_tile_count + 1,
        "land3_tile_min": zoning.LAND2_TILE_COUNT + 1,
        "has_land2": bool(land2_workers),
        "has_land3": bool(land3_workers),
        "layout_name": layout_name,
    }
