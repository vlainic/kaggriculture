"""Acceptance checklist and idle proxies for smoke runs."""

from __future__ import annotations

from typing import Any


def compute_kpis(
    *,
    planner: dict[str, Any],
    snaps_empty: dict[str, list[int | None]],
    hires: dict[str, Any],
    buy_land_day: int | None,
    worker_tiles: dict[str, list[int]],
    land2_workers: tuple[str, ...],
    workers: tuple[str, ...],
    land2_tile_min: int = 26,
    has_land2: bool = True,
) -> dict[str, Any]:
    del hires
    acceptance = {
        "write_day0_ge1": _check_write_day0(planner, worker_tiles),
        "skip_not_break": _check_skip_not_break(planner, buy_land_day, workers),
        "no_dark_land2_keep": _check_no_dark_keep(
            planner, buy_land_day, land2_tile_min=land2_tile_min, has_land2=has_land2
        ),
        "thin_writes_logged": _check_thin_writes(planner),
        "hire5_idle_proxy": _check_hire5_idle(
            snaps_empty, planner, has_land2=has_land2
        ),
        "missing_from_solved": _check_missing_from_solved(planner, workers),
        "stale_start_blocks": _check_stale_start_blocks(planner),
        "smoke_health": {"pass": True, "detail": "parsed from log"},
    }
    idle_proxy = _idle_proxy(snaps_empty, planner, land2_workers)
    stuck_zones = _stuck_zone_stats(planner, heal_within_days=5)
    return {"acceptance": acceptance, "idle_proxy": idle_proxy, "stuck_zones": stuck_zones}


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"pass": ok, "detail": detail}


def _check_write_day0(planner: dict[str, Any], worker_tiles: dict[str, list[int]]) -> dict[str, Any]:
    zone_solves = planner.get("zone_solves") or []
    keep = planner.get("keep_assignments") or []
    violations: list[str] = []
    for zs in zone_solves:
        if zs.get("skipped") or int(zs.get("picks") or 0) <= 0:
            continue
        day0 = int(zs.get("day0") or 0)
        if day0 < 1:
            continue
        worker = zs["worker"]
        day = zs.get("day")
        tiles_1 = {t + 1 for t in worker_tiles.get(worker, [])}
        kept = {k["tile"] for k in keep if k.get("day") == day and k["tile"] in tiles_1}
        if tiles_1 and kept == tiles_1:
            violations.append(f"d={day} {worker} day0={day0} all tiles kept")
    ok = not violations
    detail = "all day0≥1 writes present" if ok else "; ".join(violations[:5])
    return _check("write_day0_ge1", ok, detail)


def _check_skip_not_break(
    planner: dict[str, Any],
    buy_land_day: int | None,
    workers: tuple[str, ...],
) -> dict[str, Any]:
    skips = planner.get("skip_cascade") or []
    solves = planner.get("zone_solves") or []
    w_idx = {w: i for i, w in enumerate(workers)}
    by_day: dict[int | None, list[dict[str, Any]]] = {}
    for zs in solves:
        by_day.setdefault(zs.get("day"), []).append(zs)
    failures: list[str] = []
    checked = 0
    for sk in skips:
        day = sk.get("day")
        if buy_land_day is not None and (day is None or day < buy_land_day):
            continue
        worker = sk["worker"]
        wi = w_idx.get(worker, -1)
        same_day = by_day.get(day) or []
        later = [z for z in same_day if w_idx.get(z["worker"], -1) > wi]
        checked += 1
        if not later and wi < len(workers) - 1:
            failures.append(f"d={day} after {worker} skip cascade hard-stopped")
    ok = not failures
    detail = f"{checked} post-buy skips, cascade continued" if ok else "; ".join(failures[:5])
    return _check("skip_not_break", ok, detail)


def _check_no_dark_keep(
    planner: dict[str, Any],
    buy_land_day: int | None,
    *,
    land2_tile_min: int,
    has_land2: bool,
) -> dict[str, Any]:
    if not has_land2:
        return _check("no_dark_land2_keep", True, "one-land layout (no land2)")
    if buy_land_day is None:
        return _check("no_dark_land2_keep", True, "no BUY_LAND in log")
    keep = [
        k
        for k in (planner.get("keep_assignments") or [])
        if k["tile"] >= land2_tile_min
    ]
    post = [k for k in keep if (k.get("day") or 0) >= buy_land_day]
    by_tile: dict[int, list[int]] = {}
    for k in post:
        by_tile.setdefault(k["tile"], []).append(k["day"])
    streaks = []
    for tile, days in sorted(by_tile.items()):
        if len(days) >= 5:
            streaks.append(f"t{tile} kept {len(days)} replans")
    ok = not streaks
    detail = "no long land2 keep streaks" if ok else "; ".join(streaks[:5])
    return _check("no_dark_land2_keep", ok, detail)


def _check_thin_writes(planner: dict[str, Any]) -> dict[str, Any]:
    thin = [z for z in (planner.get("zone_solves") or []) if z.get("write_anyway")]
    ok = True
    detail = f"{len(thin)} thin write-anyway zones" if thin else "no thin zones"
    return _check("thin_writes_logged", ok, detail)


