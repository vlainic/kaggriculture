"""Parse farmer/hand [exec] lines into worker action grids."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import numpy as np

EXEC_RE = re.compile(r"\[exec\] d=(\d+) h=(\d+)")

ACTION_ORDER: tuple[str, ...] = (
    "PICKUP",
    "MOVE",
    "PLANT",
    "WATER",
    "FERTILIZE",
    "BUILD",
    "FEED",
    "CARE",
    "COLLECT",
    "HARVEST",
    "DIG",
    "PLACE",
    "DROP",
    "PASS",
    "OTHER",
)

ACTION_COLORS: dict[str, str] = {
    "PICKUP": "#6a1b9a",
    "MOVE": "#78909c",
    "PLANT": "#2e7d32",
    "WATER": "#0288d1",
    "FERTILIZE": "#00897b",
    "BUILD": "#5d4037",
    "FEED": "#f9a825",
    "CARE": "#ff8f00",
    "COLLECT": "#7b1fa2",
    "HARVEST": "#c62828",
    "DIG": "#795548",
    "PLACE": "#1565c0",
    "DROP": "#455a64",
    "PASS": "#cfd8dc",
    "OTHER": "#212121",
}

_MOVE_VERBS = frozenset({"NORTH", "SOUTH", "EAST", "WEST"})
_BUILD_VERBS = frozenset({"BUILD_COOP", "BUILD_PASTURE"})
HOURS_PER_DAY = 24


def classify_action(verb: str) -> str:
    v = verb.upper()
    if v.startswith("PICKUP"):
        return "PICKUP"
    if v in _MOVE_VERBS:
        return "MOVE"
    if v in _BUILD_VERBS:
        return "BUILD"
    if v == "COLLECT_FERTILIZER":
        return "COLLECT"
    if v in ACTION_ORDER:
        return v
    return "OTHER"


def _worker_for_hand(hand_idx: int, hand_workers: tuple[str, ...]) -> str:
    if 0 <= hand_idx < len(hand_workers):
        return hand_workers[hand_idx]
    return hand_workers[-1] if hand_workers else f"hand{hand_idx}"


def _parse_actor(line: str, hand_workers: tuple[str, ...]) -> tuple[str, str] | None:
    if " farmer " in line:
        return "farmer", line.split(" farmer ", 1)[1].strip()
    hm = re.search(r" hand(\d+)(?:=\w+)? ", line)
    if hm:
        hand_idx = int(hm.group(1))
        rest = line[hm.end() :].strip()
        return _worker_for_hand(hand_idx, hand_workers), rest
    return None


def parse_worker_actions(
    lines: list[str],
    *,
    season_days: int = 30,
    hand_workers: tuple[str, ...] = (),
    workers: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build flat grid: rows = worker × action_type, cols = day × hour.

    One exec line maps to one (worker, day, hour) cell at the action-type row.
    Duplicate keys last-write-wins. Unset cells remain NaN (idle).
    """
    worker_list = list(workers)
    worker_idx = {w: i for i, w in enumerate(worker_list)}
    n_actions = len(ACTION_ORDER)
    action_idx = {a: i for i, a in enumerate(ACTION_ORDER)}

    grid = np.full(
        (len(worker_list) * n_actions, season_days * HOURS_PER_DAY),
        np.nan,
        dtype=float,
    )
    events: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    for line in lines:
        if "[exec]" not in line or " market " in line:
            continue
        m = EXEC_RE.search(line)
        if not m:
            continue
        day, hour = int(m.group(1)), int(m.group(2))
        if not (0 <= day < season_days and 0 <= hour < HOURS_PER_DAY):
            continue

        parsed = _parse_actor(line, hand_workers)
        if not parsed:
            continue
        worker, rest = parsed
        if worker not in worker_idx:
            continue
        parts = rest.split()
        if not parts:
            continue

        verb = parts[0]
        bucket = classify_action(verb)
        wi = worker_idx[worker]
        ai = action_idx[bucket]
        row = wi * n_actions + ai
        col = day * HOURS_PER_DAY + hour
        grid[row, col] = ai + 1  # 1-based for imshow; idle stays NaN

        counts[bucket] += 1
        note = ""
        nm = re.search(r" owned=\d+(?: (.+))?$", line)
        if nm and nm.group(1):
            note = nm.group(1).strip()
        events.append(
            {
                "worker": worker,
                "day": day,
                "hour": hour,
                "verb": verb,
                "bucket": bucket,
                "note": note,
                "raw_line": line.strip(),
            }
        )

    by_worker_day = _aggregate_capacity(events, worker_list, season_days)

    return {
        "action_order": list(ACTION_ORDER),
        "action_colors": dict(ACTION_COLORS),
        "hours_per_day": HOURS_PER_DAY,
        "grid": grid,
        "events": events,
        "counts_by_bucket": dict(counts),
        "by_worker_by_day": by_worker_day,
    }


def _aggregate_capacity(
    events: list[dict[str, Any]],
    workers: list[str],
    season_days: int,
) -> dict[str, list[dict[str, int]]]:
    """Daily tile ops, MOVE, PASS, reactive feed paths (one bar segment per hour)."""
    empty = {"tile_ops": 0, "move": 0, "pass": 0, "pickup": 0, "reactive": 0}
    out: dict[str, list[dict[str, int]]] = {
        w: [dict(empty) for _ in range(season_days)] for w in workers
    }
    reactive_markers = ("feed->shed", "feed-skip", "feed-wait")
    for ev in events:
        worker = ev["worker"]
        day = ev["day"]
        if worker not in out or not (0 <= day < season_days):
            continue
        row = out[worker][day]
        note = ev.get("note") or ""
        bucket = ev["bucket"]
        if any(m in note for m in reactive_markers):
            row["reactive"] += 1
            continue
        if bucket == "MOVE":
            row["move"] += 1
        elif bucket == "PASS":
            row["pass"] += 1
        elif bucket == "PICKUP":
            row["pickup"] += 1
            row["tile_ops"] += 1
        else:
            row["tile_ops"] += 1
    return out
