# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation (Aug 26, 2026)

**Active stack:** one-land **handmade-chain assignment** + snake executor + **layout catalog** + **dawn replan overhaul**.

- Zoning (`agent/zoning.py`): `FOUR` / `FIVE`; **`CURRENT = FIVE`**; `bind()` feeds planner/executor/market.
- Planner (`agent/planner.py`): CP-SAT at **import** (20s, `track_shed=True`) + dawn **replan from day 1** (15s, `track_shed=False`). Lock committed tiles (board + queue suffix); variables = empty/WEED replan-eligible only. INFEASIBLE preserves queues. Catalog prices on replan: live × `max(0.1, 1 + demand − opp_tiles/10)`.
- Executor: snake + stay-until-fed; runtime fert; no d=0 replan.
- Market: 50% floor + premium sell DP; wheat dawn buy / no early wheat sells; hire `min(2,…)` on h=0 and h=1.
- Smoke: `PLACE` may reuse empty pasture (no new BUILD required beyond first).

**Not this:** season-long weighted set packing (WSP). Abandoned Aug 12 — see `docs/weighted_set_packing_failer.md`.

## Deliverable

- `main.py` + bundle (`agent/`, `data/` including candidates + rollouts, vendored ortools)
- Local smoke: `scripts/smoke_test.sh`
- Submit: user-only via `scripts/smoke_and_submit.sh --submit "msg"`

## Scope boundaries

- **In scope:** assignment catalog, sell policy, local eval, user-requested submit
- **Out of scope unless asked:** WSP revival, agent-initiated Kaggle submit, RL, notebooks in the submission bundle

## Key references

- Rules: `docs/project_overview.md`
- Assignment notebook (CP-SAT, planner source): `experiments/OneLand-Assignement-Handmade-Candidates.ipynb`
- Mockup notebook (SCIP, no preamble): `experiments/Assignement-Master-Mockup.ipynb`
- WSP failure (do not resume): `docs/weighted_set_packing_failer.md`
