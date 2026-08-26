# System Patterns

## Current: handmade-chain assignment + snake executor (Aug 26)

```
import:
  agent/zoning.py CURRENT → bind() → WORKERS / TILES / PREAMBLE / NET_TILE_OPS / HIRE_DAILY_COST
  data/{crop,animal}_rollouts.json + handmade_dp_candidates.json
  stamp chains (no_fert weights) → CP-SAT count[zone][chain]
  decode: animals (earliest start_day) → IDLE → crops → TILE_QUEUES

obs → executor.step
  ├─ hour0: reset routes; replan if day > 0; HIRE / BUY
  ├─ market: dump SELL (all shed fert); buy animals even if tile still empty
  └─ snake: preamble → tile ops (WATER then optional FERTILIZE) → shed
```

`main.py` → `executor.step`. Import solve + dawn replan from **day 1** (not day 0).

### Zone layouts (`agent/zoning.py`)

- **`Layout` / `Zone` dataclasses** — coords, visit order (= route), preamble, `start_hour`, `net_tile_ops`, `is_hand`.
- **Catalog:** `FOUR` (classic 3-hand snake) + `FIVE` (5 columns, 4 hands). **`CURRENT = FIVE`**. Do not delete old layouts — flip `CURRENT`.
- **`bind(layout)`** fills module aliases. `workers.py` re-exports; `planner.py` imports from `zoning`.
- **Hire cash:** `_fib_hire_cost(NUM_HIRES)` → FOUR=$4/day, FIVE=$7/day. Market reserve uses that; h=0 and h=1 each hire `min(2, remaining)`.
- **Fallback queues:** FOUR handmade only if `CURRENT is FOUR`; else empty. Prefer Python catalog over zone JSON.
- Spec notes: `data/five_zone_plan.md` (FIVE); `data/two_lands.md` (draft, unwired).

### Assignment master (planner + notebooks)

- **Vars:** `count[zone][chain]` IntVar `0..zone_size`, `sum == zone_size`. Not `x[tile][chain]` — tiles in a zone are interchangeable; per-tile binaries explode permutation symmetry (183s–40min OPTIMAL proofs).
- **Yields:** zip `harvest_ages` → `yield_per_harvest`. Never stamp `yield_per_harvest[0]` on every HARVEST.
- **FEED:** inventory consumption (open wheat buy at I0), **not** a $10 seed cost in `timeline_values`. PLANT / BUILD stay as setup costs.
- **Ops (OneLand / planner):** stamped tile actions + per-chain pickups (animal place, wheat-on-FEED, fert). Hire preamble = zone-day 0/1: `preamble <=> animal_count >= 1` via `preamble <= animal_count` and `animal_count <= preamble * zsize`. Farmer zone: no preamble. Do **not** use 654-term `OnlyEnforceIf` over tiles.
- **Cash / W/F:** daily `balance` chain (domain 0–200k), inventory levels, buy shortfall at I0 ($25 wheat / $100 fert), **minus `HIRE_DAILY_COST`/day** (layout-dependent fib sum). Objective = chain value − wheat/fert buys (hires cash-only).
- **Decode:** fill `WORKER_TILES[zone]` in route order. Sort slots: animal chains by earliest `start_day` in the full chain, then IDLE (`[]`), then crop-only. Log `t{idx+1}` (t1 = index 0).
- **IDLE:** legal count filler (empty queue for the horizon). Do not replan it on day 0 — looks like “queue exhausted.”
- **OneLand notebook:** CP-SAT OPTIMAL ~66s, obj 83620. Optional `OBJECTIVE_GOOD_ENOUGH`.
- **Mockup notebook:** SCIP sibling, no preamble. SCIP is **not** faster than CP-SAT.
- **Live planner:** `OBJECTIVE_GOOD_ENOUGH = 80_000`, `num_workers=8`, import 20s / replan 5s (Kaggle 60s turn). Obj scale ~49k so 80k callback often never hits.

### Planner catalog prices (`effective_price`)