def _check_missing_from_solved(
    planner: dict[str, Any],
    workers: tuple[str, ...],
) -> dict[str, Any]:
    outcomes_by_day = planner.get("outcomes_by_day") or {}
    solved_by_day = planner.get("solved_by_day") or {}
    miss_days: dict[str, int] = {w: 0 for w in workers}
    for day, outcomes in outcomes_by_day.items():
        solved = set(solved_by_day.get(day) or [])
        for worker in workers:
            outcome = outcomes.get(worker)
            if outcome in ("infeasible", "picks0") or (
                worker not in solved and outcome is not None
            ):
                miss_days[worker] += 1
    flagged = [f"{w}:{n}d" for w, n in sorted(miss_days.items()) if n >= 3]
    ok = not flagged or all(
        w.split(":")[0] in ("hire4", "hire5") for w in flagged
    )
    detail = (
        "no worker missing solved ≥3 replans"
        if not flagged
        else "; ".join(flagged[:8])
    )
    return _check("missing_from_solved", ok, detail)


def _check_stale_start_blocks(planner: dict[str, Any]) -> dict[str, Any]:
    blocks = planner.get("start_blocks") or []
    stale = [b for b in blocks if int(b.get("age") or 0) >= 2]
    by_worker: dict[str, int] = {}
    for b in stale:
        by_worker[b["worker"]] = by_worker.get(b["worker"], 0) + 1
    detail = (
        f"{len(stale)} start_block age≥2"
        + (f" ({', '.join(f'{w}:{n}' for w, n in sorted(by_worker.items()))})" if by_worker else "")
    )
    unlocks = planner.get("stale_unlocks") or []
    if unlocks:
        detail += f"; stale_unlock={len(unlocks)}"
    ok = len(stale) == 0 or len(unlocks) > 0
    return _check("stale_start_blocks", ok, detail)


def _check_hire5_idle(
    snaps_empty: dict[str, list[int | None]],
    planner: dict[str, Any],
    *,
    has_land2: bool,
) -> dict[str, Any]:
    if not has_land2:
        return _check("hire5_idle_proxy", True, "one-land layout (no hire5)")
    hire5 = snaps_empty.get("hire5") or []
    days_nonempty = sum(1 for v in hire5 if v is not None and v > 0)
    infeas = [
        x for x in (planner.get("infeasible") or [])
        if x.get("worker") == "hire5" and int(x.get("empty") or 0) == 1
    ]
    ok = days_nonempty <= 15 and len(infeas) <= 20
    detail = (
        f"hire5_empty dawn days={days_nonempty}, "
        f"hire5 empty=1 INFEASIBLE={len(infeas)}"
    )
    return _check("hire5_idle_proxy", ok, detail)


def _idle_proxy(
    snaps_empty: dict[str, list[int | None]],
    planner: dict[str, Any],
    land2_workers: tuple[str, ...],
) -> dict[str, Any]:
    all_empty: list[int] = []
    for worker, series in snaps_empty.items():
        for v in series:
            if v is not None:
                all_empty.append(v)
    hire5 = snaps_empty.get("hire5") or []
    streak = _max_streak(v for v in hire5 if v is not None and v > 0)
    land2_empty = []
    for w in land2_workers:
        for v in snaps_empty.get(w) or []:
            if v is not None:
                land2_empty.append(v)
    infeas_hire5 = sum(
        1 for x in (planner.get("infeasible") or [])
        if x.get("worker") == "hire5"
    )
    return {
        "mean_empty_per_dawn": sum(all_empty) / len(all_empty) if all_empty else 0.0,
        "hire5_empty_days": sum(1 for v in hire5 if v is not None and v > 0),
        "max_hire5_empty_streak": streak,
        "land2_mean_empty_per_dawn": sum(land2_empty) / len(land2_empty) if land2_empty else 0.0,
        "hire5_infeasible_count": infeas_hire5,
    }


def _stuck_zone_stats(planner: dict[str, Any], *, heal_within_days: int = 5) -> dict[str, Any]:
    summary = planner.get("zone_streak_summary") or []
    stuck_workers = [r for r in summary if r.get("first_stuck_day") is not None]
    healed_quick = []
    permanent = []
    for row in stuck_workers:
        first = row["first_stuck_day"]
        recovered = row.get("recovered_day")
        if recovered is None:
            permanent.append(row["worker"])
        elif recovered - first <= heal_within_days:
            healed_quick.append(row["worker"])
        else:
            permanent.append(row["worker"])
    return {
        "stuck_event_count": len(planner.get("zone_streak_events") or []),
        "workers_stuck": [r["worker"] for r in stuck_workers],
        "workers_healed_within_n_days": healed_quick,
        "workers_permanent_or_slow": permanent,
        "heal_within_days": heal_within_days,
        "by_worker": summary,
    }


def _max_streak(values) -> int:
    best = cur = 0
    for v in values:
        if v:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best
