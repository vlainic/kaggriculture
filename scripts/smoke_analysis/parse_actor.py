"""Parse worker identity from [exec] farmer/hand lines (spawn-bound hire labels)."""

from __future__ import annotations

import re

HAND_ACTOR_RE = re.compile(
    r" hand(\d+)(?:=(?P<hworker>\w+))? "
)


def worker_for_hand(hand_idx: int, hand_workers: tuple[str, ...]) -> str:
    if 0 <= hand_idx < len(hand_workers):
        return hand_workers[hand_idx]
    return hand_workers[-1] if hand_workers else f"hand{hand_idx}"


def parse_exec_actor(
    line: str,
    hand_workers: tuple[str, ...] = (),
) -> tuple[str, str] | None:
    """Return (worker_key, action_rest) or None if not a farmer/hand exec line."""
    if " farmer " in line:
        return "farmer", line.split(" farmer ", 1)[1].strip()
    hm = HAND_ACTOR_RE.search(line)
    if not hm:
        return None
    hand_idx = int(hm.group(1))
    hworker = hm.group("hworker")
    worker = hworker if hworker else worker_for_hand(hand_idx, hand_workers)
    rest = line[hm.end() :].strip()
    return worker, rest
