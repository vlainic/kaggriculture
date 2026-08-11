# System Patterns

## Implemented coupled agent (Phase 1 — Aug 11)

```
obs → Executor.step
  ├─ hour0: reset route_idx; replan if triggers fire
  ├─ Planner.solve_plan (CP-SAT → greedy fallback)
  │    ├─ candidates: crops (all 9 tiles) + animals (BUILD/PLACE/FEED/HARVEST)
  │    ├─ crop occupancy: half-open [plant, free)
  │    ├─ animal occupancy: placed tile locked until OPS_HORIZON
  │    ├─ capacity: remaining ops + weed DIG + daily_op_budget(day)  [16 total, snake implicit]
  │    ├─ crop weight: yield × live_price × (1+shop_demand) − seed − fert_cost
  │    ├─ animal weight: revenue_window(live_product_price) × (1+d) − animal_cost − feed_days × live_wheat
  │    └─ output: full forward placement list (replaces self.plan)
  ├─ market (≤10 orders, every turn):
  │    SELL shed → BUY_SEED (today; +day+1 if snake done)
  │    → BUY_ANIMAL (day, day+1) → BUY fert → BUY wheat
  └─ farmer: sticky current tile → strict TILE_COORDS snake → move/op
```

### Packing / horizon conventions

| Constant | Value | Role |
| --- | --- | --- |
| `SEASON_DAYS` / `OPS_HORIZON` | 30 | Ops + lifecycle_fits through day 29 |
| `PLAN_HORIZON` | 28 | Occupancy cells + start_day enumeration |
| `DAILY_OP_BUDGET` | 16 | Total daily tile ops incl. ~8 implicit snake moves |
| `FIRST_DAY_OP_RESERVE` | 1 | Day 0 tile-op budget 15 |
| `tile_free_age` (crop) | last harvest/DIG age | Half-open end; same-day replant allowed |
| animal tile lock | `earliest[tile]=OPS_HORIZON` | No mid-season animal tile recycle |

### Replan semantics (critical)

**Triggers (`hour == 0`):**
- First run (`last_replan_day is None`)
- Crop or animal harvest today
- Weed on any tile
- Animal `consecutive_unfed >= 1`
- Empty tile with **no** plan entry where `start_day >= day` (NOT empty-set equality)

**Fixed on replan:** in-progress plants + live animals (ops load + earliest start); weed DIG +1 today.

**Free on replan:** all future crop/animal placements — full forward reshuffle under new prices.

### Executor routing

1. Sticky: finish pending ops on current tile before leaving (harvest→plant, animal FEED/HARVEST).
2. Strict snake: scan `TILE_COORDS` in order; weeds DIG when reached.
3. `_snake_done()` when `_route_idx >= 9` — enables end-of-day tomorrow market buys.

### Animal execution

- `_animal_pending_for_tile`: template actions + catch-up HARVEST if `yield_units > 0`.
- FEED gated on WHEAT inventory and `fed_today`.
- BUILD_COOP/PASTURE on empty tile; PLACE when animal in inventory.
- Profiles stored in `animal_profiles[(idx, placed_day)]`.

### Market buying semantics

- Farmer ops and market orders are **independent** per turn.
- Seeds: `start_day == day` during snake; `start_day == day+1` when snake done.
- Fert/wheat deficit from `_fert_ops_for_day` / `_feed_ops_for_day` for today (+ tomorrow if snake done).
- WHEAT sell reserve: `live_animals × WHEAT_FEED_RESERVE_DAYS`.

## Target architecture (later phases)

```
Master (MCTS or shallow lookahead — TBD)
  └─ segments → daily CP-SAT → routing → hires / land unlock
```

## Spatial decomposition

Single 5×5 NW quadrant owned; current agent uses 3×3 near shed (`TILE_COORDS` snake from (4,4)).

## Staged rollout

1. Coupled crop+animal, no-hire, 3×3 — **in progress on ladder**
2. Hires + extra segments + 5×5
3. Master hire/land
4. Fert profiles + sell timing polish

## Algorithm fit

| Module | Approach | Status |
| --- | --- | --- |
| Plants + animals (season packing) | CP-SAT weighted set packing | Live |
| Op budget dispatch | `ops_budget.executor_ops_by_day` | Live |
| Routing | Snake + sticky + BFS step | Live |
| Shop demand | Static map × unlocked shops | Live (crops + animal products) |
| Live replan pricing | `obs["market"]["prices"]` | Live |
| Master / hires | Heuristic / MCTS | Not started |

## Repo layout (current)

```
main.py
agent/{rollouts,planner,executor,ops_budget,animal_rollouts}.py
data/{crop_rollouts,animal_rollouts}.json
scripts/{vendor_ortools,smoke_and_submit}.sh
vendor/ortools/...
```
