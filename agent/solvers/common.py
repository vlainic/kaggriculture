"""Shared chain decode helpers for CP-SAT solvers."""

from __future__ import annotations

from agent import animal_rollouts
from agent.zoning import (
    EST_OPS_ANIMAL,
    EST_OPS_CROP,
    EST_OPS_TARGET_HI,
    EST_OPS_TARGET_LO,
    NET_TILE_OPS,
    TILE_COORDS,
    WORKER_ROUTES,
    WORKER_TILES,
)

ANIMAL_NAMES = frozenset(animal_rollouts.animal_names())
PROFILE_SUFFIXES = ("no_fert", "with_fert", "no_care", "with_care")


def chain_est_ops(raw_chain: list) -> float:
    """Tile-level est_ops for a decode chain (animal beats crop)."""
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


def land_is_construction(workers: tuple[str, ...], empty_set: set[int]) -> bool:
    """True when every owned tile in the land group is still empty (first fill)."""
    owned = [idx for w in workers for idx in WORKER_TILES.get(w, ())]
    return bool(owned) and all(idx in empty_set for idx in owned)


def _hand_ops_peak(
    slots: list[list],
    pattern_index: dict[tuple[str, int], dict],
    horizon: int,
) -> int:
    daily = [0] * horizon
    animal_days = [0] * horizon
    for chain in slots:
        for profile_key, start_day in chain:
            pat = pattern_index.get((profile_key, int(start_day)))
            if pat is None:
                continue
            ops = pat.get("daily_tile_ops") or []
            active = pat.get("daily_animal_active") or []
            for d in range(min(horizon, len(ops))):
                daily[d] += int(ops[d])
            for d in range(min(horizon, len(active))):
                animal_days[d] += int(active[d])
    for d in range(horizon):
        if animal_days[d] > 0:
            daily[d] += 1
    return max(daily) if daily else 0


# CP-SAT vs post-hoc peak can disagree by ~1 (preamble / overlap); allow tiny slack.
_OPS_PEAK_SLACK = 1


