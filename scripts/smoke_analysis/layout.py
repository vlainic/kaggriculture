"""Derive land1/land2 partitions from live agent.zoning.CURRENT."""

from __future__ import annotations

from typing import Any


def active_layout() -> dict[str, Any]:
    """Read agent workers/zoning and return layout-aware partitions.

    Land1 = FIVE zone names (always the NW 25-tile catalog).
    Land2 = workers in CURRENT that are not in FIVE (empty on one-land).
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from agent import zoning

    # Use zoning.CURRENT directly — agent.workers snapshots WORKERS at import time
    # and can stay on FIVE if imported before bind(TWO).
    layout = zoning.CURRENT
    workers_tuple = tuple(z.name for z in layout.zones)
    hand_workers = tuple(z.name for z in layout.zones if z.is_hand)
    worker_tiles = {z.name: list(z.tiles) for z in layout.zones}

    land1_names = frozenset(z.name for z in zoning.FIVE.zones)
    land2_workers = tuple(w for w in workers_tuple if w not in land1_names)
    land1_tile_count = len(zoning.FIVE.coords)
    return {
        "workers": workers_tuple,
        "hand_workers": hand_workers,
        "worker_tiles": worker_tiles,
        "land1_workers": tuple(w for w in workers_tuple if w in land1_names),
        "land2_workers": land2_workers,
        "land2_probe_worker": land2_workers[0] if land2_workers else None,
        "land1_tile_count": land1_tile_count,
        "land2_tile_min": land1_tile_count + 1,  # 1-indexed assign tile ids
        "has_land2": bool(land2_workers),
        "layout_name": (
            "TWO"
            if zoning.CURRENT is zoning.TWO
            else "FIVE"
            if zoning.CURRENT is zoning.FIVE
            else "FOUR"
            if zoning.CURRENT is zoning.FOUR
            else "CUSTOM"
        ),
    }
