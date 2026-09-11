# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation (Sep 11, 2026)

**Active stack:** **two-land WSP** (`CURRENT_SOLVER = twoland_wsp`, `zoning.CURRENT = TWO`) + snake executor + dawn replan + pickups-honest animal ops.

- Zoning: `FOUR` / `FIVE` / **`TWO`** (50 tiles); live = **TWO**.
- Solver: sequential per-zone WSP; day-0 `wsp_prestart.json`; land2 probe hire5 → `BUY_LAND`; **full** conservative cash cascade (no per-zone bank clamp — ladder rejected caps).
- Planner: import solve + dawn replan; WSP replan **`track_shed=False`**, `min_balance=0`; lock commitments; empties only.
- Animals: `animal_with_pickups.json`; ops = **`daily_tile_ops` only** (+ hire preamble).
- One-land fallback: `zonewise_wsp` + `FIVE`.

**Ruled out (diagnosis):** static NW spend caps; melon/wool glut as TwoLand gap cause. See `docs/twoland/diagnosis_0911.md`.

## Deliverable

- `main.py` + bundle (`agent/`, `data/` including `animal_with_pickups.json` + crop rollouts, vendored ortools)
- Local smoke: `scripts/smoke_test.sh`
- Submit: user-only via `scripts/smoke_and_submit.sh --submit "msg"`

## Scope boundaries

- **In scope:** assignment catalog, sell policy, local eval, user-requested submit
- **Out of scope unless asked:** WSP revival, agent-initiated Kaggle submit, RL, notebooks in the submission bundle

## Key references

- Rules: `docs/project_overview.md`
- Pickups / ops history: `docs/two_land_approach.md`
- Memory: `.cursor/memory/`
