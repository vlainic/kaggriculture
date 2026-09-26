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

## Strategic status (Sep 26 — live = milos OneLand **6-man**)

| Track | Status |
| --- | --- |
| **Live submission** | **`milos/`** — `CURRENT = MILOS_ONELAND6` (25 tiles, farmer + **5** hires) |
| **Ops caps** | farmer/hire1–5: **19/16/16/17/17/14** |
| **`agent/` TwoLand** | Legacy; not live |
| **Dawn market** | HIRE×5; room sells; wheat → animals → seeds; fert dump each hour |
| **Wheat** | Buy: raw feed sum + **one** global zone buffer; PICKUP: raw need only |
| **Shed** | Cap 100; hourly FERT dump to ≤`max(10, fert need)`; `[snap] shed_total=` |
| **Day-0 / replan write** | Queues from `result.assigned` / `replan_set` (not worker×WORKER_TILES) |
| **Smoke** | ~**130k** vs random after shed-cap fix; FEED days 1–28 |
| **Competition submission** | Local smoke only unless user asks |

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

