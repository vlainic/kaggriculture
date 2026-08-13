# Product Context

## Why this project exists

Compete on Kaggriculture with an autonomous agent that beats typical heuristic/LLM submissions. The game rewards supply-chain arithmetic, labor scheduling, and sell timing over vague policies.

## Problem shape (unchanged)

- Endogenous market pricing
- Time-coupled crops/animals (water, feed, care bonus, decay)
- Tight action budget: 1 op/worker/hour + ≤10 market orders
- **Farmer acts before market in the same hour** — critical for h=0 seed/hire timing
- Daily re-hire of farm hands

## What we learned from WSP (Aug 2026) — not the path forward

The **season-long CP-SAT set packing** planner tried to assign lifecycles to a calendar grid and have a snake executor follow the plan. It failed because:

- The model counted **tile ops**, not **movement + shed + market-hour waste**
- Plans optimized **total season NPV**, not **early revenue or zone fairness**
- **~8.7k candidates / 3–6s solve** at 1 land — would explode at 2–3 lands
- **8–15 PASSes/worker/day** in practice — idle `route=done` and daily h=0 re-hire

Notebook success at **9 tiles, 1 worker** did not transfer to **25 tiles, 4 workers**.

Full write-up: `docs/weighted_set_packing_failer.md`.

## Intended agent behavior (still valid goals)

1. Early: reliable crops on unlocked land; don't leave farmer zone empty for 20 days
2. Mid: hire when marginal; sell before glut; use town demand growth
3. Late: liquidate; bank coins win, not shed stockpile

**How** to achieve this is **open** — not via season WSP.

## User workflow preferences

- Plain `.py` in submission; notebooks OK in `experiments/` only
- Plan/Act via `core-plan-act` skill
- Agents: `smoke_test.sh` only; never submit without explicit ask
- `live_analysis.ipynb` for post-run diagnosis from Kaggle logs

## Current repo (legacy)

Still ships WSP code in `agent/planner.py` + `agent/executor.py`. Treat as reference until user picks next architecture.
