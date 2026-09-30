# Active Context

## Current focus (Sep 30, 2026 — evening)

**Live submission = `milos/` ThreeLand 12** — `main.py` → `milos.executor.step`. Default `KAGGRI_LAYOUT=threeland12`, **`KAGGRI_V55_OPENER=1`** (144-step tape d0–5; day 6 adopts live queues). **`KAGGRI_SW=1`**. Four hands per land (NW farmer+hire1–3, NE hire4–7, SW hire8–11). Legacy `agent/` TwoLand not live.

### Recent shipped (this session)

1. **d6–11 ablation flags** (`milos/fix_flags.py`): `KAGGRI_ABL_LAND` (hourly BUY_LAND from d6), `KAGGRI_ABL_CATALOG`, `KAGGRI_ABL_CASH` — **default on** unless env `=0`. Step 0: `[abl] land= catalog= cash=`.
2. **MIP cash loosening** (`planner.py`, `milos/wsp/twoland.py`, `mip.py`): activation affordability = spend days 0–1 + 1 hire day; value gate **`obj − hire only`** (setup already in obj); cascade handoff = solved **`balance`** with harvest **+1 day** in handoff only; hire charged on **work days** only; Walk 3 every dawn (dropped `len(ACTIVE_NE)==n_ne` skip).
3. **Goose / wheat / strawberry** (`mip.py`, `market.py`, `config.py`): GOOSE patterns + market buys restored; **EGG** in `CONCAVE_PRODUCTS`; goose fert credit in `_animal_valuation_bonus`; wheat feed at quote **without** eating `D_rem` (`sell_cap = max_u − feed`); strawberry opp haircut **0.25×D** on calendar d6–8.
4. **Concave committed supply** (`replan_lock.py`, `build_revenue_curves`): locked tiles stamp **`harvest_units`** → `committed_harvest_units()` → **`D_rem = D − committed − carried − opp`** (log `committed=`). Fixes melon over-plant vs full town sink each dawn.
5. **EGG sells** (`sell_dp.greedy_premium_sells`): EGG in hourly greedy list with premium good-price logic (not room-only).
6. **Smoke** (`scripts/smoke_episode.py`): skip hand2 PLACE/FEED check **d0–5** (opener); optional **`SMOKE_SEEDS=pinned`** (11,22,33,44,55) for mean margin — diagnostic only, not required for fixes.

### Land buys (control + abl)

- Control dusk NE/SW thresholds unchanged when abl off.
- **Abl land:** every hour from d6, sells-first `BUY_LAND` if money+hour sells ≥ 1300 (NE) or ≥ 2300 (SW, overage/window).

### Immediate next steps

1. Re-run smoke / `smoke_analysis.ipynb` on committed melon + EGG sells; grep `[concave] … committed=` and `SELL EGG`.
2. Do not judge single-smoke reward vs V55 (shop seed variance ±40k gross).
3. Agents **never** Kaggle-submit without explicit ask.

### Anti-patterns (still)

- Mid-day BUY wheat/animal/seed (except abl midday if ever enabled); per-zone wheat pickup buffer; missing `zone_objectives` as hard reject; agents submitting without ask; treating `[concave] D_rem` without **committed** as full sink headroom on replan days.
