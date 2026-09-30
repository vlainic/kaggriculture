"""Env-gated rollout flags for forecast/sell fixes (default on)."""

from __future__ import annotations

import os

_CACHE: dict[str, bool] = {}


def fix_enabled(name: str, *, default: bool = True) -> bool:
    key = f"KAGGRI_FIX_{name}"
    if key in _CACHE:
        return _CACHE[key]
    raw = os.environ.get(key)
    if raw is None:
        val = default
    else:
        val = raw.strip().lower() not in ("0", "false", "no", "off")
    _CACHE[key] = val
    return val


def fix_calib() -> bool:
    return fix_enabled("CALIB")


def fix_prior() -> bool:
    return fix_enabled("PRIOR")


def fix_sell() -> bool:
    return fix_enabled("SELL")


def fix_fert() -> bool:
    return fix_enabled("FERT")


def fix_reset() -> bool:
    return fix_enabled("RESET")


_DISPOSAL_CACHE: dict[str, bool] = {}


def _disposal_flag(env_name: str, *, default: bool = True) -> bool:
    key = f"KAGGRI_{env_name}"
    if key in _DISPOSAL_CACHE:
        return _DISPOSAL_CACHE[key]
    raw = os.environ.get(key)
    if raw is None:
        val = default
    else:
        val = raw.strip().lower() not in ("0", "false", "no", "off")
    _DISPOSAL_CACHE[key] = val
    return val


def fix_room_guard() -> bool:
    return _disposal_flag("ROOM_GUARD")


def fix_animal_cap() -> bool:
    return _disposal_flag("ANIMAL_CAP")


def fix_room_glut() -> bool:
    return _disposal_flag("ROOM_GLUT")


def fix_animal_cap_product() -> bool:
    return _disposal_flag("ANIMAL_CAP_PRODUCT")


def fix_sell_lead() -> bool:
    return _disposal_flag("SELL_LEAD")


def fix_opp_dump() -> bool:
    return _disposal_flag("OPP_DUMP")
