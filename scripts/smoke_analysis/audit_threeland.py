"""ThreeLand15 execution audit from smoke stdout."""

from __future__ import annotations

import re
from typing import Any

WASTED_LAND_RE = re.compile(
    r"\[sw\] buy_replan wasted_land d=(\d+) n_active=(\d+)"
)
REJECT_RE = re.compile(
    r"\[(ne|sw)\] reject d=(\d+) zone=(\w+) reason=(\w+)"
)
VALUE_UNKNOWN_RE = re.compile(
    r"\[(ne|sw)\] d=(\d+) zone=(\w+) value_unknown"
)
CASCADE_SKIP_RE = re.compile(r"cascade skip=")
BUY_REPLAN_OVERAGE_RE = re.compile(r"buy_replan skip overage")
NE_FILL_RE = re.compile(r"\[ne\] fill count=(\d+)")


def audit_threeland(lines: list[str], *, season_days: int = 30) -> dict[str, Any]:
    wasted_land = 0
    sw_n_active: list[int] = []
    low_value_rejects: list[dict[str, Any]] = []
    value_unknown = 0
    cascade_skip = 0
    buy_replan_overage = 0
    ne_fill_final: int | None = None
    walk23_block_days = 0
    block_streak = 0
    max_block_streak = 0

    activated_workers: set[str] = set()
    act_re = re.compile(r"\[(?:ne|sw)\] accept d=\d+ zone=(\w+)")

    for line in lines:
        m = WASTED_LAND_RE.search(line)
        if m:
            wasted_land += 1
            sw_n_active.append(int(m.group(2)))
        m = REJECT_RE.search(line)
        if m:
            tag, day_s, worker, reason = m.groups()
            day = int(day_s)
            if reason == "low_value":
                low_value_rejects.append(
                    {"tag": tag, "day": day, "worker": worker, "reason": reason}
                )
                if tag in ("ne", "sw") and day < season_days - 1:
                    block_streak += 1
                    max_block_streak = max(max_block_streak, block_streak)
            else:
                block_streak = 0
        m = VALUE_UNKNOWN_RE.search(line)
        if m:
            value_unknown += 1
        if CASCADE_SKIP_RE.search(line):
            cascade_skip += 1
        if BUY_REPLAN_OVERAGE_RE.search(line):
            buy_replan_overage += 1
        m = NE_FILL_RE.search(line)
        if m:
            ne_fill_final = int(m.group(1))
        m = act_re.search(line)
        if m:
            activated_workers.add(m.group(1))

    latch_suspects: list[dict[str, Any]] = []
    for rej in low_value_rejects:
        w = rej["worker"]
        if w not in activated_workers:
            latch_suspects.append(rej)

    if max_block_streak > 0:
        walk23_block_days = max_block_streak

    return {
        "wasted_land_events": wasted_land,
        "sw_n_active_on_wasted": sw_n_active,
        "low_value_rejects": low_value_rejects,
        "low_value_latch_suspects": latch_suspects,
        "value_unknown_events": value_unknown,
        "walk23_block_max_streak": walk23_block_days,
        "cascade_skip_lines": cascade_skip,
        "buy_replan_skip_overage": buy_replan_overage,
        "ne_fill_final": ne_fill_final,
        "workers_ever_activated": sorted(activated_workers),
    }
