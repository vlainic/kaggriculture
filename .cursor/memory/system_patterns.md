# System Patterns

## FAILURE note (Sep 9)

**Sept02 overhaul patterns are REJECTED.** Do not copy Wave 2–8 “safety rails” (`cons≥0`, WSP `track_shed=True`, formula `net_tile_ops`, fert dawn pipeline) into live agent. Pre-overhaul WSP: **`track_shed=False`**, **`min_balance=0`**, **unbounded `conservative`**, hand-calibrated `NET_TILE_OPS`. See `progress.md` FAILURE banner.

## Current: milos TWOLAND12 (Sep 29)

```
import:
  milos/zoning.py MILOS_TWOLAND12 → NW 25 + NE zones VII–XII
  NW_WORKERS / NE_WORKERS; NUM_ACTIVE_HIRES=5 (h0 HIRE loop)
  envconfig.ingest(config) from main.agent(obs, config)
  price_forecast + drain_calib + wsp/mip (locked_counts, product_caps)

obs → milos.executor.step
  ├─ h23: schedule_ne_buy_at_dusk (cash ≥ 3000 → BUY_LAND_DAY tomorrow)
  ├─ hour0: observe_drain; tile_state dawn; planner.replan (Walk1 + Walk2 if NE owned)
  │         sell_dp.replan; market BUY_LAND first on buy day; HIRE×5 NW + NE hires h1+
  ├─ hour1: replan_after_buy on buy day (NE owned); recompute _empty_at_dawn
  ├─ hours 1–23: snakes; owned-shed PICKUP; tile_ops
  └─ day ≥ 29: endgame harvest
```

**OneLand 6-man (`MILOS_ONELAND6`)** — prior live layout; still valid reference for shed/wheat patterns.

```
obs → milos.executor.step (6-man snapshot)
  ├─ hour0: replan → market HIRE×5 + room + WHEAT → ANIMAL → SEED; fert dump
  └─ …
```

**Day-0 / replan queues:** write from `result.assigned` / `replan_set` — never gate on `WORKER_TILES[solved_worker]` when layout ≠ prestart worker map.

**Wheat:** `total_wheat_feed_need` = Σ zone feed + **one** `(zones_with_animals+1)//2`. `wheat_pickup_needed` = raw need − inv **only**.

**Shed cap:** `FERT_SHED_CAP=10` dump first each market hour; dawn `_make_room_sells` if planned deposits > free slots. Env rejects buys when `sum(shed)>=100`.

**Animal tile ops:** CARE requires `fed_today`.

`main.py` → `milos.executor.step`. Bundle: `main.py` + `milos/` + `data/` + ortools.

## Prior: milos 5-man / farmer-only (historical)

`MILOS_ONELAND` (4 hires) superseded by `MILOS_ONELAND6`. `MILOS_FARMER` sandbox remains.

### Dawn market buy order

1. HIREs
2. Room sells (if deposit units > free shed)
3. Feed wheat via `total_wheat_feed_need` (global buffer)
4. Animals → seeds
5. Sells (fert dump first, then staples/premiums)

### Shed-adjacent **ONLY IF OWNED** (engine + executor)

- Four centers; **PICKUP/DROP no-op on LOCKED**.
- Live gate: `_owned_shed_tiles(me)`.

### Milos modules (live)

```
milos/
  executor.py   # turn loop, _claim_worker / TWOFOLD_HIRE, shed_total snap
  market.py     # fert dump, make_room_sells, h=0 buys
  script.py     # wheat_pickup_needed (raw); total_wheat_feed_need (global buffer)
  planner.py    # assigned-tile queue write; NUM_ACTIVE_HIRES=NUM_HIRES
  zoning.py     # MILOS_ONELAND6 CURRENT
  …
```

### Zone layouts (`agent/zoning.py`)

- **`Layout` / `Zone` dataclasses** — coords, visit order (= route), preamble, `start_hour`, `net_tile_ops`, `is_hand`.
- **Catalog:** `FOUR` + `FIVE` + **`TWO`** + `THREE`. **`CURRENT = TWO`** (live).
- Live TWO: land1 ops **18/17/16/14/13**, land2 **16/14/13/12/11**.
- Module constants: `LAND1_TILE_COUNT`, `LAND1_WORKERS`, `LAND2_WORKERS`, `LAND2_BUY_COST` (+ LAND3_* for opt-in).
- **`bind(layout)`** fills module aliases; **`NET_TILE_OPS = z.net_tile_ops`**.
- Hire cash: fib sum of active hands (`planner.NUM_ACTIVE_HIRES`).

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
- **Replan (WSP):** **`track_shed=False`**, **`min_balance=0`**; `cons = NewIntVar(-200_000, 200_000)` — **no** `cons >= min_balance`; cascade handoff `opening = res["conservative"]` **uncapped** (full handoff); break if `open0 < 0`. Do **not** clamp zone openings to `money/N` or `min(money/2, handoff)` — ladder rejected both.
- **Cascade fail:** INFEASIBLE/`picks0` → **skip zone, locked handoff, `continue`** (log `cascade skip=`); never IDLE wipe; do **not** hard-stop later lands. `SolveResult.zone_outcomes` records per-worker status.
- **Dawn replan triage:** empties + WEED only; locked = board + queue suffix; horizon = remaining days.
- **Zonewise / WSP solvers:** sequential zones; WSP atomic patterns; day-0 `wsp_prestart.json`; replan from d≥3.
- **`ZONE_OPS_MIX`:** construction-time chain swap on fixed snakes (default on). Dead: BUDGET / IDLE_FILLER / TILE_RESIZE.
- **Hiring:** `NUM_ACTIVE_HIRES` from healthy solved hands with work, **excluding `DEAD_HANDS`**; market `_hire_batches` + `dead=` log. Ratchet: 3 consecutive non-ok dawns with empties → mark dead; clear on `ok`.

