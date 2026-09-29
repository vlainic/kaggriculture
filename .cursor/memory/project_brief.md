# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation (Sep 29, 2026)

**Active stack:** **`milos/` TwoLand expansion** — `main.py` → `agent(obs, config=None)` → `milos.executor.step`.

- Layout: **`MILOS_TWOLAND12`** (NW 25 tiles + 6 NE zones; farmer + 5 dawn HIREs + gradual NE hires). Spec in `data/milos_zoning.md` / `milos/zoning.py`.
- **NE buy:** dusk cash trigger → h0 `BUY_LAND` → h1 `replan_after_buy` joint NE cascade (see `.cursor/memory/ne_expansion_and_forecast.md`).
- **Pricing:** config-aware forecast + drain calibrator + MIP glut caps (`fix_price_forecast` plan).
- Market: NW HIRE×5; room sells; **wheat → animals → seeds**; FERT dump; buy-day extended hours for NE overflow.
- **Wheat / shed:** unchanged global-buffer buy, raw pickup, cap-100 hygiene.
- **Legacy:** `agent/` TwoLand WSP in repo, not live dispatch.

## Deliverable

- `main.py` + bundle (`milos/`, `data/` including crop + animal rollouts, vendored ortools)
- Local smoke: `scripts/smoke_test.sh`
- Submit: user-only via `scripts/smoke_and_submit.sh --submit "msg"`

## Scope boundaries

- **In scope:** milos farmer / five-zone expansion when asked, sell policy, local eval, user-requested submit, smoke diagnostics
- **Out of scope unless asked:** agent-initiated Kaggle submit, RL, switching live back to `agent/` TwoLand

## Key references

- Rules: `docs/project_overview.md`
- Milos layout target: `data/milos_zoning.md`
- TwoLand history: `docs/twolands/twoland_readd.md`, `docs/twoland/diagnosis_0911.md`
- Memory: `.cursor/memory/`
