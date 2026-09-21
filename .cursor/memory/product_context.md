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

## How the current agent is supposed to work (TwoLand — live)

1. **Import:** bind `zoning.CURRENT` (**TWO**); WSP day-0 land1 from `wsp_prestart.json`; hire5 probe.
2. **Dawn replan (WSP, day ≥ 3):** remaining horizon; lock commitments; land cascade with **full** conservative handoff. INFEASIBLE/`picks0` → **skip zone, continue cascade**, keep queues.
3. **Hiring / land:** `NUM_ACTIVE_HIRES` from healthy hands (excl. `DEAD_HANDS`); `BUY_LAND_DAY` after probe; market hire batches + BUY_LAND; `ZONE_OPS_MIX` on at construction.
4. **Runtime:** owned-shed first → PICKUP → snake; market sell floor + premium DP; wheat dawn buy.

## Milos sandbox

`milos/` is an **experiments-only** farmer WSP (self-contained). Smoke still runs live `agent/`. Use `experiments/milos-simplification.ipynb` for replan Gantts from `[wsp_plan]` logs — not a second submission agent.

## User workflow preferences

- Plain `.py` in submission; notebooks OK in `experiments/` only
- Plan/Act via `core-plan-act` skill
- Agents: `smoke_test.sh` only; never submit without explicit ask
- Analysis tooling must follow live `zoning.CURRENT` / workers (no hardcoded land2)
- Do not commit `.cursor/` (gitignore); do not stage `logs.txt`
- Hard resets / force-pushes: user-driven; do not assume tip matches origin without checking
- `milos/` stays out of `submission.tar.gz` unless user asks to wire it live
