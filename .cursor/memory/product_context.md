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

1. **Import:** bind `zoning.CURRENT` (**TWO**); twoland WSP day-0 from `wsp_prestart.json` (land1); ops = `daily_tile_ops` (+ hire preamble).
2. **Dawn replan (WSP, day ≥ 3):** remaining horizon; lock commitments; sequential zones with **full** conservative handoff; probe hire5 → schedule NE buy. INFEASIBLE → break cascade, keep queues.
3. **Buy morning / NE owned:** cascade VI–X; `NUM_ACTIVE_HIRES` from solved prefix; market hire batches.
4. **Runtime:** snake; pickup-first preambles; fert after WATER. Market: sell floor + premium DP; wheat dawn buy.

## Known product gap

TwoLand only ~+7k over OneLand: **post-NE ops/weed collapse** (not glut). Static zone bank caps make it worse — keep full handoff. Late dawns can still go INFEASIBLE. Score variance large — prefer ≥30 episodes / ladder over n=3 smoke.

## User workflow preferences

- Plain `.py` in submission; notebooks OK in `experiments/` only
- Plan/Act via `core-plan-act` skill
- Agents: `smoke_test.sh` only; never submit without explicit ask
- Zonewise experiments OK for MIP/catalog A/B before wiring agent
- Do not commit `.cursor/` (gitignore); do not stage `logs.txt`
