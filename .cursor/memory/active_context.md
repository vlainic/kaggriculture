# Active Context

## Current focus (Aug 31, 2026)

**Zonewise CP-SAT agent** on FIVE layout — solver cascade + replan cash accounting + sell pacing. `CURRENT_SOLVER = "zonewise"` in `agent/solvers/__init__.py`.

### Just shipped (Aug 31 session)

1. **Zonewise = drop-in solver** ([`agent/solvers/zonewise.py`](../../agent/solvers/zonewise.py))
   - Same `solve()` / `apply_replan()` interface as monolithic; zone cascade is internal only.
   - `apply_replan`: zone-prefix partial write (farmer first); skip empty assignment if tile already has queue.
   - Handoff uses **close balance** (`res["balance"]`), not conservative spend floor.
   - Stop cascade if `open0 < 0` after zone solve; log `open0=` on INFEASIBLE.

2. **Replan cost-aware** ([`agent/planner.py`](../../agent/planner.py))
   - Replan uses default `charge_hire_daily=True`, `track_shed=True` (no longer cash-blind).
   - Seeds W/F from `obs["private"]["shed"]` via `w_open0` / `f_open0`.
   - **Liquidity floor** on replan: `min_balance = hire_reserve + feed_reserve × 3` (mirrors market reserves).

3. **Day-0 floor**
   - `_build_from_solver`: partial apply on incomplete (farmer prefix OK); `cascade_reserve=True`.
   - FIVE: no empty script fallback on solver fail — re-raise.
   - Smoke + executor: day-0 must have `BUY_SEED` or `PLANT`.

4. **Day-0 cascade reserve** (Fix 1)
   - `_downstream_cash_reserve()` → `min_close0` on zone day-0 close balance.
   - All 5 zones OPTIMAL on day-0 in smoke (farmer `close0≈2895`, not ~2820).

5. **Wool sell pacing** (Fix 3)
   - WOOL daily cap `max(4, T//8)` = 13 in `sell_dp` + `pricing.allowed_sell_qty`.
   - Season drip mostly 1 wool/hour; total ~231/game in smoke (was 185–210 at burst rates).

6. **Layout ops** — FIVE `net_tile_ops` aligned to `data/two_lands.md`: **18/17/16/14/13**.

7. **Diagnostics** — `experiments/hire1_idle_repro.py` (all-IDLE fixed test; run via submission bundle env).

### Pricing (agent)

| When | `price_of` |
| --- | --- |
| Day-0 | i0 `base_price` |
| Replan | live quote × `max(0.1, 1 + shop_demand − opp_tiles/10)` |

### Replan

- Horizon = `NUM_DAYS - day`.
- Vars = `_replan_eligible` empties; rest locked (board + queue suffix).
- **`track_shed=True`** + shed W/F seeding + liquidity floor.
- INFEASIBLE with farmer prefix → partial apply; `active=none` only if farmer fails.

### Layout

```python
CURRENT = FIVE   # ops 18/17/16/14/13 (two_lands LandOne)
```

## Smoke / score notes (Aug 31)

- Post all fixes: **~91–107k** vs random (720 steps); day-0 productive (PLANT/BUY_SEED).
- `active=none` replan days: **2** in latest smoke (d=11, d=12) vs ~6–8 in losing Kaggle episodes.
- d=3 bank can still hit **$1** — liquidity floor helps solver but market execution still drains cash.

## Immediate next steps

- Kaggle A/B: Fix 1 vs Fix 1+2 separately on episode logs (metrics: `active=none` days, d=3 bank, d=12 empty tiles, wool revenue).
- If d=3 still ~$0: raise `LIQUIDITY_DAYS` or tighten `min_balance` after Kaggle data.
- Optional: per-zone hire targeting (`busy_hand_zones`) if empty tiles persist at d=12.
- Do not revive WSP; agents never submit without ask.
