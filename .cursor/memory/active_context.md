# Active Context

## Current focus (Aug 12, 2026)

**Weighted set packing (WSP) + CP-SAT season planner is abandoned.** Do not extend `agent/planner.py` CP-SAT set packing, incremental patch fixes, or planner–executor coupling work unless the user explicitly starts a new approach.

Full post-mortem: [`docs/weighted_set_packing_failer.md`](../../docs/weighted_set_packing_failer.md)

**Repo state:** `main.py` still delegates to the WSP agent (`agent/planner.py` + `agent/executor.py`). Treat as **legacy / reference implementation**, not the strategic direction. Next agent architecture TBD by user (likely short-horizon heuristics, per-zone rules, or small rolling MILP — not season-long CP-SAT).

## What happened (Aug 12 session summary)

Extended debugging after Aug 11 “~60k SHED_DOOR fix” optimism:

1. **Live analysis** (`experiments/live_analysis.ipynb`) — PASS counts, per-zone empty tiles, money charts; exposed farmer zone underuse and snap timing bugs.
2. **Planner fixes** — empty tiles only; one lifecycle per tile per solve; cash constraint; `MAX_ACTIVE_PER_WORKER_DAY` tried then **reverted** (ops/day is the right cap).
3. **Executor fixes** — plan-following (no skip on blocked tiles); h=0 seed timing (`market-hour` PASS); conditional defer; eod DROP + h=23 sell from inv; `[snap]` zone-empty logging.
4. **Outcome** — smoke rewards swung **~5k–51k** depending on patch; never stable ~50k+ with low PASSes. Farmer zone often **6–8 empty tiles until late season**. **8–15 PASSes/worker/day** persisted (mostly `route=done` + daily `market-hour` for re-hire).

## Why WSP failed (one paragraph)

CP-SAT optimized a **static season calendar** (~8,775 candidates, 3–6s day-0 solve) with **tile ops ≠ executor turns** (movement, shed trips, h=0 market-before-farmer, inventory). Planner–executor drift required endless patches. **Not scalable** to 2–3 lands (candidate explosion + 60s overage cap).

## Do NOT continue (unless user asks)

- Season-long CP-SAT set packing on more tiles/lands
- More `FARMER_DAY0_BONUS` / zone weight hacks in planner
- Incremental executor patches to “make WSP work”
- Assuming Aug 11 ~59k smoke is representative of WSP health

## Still valid from Aug 11 work

- **`SHED_DOOR = (4,4)`** lock-escape for hire2/hire3 PICKUP — real bug fix, keep in any future executor.
- **`scripts/smoke_test.sh`** local only; **`smoke_and_submit.sh --submit`** for humans; agents never submit without explicit request.
- **`data/crop_rollouts.json`**, **`data/animal_rollouts.json`** — useful offline templates regardless of planner choice.
- **`experiments/live_analysis.ipynb`** — essential for diagnosing runs from Kaggle logs.

## Key files

| File | Status |
| --- | --- |
| `docs/weighted_set_packing_failer.md` | **Source of truth for WSP failure** |
| `docs/weighted_set_packing.md` | Original 9-tile idea (notebook scale only) |
| `agent/planner.py`, `agent/executor.py` | Legacy WSP stack — do not invest further by default |
| `experiments/live_analysis.ipynb` | Diagnostics — still useful |
| `submissions/260812_*` | WSP iteration logs |

## Immediate next steps

**None for WSP.** Wait for user direction on replacement architecture.
