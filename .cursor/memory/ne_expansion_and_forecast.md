# NE land expansion and price forecast (plan chain)

Historical plans live under `.cursor/plans/`. **Live code:** `milos/zoning.py` → `CURRENT = MILOS_TWOLAND12` (NW 25 tiles + 6 NE zones, 11 hire slots total, `NUM_ACTIVE_HIRES = 5` for NW h0 HIREs).

## NE buying — plans implemented (order of evolution)

### 1. `ne-land_minimal_trigger` (completed)

**Goal:** Add NE as six zones (VII–XII) that activate one at a time after NW is running.

**Shipped:**
- `MILOS_TWOLAND12` layout, `NW_WORKERS` / `NE_WORKERS` / `NE_TILES`, NE zones with PICKUP-only preambles and doc ops caps.
- `oneland.solve(workers=...)` so inactive NE hands are not charged daily cost.
- `planner.replan()` **Walk 1** over `active_workers()`; **Walk 2** `_activate_next_ne` for front pending zone.
- Original land path: zone VII mini-solve could set `BUY_LAND_DAY = day+1` with busy/cash gates; `is_buy_morning_locked` treated NE as empty on buy morning; market `BUY_LAND` first at h0 + h1 HIREs × `len(ACTIVE_NE)`; buy window h0–h1 for overflow.
- Executor: slot-based NE bind → `NE_BOUND_TODAY`; fix LOCKED tiles marked `active` in `_on_new_day`.

**Pain:** `BUY_LAND_DAY` tied to VII CP-SAT accept → nondeterministic / never-buy episodes.

### 2. `cash_trigger_for_ne` (completed, later superseded)

**Goal:** Decouple land buy from VII solve — trigger when `money >= NE_BUY_MIN_CASH` at dawn.

**Shipped:** `_maybe_trigger_ne_buy` in `replan()` before walks; `BUY_LAND_DAY = today`; Walk 2 VII on buy morning with LOCKED tiles + land reserve; executor recomputed `_empty_at_dawn` after replan on buy day.

**Superseded by:** dusk scheduling + buy-day joint replan (`robust_ne_buy`).

### 3. `fix_ne_rollback_bugs` (completed)

**Goal:** Stop false NE rollbacks and queue wipes.

**Shipped:**
- `NE_DUE_DAY` replaces `NE_PENDING_EXPECT` / `NE_BOUND_PREV_DAY` / `NE_ACTIVATED_DAY`; `dawn_ne_bound_handoff` rolls back only when due day passed and hire did not bind yesterday.
- `_write_ne_activation` loops `assigned.items()` only (no wipe of planted tiles).
- Separate try/except for Walk 1 vs Walk 2; `[ne] reject` includes `ok=`.

### 4. `lower_ne_busy_gate` (partial / intent absorbed)

**Goal:** Buy NE without utilization gate; later zones `busy_day0 < 1` instead of `< 2`.

**Live today:** Land buy no longer goes through Walk 2 VII gate — **`schedule_ne_buy_at_dusk`** sets `BUY_LAND_DAY`. Walk 2 only runs when NE is **owned**; gate is `busy_day0 < 1` + cash + solver ok (not the old `< 2` on all zones).

### 5. `robust_ne_buy` (completed in code)

**Goal:** Forecast failures must not block buy; dusk cash trigger; one joint NE cascade at h1 on buy day.

**Shipped:**
- **W1:** `_safe_price_of` wraps forecast (fallback to market quotes / I0 path); Walk 2 uses `pending[0]` not `NE_WORKERS[len(ACTIVE_NE)]`.
- **W2:** `schedule_ne_buy_at_dusk` at h23 (`NE_BUY_MIN_CASH=3000`, days 2–22); removed dawn `_maybe_trigger_ne_buy`; market h0 `BUY_LAND` guarded with NE not already owned.
- **W3:** `is_buy_morning_locked` → always `False`; buy morning skips Walk 2; **`replan_after_buy`** at h1 (NE tiles only, NW locked in cascade but not rewritten); `_empty_at_dawn` recompute at h1; market buy hours `(0,1,2)` on `BUY_LAND_DAY`.

**Tunables:** `NE_BUY_MIN_CASH`, `NE_BUY_FIRST_DAY`, `NE_BUY_LAST_DAY`, buy-replan `max_time=24`.

### 6. `daily_price_forecast` (completed, earlier)

**Goal:** Replace dawn price heuristic with inventory walk (frozen queues, shops, town center).

**Shipped:** `milos/price_forecast.py`, replan `price_of(product, rel_day)`; removed separate glut/effective_price heuristics in one wave.

**Gap left for next plan:** solver self-impact and competition config mismatch.

---

## Price forecast fix — `fix_price_forecast` (completed, Sep 2026 chat)

**Problem:** Wool/melon looked valuable while market glutted ($1); local engine ≠ competition (e.g. `townCenterSellInterval: 24`, duplicate shop unlocks); MELON `with_fert` KeyError crashed forecast → optimistic I0 fallback; MIP ignored own wool supply (`del locked_counts`).

**Waves (one commit each):**

| Wave | What |
| --- | --- |
| **W1** | `_resolve_profile` fallback in `_add_profile_harvests`; `_safe_price_of` falls back to **live market quotes**, logs `[fc] FORECAST FAILED` |
| **W2** | `main.py` `agent(obs, config=None)` + `milos/envconfig.py` (intervals, shed cap, `marketParams`); duplicate-shop-safe demand; `sell_dp` speculative shop term discounted (`P_NEW_SHOP`, drop for glut products); `[cfg]` / `[shops]` logs |
| **W3** | `walk_prices_and_inv`; `price_of(..., extra_units)`; `extra_units=0` on all fallback lambdas |
| **W4** | `mip._pattern_weight` uses `locked_counts` + per-unit curve; `product_caps` / `_glut_headroom` in oneland/twoland solves |
| **W5** | `milos/drain_calib.py` — clean-day observed vs modelled drain, clamp 0.1–1.0; `observe_drain` at h0; `note_sells` in market |

**Verify:** 3× `smoke_test.sh` + one run with `townCenterSellInterval=24`; grep `[fc]`, `[cfg]`, WOOL inventory/caps/drain. Do not submit unless asked.

**Submissions referenced in comparison nb:** e.g. `56640030` vs `56641070` (robust NE vs better forecast).

---

## Replay / notebook notes (Sep 2026)

- **`scripts/replay_analysis/kpi.py`:** `revenue_per_tile_day_by_crop` must use `crop_tile_days.get(prod)` (product keys EGG/MILK/WOOL), not animal names.
- **Cached summaries** (`kaggle_logs/<id>/<id>.json`) store planner KPIs at summarize time — stale `revenue_per_tile_day_by_crop` after KPI fixes.
- **`experiments/submission_nb.revenue_per_tile_day_by_product(game)`** recomputes from `sells.by_player[us].revenue` ÷ `planner.crop_tile_days` so comparison §5 shows animals without `REFRESH=True`.
- **`submission_comparison.ipynb` §1:** split violins use `density_norm="count"` so bar width reflects episode count (fair A vs B when win rates differ).
