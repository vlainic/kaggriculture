# NE / SW land expansion, price forecast, and zone value gate

Historical plans live under `.cursor/plans/`. **Live code:** `milos/zoning.py` → `CURRENT = MILOS_THREELAND15` (default), `NUM_ACTIVE_HIRES = NW_HANDS`, SW on via `KAGGRI_SW=1`.

## Live layout (Sep 29)

| Layout | Env | Hands |
| --- | --- | --- |
| **THREELAND15** (live) | `KAGGRI_LAYOUT=threeland15` | NW farmer+hire1–4, NE hire5–9, SW hire10–14 |
| THREELAND18 | `threeland18` | 6-man NW + NE + SW |
| TWOLAND12 | `twoland12` | NW + NE only (historical live) |

Buy-day NE/SW replans solve **only** that land’s workers with full money and overage-clamped `max_time`.

---

## Zone value activation gate — `zone_value_activation_gate` (completed Sep 29)

**Problem:** Feasible/cash-OK SW zones (esp. hire14) can have solver `obj` below hire+spend over remaining days.

**Rule:** accept new NE/SW zone iff `obj − _zone_plan_cost >= min_net` (ship `min_net=0`).
- `obj` = CP-SAT harvest objective (gross of hire/spend).
- `cost` = full-horizon seed/animal spend + `HAND_DAILY_COST × D`.
- Missing obj → fail open (`value_unknown`).
- Buy-day: break on first reject (prefix). Walk 2/3 retries (no latch).
- SW buy-day: log `wasted_land` if `n_active < 2`.

**Shipped in:** `milos/wsp/{mip,twoland,oneland,types}.py`, `milos/planner.py`.

**Verify:** `active_sw` stops before hire14; NE fills all 5; not final reward.

---

## SW expansion — `sw_land_expansion` + `5-man_three_lands` (completed)

**Shipped:**
- Dusk `schedule_sw_buy_at_dusk`: NE full+bound, cash ≥ 4000, overage ≥ 40, day 8..18.
- `replan_after_buy_sw` + Walk 3 `_activate_next_sw`; rollbacks via `dawn_sw_bound_handoff`.
- THREELAND15 5-man rosters; `SW_MAX_ZONES=5`, `SW_BUY_LAST_DAY=18`.
- Ops +1 in code for live three-land caps (do not edit `milos_zoning.md` for that unless asked).

---

## NE buying — plans implemented (order of evolution)

### 1. `ne-land_minimal_trigger` (completed)

**Goal:** Add NE as six zones (VII–XII) that activate one at a time after NW is running.

**Shipped:**
- `MILOS_TWOLAND12` layout, `NW_WORKERS` / `NE_WORKERS`, Walk 1/2, early VII-tied buy path.
- Pain: `BUY_LAND_DAY` tied to VII CP-SAT → nondeterministic never-buy.

### 2. `cash_trigger_for_ne` (completed, later superseded)

Dawn cash trigger → superseded by dusk + buy-day joint replan (`robust_ne_buy`).

### 3. `fix_ne_rollback_bugs` (completed)

`NE_DUE_DAY` + `dawn_ne_bound_handoff`; `_write_ne_activation` only writes assigned tiles.

### 4. `lower_ne_busy_gate` (intent absorbed)

Land buy via dusk; Walk 2 when owned with `busy_day0 < 1` + cash + solver + **zone value gate**.

### 5. `robust_ne_buy` (completed)

- `_safe_price_of`; dusk `schedule_ne_buy_at_dusk` (`NE_BUY_MIN_CASH=2000` live, days 2–22).
- Buy morning: skip Walk 2; `replan_after_buy` at h1 (NE workers only on ThreeLand15); market hours 0–2 on buy day.

### 6. `daily_price_forecast` (completed, earlier)

`milos/price_forecast.py` inventory walk; gaps filled by `fix_price_forecast`.

---

## Price forecast fix — `fix_price_forecast` (completed)

| Wave | What |
| --- | --- |
| **W1** | Profile/forecast fail → **live market quotes**, log `[fc] FORECAST FAILED` |
| **W2** | `agent(obs, config)` + `envconfig`; shop-safe demand; sell_dp shop term |
| **W3** | `walk_prices_and_inv`; `price_of(..., extra_units)` |
| **W4** | MIP `locked_counts` + `product_caps` |
| **W5** | `drain_calib` clean-day clamp |

Do not submit unless asked.

---

## Replay / notebook notes

- Animal `$/tile-day` keyed by product (EGG/MILK/WOOL); `submission_nb.revenue_per_tile_day_by_product` for stale caches.
- Comparison violins: `density_norm="count"`.
- Smoke: `plot_zone_earnings_vs_cost` motivated the zone value gate.
