# System Patterns

## FAILURE note (Sep 9)

**Sept02 overhaul patterns are REJECTED.** Do not copy Wave 2–8 “safety rails” (`cons≥0`, WSP `track_shed=True`, formula `net_tile_ops`, fert dawn pipeline) into live agent. Pre-overhaul WSP: **`track_shed=False`**, **`min_balance=0`**, **unbounded `conservative`**, hand-calibrated `NET_TILE_OPS`. See `progress.md` FAILURE banner.

## Current: DP-catalog assignment + snake executor (pre-Sept02 restore)

```
import:
  agent/zoning.py CURRENT → bind() → WORKERS / TILES / PREAMBLE / NET_TILE_OPS / HIRE_DAILY_COST
  data/crop_rollouts.json + data/animal_with_pickups.json
  dp_catalog.build_catalog(horizon, price_of) → stamp chains → CP-SAT count[zone][chain]
    decode: animals (earliest start_day) → IDLE → crops → TILE_QUEUES

obs → executor.step
  ├─ hour0: reset routes; dawn replan if 0 < day < SEASON_LAST; HIRE / BUY
  │         replan: lock commitments → CP-SAT empties only
  │         WSP: track_shed=False, min_balance=0; zonewise: track_shed + liquidity floor
  ├─ market: dump SELL; buy animals even if tile still empty
  └─ snake: preamble → tile ops → shed
```

`main.py` → `executor.step`. Import solve + dawn replan from **day 1** (not day 0).

### Zone layouts (`agent/zoning.py`)

- **`Layout` / `Zone` dataclasses** — coords, visit order (= route), preamble, `start_hour`, `net_tile_ops`, `is_hand`.
- **Catalog:** `FOUR` + `FIVE` + **`TWO`** (FIVE land1 + NE land2, 10 zones). **`CURRENT = TWO`** for twoland_wsp; flip to `FIVE` for one-land.
- Live FIVE/TWO land1 ops **18/17/16/14/13**; land2 **16/14/13/12/11** (`two_lands.md`).
- **`bind(layout)`** fills module aliases; **`NET_TILE_OPS = z.net_tile_ops`** (hand table). Do not ship formula caps that omit intra-zone route cost.
- Hire cash: fib sum of hands (FIVE=$7/day).
- Spec notes: `data/five_zone_plan.md` (FIVE); `data/two_lands.md`.

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
- **Cash / W/F (day-0):** balance chain, shed ledgers, hire daily; **`cascade_reserve`** enforces `min_close0` for downstream zones.
- **Replan (zonewise):** `track_shed=True`; shed W/F from obs; **`min_balance`** on **balance_vars only** (liquidity floor); never on `conservative`.
- **Replan (WSP / twoland):** **`track_shed=False`**, **`min_balance=0`**; `cons = NewIntVar(-200_000, 200_000)` — **no** `cons >= min_balance`; cascade handoff `opening = res["conservative"]`; break if `open0 < 0`.
- **Dawn replan triage:** empties + WEED only; locked = board + queue suffix; horizon = remaining days. INFEASIBLE → preserve queues (never IDLE wipe).
- **Zonewise solver:** sequential zones; handoff = close balance; stop if `open0 < 0`.
- **WSP / twoland:** atomic patterns; day-0 `wsp_prestart.json`; replan from d≥3; hire5 probe → buy if cons leftover ≥ $1k; buy morning full cascade.

### Two-land flow (`twoland_wsp` + planner + market)

```
d≥3 replan (NE not owned):
  solve land1 → probe hire5–9 → ROI test → BUY_LAND_DAY = tomorrow
  (no land2 queues written on probe day)

BUY_LAND_DAY dawn:
  replan all zones until INFEASIBLE → NUM_ACTIVE_HIRES after INFEASIBLE gate
  market h=0: BUY_LAND + hire batches per two_lands.md

NE owned:
  full cascade each replan; update NUM_ACTIVE_HIRES (non-empty zones only)
```

### Planner catalog prices (`effective_price`)

- **Day 0:** i0 quoted, empty shops, no opponent.
- **Dawn replan:** `pricing.marginal_unit_price` at forecast inventory (town drain + opp units); capped ±40% vs live quote.
- Same `price_of` for catalog generation and stamp cash.

### Executor + fert + feed (runtime, not CP-SAT)

- Snake routes; BUILD only if animal in inv; PLACE same day needs wheat.
- Preamble / walk / fert / sell-floor knobs from **Sept02 are failed experiments** — restore pre-overhaul executor/market unless a change is revalidated against `d35bff5` smoke.

### Engine facts

- Farmer/hands → market → farm update → day rollover
- h=0: seeds not in `private["seeds"]` same hour → PASS (`market-hour`)
- Daily re-hire

---

## Anti-patterns

1. **Per-tile assignment binaries** when constraints are zone-shared.
2. **Ops cap summing pickups side-channels while using `animal_with_pickups.json`** — double-count; smoke collapses.
3. **Season-long WSP as sole backend** — abandoned Aug 12 for set-packing; **revived** as `zonewise_wsp.py` with atomic patterns + conservative cascade (Sep 2026).
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
18. **Batch aggregate with fixed `us_index`** — Kaggle seats vary per episode; use `g["us_index"]` in `_aggregate()`, not `games[0].us_index`.
19. **Trust batch `reward_us` before us_index fix** — ~50% of episodes had opponent scores in aggregate rollups.
20. **Blind movement before `PICKUP_*` in zone preamble** — `pre-wait-shed` absorbing PASS; always pickup-first + walk-to-shed fallback.
21. **Hand-tuned price multipliers** (`GLUT_CAPS`, `1 + shop_demand`, `−opp/10`) — use `pricing.marginal_unit_price` at forecast inventory instead.

---

## Repo layout

```
main.py → agent/executor.py → script.TILE_QUEUES
agent/zoning.py           # FOUR / FIVE / TWO / CURRENT + bind()
agent/planner.py          # BUY_LAND_DAY, NUM_ACTIVE_HIRES, zone-count CP-SAT + replan
agent/solvers/            # monolithic + zonewise + zonewise_wsp + twoland_wsp
agent/dp_catalog.py       # runtime WIS catalog (lags, inserts)
agent/{script,workers,tile_ops,market,rollouts,animal_rollouts}.py
data/crop_rollouts.json
data/animal_with_pickups.json   # agent animal tapes (PICKUP/BUILD/PLACE in actions)
data/animal_rollouts.json       # tile-only; notebooks / legacy
data/handmade_dp_candidates.json  # notebooks / FOUR fallback
data/two_lands.md
experiments/OneL-Zonewise-CPSAT-{Handmade,DP}-Catalog.ipynb
scripts/{smoke_test,smoke_and_submit,vendor_ortools,download_submission_logs,summarize_replays}.sh
scripts/replay_analysis/   # load, metrics, sells, kpi, plot; python -m replay_analysis
experiments/replay_analysis.ipynb
kaggle_logs/              # gitignored; <id>/replays/ + <id>.json batch summary
```