- **Day 0 `_build_from_solver`:** i0 quoted, empty shops, **no** opponent counts.
- **Dawn `replan`:** live market prices × `max(0.1, 1 + shop_demand − opp_tiles/10)`.
- Opponent tiles: `PLANT.crop` or live `COOP`/`PASTURE` animal → `animal_rollouts.product_for`. Empty/WEED/empty structure ignored.
- Floor **0.1** is on the whole `price_factor`, not a separate multiply.

### Executor + fert + feed (runtime, not CP-SAT)

- Snake routes, `SHED_DOOR = (4,4)` for wheat/animal PICKUP — **never** shed fert
- BUILD pasture/coop only if animal already in worker inv; PLACE same day **and** `inv.WHEAT >= 1`
- Unfed animal (`tile_needs_feed`): `tile_needs_work` stays true even if `_animal_action` is None; **do not** `route_idx += 1`; PASS or PICKUP wheat
- FERTILIZE after WATER on that tile if bag > 0 + zone has a live animal + `with_fert` age; then HARVEST from tape
- Skip `COLLECT_FERTILIZER` only on **non-at-risk** tiles; never skip HARVEST / CARE / FERTILIZE for route slack
- Market: h=0 `BUY_PRODUCT WHEAT` if shed < live animals + placing today; skip `SELL WHEAT` when `hour < 5`; sell DP + 50% floor for other goods; wheat feed reserve

### Engine facts

- Turn order: farmer/hands → market → farm update → day rollover
- h=0: seeds from market are not in `private["seeds"]` during same-hour farmer action → PASS (`market-hour`)
- SELL from shed; harvest goes to worker inv; eod dump inv→shed
- Daily re-hire

---

## Anti-patterns

1. **Per-tile assignment binaries** when constraints are zone-shared — permutation symmetry, not model size.
2. **Reified OR via two `OnlyEnforceIf` linear sums** for preamble — use count + linear 0/1.
3. **Season-long WSP** (abandoned Aug 12) — tile ops ≠ executor turns; candidate explosion.
4. **Trusting solver obj as bank** — I0 prices; dump sells crash melon.
5. **Replan on day 0** — IDLE empty queues get a new (often animal) chain on t9.
6. **Committing `.cursor/`** — gitignored; Cursor will refuse the commit.
7. **`yield_per_harvest[0]` on every HARVEST** — later harvests have different units; zip `harvest_ages`.
8. **FEED as seed purchase** — feed is W inventory + `buy_w` at $25.
9. **Switching mockup SCIP → CP-SAT for speed** — same model; SCIP is slower. User kept SCIP.
10. **FERTILIZE before WATER** — steals watering; tomato age 10 also needs HARVEST after fert.
11. **BUILD pasture without animal in inv** — pasture sits empty for days (buy was gated on existing pasture).
12. **Treat FEED-with-no-wheat as no work** — executor advances; sheep die in ~2 days; hire3 PLACE ≫ BUILD.
13. **Opponent factor on day-0 catalog** — no opp farm yet; replan-only.
14. **Replace FOUR when adding FIVE** — keep both; switch with `CURRENT`.
15. **Zone geometry as JSON** — author as Python `Layout`; dump later if needed.

---

## Legacy WSP (do not extend)

See `docs/weighted_set_packing_failer.md`. Old day-0 ~8.7k set-packing candidates. Current `planner.py` is **not** that code.

---

## Repo layout

```
main.py → agent/executor.py → script.TILE_QUEUES
agent/zoning.py           # FOUR / FIVE / CURRENT + bind()
agent/planner.py          # zone-count CP-SAT at import (reads zoning)
agent/{script,workers,tile_ops,market,rollouts,animal_rollouts}.py
data/{crop_rollouts,animal_rollouts,handmade_dp_candidates}.json
data/five_zone_plan.md    # FIVE design
data/two_lands.md         # two-land draft (unwired)
experiments/OneLand-Assignement-Handmade-Candidates.ipynb   # CP-SAT source
experiments/Assignement-Master-Mockup.ipynb               # SCIP sibling, no preamble
data/animal_with_pickups.json                             # mockup animal days
scripts/{smoke_test,smoke_and_submit,vendor_ortools}.sh
```
