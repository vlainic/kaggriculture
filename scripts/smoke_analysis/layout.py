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
    from agent import workers, zoning

    land1_names = frozenset(z.name for z in zoning.FIVE.zones)
    land2_workers = tuple(w for w in workers.WORKERS if w not in land1_names)
    land1_tile_count = len(zoning.FIVE.coords)
    return {
        "workers": workers.WORKERS,
        "hand_workers": workers.HAND_WORKERS,
        "worker_tiles": workers.WORKER_TILES,
        "land1_workers": tuple(w for w in workers.WORKERS if w in land1_names),
        "land2_workers": land2_workers,
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
