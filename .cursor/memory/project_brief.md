# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation (Sep 23, 2026)

**Active stack:** **`milos/` farmer-only** — `main.py` → `milos.executor.step`.

- Layout: `MILOS_FARMER` (5 tiles / zone I, 0 hires). Five-zone + 4 hires = target spec in `data/milos_zoning.md`.
- Market: h=0 buys **wheat → animals → seeds**; sells drip/dump; farmer PASSes at h=0.
- Tile ops: `milos/tile_ops.py` + rollouts JSON; **`plant_harvest_transfer`** for sim; endgame `_endgame_harvested`.
- **Dawn replan:** `milos/planner.replan` + `replan_lock` (farmer WSP, live prices).
- Sell policy: `sell_dp` (premium) + `pricing` (staples).
- Shed: PICKUP/DROP only on **owned** center tiles.
- Diagnostics: dawn theo dry-run (`[theo]` / `est_ops=`) + `scripts/smoke_analysis` / `experiments/smoke_analysis.ipynb`.
- **Legacy:** `agent/` TwoLand WSP still in repo, not live dispatch.

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
