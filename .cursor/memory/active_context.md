# Active Context

## Current focus (Sep 29, 2026)

**Live submission = `milos/` TwoLand 12-hand layout** — `main.py` → `agent(obs, config=None)` → `milos.executor.step`. Layout: **`MILOS_TWOLAND12`** (`CURRENT` in `milos/zoning.py`): NW 25 tiles (farmer + **5** h0 HIREs) + **6 NE zones** (hire6–11) activated incrementally. Spec: [`data/milos_zoning.md`](../../data/milos_zoning.md) + NE columns in zoning module.

`agent/` TwoLand WSP remains legacy. Smoke tarball uses `milos/`.

### NE land buy (current behavior)

- **Dusk (h23):** `schedule_ne_buy_at_dusk` — if NE unowned, `money >= 3000`, buy day in **2..22** → `BUY_LAND_DAY = tomorrow`, log `[ne] dusk_trigger`.
- **Buy morning h0:** `BUY_LAND` first (market); `replan()` Walk 1 only (no Walk 2 before land).
- **Buy morning h1:** `replan_after_buy` — one CP-SAT cascade over NW+NE workers, write **NE tiles only**; recompute `_empty_at_dawn`; HIREs + buys may spill to **h2** on buy day.
- **Later dawns:** Walk 2 `_activate_next_ne` when NE owned (`busy_day0 >= 1`, cash, solver ok); `NE_DUE_DAY` + hire-landed rollback via `dawn_ne_bound_handoff`.
- **Plan history:** see [ne_expansion_and_forecast.md](./ne_expansion_and_forecast.md).

### Price forecast (post–fix_price_forecast)

- Episode **config** ingested once (`milos/envconfig.py`): intervals, `marketParams`, shed cap.
- Dawn replan uses inventory walk + `price_of(product, rel_day, extra_units)`; MIP self-impact via `locked_counts` + glut **product_caps**.
- **Drain calibrator** (`drain_calib`) shrinks modelled town drain on clean days (ramp not in config).
- Fallback on forecast exception: **current market quotes**, not blind I0 optimism.

### Critical engine rules (unchanged)

1. **Shed-adjacent ONLY IF OWNED** — PICKUP/DROP no-op on `LOCKED`.
2. **Shed capacity 100** — silent buy reject; FERT dump + dawn make-room sells.
3. **Wheat:** global buffer on buy only; pickup = raw zone need (no per-zone buffer in pickup).

### Replay notebooks

- `experiments/submission_comparison.ipynb` — A/B KPIs; §5 animals via `revenue_per_tile_day_by_product`; `REFRESH=True` only needed to refresh cached planner fields in JSON.
- Agents **never** Kaggle-submit without explicit ask.

### Immediate next steps

1. Watch next submission `[cfg]` / `[shops]` / `[fc] drain` on real episodes (local engine may not match competition shop dedupe).
2. Tune `NE_BUY_MIN_CASH` or glut `floor_ratio` if smokes regress.
3. Optional: `REFRESH=True` once on comparison notebooks after KPI changes.

### Anti-patterns (still)

- Mid-day BUY wheat/animal/seed; per-zone wheat pickup buffer; freezing routes for wheat/PLACE; CARE without `fed_today`; building queues via `WORKER_TILES[solved_worker]` when layout ≠ prestart map; trusting cached `revenue_per_tile_day_by_crop` without recompute or refresh; agents submitting without ask.
