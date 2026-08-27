# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — 720-turn, two-player farming sim. Win = most bank coins at season end (ELO ladder).

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Entry:** `agent(obs) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Sept 30, 2026 (final submission)

## Goal

Heuristic/rule-based Python agent (no ML/RL pipeline) that wins on the ladder.

## Current implementation (Aug 27, 2026)

**Active stack:** one-land **DP-catalog assignment** + snake executor + **layout catalog** + **dawn replan** + **pickups-honest animal ops**.

- Zoning (`agent/zoning.py`): `FOUR` / `FIVE`; **`CURRENT = FIVE`**; `bind()` feeds planner/executor/market.
- Catalog (`agent/dp_catalog.py`): WIS chains with lag + insert variants; greedy multi-extra prefixes; no forced wheat/carrot before inserts.
- Planner (`agent/planner.py`): CP-SAT at **import** (20s, `track_shed=True`) + dawn **replan from day 1** (15s, `track_shed=False`). Lock committed tiles; variables = replan-eligible empties. Animals from **`animal_with_pickups.json`**. Ops cap = **`daily_tile_ops` only** (+ hire preamble). Catalog prices on replan: live × `max(0.1, 1 + demand − opp_tiles/10)`.
- Executor: snake + stay-until-fed; runtime fert; no d=0 replan.
- Market: 50% floor + premium sell DP; wheat dawn buy / no early wheat sells.
- Experiments: zonewise handmade/DP notebooks with **conservative** inter-zone cash (start − loss, no sells).

**Not this:** season-long weighted set packing (WSP). Abandoned Aug 12 — see `docs/weighted_set_packing_failer.md`.

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
