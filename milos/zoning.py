"""Farmer-only zone geometry — milos sandbox (FIVE zone I)."""

from __future__ import annotations

from milos.wsp.config import FARMER, FARMER_NET_TILE_OPS, FARMER_TILES, NUM_DAYS

FARMER_TILES = FARMER_TILES
NET_TILE_OPS = FARMER_NET_TILE_OPS
NUM_TILES = len(FARMER_TILES)
WORKERS: tuple[str, ...] = (FARMER,)
WORKER_TILES: dict[str, tuple[int, ...]] = {FARMER: FARMER_TILES}


def worker_for_tile(idx: int) -> str:
    if idx not in FARMER_TILES:
        raise ValueError(f"tile {idx} not in farmer zone")
    return FARMER
