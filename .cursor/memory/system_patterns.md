# System Patterns

## Current: DP-catalog assignment + snake executor (Aug 27)

```
import:
  agent/zoning.py CURRENT → bind() → WORKERS / TILES / PREAMBLE / NET_TILE_OPS / HIRE_DAILY_COST
  data/crop_rollouts.json + data/animal_with_pickups.json
  dp_catalog.build_catalog(horizon, price_of) → stamp chains → CP-SAT count[zone][chain]
  decode: animals (earliest start_day) → IDLE → crops → TILE_QUEUES

obs → executor.step
  ├─ hour0: reset routes; dawn replan if 0 < day < SEASON_LAST; HIRE / BUY
  │         replan: lock commitments → CP-SAT empties only (track_shed=False)
  ├─ market: dump SELL (all shed fert); buy animals even if tile still empty
  └─ snake: preamble → tile ops (WATER then optional FERTILIZE) → shed
```

`main.py` → `executor.step`. Import solve + dawn replan from **day 1** (not day 0).

### Zone layouts (`agent/zoning.py`)

- **`Layout` / `Zone` dataclasses** — coords, visit order (= route), preamble, `start_hour`, `net_tile_ops`, `is_hand`.
- **Catalog:** `FOUR` (classic 3-hand snake) + `FIVE` (5 columns, 4 hands). **`CURRENT = FIVE`**. Do not delete old layouts — flip `CURRENT`.
- Live FIVE ops still **18/13/14/14/15**; zonewise notebooks often use `two_lands.md` **18/17/16/14/13**.
- **`bind(layout)`** fills module aliases. Hire cash: fib sum of hands (FIVE=$7/day).
- Spec notes: `data/five_zone_plan.md` (FIVE); `data/two_lands.md` (draft / notebook geometry).

### DP catalog (`agent/dp_catalog.py`)

- **Families:** mono WHEAT/CARROT, mix WIS, insert_crop (extra mono-greedy × lag + mix suffix), insert_animal (single place), animal-only starts, IDLE.
- **`lags`:** `None` → module `LAGS=(0,1,2)`; int or tuple OK.
- **Insert thinning:** keep near-best by value band; **always pin argmax**; then day-stride sample (`INSERT_MAX_VARIANTS`).
- **No forced wheat/carrot prefix** before extras/animals (greedy early high-value).
- **Multi-extra:** `_mono_greedy_from` repeats MELON/TOMATO/STRAWBERRY while they fit (handmade-style 2× melon).
- Prices for WIS come from caller `price_of` (day-0 i0; replan effective live).

### Assignment master (planner + notebooks)

- **Vars:** `count[zone][chain]` IntVar `0..zone_size`, `sum == zone_size`.
- **Yields:** zip `harvest_ages` → `yield_per_harvest`.
- **Ops (with pickups JSON):** **`daily_tile_ops` only** (+ hire preamble if any animal active). Do **not** add `daily_wheat_pickup` / `daily_animal_place` / `daily_fert_pickup` or extra `build_day += 1` — those double-count PICKUP/BUILD already in the tape.
- **Cash / W/F (day-0):** balance chain, shed ledgers, hire daily. Replan: `track_shed=False`.
- **Dawn replan triage:** `_replan_eligible` empties only; locked = board + queue suffix; horizon = remaining days. INFEASIBLE → preserve.
- **Zonewise notebooks:** sequential zone solves; **conservative money** = prev start − loss (setups + buys + hire; no sells).

### Planner catalog prices (`effective_price`)

- **Day 0:** i0 quoted, empty shops, no opponent.
- **Dawn replan:** live × `max(0.1, 1 + shop_demand − opp_tiles/10)`.
- Same `price_of` for catalog generation and stamp cash.

### Executor + fert + feed (runtime, not CP-SAT)

- Snake routes; BUILD only if animal in inv; PLACE same day needs wheat.
- FERTILIZE after WATER; stay on unfed pastures.
- Market: wheat dawn buy; skip early SELL WHEAT; sell DP + 50% floor.

### Engine facts

- Farmer/hands → market → farm update → day rollover
- h=0: seeds not in `private["seeds"]` same hour → PASS (`market-hour`)
- Daily re-hire

---

## Anti-patterns

1. **Per-tile assignment binaries** when constraints are zone-shared.
2. **Ops cap summing pickups side-channels while using `animal_with_pickups.json`** — double-count; smoke collapses.
3. **Season-long WSP** — abandoned.
4. **Trusting solver obj as bank** — I0 / dump sells.
5. **Replan on day 0.**
6. **Committing `.cursor/`.**
7. **`yield_per_harvest[0]` on every HARVEST.**
8. **FEED as seed purchase.**
9. **FERTILIZE before WATER.**
10. **BUILD pasture without animal in inv.**
11. **Opponent factor on day-0 catalog.**
12. **Replace FOUR when adding FIVE.**
13. **IDLE-wipe on replan INFEASIBLE.**
14. **Replan with wheat/fert shed ledger** without ablation.
15. **Day-stride thin without pinning best insert** — drops argmax chains.
16. **Forced wheat/carrot prefix before high-value insert** — fights greedy early animal/extra.
17. **Smoke `PLACE ≤ BUILD+1`.**

---

## Repo layout

```
main.py → agent/executor.py → script.TILE_QUEUES
agent/zoning.py           # FOUR / FIVE / CURRENT + bind()
agent/planner.py          # zone-count CP-SAT + replan
agent/dp_catalog.py       # runtime WIS catalog (lags, inserts)
agent/{script,workers,tile_ops,market,rollouts,animal_rollouts}.py
data/crop_rollouts.json
data/animal_with_pickups.json   # agent animal tapes (PICKUP/BUILD/PLACE in actions)
data/animal_rollouts.json       # tile-only; notebooks / legacy
data/handmade_dp_candidates.json  # notebooks / FOUR fallback
data/two_lands.md
experiments/OneL-Zonewise-CPSAT-{Handmade,DP}-Catalog.ipynb
scripts/{smoke_test,smoke_and_submit,vendor_ortools}.sh
```
