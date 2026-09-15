---
name: TwoLand re-add on clean zonewise_wsp base
overview: "Rebuild TwoLand as zonewise_wsp + exactly two deltas (hire5 buy-probe, NE cascade), plus the supporting glue that broke every prior attempt: LOCKED-tile carve-out on buy-morning, market supply that guarantees pickup, hire-count gated on real work, and day-1 diagnostics. No staleness hack, no dynamic walk-to-shed, no per-zone executor quota."
todos:
  - id: zoning-consts
    content: "zoning.py: CURRENT=TWO; re-add LAND1_TILE_COUNT / LAND1_WORKERS / LAND2_WORKERS; add LAND2_BUY_COST=1000"
    status: pending
  - id: types-buyland
    content: "types.py: add buy_land: bool = False to SolveResult"
    status: pending
  - id: dispatch
    content: "solvers/__init__.py: re-add twoland_wsp backend; CURRENT_SOLVER=twoland_wsp; pass land_owned/buy_morning only for twoland; _wsp_solver includes twoland"
    status: pending
  - id: solver-copy-delta
    content: "twoland_wsp.py: copy zonewise_wsp verbatim, then apply 5 deltas (imports, _is_prestart_solve land1, probe helpers, solve() ne_active+worker_list+probe, return buy_land). apply_replan unchanged."
    status: pending
  - id: planner-glue
    content: "planner.py: BUY_LAND_DAY global; land_owned/buy_morning in replan; NE force-inject on buy-morning; probe->BUY_LAND_DAY=day+1; abort-if-NE-unwritten; _build_from_solver land1-only; get_tile_queues allow TWO; hire count via _zone_has_work"
    status: pending
  - id: market-glue
    content: "market.py: re-add _land2_owned + BUY_LAND order (gated); reserve LAND2_BUY_COST on buy-morning; UNCAP dawn wheat buy (drop MAX_ORDERS-len slot cap); _tile_empty(day) LOCKED carve-out"
    status: pending
  - id: executor-glue
    content: "executor.py: _dawn_empty(me,idx,day) LOCKED carve-out in _on_new_day; _log_hand_status at h0"
    status: pending
  - id: smoke-verify
    content: "smoke, read logs: probe fires, buy-morning plants NE h1, no feed-wait/pre-wait-shed streaks, hire count matches working zones. No submit."
    status: pending
isProject: false
---

# TwoLand re-add — zonewise_wsp + 2 deltas + the glue that kept breaking

## The one thing that broke every prior attempt

Engine order per hour is **player actions → market orders → town → refresh**. So on buy-morning `BUY_LAND` (a market order at h0) resolves *after* the farmer/hands have already acted that hour, and *after* `replan()` (which runs at h0 before actions). Consequently **at replan time and at h0, the NE tiles still read `"LOCKED"`, not `None`.**

Three places check `tile is None` and must accept "LOCKED NE on buy-morning" as empty, or NE never starts:
1. `planner.replan` eligibility → NE never enters `replan_tiles` → never planned.
2. `executor._on_new_day` `_empty_at_dawn` → `tile_ops._start_lifecycle` refuses PLANT/PLACE all day.
3. `market._tile_empty` → no `BUY_SEED`/`BUY_ANIMAL` queued for NE.

Every "hire3/4/8/9 stuck" symptom traced back to one of these plus two independent bugs (wheat supply, and the self-inflicted walk-to-shed regression). This plan fixes the root three, fixes supply, and does **not** re-introduce the walk-to-shed or staleness hacks.

## Requirement → mechanism map

| # | Requirement | Mechanism | Risk |
| --- | --- | --- | --- |
| 1 | trigger on 6th-zone affordability | `_probe_buy_land` throwaway hire5 solve with `opening[0]-=1000`; buy iff feasible AND day0≥2 | low |
| 2 | cascade adds NE zones | `worker_list = LAND1_WORKERS + (LAND2_WORKERS if ne_active else ())`, break-on-None | low |
| 3 | market guarantees pickup supply | uncap dawn wheat buy (drop slot cap); feed need already counts same-day placements | low |
| 4 | replan never breaks a committed plan, updates only if feasible | keep `apply_replan` (skip-empty-if-queue) + cascade-break leaves tail untouched; abort buy if NE unwritten | low |
| 5 | don't hire a zone with no task | `NUM_ACTIVE_HIRES` = contiguous count of hand-zones with real work (`_zone_has_work`) | med |
| 6 | logs for why a hand idles (hire4 all-PASS) | `_log_hand_status` at h0: pos, shed-adjacent, #queued tiles, #empty | — |

