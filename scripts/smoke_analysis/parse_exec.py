"""Parse [exec] lines — passes, hires, BUY_LAND."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

PASS_ACT_RE = re.compile(
    r"\[exec\] d=(\d+) h=(\d+) "
    r"(?:farmer|hand\d+(?:=(?P<hworker>\w+))?)\s+(?P<act>\S+)"
)
EXEC_RE = re.compile(r"\[exec\] d=(\d+) h=(\d+)")
REWARD_RE = re.compile(r"Player 0: reward=([\d.]+)")
START_BLOCK_RE = re.compile(
    r"\[exec\] start_block t=(\d+) worker=(\w+) d=(\d+) age=(\d+) "
    r"item=(\w+) miss=(seeds|wheat|animal)"
)


def parse_passes(lines: list[str], *, season_days: int = 30) -> dict[str, Any]:
    counts: dict[tuple[int, str], int] = defaultdict(int)
    for line in lines:
        m = PASS_ACT_RE.search(line)
        if not m or m.group("act") != "PASS":
            continue
        day = int(m.group(1))
        hworker = m.group("hworker")
        if hworker:
            worker_key = hworker
        elif " farmer " in line:
            worker_key = "farmer"
        else:
            hm = re.search(r" hand(\d+)", line)
            worker_key = f"hand{hm.group(1)}" if hm else "farmer"
        counts[(day, worker_key)] += 1
    by_worker: dict[str, list[int]] = defaultdict(lambda: [0] * season_days)
    for (day, worker), n in counts.items():
        if 0 <= day < season_days:
            by_worker[worker][day] = n
    total = sum(counts.values())
    return {"by_worker": dict(by_worker), "total": total}


def parse_hires(lines: list[str], *, season_days: int = 30) -> dict[str, Any]:
    by_day = [0] * season_days
    events: list[dict[str, int]] = []
    for line in lines:
        if " market " not in line or "HIRE" not in line:
            continue
        m = EXEC_RE.search(line)
        if not m:
            continue
        day, hour = int(m.group(1)), int(m.group(2))
        n = line.count(" HIRE") + (1 if line.rstrip().endswith("HIRE") else 0)
        # Count standalone HIRE tokens in market segment.
        market_part = line.split(" market ", 1)[1]
        n = sum(1 for tok in market_part.split() if tok == "HIRE")
        if n <= 0:
            continue
        if 0 <= day < season_days:
            by_day[day] += n
        events.append({"day": day, "hour": hour, "count": n})
    return {"by_day": by_day, "events": events, "total": sum(by_day)}


def parse_buy_land_day(lines: list[str]) -> int | None:
    for line in lines:
        if " market " not in line or "BUY_LAND" not in line:
            continue
        m = EXEC_RE.search(line)
        if m:
            return int(m.group(1))
    for line in lines:
        m = re.search(r"BUY_LAND_DAY=(\d+)", line)
        if m:
            return int(m.group(1))
    return None


def parse_final_reward(lines: list[str]) -> float | None:
    for line in reversed(lines):
        m = REWARD_RE.search(line)
        if m:
            return float(m.group(1))
    return None


def smoke_passed(lines: list[str]) -> bool:
    return any("Smoke test passed." in line for line in lines)


def parse_start_blocks(lines: list[str]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for line in lines:
        m = START_BLOCK_RE.search(line)
        if m:
            blocks.append(
                {
                    "tile": int(m.group(1)),
                    "worker": m.group(2),
                    "day": int(m.group(3)),
                    "age": int(m.group(4)),
                    "item": m.group(5),
                    "miss": m.group(6),
                }
            )
    return blocks
