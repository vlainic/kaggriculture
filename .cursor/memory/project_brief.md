# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation (Aug 15, 2026)

**Active stack:** one-land **handmade-chain assignment** + snake executor.

- Planner (`agent/planner.py`): CP-SAT **once at import**. Catalog = `data/handmade_dp_candidates.json` (~108 chains + idle). Decision vars = **per-zone chain counts** (tiles in a zone are interchangeable). Decode counts → tiles → `QueueItem` lists.
- Executor (`agent/executor.py`): snake routes, preamble, tile ops. Reads `script.TILE_QUEUES`. **Unchanged** by the assignment reformulation.
- Hook: `script.TILE_QUEUES = get_tile_queues(_build_tile_queues)` with handmade fallback if solve fails.

**Not this:** season-long weighted set packing (WSP). That was abandoned Aug 12 — see `docs/weighted_set_packing_failer.md`. Do not revive WSP.

## Deliverable

- `main.py` + bundle (`agent/`, `data/` including candidates + rollouts, vendored ortools)
- Local smoke: `scripts/smoke_test.sh`
- Submit: user-only via `scripts/smoke_and_submit.sh --submit "msg"`

## Scope boundaries

- **In scope:** assignment catalog, sell policy, local eval, user-requested submit
- **Out of scope unless asked:** WSP revival, agent-initiated Kaggle submit, RL, notebooks in the submission bundle

## Key references

- Rules: `docs/project_overview.md`
- Assignment notebook: `experiments/OneLand-Assignement-Handmade-Candidates.ipynb`
- WSP failure (do not resume): `docs/weighted_set_packing_failer.md`