### Two-land flow (LIVE)

Probe hire5 → `BUY_LAND_DAY` → buy morning cascade VI–X + `NUM_ACTIVE_HIRES`.  
NE tiles still read `LOCKED` at h0 on buy-morning — carve-out in planner/executor/market.  
See `docs/twolands/twoland_readd.md`.

### Planner catalog prices (`effective_price`)

- **Day 0:** i0 quoted, empty shops, no opponent.
- **Dawn replan:** `pricing.marginal_unit_price` at forecast inventory (town drain + opp units); capped ±40% vs live quote.
- Same `price_of` for catalog generation and stamp cash.

### Executor + fert + feed (runtime, not CP-SAT)

- Snake routes; BUILD only if animal in inv; PLACE same day needs wheat.
- **PICKUP/DROP only on owned shed tiles** (`_owned_shed_tiles`); locked center → `_step_to_owned_shed`.
- Mid-zone walk-to-shed / Sept02 preamble rewrites are **failed** — do not reintroduce.
- Dawn `[hands] h0` logs animal/crop/`est_ops` for **all** `WORKERS` (incl. farmer); eod uses `tiles_dawn=` (tiles needing work at dawn) / `executed=` (non-PASS) / `laps=` — **no** `gap=` (misleading KPI).

### Milos (was sandbox; now live)

Self-contained under `milos/`. Smoke ships `milos/` in tarball. No `agent/` imports inside milos.

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
7. **Plotting `[wsp_plan]` deltas as full Gantts** without accumulation.7. **`yield_per_harvest[0]` on every HARVEST.**
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
20. **Blind movement before `PICKUP_*` / treating any shed-adjacent tile as pickup-valid** — SW/SE are LOCKED on TwoLand; PICKUP no-ops. Always owned-shed first (`_owned_shed_tiles`), then PICKUP, then compass. Mid-zone walk-to-shed = Sept02 failure.
21. **Hand-tuned price multipliers** (`GLUT_CAPS`, `1 + shop_demand`, `−opp/10`) — use `pricing.marginal_unit_price` at forecast inventory instead.
22. **Static per-zone replan bank caps** (`starting_money/N`, `min(day_start/2, handoff)`) — ladder: no-cap beat both; prefer trigger-based NE reserve / ops fixes instead.
23. **Blame TwoLand gap on premium glut** without fill/rv/q — diagnosis_0911 ruled melon/wool glut out; post-NE ops/weed collapse is the primary.
24. **`pos in SHED_ADJACENT` alone as shed-door** — must also be **owned** (`tile != "LOCKED"`).
25. **Per-zone wheat buffer in `wheat_pickup_needed`** — 6-man FCFS shed race; buffer belongs only in `total_wheat_feed_need`.
26. **Ignoring shed_total / silent buy reject** — `sum(shed)>=100` kills BUY_PRODUCT with no log error.
27. **Price-floor-only FERT sells under high COLLECT_FERTILIZER** — fills shed; dump to `FERT_SHED_CAP`.
28. **Day-0 queues via `WORKER_TILES[solved_worker]`** when layout workers ≠ prestart `solved_workers`.
29. **Freeze `_route_idx` / PASS-hold waiting for wheat or PLACE** — stalls the zone for most of the day.

---

## Repo layout

```
main.py → milos/executor.py → market + tile_ops + script.TILE_QUEUES
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
experiments/replay_analysis.ipynb          # single-episode viewer (do not fold into batch notebooks)
experiments/submission_nb.py               # shared notebook helpers only
experiments/submission_analysis.ipynb      # one submission: noise floor, day bands, land/anomalies
experiments/submission_comparison.ipynb    # A/B: violins, KPI deltas, post-NE alignment
docs/twoland/diagnosis_0911.md             # OneLand vs TwoLand root-cause + budget A/B (Sep 11)
kaggle_logs/              # gitignored; <id>/replays/ + <id>.json + episode_skills.json
```

### Submission analysis (notebooks-only layer)

```
kaggle_logs/<id>/<id>.json  ← summarize_replays / ensure_summary
kaggle_logs/<id>/episode_skills.json  ← GetEpisode initialScore cache
         ↓
submission_analysis.ipynb  → noise floor, scatter (reward_me vs opp × skill), land table
submission_comparison.ipynb → A/B violins, KPI effect sizes, days-since-NE-buy alignment
```

Do **not** change `scripts/replay_analysis/` KPI extractors for notebook needs — derive std/cash/skill in notebooks. KPI gotchas: `idle_empty` = tile-turns; `noop_ops` = wasted actions; `ops_utilization_by_day` = 1−PASS/(workers×24) — alignment averages can go negative if NaNs leak.
