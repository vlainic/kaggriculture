"""Shared chain decode helpers for CP-SAT solvers."""

from __future__ import annotations

from agent import animal_rollouts
from agent.zoning import WORKER_TILES

ANIMAL_NAMES = frozenset(animal_rollouts.animal_names())
PROFILE_SUFFIXES = ("no_fert", "with_fert", "no_care", "with_care")


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


def decode_monolithic_assignment(
    chains: list,
    solver,
    count: dict,
    workers: tuple[str, ...],
    empty_tiles: set[int],
) -> dict[int, list]:
    assigned: dict[int, list] = {}
    for worker in workers:
        remaining = [idx for idx in WORKER_TILES[worker] if idx in empty_tiles]
        if not remaining:
            continue
        slots: list[list] = []
        for ci, chain in enumerate(chains):
            n = int(solver.Value(count[worker][ci]))
            for _ in range(n):
                slots.append(chain["raw_chain"])
        slots.sort(key=decode_sort_key)
        for i, idx in enumerate(remaining):
            assigned[idx] = slots[i] if i < len(slots) else []
    return assigned
