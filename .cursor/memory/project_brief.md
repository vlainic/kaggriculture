# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs) -> {"farmer", "hands", "market"}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation status (Aug 12, 2026)

**Active codebase:** legacy **weighted set packing (WSP)** agent — CP-SAT season planner + snake executor for 1 land, 4 workers.

**Strategic status:** WSP approach **failed and is not being advanced**. See `docs/weighted_set_packing_failer.md`. Replacement architecture not chosen yet.

## Deliverable

- `main.py` + minimal Kaggle bundle (`agent/`, `data/`, vendored ortools if needed)
- Local smoke: `scripts/smoke_test.sh`
- Submit: user-only via `scripts/smoke_and_submit.sh --submit "msg"`

## Scope boundaries

- **In scope:** new agent strategies, local eval, user-requested submit
- **Out of scope unless asked:** continuing WSP/CP-SAT season planner, agent-initiated Kaggle submit, RL training, notebooks in submission bundle

## Key references

- Rules: `docs/project_overview.md`
- WSP failure: `docs/weighted_set_packing_failer.md`
- Original WSP idea (9-tile scale): `docs/weighted_set_packing.md`
- Strategy archive: `docs/claude_chat.md`