Core-to-working: 1,2,3, and the LOCKED carve-out. Robustness: 4,5,6.

---

## 1. `agent/zoning.py`

Flip layout and re-add the constants the strip removed. `TWO` layout block is already present.

```python
CURRENT: Layout = TWO          # was FIVE after strip

LAND2_BUY_COST = 1000          # NE (first extra quadrant) price

LAND1_TILE_COUNT = len(FIVE.coords)                       # 25
LAND1_WORKERS: tuple[str, ...] = tuple(z.name for z in FIVE.zones)
LAND2_WORKERS: tuple[str, ...] = tuple(
    z.name for z in TWO.zones if z.name not in LAND1_WORKERS
)
```

Keep `bind(CURRENT)` at the bottom — now binds the 50-tile / 9-hand TWO layout.

---

## 2. `agent/solvers/types.py`

```python
@dataclass(frozen=True)
class SolveResult:
    assigned: dict[int, list]
    complete: bool
    solved_workers: tuple[str, ...]
    buy_land: bool = False        # add; only twoland sets it
```

---

## 3. `agent/solvers/__init__.py`

```python
from agent.solvers import monolithic, twoland_wsp, zonewise, zonewise_wsp   # add twoland_wsp

CURRENT_SOLVER = "twoland_wsp"   # was zonewise_wsp

_BACKENDS = {
    "monolithic": monolithic,
    "zonewise": zonewise,
    "zonewise_wsp": zonewise_wsp,
    "twoland_wsp": twoland_wsp,
}

def _wsp_solver() -> bool:
    return CURRENT_SOLVER in ("zonewise_wsp", "twoland_wsp")
```

