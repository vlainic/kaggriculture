# Active Context

## Current focus (Sep 30, 2026)

**Live submission = `milos/` ThreeLand 15-hand layout** — `main.py` → `agent(obs, config=None)` → `milos.executor.step`. Layout: **`MILOS_THREELAND15`** via `KAGGRI_LAYOUT` default `threeland15` (`CURRENT` in `milos/zoning.py`):

| Land | Workers | Notes |
| --- | --- | --- |
| **NW** | farmer + hire1–4 | `NUM_ACTIVE_HIRES = NW_HANDS` (4); h0 HIREs |
| **NE** | hire5–9 | dusk buy → h1 buy-replan; Walk 2 activates remaining |
| **SW** | hire10–14 | dusk after NE full + cash/overage; Walk 3; **zone value gate** |

Alt layouts (env): `threeland18` (6-man NW), `twoland12`, oneland variants. **`KAGGRI_SW` default `"1"`** (SW on). Spec: [`data/milos_zoning.md`](../../data/milos_zoning.md) (ops doc may lag code +1 on NW).

`agent/` TwoLand WSP remains legacy. Smoke tarball uses `milos/`.

### Land buys

- **NE dusk:** `schedule_ne_buy_at_dusk` — unowned, `money >= NE_BUY_MIN_CASH` (**2000**), day in 2..22 → `BUY_LAND_DAY = tomorrow`.
- **NE buy morning:** h0 `BUY_LAND`; h1 `replan_after_buy` over **NE workers only** (full money, overage-clamped `max_time`); prefix + **zone value gate**.
- **SW dusk:** `schedule_sw_buy_at_dusk` — NE full + bound, `money >= 4000`, overage ≥ 40, day 8..18 → `SW_BUY_DAY`.
- **SW buy morning:** `replan_after_buy_sw` — SW workers only; same value gate; log `wasted_land` if `n_active < 2`.
- **Walk 2 / Walk 3:** `_activate_next_ne` / `_activate_next_sw` when land owned and buy day ≠ today; retries deferred zones (no latch).

### Zone value activation gate (just shipped)

Plan: `.cursor/plans/zone_value_activation_gate_21c21131.plan.md`.

- Accept new NE/SW zone iff `obj − cost >= 0` where `obj` = CP-SAT harvest objective, `cost` = `_zone_plan_cost` (full-horizon seed/animal spend + `HAND_DAILY_COST × D`).
- Missing `obj` → **fail open** (`value_unknown`); existing busy/cash/`solved_workers` still apply.
- Buy-day: **break** on first reject (same-day prefix only); Walk 2/3 retries later dawns.
- Ship defaults: `min_net=0`, ratio off. Local-only: `KAGGRI_ZONE_MIN_NET`, `KAGGRI_ZONE_MARGIN_RATIO`.
- Smoke check: SW buy-day stopped at hire12 (`hire13` `low_value`); hire14 never accepted; NE still fills all 5 via Walk 2; no `value_unknown` on live twoland.

### Price forecast (unchanged)

- Episode **config** via `milos/envconfig.py`; inventory walk; MIP `locked_counts` + glut caps; `drain_calib`.
- Fallback on forecast exception: **current market quotes**.

### Critical engine rules (unchanged)

1. **Shed-adjacent ONLY IF OWNED** — PICKUP/DROP no-op on `LOCKED`.
2. **Shed capacity 100** — silent buy reject; FERT dump + dawn make-room sells.
3. **Wheat:** global buffer on buy only; pickup = raw zone need.

### Smoke analysis (Sep 30)

- Layout-aware `scripts/smoke_analysis/` + `experiments/smoke_analysis.ipynb`.
- **`plot_us_vs_opp_daily`**: 7 panels vs `v55_logged_opponent` — tile ops; **tiles operated** (us Σ dawn `qtiles`, opp `[opp_snap] live=`); net cash Δ with **dawn money on right y-axis**; workers (us zones with qtiles>0, opp distinct farmer+handN); ops/tile; tiles/worker; ops/worker.
- Opp workers: count actors from `[opp]` lines (not `hands=` from empty `me["hands"]`). Opp live needs `live=N` on `[opp_snap]` (`v55_logged_opponent`).
- Optional: `plot_us_vs_opp_money_hours` (turn axis; dawn-only snaps → one point per day column).
- Also: `plot_zone_earnings_vs_cost`.

### Immediate next steps

1. Watch `[sw] reject … low_value` / `wasted_land` / NE fill-all-5 on more smokes (not final reward).
2. If `wasted_land` is common, consider dusk-time “≥2 profitable SW zones?” pre-check.
3. Optional: calibrate `KAGGRI_ZONE_MIN_NET` from `obj−cost` vs P&L proxy across runs.
4. Agents **never** Kaggle-submit without explicit ask.

### Anti-patterns (still)

- Mid-day BUY wheat/animal/seed; per-zone wheat pickup buffer; freezing routes for wheat/PLACE; CARE without `fed_today`; building queues via `WORKER_TILES[solved_worker]` when layout ≠ prestart map; treating missing `zone_objectives` as reject (blocks NE); latching buy-day `low_value` forever; agents submitting without ask.
