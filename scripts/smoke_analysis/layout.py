"""Derive land1/land2/land3 partitions from the live submission zoning package.

Live entry is ``main.py``: milos farmer-only → ``milos.zoning``; otherwise ``agent.zoning``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _submission_package() -> str:
    """Return ``milos`` or ``agent`` based on main.py imports (smoke bundle source)."""
    main_path = _repo_root() / "main.py"
    if not main_path.exists():
        return "agent"
    text = main_path.read_text(encoding="utf-8")
    # Prefer explicit milos entry (current default submission).
    if re.search(r"^\s*(from|import)\s+milos\b", text, re.MULTILINE):
        return "milos"
    return "agent"


def active_layout() -> dict[str, Any]:
    """Read live workers/zoning and return layout-aware partitions.

    Milos: single zone ``farmer`` (5 tiles), no land2/land3.
    Agent: Land1 = FIVE zone names; Land2 = LAND2_WORKERS; Land3 when THREE.
    """
    import sys

    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    pkg = _submission_package()
    if pkg == "milos":
        from milos import zoning

        layout = zoning.CURRENT
        workers_tuple = tuple(z.name for z in layout.zones)
        hand_workers = tuple(z.name for z in layout.zones if z.is_hand)
        worker_tiles = {z.name: list(z.tiles) for z in layout.zones}
        net_tile_ops = {z.name: z.net_tile_ops for z in layout.zones}
        nw = tuple(zoning.NW_WORKERS)
        ne = tuple(zoning.NE_WORKERS)
        sw = tuple(zoning.SW_WORKERS)
        land1_tile_count = 25
        land2_tile_min = 26
        land3_tile_min = 51
        layout_name = getattr(zoning, "_layout_tag", "milos")
        if not ne and layout is not zoning.MILOS_TWOLAND12:
            land1_workers = workers_tuple
        else:
            land1_workers = nw
        return {
            "workers": workers_tuple,
            "hand_workers": hand_workers,
            "worker_tiles": worker_tiles,
            "net_tile_ops": net_tile_ops,
            "hand_daily_cost": dict(zoning.HAND_DAILY_COST),
            "land1_workers": land1_workers,
            "land2_workers": ne,
            "land3_workers": sw,
            "land2_probe_worker": ne[0] if ne else None,
            "land3_probe_worker": sw[0] if sw else None,
            "land1_tile_count": land1_tile_count,
            "land2_tile_min": land2_tile_min,
            "land3_tile_min": land3_tile_min,
            "has_land2": bool(ne),
            "has_land3": bool(sw),
            "layout_name": layout_name,
            "package": "milos",
        }

    from agent import zoning

    layout = zoning.CURRENT
    workers_tuple = tuple(z.name for z in layout.zones)
    hand_workers = tuple(z.name for z in layout.zones if z.is_hand)
    worker_tiles = {z.name: list(z.tiles) for z in layout.zones}
    net_tile_ops = dict(zoning.NET_TILE_OPS)

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
        "net_tile_ops": net_tile_ops,
        "hand_daily_cost": dict(zoning.HAND_DAILY_COST),
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
        "package": "agent",
    }
