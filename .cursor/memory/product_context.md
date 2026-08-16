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

1. **Offline / import:** stamp handmade chains from rollouts; CP-SAT picks how many tiles in each zone run each chain, subject to zone ops (tile + pickups + hire preamble), cash ≥ 0, open wheat/fert at I0 prices. Stop at obj ≥ 80k (or OPTIMAL in the notebook).
2. **Decode:** fill zone tiles arbitrarily from counts (tiles are interchangeable at this abstraction).
3. **Runtime:** executor follows `TILE_QUEUES` with snake movement. Market still **dump-sells** the shed (greedy).

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
