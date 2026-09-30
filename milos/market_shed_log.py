"""Shed composition / drop diagnostics for smoke logs."""

from __future__ import annotations

from milos import sell_dp


def log_shed_composition(private: dict, day: int, hour: int) -> None:
    shed = private.get("shed") or {}
    total = sum(int(v) for v in shed.values())
    parts = " ".join(
        f"{k}={int(v)}"
        for k, v in sorted(shed.items())
        if int(v) > 0
    )
    print(f"[shed] d={day} h={hour} total={total} {parts}", flush=True)


def log_shed_drop_estimate(private: dict, day: int) -> None:
    cap = sell_dp.shed_cap()
    shed = private.get("shed") or {}
    total = sum(int(v) for v in shed.values())
    room = max(0, cap - total)
    hand_inv = 0
    for inv in private.get("inventories") or []:
        if isinstance(inv, dict):
            hand_inv += sum(int(v) for v in inv.values())
    est = max(0, hand_inv - room)
    print(
        f"[shed_drop] d={day} hand_inv={hand_inv} room={room} est_dropped={est}",
        flush=True,
    )
