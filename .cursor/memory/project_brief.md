# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation (Sep 21, 2026)

**Active stack:** **TwoLand WSP** (`CURRENT_SOLVER = twoland_wsp`, `zoning.CURRENT = TWO`) + snake executor + dawn replan + pickups-honest animal ops. Opt-in ThreeLand: `KAGGRI_LANDS=3`.

- Zoning catalog: `FOUR` / `FIVE` / `TWO` / `THREE`; **live = TWO**.
- Solver: land1 day-0 + hire5 probe + NE cascade; **full** conservative cash cascade (`track_shed=False`, `min_balance=0`).
- Planner: import solve + dawn replan; lock commitments; empties only; `BUY_LAND_DAY` (re-arm next dawn); `NUM_ACTIVE_HIRES` from solved prefix; optional `[wsp_plan]` when `KAGGRI_VERBOSE=1`.
- Market: hire batches; `BUY_LAND` + reserve; uncap dawn wheat.
- Animals: `animal_with_pickups.json`; ops = **`daily_tile_ops` only** (+ hire preamble).
- **Shed:** PICKUP/DROP only on **owned** center tiles (`!= LOCKED`); SW/SE never valid on TwoLand. Owned-shed first → PICKUP → zone.
- **Sandbox:** `milos/` farmer-only WSP + Gantt notebook — **not** in submission bundle.

**Ruled out:** Sept02 mid-zone walk-to-shed; stuck-zone queue-lock chase; static NW spend caps; melon/wool glut as the TwoLand gap cause.

## Deliverable

- `main.py` + bundle (`agent/`, `data/` including `animal_with_pickups.json` + crop rollouts, vendored ortools)
- Local smoke: `scripts/smoke_test.sh` (sets `KAGGRI_VERBOSE=1` for plan logs)
- Submit: user-only via `scripts/smoke_and_submit.sh --submit "msg"`

## Scope boundaries

- **In scope:** TwoLand WSP, sell policy, local eval, user-requested submit, smoke/milos diagnostics
- **Out of scope unless asked:** agent-initiated Kaggle submit, RL, notebooks/`milos/` in the submission bundle

## Key references

- Rules: `docs/project_overview.md`
- TwoLand history / re-add: `docs/twolands/twoland_readd.md`, `docs/twoland/diagnosis_0911.md`
- Memory: `.cursor/memory/`
