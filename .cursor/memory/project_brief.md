# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs, config=None) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation (Sep 29, 2026)

**Active stack:** **`milos/` ThreeLand expansion** — `main.py` → `milos.executor.step`.

- Layout: **`MILOS_THREELAND15`** (default `KAGGRI_LAYOUT=threeland15`) — NW farmer+hire1–4, NE hire5–9, SW hire10–14. SW on via `KAGGRI_SW=1`. Spec in `data/milos_zoning.md` / `milos/zoning.py`.
- **NE/SW buy:** dusk cash (and SW: NE-full + overage) → next-day `BUY_LAND` → h1 land-only buy-replan.
- **Zone value gate:** new NE/SW activations require solver `obj − plan_cost ≥ 0` (hire + seed/animal spend); buy-day contiguous prefix; Walk 2/3 retries.
- **Pricing:** config-aware forecast + drain calibrator + MIP glut caps.
- Market: NW HIRE×`NW_HANDS`; room sells; wheat → animals → seeds; FERT dump.
- **Legacy:** `agent/` TwoLand WSP in repo, not live dispatch.

## Deliverable

- `main.py` + bundle (`milos/`, `data/` including crop + animal rollouts, vendored ortools)
- Local smoke: `scripts/smoke_test.sh`
- Submit: user-only via `scripts/smoke_and_submit.sh --submit "msg"`

## Scope boundaries

- **In scope:** milos land expansion / activation gates when asked, sell policy, local eval, user-requested submit, smoke diagnostics
- **Out of scope unless asked:** agent-initiated Kaggle submit, RL, switching live back to `agent/` TwoLand

## Key references

- Rules: `docs/project_overview.md`
- Milos layout: `data/milos_zoning.md`
- NE/SW/forecast history: `.cursor/memory/ne_expansion_and_forecast.md`
- Zone value gate plan: `.cursor/plans/zone_value_activation_gate_21c21131.plan.md`
- Memory: `.cursor/memory/`
