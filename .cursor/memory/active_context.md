# Active Context

## Current focus (Sep 9, 2026)

**Sept02 overhaul = FAILURE.** Do not resume waves, “fix forward” 5b, or re-ladder from those plans.

Working direction: restore / stay on **pre-overhaul two-land WSP** at commit **`d35bff5`** (~85–87k smoke). Broken stack kept locally as **`backup/sept02-recovery`** (not on GitHub until pushed).

### Status

| Item | State |
| --- | --- |
| Live agent target | `d35bff5` semantics (`twoland_wsp` + `CURRENT = TWO`) |
| Sept02 all-waves plan | **FAILED** — collapsed ~87k → ~34k |
| Regression recovery plan | **FAILED to restore BASE** — stuck ~66–69k; abandoned |
| Next agent work | Replay-KPI fixes only (hand3 routing, crop mix, weeds) — **not** Sept02 §7 waves |

### Confirmed anti-patterns (from failure)

- Floor `conservative` at 0 / `cons >= min_balance`
- `track_shed=True` on WSP replan with W/F in conservative spend
- Gate strategy on n=3 smoke (noise > wave deltas); prefer ≥30 episodes
- Batch multiple waves in one commit

### What still stands (pre-overhaul)

1. **Two-land WSP** — probe hire5 → `BUY_LAND` → cascade VI–X
2. **Layout TWO** — 50 tiles; hand-calibrated `net_tile_ops`
3. **Planner / market glue** — `BUY_LAND_DAY`, `NUM_ACTIVE_HIRES`, hire batches
4. **Replay analysis** — `scripts/replay_analysis/` + us_index-correct A/B (ONE 42%/64k vs TWO 51%/71k)

### Immediate next steps

1. Finish revert: `main` / working tree = `d35bff5` (user intent)
2. Optional push `backup/sept02-recovery` so GH shows the failed branch
3. Agents never submit without explicit ask
4. Do **not** implement `.cursor/plans/sept02_*` again unless user explicitly reopens that work
