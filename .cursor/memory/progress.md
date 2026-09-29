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
3. Pickup-only §7.3 + formula `net_tile_ops` over-booked ops
4. Batching waves hid bisect; n=3 smoke gates were noise

**Do not:** re-enable Wave 5b `track_shed=True`; floor `conservative` at 0; treat plan “resubmit” as permission to rebuild overhaul. Good tip: **`d35bff5`**.

---

## Strategic status (Sep 29 — live = milos **THREELAND15** + zone value gate)

| Track | Status |
| --- | --- |
| **Live submission** | **`milos/`** — `CURRENT = MILOS_THREELAND15` (NW 5 + NE 5 + SW 5; `KAGGRI_LAYOUT` / `KAGGRI_SW=1`) |
| **Zone value gate** | Shipped — activate iff `obj − _zone_plan_cost >= 0`; buy-day break; Walk 2/3 retry; fail-open on missing obj |
| **Price forecast** | Config via `envconfig`; inventory walk; MIP caps; `drain_calib` |
| **`agent/` TwoLand** | Legacy; not live |
| **Dawn market** | NW HIRE×`NW_HANDS`; room sells; wheat → animals → seeds; fert dump; buy-day h0–h2 |
| **Wheat / shed** | Global buffer on buy; raw pickup; cap 100 + FERT dump |
| **Day-0 / replan** | `assigned` / `replan_set` writes; NE/SW buy-replans + Walk 2/3 |
| **Smoke analysis** | Layout-aware + `plot_zone_earnings_vs_cost` |
| **Competition submit** | User-only unless explicit ask |

**Plan chain:** NE dusk/buy-replan → SW expansion (`sw_land_expansion`) → 5-man three lands (`5-man_three_lands`) → **zone value gate** (`zone_value_activation_gate`). Details: `.cursor/memory/ne_expansion_and_forecast.md`.

## Sep 29 — zone value activation gate (KEEP)

| Change | Result |
| --- | --- |
| `mip.solve_zone` → `objective` | Surfaced on `SolveResult.zone_objectives` via twoland/oneland |
| `_zone_value_ok` / `_zone_activation_value_check` | `obj − cost >= min_net` (ship 0); None → `value_unknown` fail-open |
| Buy-day NE/SW loops | Gate + **break** on first fail; SW `wasted_land` if `n_active < 2` |
| Walk 2/3 | Same gate; no reject latch |
| Smoke | SW buy-day `hire10–12`; `hire13`/`hire14` `low_value`; NE fills 5 via Walk 2; reward ~147k one run (noise) |

**Verify by:** `active_sw` prefix, NE all-5, `low_value` logs — **not** final reward across multi-smoke.

## Sep 29 — ThreeLand15 + SW (KEEP)

| Change | Result |
| --- | --- |
| `MILOS_THREELAND15` | 5-man NW/NE/SW; `NUM_ACTIVE_HIRES=NW_HANDS`; `SW_MAX_ZONES=5`, `SW_BUY_LAST_DAY=18` |
| Buy-day replan | Solves **only** new-land workers; overage-clamped `max_time` |
| Ops +1 (code) | NW/NE/SW live caps +1 vs older `milos_zoning.md` heuristics — **do not** edit md for that without ask |
| `KAGGRI_SW` default `1` | SW on unless explicitly off |

## Sep 29 — price forecast + comparison notebook (KEEP)

| Change | Result |
| --- | --- |
| `fix_price_forecast` W1–W5 | Config intervals; self-glut; drain calibrator; live-quote fallback |
| `kpi.py` / `submission_nb` | Animal $/tile-day by product; violin `density_norm=count` |

## Strategic status (earlier — TWOLAND12 / OneLand 6-man)

Historical: TWOLAND12 was live briefly; before that `MILOS_ONELAND6` ~130k after shed-cap fix. See older KEEP sections below.

## Sep 26 — 6-man layout + wheat + shed-cap (KEEP)

| Change | Result |
| --- | --- |
| `MILOS_ONELAND6` | Zone VI north row; hire5; wheat global buffer; fert dump → ~130k smoke |

## Sep 23 — hire4 CARE + theo/act + dawn replan (KEEP)

CARE requires `fed_today`; theo/act parser; mid-season replan `track_shed=False`.

## Known issues

| Issue | Notes |
| --- | --- |
| **Shed cap 100** | Silent buy reject — watch `shed_total` |
| **Fib hire on SW** | Late zones (hire13/14) often fail value gate — intentional |
| **Buy-day cash starve** | Early `low_value` / busy fail is temporary; Walk 2/3 retries |
| **`milos_zoning.md` ops** | May lag code +1 on NW — heuristics doc, not ops source of truth |
| **Sept02 overhaul** | FAILURE — do not resume |
| Kaggle agent logs API | 403 often; replays work |

## What's left

1. Multi-smoke sanity on value gate (prefix length, NE fill, wasted_land rate)
2. Optional dusk SW profitability pre-check if wasted_land common
3. Do not Kaggle submit without ask
4. `agent/` TwoLand only if user re-points `main.py`

## Do not do unless asked

- Per-zone wheat buffer in `wheat_pickup_needed`
- Mid-day BUY wheat/animal/seed
- Treat missing `zone_objectives` as reject
- Latch buy-day `low_value` forever
- Judge gate by final reward noise (~3k vs ~130k+)
- Point `main.py` to `agent/` / Kaggle submit without ask
- Mid-zone walk-to-shed / Sept02 overhaul
- Edit `data/milos_zoning.md` for ops +1 without ask
