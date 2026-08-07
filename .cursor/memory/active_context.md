# Active Context

## Current focus

**Live set-packing plant agent is implemented and submitting.** Scope: `no_fert`, 3×3 NW tiles by shed, CP-SAT packing + snake executor, sell-all, seed buys. OR-Tools vendored for Kaggle sim (not on runtime).

## Recent changes (Aug 6, 2026)

1. **Agent modules:** `agent/rollouts.py`, `agent/planner.py`, `agent/executor.py`; thin `main.py` → `agent(obs)`.
2. **Data:** `data/crop_rollouts.json` shipped in submission (`no_fert` profiles).
3. **Submission packaging:** `submission.tar.gz` = `main.py` + `agent/` + `data/` + unpacked **cp311 manylinux** OR-Tools wheels (`scripts/vendor_ortools.sh`, `scripts/smoke_and_submit.sh`).
4. **Kaggle lessons:**
   - Single-file `main.py` failed earlier on bundling/`ortools` import; tar.gz + vendor is required.
   - Validation `90458708`: agent idle — planner returned empty / plan collapsed; fixed.
5. **Bugfixes that made the agent move and farm:**
   - Keep **full placement list** (not `dict[tile]` — that dropped early plantings).
   - Skip `PLANT` in pending once tile already has a plant (was stuck PASS instead of WATER).
   - CP-SAT: 8s limit, try incumbent on UNKNOWN, **greedy fallback** if empty; log status.
   - On replan: merge new empty-tile solves with **kept** future plantings on occupied tiles.
6. Local smoke vs `random`: ~**21k** reward, `DONE` (after fixes; was ~2k when only late melons ran).

## Active decisions

- Profile: **`no_fert` only** (no fert/hire/land/animals this pass).
- Planner: weighted set packing `(tile, crop, plant_day)`; live `obs["market"]["prices"]`; ≤16 tile ops/day; snake path 8 moves + ops ≤ 24.
- Replan: `hour == 0` when no plan yet **or** any tile harvests today.
- Submit as **tar.gz** with vendored OR-Tools (sim is Python **3.11**, no pip install).
- Prefer thin `main.py` + `agent/` modules (not inlined single file).
- Do **not** add tests/eval/`.venv` unless user asks.

## Open questions / follow-ups

1. Confirm ladder replay after latest submit shows early PLANT/WATER (not idle).
2. Op budget / day-0 stagger still from notebook heuristic — tune weights vs live prices.
3. Fertilizer / hires / more tiles — later phases.
4. Whether greedy-only (no OR-Tools) is enough if vendor size/time becomes painful.

## Immediate next steps

1. Re-submit with current planner/executor fixes; check agent log + replay.
2. Tune crop mix / replan cadence if ladder ELO is weak.
3. Optionally prune unused OR-Tools deps (pandas weight) to shrink tar.

## Key files

- `main.py`, `agent/{rollouts,planner,executor}.py`, `data/crop_rollouts.json`
- `scripts/vendor_ortools.sh`, `scripts/smoke_and_submit.sh`
- `docs/weighted_set_packing.md`, `experiments/FarmerOnly-PlantOnly-NoFert.ipynb`
