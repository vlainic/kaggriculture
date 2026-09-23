# Product Context

## Why this project exists

Compete on Kaggriculture with an autonomous agent that beats typical heuristic/LLM submissions. The game rewards supply-chain arithmetic, labor scheduling, and sell timing over vague policies.

## Problem shape

- Endogenous market pricing (own sells crash premium goods)
- Time-coupled crops/animals (water, feed, care bonus, decay)
- Tight action budget: 1 op/worker/hour + ≤10 market orders
- **Farmer acts before market in the same hour** — h=0 PASS so market can fill shed
- Daily re-hire of farm hands (when multi-hand layout is on)
- Shed cap 100 (excluding seeds)
- Animals need shed PICKUP before PLACE; seeds do not — buy animals before seeds at dawn

## How the current agent is supposed to work (milos farmer-only — live)

1. **Import:** `milos` `MILOS_FARMER` (5 tiles, farmer only).
2. **h=0:** `planner.replan` (d≥1) → sell_dp replan → farmer PASS; market buys wheat → animals → seeds; theo dry-run **after** replan.
3. **Day:** farmer snake + `tile_ops` from crop/animal rollouts; owned-shed PICKUP/DROP.
4. **d=29:** endgame harvest; do not re-HARVEST same plant after DROP.
5. **Sells:** staples dump via pricing floor; premiums drip from sell_dp daily quota (≤1/hour).

Target five-zone + 4 hires: [`data/milos_zoning.md`](../../data/milos_zoning.md).

## Legacy TwoLand (`agent/`)

Still in repo. Was live through mid-Sep. Restore only if user points `main.py` back.

## User workflow preferences

- Plain `.py` in submission; notebooks OK in `experiments/` only
- Plan/Act via `core-plan-act` skill
- Agents: `smoke_test.sh` only; never submit without explicit ask
- Analysis tooling must follow live layout (milos farmer or `agent.zoning.CURRENT`)
- Do not commit `.cursor/` (gitignore); do not stage `logs.txt`
- Hard resets / force-pushes: user-driven
