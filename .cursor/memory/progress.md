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

## Strategic status (Sep 25 — live = milos OneLand)

| Track | Status |
| --- | --- |
| **Live submission** | **`milos/`** — `main.py` → `milos.executor`; **`MILOS_ONELAND`** 25 tiles, farmer + 4 hires |
| **`agent/` TwoLand** | In-repo legacy; not dispatched by current `main.py` |
| **Dawn market** | h=0 only: wheat → animals → seeds; sells any hour (floor rules); HIRE×4 on OneLand |
| **Wheat padding** | `script.wheat_pickup_needed`: zone-count buffer `(zones_with_animals+1)//2` → shed PICKUP + dawn BUY + sell reserve |
| **Theo / smoke** | `forecast_day_counts`; **`compare_theo_act` 0 mismatches** post hire4 CARE gate + full-stack HARVEST sim; `parse_actor` `hand0=hireN` |
| **Dawn replan (milos)** | Live h0 d=1..28; `replan_lock` + WSP oneland; INFEASIBLE preserves queues |
| **Competition submission** | Local smoke only unless user asks |

## Sep 25 — wheat padding buffer (KEEP)

| Change | Result |
| --- | --- |
| Root need | Exact feed wheat left no margin for FEED→PLACE loss / multi-hand shed contention |
| `_count_zones_with_animals` | Count workers with live or place-today animals |
| `wheat_pickup_needed` | Target `need + (zones_with_animals+1)//2` minus inv WHEAT (not `need//2`) |
| Propagation | Shed PICKUP (`executor`), dawn BUY + `wheat_reserve` (`market`), sell_dp reserve via same total |
| Rejected | Flat +1 only; route-freeze on empty PLACE/FEED |

## Sep 23 — hire4 CARE loop + theo/act exec parser (KEEP)

| Change | Result |
| --- | --- |
| Root cause | FEED skipped (no wheat) but CARE still offered → sim no-op → hourly CARE in forecast (14× t22 theo d=24–25); op budget → missing WATER t23–25 |
| `tile_ops` + `executor` | CARE requires `fed_today` (align sim + game); no `animal_with_pickups.json` edit |
| `scripts/smoke_analysis/parse_actor.py` | `[exec]` attribution via `hand0=hireN` (farmer + hire1–3 aligned; hire4 fixed by CARE gate) |
| `compare_theo_act` | Post-fix: mismatches(>\|3\|)=0 on smoke |
| MIP | No change — one CARE op per calendar day in patterns already |

## Sep 23 — milos dawn replan + theo sim (KEEP)

| Change | Result |
| --- | --- |
| `milos/replan_lock.py` + `planner.replan` | Mid-season empty/WEED → CP-SAT; lock committed tiles; `track_shed=False`; smoke shows `[planner] replan` + mid `[wsp_plan]` |
| `plant_harvest_transfer` + `sim_apply` | One HARVEST = full `yield_units` stack (fixes theo `HARVEST HARVEST` on strawberry etc.) |
| `plot_zone_capacity` shed print | Only when shed theo ≠ act (no spurious PICKUP lines on tile-only mismatches) |

## Sep 22–23 — milos live hardening (KEEP)

| Change | Result |
| --- | --- |
| Live = milos | Bundle: `main.py` + `milos/` + `data/` + ortools |
| Endgame double HARVEST | `_endgame_harvested`; don’t revisit PLANT after DROP |
| Wheat buy h=0 only | Stopped mid-day buy → extra shed PICKUP |
| Buy order | h=0: **wheat → animals → seeds** (animals need PICKUP) |
| Theo est_ops | Dry-run tile_ops; drop unused animal×4+crop×1.5 return |
| sim_apply | BUILD before empty return; **full-stack plant HARVEST** via `plant_harvest_transfer` |
| Smoke capacity print | Totals + shed extras + per-tile mismatches |

## What works (live milos)

| Item | Notes |
| --- | --- |
| Farmer snake + tile_ops | Rollout-driven WATER/FERT/FEED/HARVEST; h=0 PASS for market |
| Dawn wheat/animal/seed buys | Only h=0; order wheat → animal → seed |
| Zone wheat padding | Buffer scales with animal-zone count; one function drives PICKUP + BUY + reserve |
| sell_dp + pricing | Premium daily quota + 1/h drip; staples dump via pricing |
| Owned-shed PICKUP/DROP | `_owned_shed_tiles` |
| Capacity diagnostics | `[theo]` vs act via smoke_analysis; **`compare_theo_act`**; animal **CARE gated on `fed_today`** |
| Dawn replan | Rewrites eligible tile queues; occupied tiles locked in MIP |

