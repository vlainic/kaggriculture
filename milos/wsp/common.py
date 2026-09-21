"""Chain decode helpers — milos-local (no agent imports)."""

from __future__ import annotations

from milos.wsp.config import (
    ANIMAL_NAMES,
    EST_OPS_ANIMAL,
    EST_OPS_CROP,
    FARMER,
    FARMER_NET_TILE_OPS,
    FARMER_TILES,
    PROFILE_SUFFIXES,
)

WORKER_TILES: dict[str, tuple[int, ...]] = {FARMER: FARMER_TILES}
NET_TILE_OPS: dict[str, int] = {FARMER: FARMER_NET_TILE_OPS}


def chain_est_ops(raw_chain: list) -> float:
    if not raw_chain:
        return 0.0
    has_animal = False
    has_crop = False
    for profile_key, _start in raw_chain:
        label, _ = parse_profile_key(profile_key)
        if label in ANIMAL_NAMES:
            has_animal = True
        else:
            has_crop = True
    if has_animal:
        return EST_OPS_ANIMAL
    if has_crop:
        return EST_OPS_CROP
    return 0.0


def parse_profile_key(profile_key: str) -> tuple[str, str]:
    for suffix in PROFILE_SUFFIXES:
        token = f"_{suffix}"
        if profile_key.endswith(token):
            return profile_key[: -len(token)], suffix
    raise ValueError(f"unknown profile key: {profile_key}")


def earliest_animal_day(raw_chain: list) -> int:
    best = 10**9
    for profile_key, start_day in raw_chain:
        label, _ = parse_profile_key(profile_key)
        if label in ANIMAL_NAMES:
            best = min(best, int(start_day))
    return best


def decode_sort_key(raw_chain: list) -> tuple:
    animal_day = earliest_animal_day(raw_chain)
    if animal_day < 10**9:
        return (0, animal_day)
    if not raw_chain:
        return (1, 0)
    return (2, 0)


def decode_zone_assignment(
    worker: str,
    chains: list,
    solver,
    count_vars: list,
    empty_tiles: set[int],
) -> dict[int, list]:
    remaining = [idx for idx in WORKER_TILES[worker] if idx in empty_tiles]
    if not remaining:
        return {}
    slots: list[list] = []
    for ci, chain in enumerate(chains):
        n = int(solver.Value(count_vars[ci]))
        for _ in range(n):
            slots.append(chain["raw_chain"])
    slots.sort(key=decode_sort_key)
    assigned: dict[int, list] = {}
    for i, idx in enumerate(remaining):
        assigned[idx] = slots[i] if i < len(slots) else []
    return assigned


def repack_land_mix(
    assigned: dict[int, list],
    workers: tuple[str, ...],
    empty_set: set[int],
    patterns: list,
    horizon: int,
) -> tuple[dict[int, list], str | None]:
    """No-op below 2 workers (farmer-only)."""
    del empty_set, patterns, horizon
    if len(workers) < 2:
        return assigned, None
    return assigned, None
