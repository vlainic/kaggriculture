"""V55 route-0 opener tape (days 0–5). Gated by KAGGRI_V55_OPENER."""

from __future__ import annotations

import json
import os
from pathlib import Path

from milos import workers
from milos.zoning import HAND_WORKERS, NET_TILE_OPS, TILE_COORDS, is_threeland12, worker_for_tile

_OPENER_STEPS = 144
_TAPE: list[dict] | None = None
_CACHE_FLAG: bool | None = None

_TILE_OP_VERBS = frozenset({
    "PLANT", "WATER", "FERTILIZE", "HARVEST", "FEED", "CARE", "DIG", "PLACE",
    "BUILD_COOP", "BUILD_PASTURE", "COLLECT_FERTILIZER",
})


def v55_opener_enabled() -> bool:
    global _CACHE_FLAG
    if not is_threeland12():
        return False
    if _CACHE_FLAG is not None:
        return _CACHE_FLAG
    raw = os.environ.get("KAGGRI_V55_OPENER")
    if raw is None:
        _CACHE_FLAG = True
    else:
        _CACHE_FLAG = raw.strip().lower() not in ("0", "false", "no", "off")
    return _CACHE_FLAG


def opener_step_limit() -> int:
    return _OPENER_STEPS


def load_tape() -> list[dict]:
    global _TAPE
    if _TAPE is not None:
        return _TAPE
    path = Path(__file__).resolve().parent / "v55_opener_d0_d5.json"
    with path.open(encoding="utf-8") as f:
        _TAPE = json.load(f)
    if len(_TAPE) != _OPENER_STEPS:
        raise ValueError(f"v55 opener tape expected {_OPENER_STEPS} steps, got {len(_TAPE)}")
    return _TAPE


def _tile_idx_at(me: dict, x: int, y: int) -> int | None:
    for idx, (tx, ty) in enumerate(TILE_COORDS):
        if tx == x and ty == y:
            tile = me["tiles"][ty][tx]
            if tile is None or tile == "LOCKED":
                return idx if tile == "LOCKED" else idx
            return idx
    return None


def _actor_worker(actor: str, slot: int | None) -> str:
    if actor == "farmer":
        return "farmer"
    if slot is not None and 0 <= slot < len(HAND_WORKERS):
        return HAND_WORKERS[slot]
    return f"hand{slot}"


def log_opener_mismatch(
    *,
    step: int,
    day: int,
    hour: int,
    me: dict,
    actor: str,
    slot: int | None,
    action: list,
    tile_ops_today: dict[str, int],
    reason: str,
) -> None:
    who = _actor_worker(actor, slot)
    pos = tuple(me["farmer"]) if actor == "farmer" else None
    if slot is not None and slot < len(me.get("hands", [])):
        pos = tuple(me["hands"][slot])
    tile_s = pos if pos else "-"
    verb = action[0] if action else "?"
    print(
        f"[opener] mismatch step={step} d={day} h={hour} who={who} "
        f"verb={verb} tile={tile_s} reason={reason}",
        flush=True,
    )


def check_opener_action(
    *,
    step: int,
    day: int,
    hour: int,
    me: dict,
    actor: str,
    slot: int | None,
    action: list,
    tile_ops_today: dict[str, int],
) -> None:
    if not action or action[0] not in _TILE_OP_VERBS:
        return
    if actor == "farmer":
        fx, fy = me["farmer"]
    elif slot is not None and slot < len(me.get("hands", [])):
        fx, fy = me["hands"][slot]
    else:
        return
    idx = _tile_idx_at(me, fx, fy)
    if idx is None:
        log_opener_mismatch(
            step=step,
            day=day,
            hour=hour,
            me=me,
            actor=actor,
            slot=slot,
            action=action,
            tile_ops_today=tile_ops_today,
            reason="no_tile",
        )
        return
    tile = me["tiles"][fy][fx]
    if tile == "LOCKED":
        log_opener_mismatch(
            step=step,
            day=day,
            hour=hour,
            me=me,
            actor=actor,
            slot=slot,
            action=action,
            tile_ops_today=tile_ops_today,
            reason="locked",
        )
        return
    owner = worker_for_tile(idx)
    who = _actor_worker(actor, slot)
    if owner != who:
        log_opener_mismatch(
            step=step,
            day=day,
            hour=hour,
            me=me,
            actor=actor,
            slot=slot,
            action=action,
            tile_ops_today=tile_ops_today,
            reason=f"owner={owner}",
        )
    cap = NET_TILE_OPS.get(owner, 0)
    used = tile_ops_today.get(owner, 0)
    if used >= cap:
        log_opener_mismatch(
            step=step,
            day=day,
            hour=hour,
            me=me,
            actor=actor,
            slot=slot,
            action=action,
            tile_ops_today=tile_ops_today,
            reason=f"ops_cap={used}/{cap}",
        )


def bump_opener_tile_ops(action: list, me: dict, actor: str, slot: int | None, tile_ops_today: dict[str, int]) -> None:
    if not action or action[0] not in _TILE_OP_VERBS:
        return
    if actor == "farmer":
        fx, fy = me["farmer"]
    elif slot is not None and slot < len(me.get("hands", [])):
        fx, fy = me["hands"][slot]
    else:
        return
    idx = _tile_idx_at(me, fx, fy)
    if idx is None:
        return
    owner = worker_for_tile(idx)
    tile_ops_today[owner] = tile_ops_today.get(owner, 0) + 1


def adopt_board_from_farm(me: dict, tile_state: dict[int, dict], day: int) -> None:
    from milos import script
    from milos.script import QueueItem

    plants = animals = empty = 0
    new_queues: dict[int, list[QueueItem]] = {}
    for idx in range(workers.NUM_TILES):
        x, y = TILE_COORDS[idx]
        tile = me["tiles"][y][x]
        st = tile_state[idx]
        st["queue_idx"] = 0
        st["lag"] = 0
        st["gap"] = 0
        st["pending_dig"] = False
        st["dig_plant_ok"] = False
        st["fert_today"] = False
        if tile is None or tile == "WEED":
            new_queues[idx] = []
            empty += 1
            st["active"] = False
        elif tile == "LOCKED":
            new_queues[idx] = []
            st["active"] = False
        elif isinstance(tile, dict):
            kind = tile.get("kind")
            if kind == "PLANT":
                crop = tile["crop"]
                fert_until = int(tile.get("fertilized_until_day", -1) or -1)
                profile = (
                    "with_fert"
                    if fert_until >= day
                    else script.CROP_PROFILE
                )
                new_queues[idx] = [
                    QueueItem("crop", crop, profile=profile)
                ]
                plants += 1
                st["active"] = True
            elif kind in ("COOP", "PASTURE"):
                animal = tile.get("animal") or "SHEEP"
                new_queues[idx] = [
                    QueueItem("animal", animal, profile=script.ANIMAL_PROFILE)
                ]
                animals += 1
                st["active"] = True
            else:
                new_queues[idx] = []
                st["active"] = False
        else:
            new_queues[idx] = []
            st["active"] = False

    script.TILE_QUEUES.clear()
    script.TILE_QUEUES.update(new_queues)
    print(
        f"[opener] adopt d={day} plants={plants} animals={animals} empty={empty}",
        flush=True,
    )
