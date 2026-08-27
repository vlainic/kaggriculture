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
- Animal care needs honest shed trips (PICKUP wheat/animal) — undercounting ops lied about score; overcounting (pickups JSON + side counters) crushed animals

## How the current agent is supposed to work

1. **Import:** bind `zoning.CURRENT` (**FIVE**); `dp_catalog.build_catalog` at i0; stamp with `animal_with_pickups`; CP-SAT zone counts with shed W/F + hire cash (20s). Ops = `daily_tile_ops` (+ hire preamble).
2. **Decode:** animals on route-first tiles, IDLE middle, crops last.
3. **Dawn replan (day ≥ 1):** remaining horizon; lock non-empty / waiting-PLACE; assign DP chains to empty tiles; live prices × demand/opp; **no W/F shed ledger**; cash ≥ 0 + ops. INFEASIBLE → keep queues.
4. **Runtime:** snake; fert after WATER; stay on unfed pastures. Market: 50% floor + premium DP; wheat reserved; 2+2 hire on FIVE.

## Known product gap

Day-0 catalog still i0. Replans use live × opponent factor. Late dawns can still go INFEASIBLE. Score variance historically large — **do not bank** peaks. Occasional weeds from missed WATER. After pickups switch, smoke must be re-validated with de-duplicated ops.

## User workflow preferences

- Plain `.py` in submission; notebooks OK in `experiments/` only
- Plan/Act via `core-plan-act` skill
- Agents: `smoke_test.sh` only; never submit without explicit ask
- Zonewise experiments OK for MIP/catalog A/B before wiring agent
- Do not commit `.cursor/` (gitignore); do not stage `logs.txt`
