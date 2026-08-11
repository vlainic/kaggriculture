# Active Context

## Current focus

**Coupled crop + animal set-packing agent — Aug 11 stabilization.** Planner packs crops and animals under shared `DAILY_OP_BUDGET=16`; executor runs sticky snake routing with live-price replans, animal care/harvest, and end-of-day tomorrow market buys. Still `no_fert` / `no_care`, 3×3 NW tiles, sell-all shed, vendored OR-Tools.

## Recent changes (Aug 11, 2026)

### Op budget / planner–executor alignment (260811_1 regression)

1. **Removed double snake budget:** dropped `SNAKE_MOVE_OPS` and `add_snake_baseline()` from `agent/ops_budget.py` and `agent/planner.py`. `DAILY_OP_BUDGET=16` already assumes ~8 snake moves per day — adding 8 on top left only ~8 tile-ops/day packed and under-filled the farm.
2. **`ops_budget.py` simplified:** only dispatches `executor_ops_by_day` for crops vs animals + `peak_load` helper.

### Replan trigger fix (animals dropped mid-season)

3. **Plan-coverage replan:** `_should_replan` no longer fires when empty-tile set shrinks (normal planting). Replan when: first run, harvest today (crop/animal), weed, unfed animal, or **empty tile lacks any plan entry with `start_day >= day`**. Removed `_last_empty_tiles` equality check that dropped future animal BUILD plans.

### Executor animal / market fixes (260811_2 logs)

4. **Wool catch-up HARVEST:** `_animal_pending_for_tile` prepends `HARVEST` when `yield_units > 0` even if template age has no HARVEST (sheep ages 28–29). Snake pass skips HARVEST when `yield_units=0`.
5. **FEED wheat gate:** skip FEED in pending when no WHEAT or `fed_today`; `_format_action("FEED")` also requires WHEAT — stops day-28 FEED loops.
6. **BUY_SEED same-day only:** market buys seeds only for `start_day == day` (removed day+1 lookahead during snake). Tomorrow seeds added separately when snake done (below).

### Live animal pricing on replan

7. **`animal_rollouts.revenue_in_window(..., unit_price=None)`** — optional live product price.
8. **`_build_animal_candidates`** uses live EGG/MILK/WOOL prices + live WHEAT for feed cost; shop `(1+d)` on revenue unchanged. Placed animals still lock tiles (`earliest[tile]=OPS_HORIZON`).

### End-of-day tomorrow market buys

9. **`_snake_done()`:** `_route_idx >= len(TILE_COORDS)` (9 tiles visited).
10. When snake done: add **day+1** seed demand (empty/weed tiles); add **day+1** fert/wheat ops for **live** tiles only (`_feed_ops_for_day` / `_fert_ops_for_day` generalized; `fed_today` gate only when `calendar_day == today`).
11. Animals unchanged: BUY_ANIMAL for `start_day in (day, day+1)`.

### Packaging

12. **`scripts/smoke_and_submit.sh`:** bundles `data/animal_rollouts.json` with crop rollouts.

## Active decisions

- Profiles: **`no_fert`** (crops), **`no_care`** (animals).
- Seeds/animal shop costs: **fixed** from rollouts; sell/product weights: **live** `obs["market"]["prices"]`.
- Replan at `hour == 0` per triggers above; full forward plan replace (crops + animals).
- Daily capacity: **`DAILY_OP_BUDGET=16`** total tile ops (snake implicit); day 0 = 15 (`FIRST_DAY_OP_RESERVE`).
- Market order priority: SELL shed → BUY_SEED (today; +tomorrow if snake done) → BUY_ANIMAL → BUY fert → BUY wheat.
- Farmer and market are **separate per turn**; market orders do not consume farmer ops.
- Placed animals **cannot** free tiles mid-season (no DIG with animal present; no swap/abandon).
- Do **not** add tests/eval/`.venv` unless user asks.

## Open questions / follow-ups

1. Ladder replay after Aug 11 fixes — confirm ~32–35k smoke holds vs ladder opponents.
2. Plan-aware tomorrow fert/wheat for **future** placements (currently live tiles only).
3. Orphan seeds if same-day BUY_SEED then replan drops plant before snake reaches tile.
4. **5×5 grid, hires, land unlock** — next phase; not started.
5. Fertilizer profile (`with_fert`) — deferred.
6. Town-center demand in weights — still out of scope.

## Immediate next steps

1. Submit via `scripts/smoke_and_submit.sh` if user wants fresh ladder run.
2. Monitor logs for orphan seeds, missed harvests, end-day BUY_SEED on `route=done` hours.
3. Phase 2: hires + extra segments when coupled crop/animal loop is stable on ladder.

## Key files

- `main.py`, `agent/{rollouts,planner,executor,ops_budget,animal_rollouts}.py`
- `data/{crop_rollouts,animal_rollouts}.json`
- `scripts/smoke_and_submit.sh`, `scripts/vendor_ortools.sh`
- `submissions/260811_1/` (broken), `submissions/260811_2/` (better; wool/carrot issues led to fixes)
- `docs/weighted_set_packing.md`, `docs/project_overview.md`
