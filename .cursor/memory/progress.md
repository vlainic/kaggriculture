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

## Strategic status (Sep 30 — live = milos **THREELAND12** + V55 opener + abl defaults on)

| Track | Status |
| --- | --- |
| **Live submission** | **`milos/`** — `threeland12` (4 per land); `KAGGRI_V55_OPENER` default on; `KAGGRI_ABL_*` default **on** (land/catalog/cash) |
| **Zone activation** | Near-term `money < cost` (d0–1 spend + 1 hire); gate **`obj − hire`** only; cascade balance handoff +1 harvest day |
| **Concave sink** | `D_rem = D − committed − carried − opp`; `committed` from locked tile `harvest_units` (`replan_lock`) |
| **Selling** | EGG in greedy hourly seller + concave; GOOSE back in MIP + market |
| **Smoke** | `scripts/smoke_test.sh`; opener wheat whitelist step&lt;144; optional `SMOKE_SEEDS=pinned` |
| **Competition submit** | User-only unless explicit ask |

## Sep 30 (evening) — ablation, cash gates, goose, committed melon (KEEP)

| Change | Result |
| --- | --- |
| `KAGGRI_ABL_*` + `[abl]` log | Hourly land d6+, full catalog activations, full-bank cascade when cash flag on |
| MIP cash loosening | B1 near-term cost; B2 hire-only gate; G1 balance handoff; G4 walk3 every dawn |
| GOOSE + EGG concave + fert bonus | `wsp_plan` / exec can BUY/PLACE goose; egg revenue curve in solve |
| Wheat `sell_cap` vs feed segment | Feed at quote; town `D_rem` not consumed by feed virtual sold |
| Strawberry d6–8 | Opp haircut 0.25×D when EMA opp zero |
| `committed_harvest_units` | Dawn replan sees prior locked melon (etc.) in `[concave] committed=` |
| `greedy_premium_sells` + EGG | Eggs sell when price good, not only shed-room branch |

Plans (reference only): `d6-11_ablation_flags`, `mip_cash_loosening`, `goose_wheat_strawberry`, `v55_opener_tape`.

## Sep 30 — smoke us-vs-opp dashboard (KEEP)

| Change | Result |
| --- | --- |
| `parse_opp` / `parse_exec` / `parse_snap` | Opp workers from distinct `[opp]` actors; `live=` tiles; us qtiles workers/tiles; money-by-turn |
| `v55_logged_opponent` | `[opp_snap] … live=N`; `hands=` from action hands |
| `plot_us_vs_opp_daily` | 7 panels: ops → **tiles operated** → cash Δ + dawn money twin axis → workers → efficiency |
| Notebook md | Documents 7 panels + right-axis money |

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
| **Single-smoke reward vs V55** | Shop draw swings opp gross ~±40k — use pinned seeds only for deltas, not one-off margin |
| **Melon over-plant** | Mitigated by `committed` in `D_rem`; verify `[concave] committed=` grows on replan days |
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
