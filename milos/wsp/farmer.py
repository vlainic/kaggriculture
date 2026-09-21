"""Farmer-only WSP (FIVE zone I, 5 tiles) — milos-local, no agent imports."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from milos.wsp import data as rollouts
from milos.wsp import mip
from milos.wsp.config import FARMER, FARMER_TILES, NUM_DAYS
from milos.wsp.types import SolveResult

FARMER_TILES_FIVE = FARMER_TILES
_PRESTART_PATH = Path(__file__).resolve().parent / "prestart.json"


@lru_cache(maxsize=1)
def _load_prestart() -> tuple[dict[int, list], bool, tuple[str, ...]]:
    with _PRESTART_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    assigned = {int(k): list(v) for k, v in data["assigned"].items()}
    complete = bool(data.get("complete", True))
    solved = tuple(data.get("solved_workers", (FARMER,)))
    return assigned, complete, solved


def _empty_locked(horizon: int) -> dict:
    z = lambda: [0] * horizon
    return {
        "daily_tile_ops": z(),
        "daily_animal_active": z(),
        "daily_feed": z(),
        "daily_fert": z(),
        "daily_collect": z(),
        "daily_wheat": z(),
        "cash_by_day": z(),
        "spend_by_day": z(),
    }


def _is_prestart_solve(
    horizon: int,
    empty_tiles: list[int],
    empty_counts: dict[str, int],
) -> bool:
    if horizon != NUM_DAYS:
        return False
    if sorted(empty_tiles) != list(FARMER_TILES):
        return False
    return empty_counts.get(FARMER, 0) == len(FARMER_TILES)


def solve(
    chains: list,
    *,
    horizon: int,
    empty_tiles: list[int],
    empty_counts: dict[str, int] | None = None,
    locked_by_worker: dict[str, dict] | None = None,
    starting_money: int,
    max_time: float = 20.0,
    track_shed: bool = True,
    w_open0: int = 0,
    f_open0: int = 0,
    min_balance: int = 0,
    price_of: Callable[[str], int] | None = None,
    **kwargs,
) -> SolveResult:
    del chains, kwargs
    counts = empty_counts or {FARMER: len(empty_tiles)}
    if _is_prestart_solve(horizon, empty_tiles, counts):
        assigned, complete, solved_workers = _load_prestart()
        print(
            f"[milos/wsp] farmer prestart loaded tiles={len(assigned)} "
            f"from {_PRESTART_PATH.name} complete={complete}",
            flush=True,
        )
        return SolveResult(assigned, complete, solved_workers)

    if price_of is None:
        base = rollouts.i0_base_prices()
        price_of = lambda product, _base=base: _base[product]

    empty_set = set(empty_tiles)
    farmer_tiles = [idx for idx in FARMER_TILES if idx in empty_set]
    if not farmer_tiles:
        farmer_tiles = list(empty_tiles)

    locked = (locked_by_worker or {}).get(FARMER) or _empty_locked(horizon)
    patterns = mip.build_patterns(horizon, price_of)
    opening = [starting_money] * horizon

    res = mip.solve_zone(
        patterns,
        horizon=horizon,
        empty_tiles=farmer_tiles,
        locked=locked,
        locked_counts={},
        opening_balances=opening,
        w_open=w_open0 if track_shed else 0,
        f_open=f_open0 if track_shed else 0,
        max_time=max_time,
        track_shed=track_shed,
        min_balance=min_balance,
        price_of=price_of,
    )
    if res is None:
        return SolveResult({}, False, ())

    assigned = mip.decode_wsp_assignment(empty_set, res["picked"])
    return SolveResult(assigned, True, (FARMER,))
