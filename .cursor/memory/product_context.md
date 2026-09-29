# Product Context

## Why this project exists

Compete on Kaggriculture with an autonomous agent that beats typical heuristic/LLM submissions. The game rewards supply-chain arithmetic, labor scheduling, and sell timing over vague policies.

## Problem shape

- Endogenous market pricing (own sells crash premium goods)
- Time-coupled crops/animals (water, feed, care bonus, decay)
- Tight action budget: 1 op/worker/hour + ≤10 market orders
- **Farmer acts before market in the same hour** — h=0 PASS so market can fill shed
- Daily re-hire of farm hands (fib cost rises with more hands)
- Shed cap 100 (excluding seeds)
- Animals need shed PICKUP before PLACE; seeds do not — buy animals before seeds at dawn
- Extra lands cost 1k/2k; late SW hires can burn more fib than the zone earns

## How the current agent is supposed to work (milos THREELAND15 — live)

1. **Import:** `MILOS_THREELAND15` — NW + NE + SW zones; SW enabled by default.
2. **NE buy arc:** dusk cash → next-day `BUY_LAND` → h1 NE-only replan (value-gated prefix); further NE via Walk 2.
3. **SW buy arc:** dusk when NE full + cash/overage → SW buy + h1 SW-only replan (value-gated); further SW via Walk 3.
4. **h=0:** drain observe + replan (forecast uses episode config) → sell_dp → market (NW HIREs, buys).
5. **Day:** snakes on active workers; owned-shed PICKUP; shed FERT hygiene.
6. **d=29:** endgame harvest.

Layout: [`data/milos_zoning.md`](../../data/milos_zoning.md). Expansion history: `.cursor/memory/ne_expansion_and_forecast.md`.

**OneLand 6-man** remains the reference for wheat-buffer and shed-cap behavior on a single quadrant.

## Legacy TwoLand (`agent/`)

Still in repo. Restore only if user points `main.py` back.

## User workflow preferences

- Plain `.py` in submission; notebooks OK in `experiments/` only
- Plan/Act via `core-plan-act` skill
- Agents: `smoke_test.sh` only; never submit without explicit ask
- Analysis tooling must follow live layout (`milos.zoning` / `layout.py`)
- Do not commit `.cursor/` (gitignore); do not stage `logs.txt`
- Hard resets / force-pushes: user-driven
- Judge activation-gate success by zone logs / P&L proxy, not single-run final reward
