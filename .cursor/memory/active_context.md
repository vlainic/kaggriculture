# Active Context

## Current focus

**Live set-packing plant agent — Aug 7 refinements.** Full forward replan under live prices + shop demand; sticky snake executor. Still `no_fert`, 3×3 NW tiles, sell-all, seed buys, vendored OR-Tools for Kaggle.

## Recent changes (Aug 7, 2026)

1. **Half-open occupancy:** packing subsets cover ages `[0, tile_free_age)`; last-day HARVEST/DIG still count in `ops_by_day` → same-day harvest→plant handoff allowed.
2. **Tomato/strawberry DIG:** last harvest day includes DIG; `tile_free_age` 11 / 16 (not day-after).
3. **Horizons:** `SEASON_DAYS=30`, `PLAN_HORIZON=28` (half-open −1 + sell lag −1); ops through day 29; day 0 op budget 15 (`FIRST_DAY_OP_RESERVE`).
4. **Full forward replan (not kept-merge):** on replan, replace `self.plan` entirely. Fixed = in-progress plants (`earliest_plant` + remaining ops) + weed DIG (+1 op). All future plantings free under new prices.
5. **Weed react (executor):** DIG in snake order; no planner tile reserve. Replan on weed / empty-set change.
6. **Shop demand weights:** `weight = yield × price × (1 + shop_demand) − seed_cost` from currently unlocked shops only (no unlock forecast, no town center).
7. **Sticky snake executor:** finish current tile before leaving (stops harvest→move away→return waste); strict `TILE_COORDS` scan (no weed-first jump).
8. **Checks notebook:** `experiments/MainChecks.ipynb` for half-open / handoff gantt.

## Active decisions

- Profile: **`no_fert` only**.
- Seeds: **fixed** costs from rollouts; sell prices: **live** `obs["market"]["prices"]`.
- Replan at `hour == 0` when: first run, harvest today, weed present, or empty-tile set changed.
- Packing: half-open occupancy; capacity uses full ops + day-0 reserve + weed DIG.
- Shop boost on **revenue term only**; MELON demand 0; Yarn/Smoothie ignored (animals).
- Prefer thin `main.py` + `agent/` + `data/` + vendored ortools tar.gz.
- Do **not** add tests/eval/`.venv` unless user asks.

## Open questions / follow-ups

1. Ladder replay after sticky/shop changes — farming + no leave/return after harvest.
2. Town-center demand in weights? (out of scope for now.)
3. Fertilizer / hires / more tiles — later.
4. Greedy-only if vendor size/time hurts.

## Immediate next steps

1. Smoke vs `random` / submit; watch agent log for sticky plant-after-harvest.
2. Tune shop demand scale if wheat over-preferred.
3. Fert / hire / land when plant loop is stable on ladder.

## Key files

- `main.py`, `agent/{rollouts,planner,executor}.py`, `data/crop_rollouts.json`
- `experiments/MainChecks.ipynb`
- `scripts/vendor_ortools.sh`, `scripts/smoke_and_submit.sh`
- `docs/weighted_set_packing.md`, `docs/README.md` (town shops)
