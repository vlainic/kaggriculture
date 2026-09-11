# Progress

## FAILURE — Sept02 overhaul (DO NOT RELITIGATE)

**Verdict: FAILURE.** The Sept02 all-waves / §7 overhaul and the follow-on regression-recovery re-ladder **broke the live agent**. User discarded the overhaul direction.

| Metric | Pre-overhaul (`d35bff5`) | After overhaul / recovery |
| --- | ---: | ---: |
| Smoke median (twoland vs random) | **~85–87k** | **~34k** merged; recovery stuck **~66–69k** |
| Outcome | Working two-land WSP | Mass INFEASIBLE / under-harvest; never restored BASE |

**Root causes (confirmed):**
1. `conservative` floored at 0 + `cons >= min_balance` on spend-only ledger → cascade INFEASIBLE
2. `track_shed=True` on WSP replan put W/F buys into conservative `spend_terms`
3. Pickup-only §7.3 + formula `net_tile_ops` over-booked ops (formula omitted intra-zone route laps; pin to empirical caps did not restore BASE on n=3)
4. Batching waves hid bisect; n=3 smoke gates were noise (within-step spreads > wave deltas)

**Do not:**
- Re-enable Wave 5b `track_shed=True` / fert pipeline as “just missing a knob”
- Floor `conservative` at 0 or put `min_balance` on `cons`
- Treat plan todos like “resubmit” / “re-ladder 5b” as permission to rebuild the overhaul
- Ship `_formula_net_tile_ops` until `_route_move_cost` (intra-zone) is wired and validated at ≥30 episodes

**Recovery pointer:** good tip is **`d35bff5`** (`Enhance replay analysis…`). Local backup of broken stack: branch **`backup/sept02-recovery`** (local only until pushed). Overhaul plans under `.cursor/plans/sept02_*` are historical autopsy, not a roadmap to re-run.

---

## Strategic status (restore target = pre-Sept02)

| Track | Status |
| --- | --- |
| **Two-land WSP** | **Restore / keep at `d35bff5` semantics** — `twoland_wsp.py`; `CURRENT = TWO`; probe hire5 → buy NE |
| **One-land WSP** | Flip `CURRENT_SOLVER = zonewise_wsp`, `CURRENT = FIVE` |
| **Chain assignment (zonewise)** | Live — `dp_catalog.build_catalog`; ~107k smoke on FIVE |
| **Solver backend** | **`CURRENT_SOLVER = "twoland_wsp"`** |
| **Land buy** | Probe: hire5 feasible + ≥$1k conservative → `BUY_LAND` next dawn |
| **Hiring** | `NUM_ACTIVE_HIRES` from solved prefix; batches per `two_lands.md` |
| **Dawn replan** | Lock commitments; WSP **`track_shed=False`**, `min_balance=0`; unbounded `cons`; **full** conservative handoff (no zone budget clamp); INFEASIBLE → break cascade |
| **Layout catalog** | `FOUR` + `FIVE` + **`TWO`**; **`CURRENT = TWO`**; pin **`NET_TILE_OPS = z.net_tile_ops`** (hand table) |
| **Episode download** | `scripts/download_submission_logs.sh` (replays default) |
| **Replay analysis** | `scripts/replay_analysis/` + `scripts/summarize_replays.sh` → `<id>.json` |
| **Competition submission** | Local smoke only unless user asks |

## What works (pre-overhaul baseline)

| Item | Notes |
| --- | --- |
| twoland_wsp smoke @ `d35bff5` | ~**85–87k**; land2 buy ~d8; up to 9 hires when cascade allows |
| Land2 probe | hire5 only on probe day; no queue commit until buy morning |
| TWO layout | Zones I–X; land1 = FIVE geometry; land2 NE snakes |
| WSP conservative cascade | Sep 1 semantics — unbounded cons, no cons≥min_balance |
| download_submission_logs.sh | Replays bulk; `--with-logs` optional |
| replay_analysis + summarize_replays.sh | Batch JSON; KPIs; slim default |
| **Submission analysis notebooks** | `submission_nb.py` + `submission_analysis.ipynb` + `submission_comparison.ipynb` — self-contained (download/summarize in-notebook) |
| Corrected A/B ONE vs TWO | 55934103: 42.1% / 64k; 55938405: 51.2% / 71k |