In `solve()`, add the two params and forward only for twoland (zonewise_wsp doesn't accept them):

```python
def solve(chains, *, horizon, empty_tiles, empty_counts, locked_by_worker,
          starting_money, max_time=20.0, charge_hire_daily=True, track_shed=True,
          w_open0=0, f_open0=0, cascade_reserve=False, min_balance=0,
          price_of=None, land_owned=False, buy_morning=False):
    kwargs = { ... unchanged ... }
    if price_of is not None:
        kwargs["price_of"] = price_of
    if CURRENT_SOLVER == "twoland_wsp":
        kwargs["land_owned"] = land_owned
        kwargs["buy_morning"] = buy_morning
    return _backend().solve(chains, **kwargs)
```

`apply_replan()` stays exactly as the stripped version (single `_backend()` call, no `write_all_solved`).

---

## 4. `agent/solvers/twoland_wsp.py`

**Copy `zonewise_wsp.py` verbatim**, then apply these five deltas. `apply_replan` is copied unchanged — it already writes only the solved contiguous prefix and skips an empty chain when a queue exists (that IS requirement 4).

### 4a. Imports — add to the `from agent.zoning import (...)` block

```python
from agent.zoning import (
    HAND_DAILY_COST, HAND_WORKERS, NET_TILE_OPS, NUM_TILES,
    WORKER_TILES, WORKERS,
    LAND1_TILE_COUNT, LAND1_WORKERS, LAND2_WORKERS, LAND2_BUY_COST,   # add
)

NEW_ZONE_MIN_DAY0_STARTS = 2
LAND2_PROBE_WORKER = LAND2_WORKERS[0]   # "hire5"
```

### 4b. `_is_prestart_solve` — day-0 is land1-only (25 tiles), NE locked

```python
def _is_prestart_solve(horizon, empty_tiles, empty_counts) -> bool:
    if horizon != NUM_DAYS or len(empty_tiles) != LAND1_TILE_COUNT:
        return False
    if any(empty_counts.get(w, 0) != len(WORKER_TILES[w]) for w in LAND1_WORKERS):
        return False
    return all(empty_counts.get(w, 0) == 0 for w in LAND2_WORKERS)
```

### 4c. New helpers (place next to `_solve_zone`)

```python
def _count_day0_starts(picked: list) -> int:
    return sum(1 for p in picked if p["pattern"]["start_day"] == 0)


def _empty_locked_dict(horizon: int) -> dict:
    z = [0] * horizon
    return {
        "daily_tile_ops": list(z), "daily_feed": list(z), "daily_fert": list(z),
        "daily_collect": list(z), "daily_wheat": list(z),
        "daily_animal_active": list(z), "cash_by_day": list(z), "spend_by_day": list(z),
    }


def _probe_buy_land(patterns, horizon, opening, price_of, *,
                    max_time, charge_hire_daily) -> bool:
    """Throwaway hire5 solve to decide if NE is worth buying yet.

    Does NOT write assigned/solved_workers/locked_harvest — signal only.
    hire5 has never run pre-buy, so its locked state is genuinely all-zero.
    """
    probe_opening = list(opening)
    probe_opening[0] -= LAND2_BUY_COST
    res = _solve_zone(
        LAND2_PROBE_WORKER, patterns, horizon=horizon,
        empty_tiles=list(WORKER_TILES[LAND2_PROBE_WORKER]),
        locked=_empty_locked_dict(horizon), locked_counts={},
        opening_balances=probe_opening, w_open=0, f_open=0,
        max_time=max_time, charge_hire_daily=charge_hire_daily,
        track_shed=False, min_balance=0, price_of=price_of,
    )
    if res is None:
        print("[planner] twoland probe hire5 INFEASIBLE defer", flush=True)
        return False
    day0 = _count_day0_starts(res["picked"])
    ok = day0 >= NEW_ZONE_MIN_DAY0_STARTS
    print(
        f"[planner] twoland probe hire5 day0={day0} "
        f"{'buy_land tomorrow' if ok else 'defer'}",
        flush=True,
    )
    return ok
```

### 4d. `solve()` — the only structural change

Signature gains `land_owned=False, buy_morning=False`. Body differs from zonewise only in the marked lines:

```python
def solve(chains, *, horizon, empty_tiles, empty_counts, locked_by_worker,
          starting_money, max_time=20.0, charge_hire_daily=True, track_shed=True,
          w_open0=0, f_open0=0, cascade_reserve=False, min_balance=0,
          price_of=None, land_owned=False, buy_morning=False):        # <-- +2 params
    del chains, cascade_reserve
    if _is_prestart_solve(horizon, empty_tiles, empty_counts):
        assigned, complete, solved_workers = _load_prestart()
        print(f"[planner] twoland prestart tiles={len(assigned)} complete={complete}",
              flush=True)
        return SolveResult(assigned, complete, solved_workers)

    if price_of is None:
        base = _i0_base_prices()
        price_of = lambda product, _b=base: _b[product]

    ne_active = land_owned or buy_morning                              # <-- new
    worker_list = LAND1_WORKERS + (LAND2_WORKERS if ne_active else ())  # <-- new

    empty_set = set(empty_tiles)
    per_zone_time = max_time / max(1, len(worker_list))                # <-- worker_list
    opening = [starting_money] * horizon
    if buy_morning and not land_owned:                                 # <-- new
        opening[0] -= LAND2_BUY_COST

    patterns = build_patterns(horizon, price_of)

    buy_land = False                                                   # <-- new block
    if not land_owned and not buy_morning:
        buy_land = _probe_buy_land(
            patterns, horizon, opening, price_of,
            max_time=max(1.5, max_time * 0.15),
            charge_hire_daily=charge_hire_daily,
        )

    assigned: dict[int, list] = {}
    solved_workers: list[str] = []
    locked_harvest: dict[str, int] = {}

    for worker in worker_list:                                         # <-- worker_list
        n_empty = empty_counts.get(worker, 0)
        locked = locked_by_worker[worker]
        if n_empty == 0:
            opening = _locked_conservative_handoff(
                opening, locked, horizon, worker, charge_hire_daily=charge_hire_daily)
            solved_workers.append(worker)
            continue

        zone_empty = [idx for idx in WORKER_TILES[worker] if idx in empty_set]
        if worker == WORKERS[0] and track_shed:
            w_open, f_open = w_open0, f_open0
        else:
            w_open, f_open = 0, 0

        res = _solve_zone(
            worker, patterns, horizon=horizon, empty_tiles=zone_empty,
            locked=locked, locked_counts=locked_harvest, opening_balances=opening,
            w_open=w_open, f_open=f_open, max_time=per_zone_time,
            charge_hire_daily=charge_hire_daily, track_shed=track_shed,
            min_balance=min_balance, price_of=price_of,
        )
        if res is None:
            break                                                     # same as zonewise

        assigned.update(_decode_wsp_assignment(worker, empty_set, res["picked"]))
        for pick in res["picked"]:
            for prod, units in pick["pattern"]["harvest_units"].items():
                locked_harvest[prod] = locked_harvest.get(prod, 0) + units
        opening = res["conservative"]
        solved_workers.append(worker)

    return SolveResult(
        assigned,
        len(solved_workers) == len(worker_list),                      # <-- worker_list
        tuple(solved_workers),
        buy_land=buy_land,                                            # <-- new
    )
```

`per_zone_time` now divides by `len(worker_list)` (5 pre-buy, 10 post) — pre-buy each land1 zone gets *more* time than today (÷5 vs ÷5, unchanged; post-buy ÷10). Fine.

---

## 5. `agent/planner.py`

### 5a. Imports + global

```python
from agent.zoning import (
    NUM_TILES, TILE_COORDS, WORKER_TILES, WORKERS, worker_for_tile,
    LAND1_TILE_COUNT, LAND1_WORKERS, LAND2_WORKERS,          # add
)

BUY_LAND_DAY: int | None = None
_NE_TILES = tuple(range(LAND1_TILE_COUNT, NUM_TILES))


def _land2_owned(me: dict) -> bool:
    return "NE" in me.get("unlocked_quadrants", [])


def _zone_has_work(me, worker, tile_queues, assigned) -> bool:
    for idx in WORKER_TILES[worker]:
        tile = _tile_at(me, idx)
        if isinstance(tile, dict) and tile.get("kind") in ("PLANT", "COOP", "PASTURE"):
            return True                       # live crop/animal to tend (must staff)
        if assigned.get(idx):
            return True                       # fresh plan this replan
        if tile_queues.get(idx):
            return True                       # committed queue
    return False
```

### 5b. `replan()` — insert land_owned/buy_morning, NE injection, probe wiring

Right after `me = obs["farms"][player]`:

```python
    global BUY_LAND_DAY
    land_owned = _land2_owned(me)
    buy_morning = (
        BUY_LAND_DAY is not None and day == BUY_LAND_DAY and not land_owned
    )
```

The eligibility loop must force NE tiles in on buy-morning (they read LOCKED). Change the per-tile loop:

```python
    for idx in range(NUM_TILES):
        tile = _tile_at(me, idx)
        worker = worker_for_tile(idx)
        st = st_map.get(idx, {})
        force_ne = buy_morning and idx in _NE_TILES and tile == "LOCKED"
        if force_ne or _replan_eligible(idx, tile, st, tile_queues):
            replan_tiles.append(idx)
            empty_counts[worker] += 1
        else:
            seg = _stamp_tile_commitment(...)   # unchanged
            ...
```

Also the early-bail `if not any(_replan_eligible(...))` near the top must not skip buy-morning:

```python
    if not buy_morning and not any(
        _replan_eligible(i, _tile_at(me, i), st_map.get(i, {}), tile_queues)
        for i in range(NUM_TILES)
    ):
        return
```

Pass the flags into `solvers.solve(...)`:

```python
    result = solvers.solve(
        chains, horizon=horizon, empty_tiles=replan_tiles, empty_counts=empty_counts,
        locked_by_worker=locked_by_worker, starting_money=int(me["money"]),
        max_time=15.0, w_open0=w_open0, f_open0=f_open0,
        min_balance=replan_min_balance, track_shed=not _wsp_solver(),
        price_of=price_of, land_owned=land_owned, buy_morning=buy_morning,   # add
    )
```

### 5c. Hire count from real work (requirement 5) — replace the `hires` block

```python
    ordered_hands = [w for w in WORKERS if w in zoning.HAND_WORKERS]
    active = 0
    for w in ordered_hands:
        if w in result.solved_workers and _zone_has_work(
            me, w, tile_queues, result.assigned
        ):
            active += 1
        else:
            break                              # contiguous — routing is positional
    NUM_ACTIVE_HIRES = max(4, active)          # floor keeps land1 committed crops fed
```

Note the ordering: this runs *after* `apply_replan` so `tile_queues` reflects NE writes. Move the existing `apply_replan(...)` call to before this block if it isn't already, then compute `active`.

### 5d. Probe decision + abort-if-NE-unwritten (requirement 4 safety)

After `apply_replan(...)`:

```python
    if buy_morning:
        ne_written = any(tile_queues.get(idx) for idx in _NE_TILES)
        if not ne_written:
            print(f"[planner] d={day} buy-morning NE unwritten -> abort buy", flush=True)
            BUY_LAND_DAY = None                # re-probe later; market won't BUY_LAND
    elif not land_owned and BUY_LAND_DAY is None and result.buy_land:
        BUY_LAND_DAY = day + 1
        print(f"[planner] d={day} probe OK -> BUY_LAND_DAY={BUY_LAND_DAY}", flush=True)
```

### 5e. `_build_from_solver()` — day-0 is land1-only for twoland

```python
def _build_from_solver() -> dict[int, list]:
    if _wsp_solver():                          # covers twoland + zonewise
        empty_tiles = list(range(LAND1_TILE_COUNT))
        empty_counts = {
            w: (len(WORKER_TILES[w]) if w in LAND1_WORKERS else 0) for w in WORKERS
        }
        chains, cascade_reserve = [], False
    else:
        empty_tiles = list(range(NUM_TILES))
        empty_counts = {w: len(WORKER_TILES[w]) for w in WORKERS}
        ... (dp_catalog branch unchanged) ...
    locked_by_worker = {w: _empty_locked(NUM_DAYS) for w in WORKERS}
    result = solvers.solve(
        chains, horizon=NUM_DAYS, empty_tiles=empty_tiles, empty_counts=empty_counts,
        locked_by_worker=locked_by_worker, starting_money=STARTING_MONEY,
        max_time=20.0, cascade_reserve=cascade_reserve,
        # land_owned/buy_morning default False -> NE excluded on day 0
    )
    ... rest unchanged ...
```

For zonewise_wsp on FIVE, `LAND1_TILE_COUNT == NUM_TILES == 25` and `LAND1_WORKERS == WORKERS`, so this is a no-op there. Only TWO changes behavior.

### 5f. `get_tile_queues()` — allow the TWO layout

```python
        except (...) as exc:
            if zoning.CURRENT in (zoning.FIVE, zoning.TWO):     # was: is zoning.FIVE
                raise RuntimeError(...) from exc
```

---

## 6. `agent/market.py`

### 6a. Re-add ownership + buy-morning helpers

```python
def _land2_owned(me: dict) -> bool:
    return "NE" in me.get("unlocked_quadrants", [])
```

`_target_hires` stays `return planner.NUM_ACTIVE_HIRES` (planner now ramps it correctly).

### 6b. BUY_LAND order — gated on planner keeping the decision (req 4)

In `build_orders`, at h0, after the HIRE block:

```python
    if (
        hour == 0
        and planner.BUY_LAND_DAY is not None
        and day == planner.BUY_LAND_DAY
        and not _land2_owned(me)
    ):
        orders.insert(0, ["BUY_LAND"])
```

Because planner sets `BUY_LAND_DAY=None` when NE came back unwritten (5d), a doomed buy is never issued.

### 6c. Reserve the land price on buy-morning

Right after `money = int(me["money"])`:

```python
    if (
        planner.BUY_LAND_DAY is not None
        and day == planner.BUY_LAND_DAY
        and not _land2_owned(me)
    ):
        money = max(0, money - zoning.LAND2_BUY_COST)
```

(so seed/animal buys this dawn don't spend the $1000 the BUY_LAND needs.)

### 6d. UNCAP the dawn feed-wheat buy (requirement 3 — the actual supply bug)

Current code caps the *quantity* by remaining order slots, which starves late zones once many animals exist:

```python
        buy = min(deficit, money // cost, MAX_ORDERS - len(orders)) if cost else 0
```

Change to (one order, full deficit, bounded only by cash):

```python
        buy = min(deficit, money // cost) if cost else 0
```

`total_wheat_feed_need` already counts animals being PLACEd today (via `script.zone_animal_feed_count`), so buying the full deficit here guarantees every feed-zone can pick up its share regardless of preamble arrival order. The feed-wheat order is added before seeds/animals, so end-of-list truncation can't drop it.

### 6e. `_tile_empty` LOCKED carve-out + thread day

```python
def _tile_empty(me: dict, idx: int, *, day: int) -> bool:
    tile = _tile_at(me, idx)
    if tile is None:
        return True
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return True
    if (
        tile == "LOCKED"
        and idx >= zoning.LAND1_TILE_COUNT
        and planner.BUY_LAND_DAY is not None
        and day == planner.BUY_LAND_DAY
    ):
        return True
    return False
```

Update its only caller in `needed_buys`:

```python
        if crop and _tile_empty(me, idx, day=day):
```

(`zoning` and `planner` already imported.)

---

## 7. `agent/executor.py`

### 7a. `_dawn_empty` carve-out (the h0-LOCKED start gate)

```python
from agent import market, planner, rollouts, script, sell_dp, tile_ops, workers, zoning  # add zoning


def _dawn_empty(me: dict, idx: int, day: int) -> bool:
    tile = _tile_at(me, idx)
    if tile is None:
        return True
    if (
        tile == "LOCKED"
        and idx >= zoning.LAND1_TILE_COUNT
        and planner.BUY_LAND_DAY is not None
        and day == planner.BUY_LAND_DAY
    ):
        return True
    return False
```

In `_on_new_day`, replace the `_empty_at_dawn` set build:

```python
        self._empty_at_dawn = {
            idx for idx in range(workers.NUM_TILES) if _dawn_empty(me, idx, day)
        }
```

Everything else in `_on_new_day` stays. Note the `st["active"]/empty` lifecycle block above still uses `tile is None` (correct — a LOCKED tile is not a just-finished lifecycle).

### 7b. `_log_hand_status` at h0 (requirement 6 — why hire4 idles)

Add method:

```python
    def _log_hand_status(self, me: dict, day: int) -> None:
        for i, w in enumerate(workers.HAND_WORKERS):
            hired = i < len(me["hands"])
            pos = tuple(me["hands"][i]) if hired else None
            adj = pos in workers.SHED_ADJACENT if hired else False
            q = sum(1 for idx in workers.WORKER_TILES[w] if script.TILE_QUEUES.get(idx))
            empty = sum(1 for idx in workers.WORKER_TILES[w] if _tile_at(me, idx) is None)
            live = sum(
                1 for idx in workers.WORKER_TILES[w]
                if isinstance(_tile_at(me, idx), dict)
                and _tile_at(me, idx).get("kind") in ("PLANT", "COOP", "PASTURE")
            )
            _log(
                f"[hands] d={day} {w} hired={int(hired)} pos={pos} shed_adj={int(adj)} "
                f"qtiles={q} empty={empty} live={live}"
            )
```

Call it in `step` right after `self._log_snap(...)` at h0. This single line per hand disambiguates the four idle causes:
- `hired=0` → planner didn't staff it (check `NUM_ACTIVE_HIRES` / cascade break).
- `hired=1 shed_adj=0` at h1 → spawn/preamble adjacency (would explain old all-PASS).
- `qtiles=0 empty>0` → solver wrote no plan for owned empty tiles (IDLE pick set).
- `qtiles>0` but stuck → executor/tile_ops, look at the per-hand action notes.

---

## Deliberately NOT doing

- **No `_replan_eligible` staleness/`written_day` hack.** The `qi==0` lock stays; it protects committed-but-unstarted animal tiles. NE froze before only because the LOCKED carve-out was missing, so day-0 chains couldn't start. With 7a they start and `qi` advances.
- **No dynamic walk-to-shed.** Hands spawn shed-adjacent (game fills the 4 center tiles first, doubling up beyond 4), so fixed compass preambles that pick-up-first (hire5–9) work as-is. If 7b logs show `shed_adj=0` at h1, fix the *scripted* preamble in `zoning.py`, don't pathfind.
- **No executor-side per-zone wheat quota.** Supply fix (6d) is sufficient once aggregate ≥ total need, because each zone's `wheat_pickup_needed` only ever draws its own count.
- **No ledger/noise_std/plot/A-B work.** Separate follow-up.

## Smoke checklist (no submit)

1. Confirm OneLand parity is *not* the target here — we're on TWO now. Sanity: day-0 builds 25-tile prestart (`twoland prestart tiles=25`), NE absent.
2. `[planner] twoland probe hire5 day0=N buy_land tomorrow` fires at a plausible day (cash-dependent).
3. On `BUY_LAND_DAY`: `[exec] ... market BUY_LAND`, then NE `PLANT`/`PLACE` appearing at **h1 that same day**, and `[planner] wsp zone=hire5..hire9` actually solving with `empty=5`.
4. `[hands]` lines: every intended NE hand `hired=1`, `shed_adj=1` at h1, `qtiles>0`. No hand with `hired=1 qtiles=0` persisting.
5. Worker-actions plot: no all-day `feed-wait` or `pre-wait-shed` streaks on any zone.
6. Reward vs the pre-strip TwoLand numbers — but treat the first clean run as the new baseline, not the tangled ones.