## Strategic status (Sep 21 — historical: TwoLand; milos was sandbox)

| Track | Status |
| --- | --- |
| **Two-land WSP** | Was LIVE — `CURRENT_SOLVER = twoland_wsp`, `CURRENT = TWO` |
| **Three-land WSP** | Opt-in `KAGGRI_LANDS=3` → `threeland_wsp` + THREE |
| **One-land WSP** | Available as `zonewise_wsp` + FIVE catalog; not CURRENT |
| **`milos/`** | Was farmer-only WSP + Gantt sandbox — **now live submission** |
| **Land buy** | Probe → `BUY_LAND_DAY`; NE $1k; clear next dawn after buy day |
| **Hiring** | `NUM_ACTIVE_HIRES` from healthy solved hands (excl. `DEAD_HANDS`); market hire batches + `dead=` log |
| **Dawn replan** | Lock commitments; WSP **`track_shed=False`**, `min_balance=0`; unbounded `cons`; **full** conservative handoff; INFEASIBLE/`picks0` → **skip zone, continue cascade** (not break) |
| **Mix balance** | `ZONE_OPS_MIX` default **on** — construction-time chain swap on fixed snakes; dead flags stripped |
| **Layout catalog** | `FOUR` + `FIVE` + `TWO` + `THREE`; **`CURRENT = TWO`**; pin **`NET_TILE_OPS = z.net_tile_ops`** |
| **Shed pickup** | **Only on owned center tiles** (`!= LOCKED`); see active_context |
| **Smoke analysis** | Layout-aware; + `plot_zone_capacity` (est_ops vs tile/MOVE/PASS) |
| **Episode download** | `scripts/download_submission_logs.sh` (replays default) |
| **Competition submission** | Local smoke only unless user asks |

## What works (live)

| Item | Notes |
| --- | --- |
| twoland_wsp + TWO smoke | ~**100–110k** typical vs random (opp≈0) |
| Owned-shed first preamble | hire1–4 pickup-first; `_step_to_owned_shed`; no PICKUP on LOCKED centers |
| WSP conservative cascade | Sep 1 semantics — unbounded cons, no cons≥min_balance |
| Cascade skip-not-break | `twoland`/`threeland`: INFEASIBLE/`picks0` → skip + locked handoff + `continue`; `zone_outcomes` on `SolveResult` |
| `DEAD_HANDS` ratchet N=3 | Streak on empty>0 non-ok; hire depth excludes dead; market/planner `dead=` |
| `ZONE_OPS_MIX` | Default on; construction mix after decode; BUDGET/FILLER/RESIZE stripped |
| `NUM_ACTIVE_HIRES` + hire batches | Healthy solved hands with work |
| smoke_analysis | Layout-aware; hands est_ops parse; zone capacity plot; PASS in stack |
| `[wsp_plan]` verbose | Smoke only (`KAGGRI_VERBOSE=1`); milos notebook accumulates → full farmer Gantt |
| Historical one-land strip | ~85k FIVE — superseded by TwoLand re-add |

## Sep 18 — post-submit bundle (KEEP)

| Change | Result |
| --- | --- |
| EOD hand log | Dawn tiles-needing-work snapshot + non-PASS count; later renamed `tiles_dawn=`/`executed=`/`laps=` (no `gap=` — misleading) |
| Strip dead flags | Removed `ZONE_OPS_BUDGET`, `ZONE_IDLE_FILLER`, `ZONE_TILE_RESIZE` (+ gated code) |
| Keep mix | `ZONE_OPS_MIX=1` construction chain swap; idle/tile-resize experiments stopped |
| Cascade skip | No more hard `cascade stop` starving later lands; log `cascade skip=` |
| Dead-zone ratchet | `STUCK_THRESHOLD=3` → `DEAD_HANDS`; recover on `ok` |
| 5×5 gate | ~110k mean [101–130]; `cascade_stop=0`; skips fire; streaks/dead fire |

## Sep 21 — milos + capacity diagnostics (KEEP)