## Known issues

| Issue | Notes |
| --- | --- |
| **Sept02 overhaul** | **FAILURE** — see banner above; do not resume |
| hire9 INFEASIBLE late season | Partial prefix OK; common after land2 expansion |
| Kaggle agent logs API | 403 on ladder episodes; replays work |
| WSP vs zonewise gap | ~87k twoland vs ~107k zonewise one-land |
| hire5 probe UNKNOWN | Occasional 5s timeout; retry next dawn |
| TwoLand conversion leaks (analysis) | post-NE ops/weed collapse — see `docs/twoland/diagnosis_0911.md` |
| Static NW zone budget caps | **REJECTED** (ladder): no-cap > half-handoff > money/N |

## Sep 11 — TwoLand diagnosis + budget A/B (KEEP)

| Finding | Result |
| --- | --- |
| A/B 55934103 vs 55938405 | TwoLand ~+7k only; writeup `docs/twoland/diagnosis_0911.md` |
| Root cause (strong) | NE buy → ops_util crash → occupied% lag → weeds; opponent expands without PASS spike |
| Glut (melon/wool) | Ruled out |
| Hard NW spend caps | no-cap rating ~555–561; `min(day_start/2, handoff)` ~533; `day_start/n_hands` ~508 — **keep full handoff** |
| Next | route-cost / NE-hand PASS / early-buy trigger — not softer static caps |
| Tooling | noise_std fallback, unexplained_delta, wool rv/q zero-fill — fix before trusting beyond_noise |

## Sep 4–9 — recovery attempt then abandon

| Step | Median / result |
| --- | --- |
| Hotfix (unbounded cons, track_shed off) on stacked tree | ~33k — not enough |
| Re-ladder W0–5a from `d35bff5` | peak wave ~73k; final ~69k |
| Pin empirical `net_tile_ops` A/B | ~66k — **no** jump to BASE (n=3 noise) |
| Wave 5b track_shed + fert | ~27–34k — deferred / abandoned |
| **User decision** | **Revert to pre-overhaul; overhaul = FAILURE** |

## Sep 2 session (replay analysis — KEEP)

| Change | Result |
| --- | --- |
| `scripts/replay_analysis/` | Per-game + batch JSON; KPIs |
| `sold_units()` / `potential_yield` / us_index fix | Corrected A/B rollups |
| A/B 55934103 vs 55938405 | TwoLand +11% bank, +9pp win |

## Sep 9 session (submission analysis notebooks — KEEP)

| Change | Result |
| --- | --- |
| `experiments/submission_nb.py` | `load_summary`, `day_band`, `ensure_summary`, `ensure_episode_skills`, land/anomaly helpers |
| `submission_analysis.ipynb` | Score scatter (me vs opp, color=initial skill), day bands, land table + cash/score scatter, anomalies |
| `submission_comparison.ipynb` | Win/loss half-violins, KPI-delta table, post-NE alignment, MELON/WOOL glut |
| In-notebook fetch | No shell prereq; `GetEpisode` → `initialScore` cached per submission |
| Key A/B read | TwoLand post-NE occupied % stall; ops_util alignment plot unreliable (negative = bug) |

## Sep 2 session (two-land WSP @ pre-overhaul — KEEP)

| Change | Result |
| --- | --- |
| `TWO` + `twoland_wsp` | ~87k smoke |
| `BUY_LAND_DAY` / `NUM_ACTIVE_HIRES` | Planner + market glue |

## Sep 1 session (WSP conservative handoff — KEEP)

| Change | Result |
| --- | --- |
| Conservative cascade in `zonewise_wsp` | ~81–85k one-land |

## What's left

1. Post-NE ops crash: `_route_move_cost` wiring and/or NE-hand PASS routing (`by_worker`)
2. Early-NE-buy / trigger-based NW→NE reserve (day-based) — not static fraction of bank
3. Fix submission comparison tooling bugs (noise_std, unexplained_delta)
4. Do not Kaggle submit without ask

## Do not do unless asked

- **Re-run Sept02 overhaul / regression-recovery plan**
- Re-try static per-zone money caps (`money/N`, half-cash clamp, etc.)
- Buy SW/SE (land 3–4) in twoland_wsp
- Runtime `bind()` layout switch mid-game
- Kaggle submit
- Commit `kaggle_logs/`
