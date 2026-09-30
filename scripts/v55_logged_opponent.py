#!/usr/bin/env python3
"""V55 opponent with execution/money logging for local smoke (not for submission).

Loads opponents/v55/main.py via KE's get_last_callable (final_price_guard), then
logs tile ops, market orders, and dawn money/shed under [opp] / [opp_snap]
so they never collide with our [exec]/[snap] parsers.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(os.environ.get("SMOKE_ROOT") or os.getcwd())
_V55_MAIN = _ROOT / "opponents" / "v55" / "main.py"
_INNER: Callable | None = None
_PREV_DAWN_MONEY: int | None = None
_TILE_OPS: dict[str, int] = {}
_MARKET_OPS: dict[str, int] = {}
_SUMMARY_DONE = False


def _ensure_v55_main() -> None:
    if _V55_MAIN.is_file():
        return
    import importlib.util

    script = _ROOT / "scripts" / "extract_v55_opponent.py"
    spec = importlib.util.spec_from_file_location("extract_v55_opponent", script)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(f"missing {_V55_MAIN} and cannot load extractor")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.extract(_V55_MAIN)


def _load_inner() -> Callable:
    global _INNER
    if _INNER is not None:
        return _INNER
    _ensure_v55_main()
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.utils import read_file

    path = str(_V55_MAIN)
    _INNER = get_last_callable(read_file(path, path), path=path)
    return _INNER


def _fmt(op: Any) -> str:
    if not op:
        return "PASS"
    if isinstance(op, (list, tuple)):
        return " ".join(str(x) for x in op)
    return str(op)


def _verb(op: Any) -> str:
    if not op:
        return "PASS"
    if isinstance(op, (list, tuple)) and op:
        return str(op[0])
    return str(op)


def _is_tile_op(verb: str) -> bool:
    v = verb.upper()
    if v in {"PASS", "NORTH", "SOUTH", "EAST", "WEST"}:
        return False
    return True


def _enabled() -> bool:
    return os.environ.get("SMOKE_OPP_VERBOSE", "1") not in ("0", "false", "False")


def _log(msg: str) -> None:
    if _enabled():
        print(msg, flush=True)


def _count_market(orders: list) -> None:
    for o in orders or []:
        if not o:
            continue
        key = str(o[0])
        _MARKET_OPS[key] = _MARKET_OPS.get(key, 0) + 1


def _count_tile(verb: str) -> None:
    if not _is_tile_op(verb):
        return
    _TILE_OPS[verb] = _TILE_OPS.get(verb, 0) + 1


def _fmt_join(orders: list) -> str:
    return " ".join(_fmt(o) for o in orders)


def _live_tile_count(me: dict) -> int:
    tiles = me.get("tiles") or []
    live = 0
    for row in tiles:
        if not isinstance(row, (list, tuple)):
            continue
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") in (
                "PLANT",
                "COOP",
                "PASTURE",
            ):
                live += 1
    return live


def agent(observation, configuration=None):
    """KE entry — must stay the last callable in this module."""
    global _PREV_DAWN_MONEY, _SUMMARY_DONE

    inner = _load_inner()
    if configuration is None:
        action = inner(observation)
    else:
        try:
            action = inner(observation, configuration)
        except TypeError:
            action = inner(observation)

    if not isinstance(action, dict):
        return action

    day = int(observation.get("day", 0))
    hour = int(observation.get("hour", 0))
    player = int(observation.get("player", 0))
    me = observation["farms"][player]
    private = observation.get("private") or {}
    money = int(me.get("money", 0))
    shed = private.get("shed") or {}
    shed_total = sum(int(v) for v in shed.values())

    farmer = action.get("farmer") or ["PASS"]
    hands = action.get("hands") or []
    market = action.get("market") or []

    if market:
        _log(f"[opp] d={day} h={hour} market {_fmt_join(market)}")
        _count_market(market)

    _log(f"[opp] d={day} h={hour} farmer {_fmt(farmer)}")
    _count_tile(_verb(farmer))

    hand_pos = me.get("hands") or []
    for i, act in enumerate(hands):
        pos = tuple(hand_pos[i]) if i < len(hand_pos) else None
        _log(f"[opp] d={day} h={hour} hand{i} {_fmt(act)} pos={pos}")
        _count_tile(_verb(act))

    if hour == 0:
        if _PREV_DAWN_MONEY is None:
            delta = ""
        else:
            delta = f" d_money={money - _PREV_DAWN_MONEY}"
        n_hired = len(hands)
        if n_hired <= 0 and hand_pos:
            n_hired = len(hand_pos)
        _log(
            f"[opp_snap] d={day} h={hour} money={money} shed_total={shed_total}"
            f"{delta} hands={n_hired} quads={me.get('unlocked_quadrants')}"
            f" live={_live_tile_count(me)}"
        )
        _PREV_DAWN_MONEY = money

    # Official episode calls agents 719 times (last = d=29 h=22).
    if not _SUMMARY_DONE and day == 29 and hour >= 22:
        _SUMMARY_DONE = True
        tile_s = " ".join(f"{k}={v}" for k, v in sorted(_TILE_OPS.items())) or "none"
        mkt_s = " ".join(f"{k}={v}" for k, v in sorted(_MARKET_OPS.items())) or "none"
        _log(f"[opp] summary tile_ops {tile_s}")
        _log(f"[opp] summary market_ops {mkt_s}")
        _log(f"[opp] summary final_money={money} shed_total={shed_total}")

    return action
