# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation (Sep 15, 2026)

**Active stack:** **one-land WSP** (`CURRENT_SOLVER = zonewise_wsp`, `zoning.CURRENT = FIVE`) + snake executor + dawn replan + pickups-honest animal ops.

- Zoning catalog: `FOUR` / `FIVE` / `TWO` (50 tiles kept as catalog); **live = FIVE**.
- Solver: sequential per-zone WSP; day-0 `wsp_prestart.json`; **full** conservative cash cascade (`track_shed=False`, `min_balance=0`).
- Planner: import solve + dawn replan; lock commitments; empties only; `NUM_ACTIVE_HIRES` from solved prefix.
- Market: hire batches from `NUM_ACTIVE_HIRES`; **no** `BUY_LAND` path in live agent.
- Animals: `animal_with_pickups.json`; ops = **`daily_tile_ops` only** (+ hire preamble).
- TwoLand: stub `twoland_wsp.py` + docs under `docs/twoland*/` — **not** wired.

**Ruled out:** Sept02 overhaul; stuck-zone queue-lock chase; OneLand-parity rewrite without a fresh plan; static NW spend caps; melon/wool glut as the TwoLand gap cause.

## Deliverable

- `main.py` + bundle (`agent/`, `data/` including `animal_with_pickups.json` + crop rollouts, vendored ortools)
- Local smoke: `scripts/smoke_test.sh`
- Submit: user-only via `scripts/smoke_and_submit.sh --submit "msg"`

## Scope boundaries

- **In scope:** one-land WSP, sell policy, local eval, user-requested submit
- **Out of scope unless asked:** re-wire TwoLand / `BUY_LAND`, agent-initiated Kaggle submit, RL, notebooks in the submission bundle

## Key references

- Rules: `docs/project_overview.md`
- TwoLand history / re-add: `docs/twolands/twoland_readd.md`, `docs/twoland/diagnosis_0911.md`
- Memory: `.cursor/memory/`
