# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation (Sep 26, 2026)

**Active stack:** **`milos/` OneLand 6-man** — `main.py` → `milos.executor.step`.

- Layout: **`MILOS_ONELAND6`** (25 tiles, farmer + 5 hires; zone VI north row). Spec in `data/milos_zoning.md`.
- Market: HIRE×5; room sells if needed; **wheat → animals → seeds**; hourly FERT dump to ≤~10; farmer PASSes at h=0.
- **Wheat:** dawn buy uses raw feed + one global zone buffer; shed PICKUP uses raw zone need only.
- Tile ops + dawn replan + sell_dp as before; owned-shed PICKUP/DROP.
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
