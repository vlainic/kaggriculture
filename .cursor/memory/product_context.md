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

1. **Import:** bind `zoning.CURRENT` (default **FIVE**); stamp `no_fert` handmade chains; CP-SAT zone counts with shed W/F + hire cash (20s).
2. **Decode:** animals on route-first tiles, IDLE middle, crops last.
3. **Dawn replan (day ≥ 1):** lock non-empty / waiting-PLACE tiles for the remaining horizon; assign catalog chains only to empty replan-eligible tiles; **no W/F shed ledger** in the MIP (`track_shed=False`); cash ≥ 0 + ops caps kept. On INFEASIBLE, keep old queues.
4. **Runtime:** snake; fert after WATER; stay on unfed pastures. Market: 50% floor + premium DP; wheat reserved; 2+2 hire on FIVE.

## Known product gap

Day-0 catalog still uses **i0**. Replans use live quotes × opponent factor. Shed-off replan unlocked mid-season diversity (COW/STRAWBERRY); some late dawns still INFEASIBLE. Local FIVE smoke peaked ~98k once, later ~64k — **do not bank**. Occasional weeds from missed WATER remain.

## User workflow preferences

- Plain `.py` in submission; notebooks OK in `experiments/` only
- Plan/Act via `core-plan-act` skill
- Agents: `smoke_test.sh` only; never submit without explicit ask
- CP-SAT `num_workers = 1` when the user has other jobs on the machine
- Mockup `Assignement-Master-Mockup.ipynb` stays on SCIP; do not add hire preamble or extra PICKUPs unless asked
- Do not commit `.cursor/` (gitignore); do not stage `logs.txt`
- `live_analysis.ipynb` for post-run diagnosis from Kaggle logs