def repack_land_mix(
    assigned: dict[int, list],
    workers: tuple[str, ...],
    empty_set: set[int],
    patterns: list,
    horizon: int,
) -> tuple[dict[int, list], str | None]:
    """
    Swap chains across fixed snakes to shrink est_ops spread.

    Starts from the decoded assignment and only accepts swaps that keep each
    hand's daily_tile_ops peak ≤ NET_TILE_OPS + small slack.
    """
    workers = tuple(w for w in workers if w in WORKER_TILES)
    if len(workers) < 2:
        return assigned, None

    tiles_by_w: dict[str, list[int]] = {}
    for w in workers:
        tiles_by_w[w] = [idx for idx in WORKER_TILES[w] if idx in empty_set]
        if not tiles_by_w[w]:
            return assigned, None

    slots: dict[str, list[list]] = {w: [] for w in workers}
    for w in workers:
        for idx in tiles_by_w[w]:
            chain = assigned.get(idx) or []
            if chain:
                slots[w].append(list(chain))

    def loads_of(s: dict[str, list[list]]) -> dict[str, float]:
        return {w: sum(chain_est_ops(c) for c in s[w]) for w in workers}

    loads = loads_of(slots)
    start_spread = max(loads.values()) - min(loads.values())
    start_sum = sum(loads.values())
    start_mean = start_sum / len(workers)
    if start_spread <= 0:
        return assigned, None

    pattern_index = {
        (p["profile_key"], int(p["start_day"])): p for p in patterns
    }

    def peak_ok(s: dict[str, list[list]], w: str) -> bool:
        cap = NET_TILE_OPS.get(w, 10**9) + _OPS_PEAK_SLACK
        return _hand_ops_peak(s[w], pattern_index, horizon) <= cap

    swapped = 0
    while True:
        loads = loads_of(slots)
        cur_spread = max(loads.values()) - min(loads.values())
        if cur_spread <= 0:
            break
        best: tuple[float, str, str, int, int] | None = None
        for donor in workers:
            for recv in workers:
                if donor == recv or loads[donor] <= loads[recv]:
                    continue
                for di, c_d in enumerate(slots[donor]):
                    w_d = chain_est_ops(c_d)
                    for ri, c_r in enumerate(slots[recv]):
                        w_r = chain_est_ops(c_r)
                        if w_d <= w_r:
                            continue
                        trial_d = list(slots[donor])
                        trial_r = list(slots[recv])
                        trial_d[di], trial_r[ri] = trial_r[ri], trial_d[di]
                        trial_loads = dict(loads)
                        trial_loads[donor] = loads[donor] - w_d + w_r
                        trial_loads[recv] = loads[recv] - w_r + w_d
                        new_spread = max(trial_loads.values()) - min(
                            trial_loads.values()
                        )
                        if new_spread >= cur_spread:
                            continue
                        trial_slots = dict(slots)
                        trial_slots[donor] = trial_d
                        trial_slots[recv] = trial_r
                        if not peak_ok(trial_slots, donor) or not peak_ok(
                            trial_slots, recv
                        ):
                            continue
                        if best is None or new_spread < best[0]:
                            best = (new_spread, donor, recv, di, ri)
        if best is None:
            break
        _ns, donor, recv, di, ri = best
        slots[donor][di], slots[recv][ri] = slots[recv][ri], slots[donor][di]
        swapped += 1

    if swapped == 0:
        return assigned, None

    after_loads = loads_of(slots)
    after_spread = max(after_loads.values()) - min(after_loads.values())
    after_sum = sum(after_loads.values())
    after_mean = after_sum / len(workers)

    out = dict(assigned)
    changed = 0
    for w in workers:
        ordered = sorted(slots[w], key=decode_sort_key)
        tiles = tiles_by_w[w]
        for i, idx in enumerate(tiles):
            new_chain = ordered[i] if i < len(ordered) else []
            old_chain = assigned.get(idx) or []
            if new_chain != old_chain:
                changed += 1
            out[idx] = new_chain

    if changed == 0:
        return assigned, None

    note = (
        f"{workers[0]}..{workers[-1]} "
        f"spread={start_spread:.1f}->{after_spread:.1f} "
        f"sum={start_sum:.1f}->{after_sum:.1f} "
        f"mean={start_mean:.1f}->{after_mean:.1f} "
        f"swaps={swapped} tiles={changed}"
    )
    return out, note


_RESIZE_MIN_TILES = 2
_RESIZE_MAX_TILES = 8
# Extra daily ops allowed per tile beyond the catalog 5-snake.
_RESIZE_OPS_PER_EXTRA_TILE = 2


def _sort_route_tiles(tiles: list[int]) -> list[int]:
    return sorted(tiles, key=lambda i: (TILE_COORDS[i][0], -TILE_COORDS[i][1]))


