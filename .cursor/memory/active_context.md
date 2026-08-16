# Active Context

## Current focus (Aug 16, 2026)

**Mockup SCIP notebook now matches OneLand on economy, not solver.** `experiments/Assignement-Master-Mockup.ipynb` stays on SCIP. Do **not** add hire preamble or extra PICKUP ops.

Live agent is unchanged: `agent/planner.py` zone-count CP-SAT from `experiments/OneLand-Assignement-Handmade-Candidates.ipynb`. Sell drip is still the next **agent** lever.

## What shipped (Aug 16 — mockup economy)

Edit only `Assignement-Master-Mockup.ipynb`. Three economy items aligned with OneLand:

1. **Yields** — `harvest_map = dict(zip(harvest_ages, yield_per_harvest))`. Never use `yield_per_harvest[0]` on every HARVEST. Goose age-4 HARVEST is 200 (not first-harvest units).
2. **FEED is inventory** — drop the `$10` wheat **seed** subtraction from `timeline_values`. Wheat/fert are open buys at I0, not seed purchases.
3. **Open W/F + hire burn** — SCIP `W[d]`, `F[d]`, `buy_w[d]`, `buy_f[d]` at $25 / $100; `W[0]=F[0]=0`; cash chain minus buys minus **$4/day** hire. Objective subtracts wheat/fert buys only (hires stay cash-only).

Also stamped per-candidate daily `feed` / `wheat` / `fert` / `collect` vectors (idle = zeros). Decode prints wheat/fert buy totals + cash floor. No preamble breakdown.

## SCIP vs CP-SAT (user conclusion)

Same MIP class as OneLand (zone counts + daily W/F + cash chain). **SCIP is not faster.** Speed win was the count reformulation, not the backend.

| Run | Solver | Time | Obj |
| --- | --- | --- | --- |
| Mockup before economy | SCIP | ~10–33s | ~105k (wrong yields, no hire/buys) |
| Mockup 10s gap 15% | SCIP | 10s cap | **83820** (status FEASIBLE) |
| Mockup 60s smoke | SCIP | ~20s OPTIMAL | **83910**, cash floor 695, wheat buy 16, 588 vars |
| OneLand 80k stop | CP-SAT | **~0.8s** | 80100 |
| OneLand OPTIMAL | CP-SAT | ~66s | 83620 |

Keep mockup on SCIP unless the user asks to switch.

## Active decision: Open-I0 plan vs dump sells (agent)

Planner weights use **base / I0 prices** (melon $250). `market._sell_orders` sells **entire shed** every hour. Vs greedy melon dump → price ~$7, bank ~**30k**. Solver 80k ≠ bank.

**Next lever (agent):** sell policy. Do not re-solve assignment to “fix” 30k vs greedy.

## User prefs (this arc)

- Mockup: **SCIP**, no hire preamble, no extra PICKUPs
- Planner: CP-SAT **1 worker** while other jobs run
- Notebook can stay open (no `max_time`); planner uses 80k stop
- Do not commit `.cursor/` / `logs.txt`
- Agents never Kaggle-submit without explicit ask

## Key files

| File | Role |
| --- | --- |
| `experiments/Assignement-Master-Mockup.ipynb` | SCIP count master + economy (yields, I0 buys, $4/day hire) |
| `experiments/OneLand-Assignement-Handmade-Candidates.ipynb` | CP-SAT source model / OPTIMAL timing |
| `agent/planner.py` | Zone-count master → queues (live) |
| `agent/script.py` | `QueueItem`, fallback queues, hook |
| `agent/executor.py` | Snake + preamble (unchanged) |
| `agent/market.py` | Dump sells — next **agent** work |
| `data/handmade_dp_candidates.json` | Chain catalog |
| `data/animal_with_pickups.json` | Mockup animal profiles (PICKUP every day) |

## Immediate next steps

- Sell / drip policy for premium goods (melon first) — agent
- Optionally bake an 83620 assignment JSON if import-time solve should disappear
- Do not revive WSP; do not add CP-SAT workers without asking
- Do not switch mockup SCIP → CP-SAT unless asked