| Change | Result |
| --- | --- |
| EOD KPI refine | `tiles_dawn=` / `executed=` / `laps=` — dropped apples-to-oranges `gap=` |
| `plot_zone_capacity` | Bars = tile ops + MOVE + PASS (+ reactive); dots = dawn est_ops; dash = net_tile_ops |
| `milos/wsp/` | Self-contained farmer MIP + prestart zone I; **no agent imports** |
| Gantt alphas | past 0.3 / unchanged future 0.6 / **delta tiles 1.0**; skip empty farmer delta |
| Smoke path | Still **agent/**; milos reads logs only |

## Sep 15 — owned-shed pickup (KEEP)

| Change | Result |
| --- | --- |
| Root cause | `PICKUP`/`DROP` **no-op on LOCKED** center tiles; SW/SE stay locked on TwoLand |
| Symptom | `adj=1 pos=(4,5) shed>0 inv=0` forever; hire3+ freeze; harvest dies |
| Fix | `_owned_shed_tiles` / `_step_to_owned_shed`; gate every pickup/drop; FIVE hire1–4 drop leading WEST/NORTH |
| Not done | Mid-zone walk-to-shed (Sept02 failure) |
| Smoke | ~74k freeze → ~**119k** |

## Sep 15 — TwoLand re-add (KEEP)

| Change | Result |
| --- | --- |
| `CURRENT = TWO`, `CURRENT_SOLVER = twoland_wsp` | Live again |
| Glue | Probe, `BUY_LAND_DAY`, NE LOCKED carve-out, uncap dawn wheat, hire-on-work |
| Smoke before shed fix | ~77k then ~74k (preamble give-up alone did not fix locked PICKUP) |

## Sep 14–15 — discard TwoLand then re-add (KEEP)

| Change | Result |
| --- | --- |
| Hard reset / one-land strip | Temporary; TwoLand re-added same day from `twoland_readd.md` |
| Kept through strip | `NUM_ACTIVE_HIRES`, hire batches, `TWO` catalog, WSP cash rules |
| Restored `scripts/smoke_analysis/` | Layout-aware |

## Known issues

| Issue | Notes |
| --- | --- |
| **Shed-adjacent ≠ owned** | Engine fact — always filter LOCKED before PICKUP/DROP |
| **Sept02 overhaul** | **FAILURE** — do not resume mid-zone walk-to-shed |
| hire9 INFEASIBLE late season | Skip-continue lets later zones solve; ratchet may mark stuck after 3 dawns |
| Idle hours 19–23 | Park filler / tile-resize killed (reward or cosmetic); bank MIX; stop chasing idle unless redesign |
| Kaggle agent logs API | 403 on ladder episodes; replays work |
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

1. Smoke-check wheat padding side effects (escapes, dawn shed WHEAT, FEED/PLACE inventory)
2. Keep theo/act aligned after behavior changes (`compare_theo_act`, smoke notebook)
3. Keep shed pickup gated on **owned** center tiles only
4. Do not Kaggle submit without ask
5. `agent/` TwoLand ladder work only if user re-points `main.py`

## Do not do unless asked

- Mid-day BUY wheat / animal / seed (breaks theo shed extras)
- Exact-match wheat need with **no zone buffer** (reopens FEED dry-outs)
- Freeze worker route / multi-hour PASS waiting for wheat or PLACE
- **`min(y,1)` in sim_apply HARVEST** — breaks theo vs live (one action, N units)
- Clear `_endgame_harvested` on DROP
- Re-enable `ZONE_OPS_BUDGET` / `ZONE_IDLE_FILLER` / `ZONE_TILE_RESIZE` or dawn live ownership moves
- Hard `break` cascade on WSP INFEASIBLE (use skip-continue)
- Mid-zone walk-to-shed / Sept02 overhaul / queue-lock chase
- Re-try static per-zone money caps (`money/N`, half-cash clamp, etc.)
- Runtime `bind()` layout switch mid-game
- Point `main.py` back to `agent/` without explicit ask
- Kaggle submit
- Treat `SHED_ADJACENT` alone as pickup-valid (must be **owned** / `!= LOCKED`)
- Commit `kaggle_logs/`
- Hardcode land2 workers in smoke/replay analysis
- Offering **CARE** when tile is not **`fed_today`** (same as sim) — inflates theo and burns hire op budget
- Treat `[wsp_plan]` delta payload as a full board without `accumulate_absolute`
