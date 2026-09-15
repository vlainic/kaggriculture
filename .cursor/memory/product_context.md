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

## How the current agent is supposed to work (one-land)

1. **Import:** bind `zoning.CURRENT` (**FIVE**); WSP day-0 from `wsp_prestart.json`; ops = `daily_tile_ops` (+ hire preamble).
2. **Dawn replan (WSP, day ≥ 3):** remaining horizon; lock commitments; sequential zones with **full** conservative handoff. INFEASIBLE → break cascade, keep queues.
3. **Hiring:** `NUM_ACTIVE_HIRES` from solved prefix; market h=0/h=1 hire batches (no land buy).
4. **Runtime:** snake routes; market sell floor + premium DP; wheat dawn buy.

## TwoLand (paused)

Prior TwoLand stack (~85–87k smoke but only ~+7k vs OneLand on ladder) hit **post-NE ops/weed collapse**. Multiple recovery attempts (Sept02 overhaul, queue-lock chase, OneLand-parity rewrite) were discarded. Re-open only from an explicit plan / [`docs/twolands/twoland_readd.md`](../../docs/twolands/twoland_readd.md).

## User workflow preferences

- Plain `.py` in submission; notebooks OK in `experiments/` only
- Plan/Act via `core-plan-act` skill
- Agents: `smoke_test.sh` only; never submit without explicit ask
- Analysis tooling must follow live `zoning.CURRENT` / workers (no hardcoded land2)
- Do not commit `.cursor/` (gitignore); do not stage `logs.txt`
- Hard resets / force-pushes: user-driven; do not assume tip matches origin without checking