def resize_land_tiles(
    assigned: dict[int, list],
    workers: tuple[str, ...],
    empty_set: set[int],
    patterns: list,
    horizon: int,
) -> str | None:
    """
    Move tile ownership (with tile-keyed chains) toward est_ops 20–22 band.

    Construction-only caller; mutates WORKER_TILES / WORKER_ROUTES / NET_TILE_OPS.
    """
    workers = tuple(w for w in workers if w in WORKER_TILES)
    if len(workers) < 2:
        return None

    ownership: dict[str, list[int]] = {}
    for w in workers:
        ownership[w] = [idx for idx in WORKER_TILES[w] if idx in empty_set]
        if not ownership[w]:
            return None

    def load_of(w: str) -> float:
        return sum(chain_est_ops(assigned.get(i) or []) for i in ownership[w])

    pattern_index = {
        (p["profile_key"], int(p["start_day"])): p for p in patterns
    }
    base_ops = {w: int(NET_TILE_OPS.get(w, 0)) for w in workers}
    start_tiles = {w: len(ownership[w]) for w in workers}

    def peak_cap(w: str, n_tiles: int) -> int:
        extra = max(0, n_tiles - start_tiles[w]) * _RESIZE_OPS_PER_EXTRA_TILE
        return base_ops[w] + _OPS_PEAK_SLACK + extra

    def peak_ok(w: str, tile_list: list[int]) -> bool:
        slots = [list(assigned[i]) for i in tile_list if assigned.get(i)]
        return _hand_ops_peak(slots, pattern_index, horizon) <= peak_cap(
            w, len(tile_list)
        )

    start_loads = {w: load_of(w) for w in workers}
    start_sum = sum(start_loads.values())
    start_mean = start_sum / len(workers)
    start_spread = max(start_loads.values()) - min(start_loads.values())

    moved = 0
    max_moves = max(6, len(workers) * 2)
    for _ in range(max_moves):
        loads = {w: load_of(w) for w in workers}
        light = [
            w
            for w in workers
            if loads[w] < EST_OPS_TARGET_LO and len(ownership[w]) < _RESIZE_MAX_TILES
        ]
        if not light:
            break
        recv = min(light, key=lambda w: (loads[w], len(ownership[w]), w))

        donors = [
            w
            for w in workers
            if w != recv
            and len(ownership[w]) > _RESIZE_MIN_TILES
            and (
                loads[w] > EST_OPS_TARGET_HI
                or loads[w] > EST_OPS_TARGET_LO
                or loads[w] > loads[recv]
            )
        ]
        if not donors:
            break
        donor = max(donors, key=lambda w: (loads[w], len(ownership[w]), w))

        ranked = sorted(
            ownership[donor],
            key=lambda i: (chain_est_ops(assigned.get(i) or []), i),
        )
        did = False
        for idx in ranked:
            if len(ownership[donor]) <= _RESIZE_MIN_TILES:
                break
            weight = chain_est_ops(assigned.get(idx) or [])
            new_recv_load = loads[recv] + weight
            if (
                weight >= EST_OPS_ANIMAL
                and new_recv_load > EST_OPS_TARGET_HI
                and loads[recv] >= EST_OPS_TARGET_LO - EST_OPS_CROP
            ):
                continue
            trial_d = [i for i in ownership[donor] if i != idx]
            trial_r = ownership[recv] + [idx]
            if not peak_ok(donor, trial_d) or not peak_ok(recv, trial_r):
                continue
            trial_loads = dict(loads)
            trial_loads[donor] = loads[donor] - weight
            trial_loads[recv] = loads[recv] + weight
            new_spread = max(trial_loads.values()) - min(trial_loads.values())
            old_spread = max(loads.values()) - min(loads.values())
            raised = loads[recv] < EST_OPS_TARGET_LO and trial_loads[recv] > loads[recv]
            if not raised and new_spread >= old_spread:
                continue
            ownership[donor] = trial_d
            ownership[recv] = trial_r
            moved += 1
            did = True
            break
        if not did:
            break

    if moved == 0:
        return None

    for w in workers:
        kept = [i for i in WORKER_TILES[w] if i not in empty_set]
        ordered = _sort_route_tiles(kept + ownership[w])
        WORKER_TILES[w] = ordered
        WORKER_ROUTES[w] = list(ordered)
        extra = max(0, len(ownership[w]) - start_tiles[w])
        if extra:
            NET_TILE_OPS[w] = base_ops[w] + extra * _RESIZE_OPS_PER_EXTRA_TILE

    after_loads = {w: load_of(w) for w in workers}
    after_tiles = {w: len(ownership[w]) for w in workers}
    after_sum = sum(after_loads.values())
    after_mean = after_sum / len(workers)
    after_spread = max(after_loads.values()) - min(after_loads.values())
    tile_note = ",".join(
        f"{w}:{start_tiles[w]}->{after_tiles[w]}" for w in workers
    )
    return (
        f"{workers[0]}..{workers[-1]} moves={moved} tiles[{tile_note}] "
        f"spread={start_spread:.1f}->{after_spread:.1f} "
        f"sum={start_sum:.1f}->{after_sum:.1f} "
        f"mean={start_mean:.1f}->{after_mean:.1f}"
    )


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
