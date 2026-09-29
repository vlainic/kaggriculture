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

## How the current agent is supposed to work (milos TWOLAND12 — live)

1. **Import:** `MILOS_TWOLAND12` — NW block (farmer + hire1–5) plus six NE zones unlocked incrementally after NE land buy.
2. **NE buy arc:** dusk cash gate → next-day `BUY_LAND` → h1 joint replan seeds NE zones; further zones via dawn Walk 2 when NE owned.
3. **h=0:** drain observe + replan (forecast uses episode config + inventory walk) → sell_dp → market (NW HIRE×5, buys, extended window on buy day).
4. **Day:** snakes on active workers; owned-shed PICKUP; shed FERT hygiene; planner must not over-value wool/melon (self-glut in solve).
5. **d=29:** endgame harvest.

Layout: [`data/milos_zoning.md`](../../data/milos_zoning.md). NE/forecast plan history: `.cursor/memory/ne_expansion_and_forecast.md`.

**OneLand 6-man** (`MILOS_ONELAND6`) remains the reference for wheat-buffer and shed-cap behavior on a single quadrant.

## Legacy TwoLand (`agent/`)

Still in repo. Was live through mid-Sep. Restore only if user points `main.py` back.

## User workflow preferences

- Plain `.py` in submission; notebooks OK in `experiments/` only
- Plan/Act via `core-plan-act` skill
- Agents: `smoke_test.sh` only; never submit without explicit ask
- Analysis tooling must follow live layout (milos farmer or `agent.zoning.CURRENT`)
- Do not commit `.cursor/` (gitignore); do not stage `logs.txt`
- Hard resets / force-pushes: user-driven
