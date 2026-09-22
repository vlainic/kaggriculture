"""Row-by-row planner → executor I/O (initial day-0 plan, live step returns)."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Any

from milos.wsp.config import NUM_DAYS
from milos.wsp.types import SolveResult
from milos.zoning import NUM_TILES


def fmt_action(action: list | tuple | None) -> str:
    if not action:
        return "PASS"
    return " ".join(str(x) for x in action)


def fmt_market(orders: list[list] | None) -> str:
    if not orders:
        return "—"
    parts = []
    for o in orders:
        if not o:
            continue
        parts.append(fmt_action(o))
    return " | ".join(parts) if parts else "—"


def wsp_chain_rows(result: SolveResult) -> list[dict[str, Any]]:
    """WSP assigned chains before queue conversion."""
    rows: list[dict[str, Any]] = []
    for tile in sorted(result.assigned):
        for slot, (profile_key, start) in enumerate(result.assigned[tile]):
            rows.append(
                {
                    "tile": tile,
                    "slot": slot,
                    "profile_key": profile_key,
                    "start_day": int(start),
                }
            )
    return rows


def planner_queue_rows(tile_queues: dict[int, list]) -> list[dict[str, Any]]:
    """What the executor reads: ``script.TILE_QUEUES`` (QueueItem per slot)."""
    rows: list[dict[str, Any]] = []
    for tile in range(NUM_TILES):
        queue = tile_queues.get(tile) or []
        for qi, item in enumerate(queue):
            rows.append(
                {
                    "tile": tile,
                    "qi": qi,
                    "kind": item.kind,
                    "label": item.label,
                    "profile": item.profile,
                    "start_lag": item.start_lag,
                    "replant_gap": item.replant_gap,
                    "dig_before": item.dig_before,
                }
            )
    return rows


def trace_episode_rows(
    *,
    opponent: str = "pass",
    episode_steps: int = 720,
    quiet: bool = True,
) -> list[dict[str, Any]]:
    """Run a full episode; one row per turn from ``milos.executor.step`` return dict."""
    from kaggle_environments import make

    import milos.executor as executor_mod

    executor_mod._EXECUTOR = None  # noqa: SLF001 — fresh run

    rows: list[dict[str, Any]] = []

    def agent(obs: dict) -> dict:
        out = executor_mod.step(obs)
        rows.append(
            {
                "day": int(obs["day"]),
                "hour": int(obs["hour"]),
                "farmer": list(out.get("farmer") or []),
                "hands": [list(h) for h in out.get("hands") or []],
                "market": [list(o) for o in out.get("market") or []],
            }
        )
        return out

    env = make(
        "kaggriculture",
        configuration={"episodeSteps": episode_steps},
        debug=False,
    )
    if quiet:
        with redirect_stdout(io.StringIO()):
            env.run([agent, opponent])
    else:
        env.run([agent, opponent])
    return rows


def print_planner_executor_trace(
    *,
    tile_queues: dict[int, list],
    episode_rows: list[dict[str, Any]] | None = None,
    wsp_rows: list[dict[str, Any]] | None = None,
    days: range | None = None,
    show_pass: bool = False,
    run_episode: bool = True,
    max_days: int | None = None,
) -> list[dict[str, Any]]:
    """Print INPUT (queues) once, then OUTPUT grouped by day from live executor."""
    print("=== PLANNER → EXECUTOR INPUT (day-0 TILE_QUEUES) ===")
    qrows = planner_queue_rows(tile_queues)
    if not qrows:
        print("(empty)")
    else:
        print("tile | qi | kind   | label      | profile   | start_lag | replant_gap | dig_before")
        for r in qrows:
            print(
                f"t{r['tile'] + 1:1d}  | {r['qi']}  | {r['kind']:6s} | "
                f"{r['label']:10s} | {r['profile']:9s} | "
                f"{r['start_lag']:9d} | {r['replant_gap']:11d} | {r['dig_before']}"
            )

    if wsp_rows:
        print()
        print("=== WSP chains (before QueueItem conversion) ===")
        print("tile | slot | profile_key              | start_day")
        for r in wsp_rows:
            print(
                f"t{r['tile'] + 1:1d}  | {r['slot']}    | {r['profile_key']:24s} | {r['start_day']}"
            )

    if episode_rows is None and run_episode:
        print()
        print("=== Running 720-step episode (milos vs pass) … ===")
        episode_rows = trace_episode_rows(quiet=True)

    if episode_rows is None:
        return episode_rows or []

    day_range = days if days is not None else range(NUM_DAYS)
    if max_days is not None:
        day_range = range(min(max_days, NUM_DAYS))

    print()
    print("=== EXECUTOR OUTPUT (return dict per hour) ===")
    by_day: dict[int, list[dict[str, Any]]] = {}
    for row in episode_rows:
        by_day.setdefault(row["day"], []).append(row)

    for day in day_range:
        day_rows = sorted(by_day.get(day, []), key=lambda r: r["hour"])
        print(f"--- d={day} ---")
        if not day_rows:
            print("  (no steps)")
            continue
        for row in day_rows:
            farmer = fmt_action(row["farmer"])
            if not show_pass and farmer == "PASS" and row["market"] == []:
                continue
            market = fmt_market(row["market"])
            hands_s = ""
            if row["hands"]:
                hands_s = " hands=" + ";".join(fmt_action(h) for h in row["hands"])
            print(f"  h{row['hour']:02d} farmer {farmer}  market {market}{hands_s}")
        print()

    return episode_rows
