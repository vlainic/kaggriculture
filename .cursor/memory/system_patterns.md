# System Patterns

## Implemented plant agent (Phase 1 — Aug 7)

```
obs → Executor.step
  ├─ hour0 replan triggers: first / harvest today / weed / empty-set change
  ├─ Planner.solve_plan (CP-SAT → greedy fallback)
  │    ├─ candidates: all 9 tiles, plant_day ≥ earliest_plant[tile]
  │    ├─ occupancy: half-open [plant, free)  — last day ops only
  │    ├─ capacity: remaining plant ops + weed DIG + daily_op_budget(day)
  │    ├─ weight: yield × live_price × (1+shop_demand) − fixed_seed_cost
  │    └─ output: full forward placement list (replaces self.plan)
  ├─ market: SELL shed; BUY_SEED for plant_day in {day, day+1}
  └─ farmer: sticky current tile → strict TILE_COORDS snake → move/op
```

### Packing / horizon conventions

| Constant | Value | Role |
| --- | --- | --- |
| `SEASON_DAYS` / `OPS_HORIZON` | 30 | Ops + lifecycle_fits through day 29 |
| `PLAN_HORIZON` | 28 | Occupancy cells + plant_day enumeration |
| `tile_free_age` | last harvest/DIG age | Half-open end; same-day replant allowed |
| `FIRST_DAY_OP_RESERVE` | 1 | Day 0 tile-op budget 15 |

### Replan semantics (critical)

- **Fixed:** plants already on tiles (ops load + `earliest_plant`); weed DIG +1 today.
- **Free:** all future `plant_day` on every tile — do **not** keep frozen future schedule rows.
- Prices/shops update → whole remaining horizon can reshuffle.

### Executor routing

1. Sticky: if standing on a managed tile with pending ops, finish it (harvest→plant).
2. Else scan `TILE_COORDS` in order (weeds DIG when reached — no weed-first jump).

## Target architecture (later phases)

```
Master (MCTS or shallow lookahead — TBD)
  └─ segments → daily CP-SAT → routing → animals heuristic
```

## Spatial decomposition

Single 5×5 NW quadrant; current agent uses 3×3 near shed (`TILE_COORDS` snake from (4,4)).

## Staged rollout

1. Plant-only, no-hire, 3×3 — **in progress on ladder**
2. Hires + extra segments
3. Master hire/land
4. Animals

## Algorithm fit

| Module | Approach | Status |
| --- | --- | --- |
| Plants (season packing) | CP-SAT weighted set packing | Live |
| Routing | Snake + sticky + BFS step | Live |
| Shop demand | Static map × unlocked shops | Live (crops only) |
| Animals / Master | Heuristic / MCTS | Not started |

## Repo layout (current)

```
main.py
agent/{rollouts,planner,executor}.py
data/crop_rollouts.json
experiments/MainChecks.ipynb
scripts/{vendor_ortools,smoke_and_submit}.sh
```
