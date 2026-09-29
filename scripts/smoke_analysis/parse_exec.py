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


HANDS_H0_RE = re.compile(
    r"\[hands\] d=(\d+) h0 (\w+) .*?qtiles=(\d+).*?animal=(\d+) crop=(\d+) est_ops=([\d.]+)"
)
HANDS_EOD_RE = re.compile(
    r"\[hands\] d=(\d+) (\w+) eod (?:planned|tiles_dawn)=(\d+) "
    r"executed=(\d+)(?: gap=-?\d+)? laps=(\d+)"
)
EXEC_HAND_BIND_RE = re.compile(r"\[exec\] d=(\d+) h=\d+ hand\d+=(\w+)")


def parse_worker_first_active_day(
    lines: list[str],
    workers: list[str] | tuple[str, ...],
    *,
    season_days: int = 30,
    harvest_by_worker_by_day: dict[str, list[float]] | None = None,
) -> dict[str, int]:
    """First day a zone is materially active (tiles, ops, harvest, or execution)."""
    first: dict[str, int | None] = {w: None for w in workers}
    if "farmer" in first:
        first["farmer"] = 0

    def _mark(day: int, worker: str) -> None:
        if worker not in first or not (0 <= day < season_days):
            return
        if first[worker] is None or day < first[worker]:
            first[worker] = day

    for line in lines:
        m = HANDS_H0_RE.search(line)
        if m:
            day, worker = int(m.group(1)), m.group(2)
            qtiles = int(m.group(3))
            est = float(m.group(6))
            if qtiles > 0 or est > 0:
                _mark(day, worker)
            continue
        m = HANDS_EOD_RE.search(line)
        if m:
            day, worker = int(m.group(1)), m.group(2)
            if int(m.group(4)) > 0:
                _mark(day, worker)

    if harvest_by_worker_by_day:
        for worker, series in harvest_by_worker_by_day.items():
            for day, val in enumerate(series[:season_days]):
                if val and float(val) > 0:
                    _mark(day, worker)

    out: dict[str, int] = {}
    for w in workers:
        if first[w] is not None:
            out[w] = first[w]
        else:
            out[w] = season_days
    return out


THEO_TILE_RE = re.compile(r"\[theo\] d=(\d+) (\w+) (.+)$")
THEO_TILE_PART_RE = re.compile(r"t(\d+)=([^ ]+)")
THEO_EXTRA_RE = re.compile(r"\[theo_extra\] d=(\d+) (\w+) (.+)$")


def parse_hands_dawn(lines: list[str], *, season_days: int = 30) -> dict[str, Any]:
    """Per-worker per-day dawn est_ops + per-tile theo verb lists from [theo] lines."""
    est_ops: dict[str, list[float | None]] = {}
    animal: dict[str, list[int | None]] = {}
    crop: dict[str, list[int | None]] = {}
    # worker -> day -> {tile_num: [verbs]}
    theo_by_tile: dict[str, list[dict[int, list[str]] | None]] = {}
    theo_extra: dict[str, list[list[str] | None]] = {}
    for line in lines:
        m = HANDS_H0_RE.search(line)
        if m:
            day = int(m.group(1))
            worker = m.group(2)
            if not (0 <= day < season_days):
                continue
            est_ops.setdefault(worker, [None] * season_days)
            animal.setdefault(worker, [None] * season_days)
            crop.setdefault(worker, [None] * season_days)
            est_ops[worker][day] = float(m.group(6))
            animal[worker][day] = int(m.group(4))
            crop[worker][day] = int(m.group(5))
            continue
        ex = THEO_EXTRA_RE.search(line)
        if ex:
            day = int(ex.group(1))
            worker = ex.group(2)
            if not (0 <= day < season_days):
                continue
            theo_extra.setdefault(worker, [None] * season_days)
            rest = ex.group(3).strip()
            if rest == "-":
                theo_extra[worker][day] = []
            else:
                theo_extra[worker][day] = [v for v in rest.split(",") if v]
            continue
        tm = THEO_TILE_RE.search(line)
        if not tm:
            continue
        day = int(tm.group(1))
        worker = tm.group(2)
        if not (0 <= day < season_days):
            continue
        theo_by_tile.setdefault(worker, [None] * season_days)
        by_t: dict[int, list[str]] = {}
        rest = tm.group(3).strip()
        if rest != "-":
            for part in THEO_TILE_PART_RE.finditer(rest):
                tnum = int(part.group(1))
                verbs = [v for v in part.group(2).split(",") if v]
                by_t[tnum] = verbs
        theo_by_tile[worker][day] = by_t
    return {
        "est_ops_by_worker_by_day": est_ops,
        "theo_by_tile_by_worker_by_day": theo_by_tile,
        "theo_extra_by_worker_by_day": theo_extra,
        "animal_by_worker_by_day": animal,
        "crop_by_worker_by_day": crop,
    }


def parse_hands_eod(lines: list[str], *, season_days: int = 30) -> dict[str, Any]:
    """EOD executed + laps (tiles_dawn is diagnostic only, not comparable to executed)."""
    executed: dict[str, list[int]] = defaultdict(lambda: [0] * season_days)
    laps: dict[str, list[int]] = defaultdict(lambda: [0] * season_days)
    tiles_dawn: dict[str, list[int]] = defaultdict(lambda: [0] * season_days)
    for line in lines:
        m = HANDS_EOD_RE.search(line)
        if not m:
            continue
        day = int(m.group(1))
        worker = m.group(2)
        if not (0 <= day < season_days):
            continue
        tiles_dawn[worker][day] = int(m.group(3))
        executed[worker][day] = int(m.group(4))
        laps[worker][day] = int(m.group(5))
    return {
        "executed_by_worker_by_day": dict(executed),
        "laps_by_worker_by_day": dict(laps),
        "tiles_dawn_by_worker_by_day": dict(tiles_dawn),
    }


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
