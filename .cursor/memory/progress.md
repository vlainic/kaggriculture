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

## Strategic status (Sep 15 — live = one-land)

| Track | Status |
| --- | --- |
| **One-land WSP** | **LIVE** — `CURRENT_SOLVER = zonewise_wsp`, `CURRENT = FIVE` |
| **Two-land WSP** | **STRIPPED** — stub `twoland_wsp.py`; no buy/probe/LAND* constants; re-add via `docs/twolands/twoland_readd.md` only |
| **Solver backend** | **`CURRENT_SOLVER = "zonewise_wsp"`** |
| **Land buy** | **Off** in live agent |
| **Hiring** | `NUM_ACTIVE_HIRES` from solved prefix; market hire batches kept |
| **Dawn replan** | Lock commitments; WSP **`track_shed=False`**, `min_balance=0`; unbounded `cons`; **full** conservative handoff; INFEASIBLE → break cascade |
| **Layout catalog** | `FOUR` + `FIVE` + `TWO`; **`CURRENT = FIVE`**; pin **`NET_TILE_OPS = z.net_tile_ops`** |
| **Smoke analysis** | `scripts/smoke_analysis/` restored; layout-aware (`layout.py`) |
| **Episode download** | `scripts/download_submission_logs.sh` (replays default) |
| **Replay analysis** | `scripts/replay_analysis/` + `scripts/summarize_replays.sh` → `<id>.json` |
| **Competition submission** | Local smoke only unless user asks |

## What works (live)

| Item | Notes |
| --- | --- |
| zonewise_wsp + FIVE smoke | ~**85k** post-strip (`scripts/smoke.txt`) |
| WSP conservative cascade | Sep 1 semantics — unbounded cons, no cons≥min_balance |
| `NUM_ACTIVE_HIRES` + hire batches | Kept from TwoLand era; works on FIVE |
| TWO layout catalog | Still in `zoning.py` (unused) |
| download_submission_logs.sh | Replays bulk; `--with-logs` optional |
| replay_analysis + summarize_replays.sh | Batch JSON; KPIs; slim default |
| **smoke_analysis** | Layout-aware KPIs/plots; re-run notebook after agent layout flips |
| **Submission analysis notebooks** | `submission_nb.py` + analysis/comparison nbs |
| Historical twoland @ `d35bff5` | ~85–87k smoke; land2 buy ~d8 — not live |

## Sep 14–15 — discard TwoLand runtime, return to one-land (KEEP)

| Change | Result |
| --- | --- |
| Hard reset / discard thrash | Parity + prior TwoLand recovery paths abandoned (3rd discard) |
| Strip plan | `one-land_twoland_strip_*` — remove twoland dispatch + buy glue |
| `CURRENT = FIVE`, `zonewise_wsp` | Live one-land |
| Stub `twoland_wsp.py` | File kept, not imported |
| Removed | `BUY_LAND_DAY`, `_land2_owned`, `land_owned`/`buy_morning`, `write_all_solved`, `LAND1_*`/`LAND2_*`, `SolveResult.buy_land` |
| Kept | `NUM_ACTIVE_HIRES`, hire batches, `TWO` catalog, WSP cash rules |
| Restored `scripts/smoke_analysis/` | Lost on reset; pulled from pre-reset commit + layout-aware fix |

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

1. Stabilize / ladder one-land as user asks
2. TwoLand re-add only from explicit plan + `docs/twolands/twoland_readd.md` (post-NE ops crash still the real gap)
3. Fix submission comparison tooling bugs (noise_std, unexplained_delta) when doing A/B again
4. Do not Kaggle submit without ask

## Do not do unless asked

- **Re-wire `twoland_wsp` / `BUY_LAND` / TWO as live CURRENT**
- **Re-run Sept02 overhaul / queue-lock chase / OneLand-parity plan**
- Re-try static per-zone money caps (`money/N`, half-cash clamp, etc.)
- Runtime `bind()` layout switch mid-game
- Kaggle submit
- Commit `kaggle_logs/`
- Hardcode land2 workers in smoke/replay analysis
