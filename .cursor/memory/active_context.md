# Active Context

## Current focus (Aug 27, 2026)

**DP catalog + pickups-honest ops** on top of dawn replan / FIVE layout.

### Just shipped (this session)

1. **Zonewise notebooks**
   - [`experiments/OneL-Zonewise-CPSAT-Handmade-Catalog.ipynb`](../../experiments/OneL-Zonewise-CPSAT-Handmade-Catalog.ipynb) — FIVE LandOne cascade; **conservative money coupling**: next zone opens at prev start − prev loss (setups + W/F buys + hire; **no sells**). Full day `closing` still logged.
   - [`experiments/OneL-Zonewise-CPSAT-DP-Catalog.ipynb`](../../experiments/OneL-Zonewise-CPSAT-DP-Catalog.ipynb) — same MIP, chains from `agent.dp_catalog.build_catalog` via `DP_LAGS`.

2. **`agent/dp_catalog.py`**
   - `build_catalog(horizon, price_of, lags=…, tolerance=…, max_variants=…)`
   - Insert diversity: near-best landing days (`INSERT_TOLERANCE=0.05`, `INSERT_MAX_VARIANTS=4`) with **best-chain pinned** before day-stride thin (stride alone dropped argmax → MIP regression).
   - **Greedy inserts:** no forced wheat/carrot prefix; extras = mono-greedy of that crop (1, 2, … while fits) + mix WIS suffix; animals = single placement (dedupes with animal-only).
   - Day-0 / replan both call this (not handmade JSON).

3. **Animals = pickups JSON**
   - Agent loads `data/animal_with_pickups.json` (`animal_rollouts.py` + `planner.py`); smoke bundle copies it (not `animal_rollouts.json`).
   - Tile-only `animal_rollouts.json` remains for older notebooks.

4. **Ops cap = `daily_tile_ops` only**
   - Pickups JSON already has PICKUP/BUILD/PLACE in `len(actions)`.
   - Removed double-counts: cap no longer adds `daily_wheat_pickup` / `daily_animal_place` / `daily_fert_pickup`; no extra `build_day += 1` stamp; `animal_rollouts.executor_ops_by_day` is `len(actions)` only.
   - Hire preamble (1 op if any animal active) still charged for hands.

### Pricing (agent)

| When | `price_of` |
| --- | --- |
| Day-0 | i0 `base_price` |
| Replan | live quote × `max(0.1, 1 + shop_demand − opp_tiles/10)` |

Same callable feeds catalog WIS **and** chain stamp cash.

### Replan (unchanged shape)

- Horizon = `NUM_DAYS - day` (remaining season).
- Vars = `_replan_eligible` empties only; rest locked (board + queue suffix).
- `track_shed=False`; INFEASIBLE → preserve queues.

### Layout

```python
CURRENT = FIVE   # zoning still 18/13/14/14/15; zonewise notebooks use two_lands 18/17/16/14/13
```

## Smoke / score notes

- Switching to pickups **without** stripping side-channel ops tanked smoke (~90k → sub-50k) — over-counted animal days.
- After single-term ops: expect animals to fit again; re-smoke to confirm (not banked yet this session).

## Immediate next steps

- Smoke vs random after pickups + ops fix; compare to prior ~64–98k FIVE band
- Optional: align live `zoning.FIVE` ops to `data/two_lands.md` (18/17/16/14/13) if notebooks stay authoritative
- Late-day replan INFEASIBLE still possible under cash/ops
- Do not revive WSP; agents never submit without ask
