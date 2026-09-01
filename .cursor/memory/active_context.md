# Active Context

## Current focus (Sep 1, 2026)

**WSP + conservative zone cash** on FIVE layout. `CURRENT_SOLVER = "zonewise_wsp"` in `agent/solvers/__init__.py` (flip to `"zonewise"` for DP-catalog chain backend).

### Just shipped (Aug 31 – Sep 1 session)

1. **Zonewise switch + executor hygiene** (plan: 90k path)
   - `CURRENT_SOLVER` flippable: `zonewise` (~107k smoke) vs `zonewise_wsp` (~81–85k smoke).
   - Replan `track_shed = (CURRENT_SOLVER != "zonewise_wsp")` — W/F ledger off for WSP only.
   - **`price_of`** optional kw on all solver backends (fixes replan crash).
   - Debug NDJSON stripped from executor/market/wsp.

2. **Executor / market / tile_ops fixes** (solver-agnostic — lifted both backends)
   - **FERT:** runtime inject via `_may_fertilize_today`; skip tape `FERTILIZE`; `fert_today` + zone ops cap.
   - **Wheat:** dawn buy uses `wheat_feed_need + 1` slack; shed-adjacent pickup before snake (only when shed has stock); feed-wait shed pickup restored.
   - **Replan:** WEED tiles eligible again (`_tile_empty_for_replan`).
   - **Smoke:** `BUILD_*` prefix match in `scripts/smoke_test.sh`.

3. **WSP conservative cash handoff** ([`agent/solvers/zonewise_wsp.py`](../../agent/solvers/zonewise_wsp.py))
   - **Removed** full live bank per zone (`_zone_banks`) — was economically wrong (5× shared cash).
   - Patterns get **`spend_by_day`** (setup only); harvests stay on `cash_by_day`.
   - Per-zone MIP: `opening_balances` + **balance** (harvests, ≥0) + **conservative** (spend only).
   - Sequential cascade: `opening = [starting_money] * horizon`; after each zone **`opening = res["conservative"]`** (notebook formula, not zonewise `balance` handoff).
   - Empty zones: `_locked_conservative_handoff`; INFEASIBLE → **break** (prefix apply only).
   - Logs: `open0=` / `cons0=` / `close0=` stepping down farmer → hire4.
   - Replan: farmer opens at live `me["money"]`; later zones get conservative leftover. **No ops-ratio slice** on replan (notebook day-0 ops/78 slice is prestart-only).

4. **Lint** — `WORKER_TILES` before `WORKERS` in zonewise_wsp imports (Ruff I001).

### Solver comparison (smoke, same executor)

| Backend | Replan catalog | Cash model | Smoke ~ |
| --- | --- | --- | --- |
| `zonewise` | `dp_catalog` chains | close balance handoff + `track_shed=True` + liquidity floor | 107k |
| `zonewise_wsp` | atomic patterns | **conservative** handoff + `track_shed=False` + `min_balance=0` | 81–85k |

### Pricing (agent)

| When | `price_of` |
| --- | --- |
| Day-0 zonewise | i0 `base_price` |
| Day-0 WSP | prestart JSON (full horizon) |
| Replan WSP | live quote × glut factor in pattern weights |
| Replan zonewise | live × `max(0.1, 1 + shop_demand − opp_tiles/10)` |

### Replan

- Horizon = `NUM_DAYS - day`.
- Vars = `_replan_eligible` empties (+ WEED); rest locked.
- WSP: replan from **d ≥ 3**; partial cascade OK if hire zone INFEASIBLE.
- Zonewise: `track_shed=True`, liquidity floor; farmer-prefix partial apply.

### Layout

```python
CURRENT = FIVE   # ops 18/17/16/14/13
```

## Immediate next steps

- Kaggle A/B: WSP conservative vs old full-bank (if baseline saved).
- If hire4 INFEASIBLE on tight replans: tune locked spend or partial apply policy — do **not** restore full-bank-per-zone.
- Optional: align live `zonewise.py` handoff to conservative (notebooks) vs current close-balance.
- Agents never submit without explicit ask.
