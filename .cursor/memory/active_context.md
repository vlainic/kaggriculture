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

### Submission analysis notebooks (Sep 9 — DONE)

Self-contained notebooks on top of existing `kaggle_logs/<id>/<id>.json` (no agent/pipeline changes):

| Artifact | Role |
| --- | --- |
| `experiments/submission_nb.py` | Shared loaders + `ensure_summary` / `ensure_episode_skills` |
| `experiments/submission_analysis.ipynb` | Single-submission deep-dive + noise floor |
| `experiments/submission_comparison.ipynb` | OneLand vs TwoLand A/B (defaults 55934103 / 55938405) |
| `experiments/replay_analysis.ipynb` | **Unchanged** — single-episode viewer |

Notebook UX: run all cells — auto-download replays + summarize if JSON missing. `US_NAME` in config cell. Initial TrueSkill per episode via Kaggle `GetEpisode` → cached `kaggle_logs/<id>/episode_skills.json`.

**Useful findings from comparison (55934103 vs 55938405):**
- Post-NE buy: **occupied %** drops ~40% day+1 and only recovers to ~70% vs OneLand ~90% — conversion stall (hand3 / route cost hypothesis).
- **Ops utilization alignment plot** can show negative values — NaN/missing-day artifact; trust **occupied %**, not left panel.
- **idle_empty** = empty-tile×turn sum over 720 turns (~3k–7k/ep), not PASS count.
- **noop_ops** ~6/ep = wasted unit actions, not passes.
- WOOL glut: OneLand fill/rv/q bimodal; TwoLand cleaner.

### Immediate next steps

1. Finish revert: `main` / working tree = `d35bff5` (user intent)
2. Optional push `backup/sept02-recovery` so GH shows the failed branch
3. Agent fixes from replay KPIs (hand3 routing, post-buy conversion) — use submission notebooks to track
4. Agents never submit without explicit ask
5. Do **not** implement `.cursor/plans/sept02_*` again unless user explicitly reopens that work
