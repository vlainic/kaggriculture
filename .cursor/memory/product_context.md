# Product Context

## Why this project exists

Compete on Kaggriculture with an autonomous agent that beats typical heuristic/LLM submissions. The game rewards supply-chain arithmetic, labor scheduling, and sell timing over vague policies.

## Problem shape

- Endogenous market pricing (own sells crash premium goods)
- Time-coupled crops/animals (water, feed, care bonus, decay)
- Tight action budget: 1 op/worker/hour + ≤10 market orders
- **Farmer acts before market in the same hour** — h=0 seed/hire timing
- Daily re-hire of farm hands
- Shed cap 100 (excluding seeds)

## How the current agent is supposed to work

1. **Import:** stamp `no_fert` handmade chains; CP-SAT zone counts (20s, 8 workers, 80k stop that often misses).
2. **Decode:** animals on route-first tiles (earliest animal day in the chain), IDLE in the middle, crops last.
3. **Runtime:** snake; collect fert from animals; FERTILIZE after WATER if the bag has some. Dawn replan from day 1 fills finished/IDLE tiles. Market dump-sells shed (all fert — intended; melon glut still the gap).

## Known product gap (expected, Aug 15)

Planner scores harvests at **I0 / base price** (melon $250). Executor `_sell_orders` dumps full shed every hour. Vs a greedy opponent that also dumps melon, price can fall to ~$7 and bank ~30k. Vs `random` smoke ~60k. **80k solver obj is not bank.** Next lever is sell policy (drip / hold), not another assignment solve.

## User workflow preferences

- Plain `.py` in submission; notebooks OK in `experiments/` only
- Plan/Act via `core-plan-act` skill
- Agents: `smoke_test.sh` only; never submit without explicit ask
- CP-SAT `num_workers = 1` when the user has other jobs on the machine
- Mockup `Assignement-Master-Mockup.ipynb` stays on SCIP; do not add hire preamble or extra PICKUPs unless asked
- Do not commit `.cursor/` (gitignore); do not stage `logs.txt`
- `live_analysis.ipynb` for post-run diagnosis from Kaggle logs
