# Active Context

## Current focus (Aug 15, 2026)

**Handmade-chain assignment is live.** `agent/planner.py` ports the zone-count CP-SAT master from `experiments/OneLand-Assignement-Handmade-Candidates.ipynb`. Executor / workers / routes untouched. `script.TILE_QUEUES` comes from `get_tile_queues(_build_tile_queues)`.

WSP season packing remains abandoned (`docs/weighted_set_packing_failer.md`). Current planner is **not** that system.

## What shipped (this arc)

1. Notebook assignment over `handmade_dp_candidates.json` (108 chains + idle).
2. Cash/W/F as daily balance + inventory levels (not O(days²) `cum_terms`).
3. Dropped then **restored** hire preamble as **zone-day 0/1** (linear, not `OnlyEnforceIf` over tiles).
4. **Zone counts** instead of `x[tile][chain]` — kills tile permutation symmetry.
5. Planner: `num_workers=1`, `OBJECTIVE_GOOD_ENOUGH=80_000`, no time limit. Smoke: `[planner] FEASIBLE good_enough=True obj=80100 time=0.758s tiles=25`. Vs random ~60k DONE.

Notebook OPTIMAL (threshold 0): ~66s, obj **83620**, all zone peaks at cap including preamble.

## Active decision: Open-I0 plan vs dump sells

Planner weights use **base / I0 prices** (melon $250). `market._sell_orders` sells **entire shed** every hour. User confirmed this is expected. Vs greedy melon dump → price ~$7, bank ~**30k**. Solver 80k ≠ bank.

**Next lever:** sell policy (drip melon while price is high; shed cap 100). Do not re-solve assignment to “fix” 30k vs greedy.

## User prefs (this arc)

- CP-SAT **1 worker** while other jobs run
- Notebook can stay open (no `max_time`); planner uses 80k stop
- Do not commit `.cursor/` / `logs.txt`
- Agents never Kaggle-submit without explicit ask

## Key files

| File | Role |
| --- | --- |
| `agent/planner.py` | Zone-count master → queues |
| `agent/script.py` | `QueueItem`, fallback queues, hook |
| `agent/executor.py` | Snake + preamble (unchanged) |
| `agent/market.py` | Dump sells — next work |
| `data/handmade_dp_candidates.json` | Chain catalog |
| `experiments/OneLand-Assignement-Handmade-Candidates.ipynb` | Source model / OPTIMAL timing |

## Immediate next steps

- Sell / drip policy for premium goods (melon first)
- Optionally bake an 83620 assignment JSON if import-time solve should disappear
- Do not revive WSP; do not add CP-SAT workers without asking
