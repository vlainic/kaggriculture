"""Executor turn budget: tile ops + pickups + BUILD."""

from __future__ import annotations

from agent import animal_rollouts, rollouts


def executor_ops_by_day(
    kind: str,
    label: str,
    profile: str,
    start_day: int,
    horizon: int,
    min_day: int = 0,
) -> dict[int, int]:
    """All farmer turns a lifecycle costs per calendar day."""
    if kind == "crop":
        return rollouts.executor_ops_by_day(label, start_day, horizon, profile)
    return animal_rollouts.executor_ops_by_day(
        label, start_day, horizon, profile, min_day=min_day
    )


def peak_load(
    selected: list[dict],
    existing_load: dict[int, int],
    current_day: int,
    horizon: int,
) -> tuple[int, int]:
    """Return (peak_day, peak_ops) including existing_load."""
    day_ops = dict(existing_load)
    for s in selected:
        for d, ops in s.get("ops_by_day", {}).items():
            day_ops[d] = day_ops.get(d, 0) + ops
    peak_day = current_day
    peak_ops = day_ops.get(current_day, 0)
    for d in range(current_day, horizon):
        ops = day_ops.get(d, 0)
        if ops > peak_ops:
            peak_ops = ops
            peak_day = d
    return peak_day, peak_ops
