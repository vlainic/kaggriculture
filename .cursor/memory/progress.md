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

## Strategic status (Sep 29 — live = milos **TWOLAND12** + forecast fix)

| Track | Status |
| --- | --- |
| **Live submission** | **`milos/`** — `CURRENT = MILOS_TWOLAND12` (NW + 6 NE zones, dusk NE buy + h1 buy-replan) |
| **Price forecast** | Config via `envconfig`; inventory walk; MIP `locked_counts` + caps; `drain_calib` (plan `fix_price_forecast`, all waves done) |
| **`agent/` TwoLand** | Legacy; not live |
| **Dawn market** | NW HIRE×5; room sells; wheat → animals → seeds; fert dump; buy-day h0–h2 buys |
| **Wheat / shed** | Global buffer on buy; raw pickup; cap 100 + FERT dump |
| **Day-0 / replan** | `assigned` / `replan_set` writes; NE Walk 2 + `replan_after_buy` |
| **Replay analysis** | `kpi.py` animal $/tile-day keyed by product; `submission_nb.revenue_per_tile_day_by_product` for stale caches |
| **Notebooks** | `submission_comparison` — violin `density_norm=count`; §5 crops + animals |
| **Competition submit** | User-only unless explicit ask |

**NE / forecast plan chain (implemented):** `ne-land_minimal_trigger` → `cash_trigger_for_ne` (superseded) → `fix_ne_rollback_bugs` → `robust_ne_buy` (+ busy-gate intent). Details: `.cursor/memory/ne_expansion_and_forecast.md`.

## Sep 29 — price forecast + comparison notebook (KEEP)

| Change | Result |
| --- | --- |
| `fix_price_forecast` W1–W5 | No forecast crash on MELON profile; real config intervals; self-glut in MIP; drain calibrator |
| `main.py` `agent(obs, config)` | Kaggle passes `configuration` into agent |
| `kpi.py` `crop_tile_days.get(prod)` | Animal products in $/tile-day when summaries refreshed |
| `submission_nb.revenue_per_tile_day_by_product` | §5 chart shows EGG/MILK/WOOL without re-summarize |
| Violin normalization | Width ∝ n per outcome bucket (fair A vs B visual) |

## Strategic status (Sep 26 — milos OneLand **6-man**, historical)

| Track | Status |
| --- | --- |
| **Was live** | `MILOS_ONELAND6` (25 tiles, farmer + **5** hires) — superseded by TWOLAND12 |
| **Smoke** | ~**130k** vs random after shed-cap fix |

## Sep 26 — 6-man layout + wheat + shed-cap (KEEP)

| Change | Result |
| --- | --- |
| `MILOS_ONELAND6` | Zone VI north row (idx 9/14/19/24); hire5; `TWOFOLD_HIRE`; `NUM_ACTIVE_HIRES=NUM_HIRES` |
| `_build_from_solver` / `apply_replan` | Write all `assigned` tiles — hire5 got queues; replan no longer skips orphan tiles |
| Wheat buffer move | Global buffer only in `total_wheat_feed_need`; pickup no longer races |
| Fert dump + make-room | Stops silent dawn buy fails when shed full of FERT; smoke ~130k, WHEAT at h=1 restored |
| Root cause of uniform starvation | `sum(shed)>=100` rejects buys — not a per-zone pickup race |

## Sep 25 — wheat padding buffer (SUPERSEDED placement)

Zone buffer in `wheat_pickup_needed` was correct intent for 5-man margin; on 6-man it became a FCFS race. **Keep global buffer on buy; pickup = raw need.**

## Sep 23 — hire4 CARE loop + theo/act exec parser (KEEP)

| Change | Result |
| --- | --- |
| Root cause | FEED skipped (no wheat) but CARE still offered → sim no-op → hourly CARE in forecast |
| `tile_ops` + `executor` | CARE requires `fed_today` |
| `parse_actor` / `compare_theo_act` | hand0=hireN attribution; post-fix mismatch≈0 |

## Sep 23 — milos dawn replan + theo sim (KEEP)

| Change | Result |
| --- | --- |
| `replan_lock` + `planner.replan` | Mid-season empty/WEED → CP-SAT; `track_shed=False`; INFEASIBLE keeps queues |
| `plant_harvest_transfer` | One HARVEST = full yield stack in sim |

## Sep 22–23 — milos live hardening (KEEP)

| Change | Result |
| --- | --- |
| Endgame double HARVEST | `_endgame_harvested` |
| Dawn buys h=0 only | wheat → animals → seeds |
| Owned-shed gate | `_owned_shed_tiles` |

## What works (live milos 6-man)

| Item | Notes |
| --- | --- |
| Six snakes + tile_ops | hire5 north row; twofold spawn bind |
| Dawn wheat/animal/seed | Room sells first if needed; then buys |
| Fert shed hygiene | Cap dump every market hour |
| Wheat buy vs pickup | Global buffer on buy; raw on pickup |
| Capacity / snap | `[theo]`; `shed_total=` in snap |
| Dawn replan | Eligible empties; write by tile assigned |

## Strategic status (Sep 21 — historical: TwoLand)

See older sections below for TwoLand / Sept02 / diagnosis history.

## Known issues

| Issue | Notes |
| --- | --- |
| **Shed cap 100** | Silent buy reject — watch `shed_total`; dump low-value staples |
| **Prestart still 5-man solved_workers** | Tile chains OK by index; optional regen under 6-man |
| **Shed-adjacent ≠ owned** | Always filter LOCKED |
| **Sept02 overhaul** | FAILURE — do not resume |
| Kaggle agent logs API | 403 often; replays work |

## What's left

1. Optional regen `milos/wsp/prestart.json` for 6-man zone/ops
2. Keep theo/act + shed_total after market changes
3. Do not Kaggle submit without ask
4. `agent/` TwoLand only if user re-points `main.py`

## Do not do unless asked

- Per-zone wheat buffer in `wheat_pickup_needed`
- Mid-day BUY wheat/animal/seed
- Rely on price-floor-only FERT sells under 6-man animal density
- Build queues via `WORKER_TILES[solved_worker]` when layout ≠ prestart workers
- Freeze routes waiting for wheat/PLACE
- CARE without `fed_today`
- Point `main.py` to `agent/` / Kaggle submit without ask
- Mid-zone walk-to-shed / Sept02 overhaul

