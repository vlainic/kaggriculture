# Active Context

## Current focus (Sep 2, 2026)

**Two-land WSP** on `TWO` layout (50 tiles, zones I–X). `CURRENT_SOLVER = "twoland_wsp"` in `agent/solvers/__init__.py`. One-land path: flip to `zonewise_wsp` + `CURRENT = FIVE`.

### Just shipped (Sep 2 session)

1. **Two-land WSP** ([`agent/solvers/twoland_wsp.py`](../../agent/solvers/twoland_wsp.py))
   - Copy of `zonewise_wsp` + land-2 probe / buy flow.
   - Day-0: `wsp_prestart.json` for **land 1 only** (25 tiles).
   - **Probe day** (NE not owned, not buy morning): land1 cascade → always **hire5** probe (5s cap); if feasible and conservative ≥ $1k → `buy_land=True`; **no hire6–9**, no hire5 queue commit.
   - **Buy morning** (`BUY_LAND_DAY == day`): charge $1k on opening; full cascade farmer→hire9; `apply_replan(write_all_solved=True)` for locked NE tiles.
   - After NE owned: normal full cascade each replan.

2. **Layout TWO** ([`agent/zoning.py`](../../agent/zoning.py))
   - FIVE + NE columns (tiles 26–50); hire5–9 per `data/two_lands.md` (ops 16/14/13/12/11).
   - `CURRENT = TWO`; `LAND1_TILE_COUNT`, `LAND1_WORKERS` helpers.

3. **Planner glue** ([`agent/planner.py`](../../agent/planner.py))
   - `BUY_LAND_DAY`, `NUM_ACTIVE_HIRES` (default 4).
   - Probe replan `max_time=5.0`; buy morning / post-buy `max_time=15.0`.
   - WSP replan from d≥3 unchanged.

4. **Market** ([`agent/market.py`](../../agent/market.py))
   - Hire batches from `two_lands.md` (2@h0 for ≤2; 3→2+1; 5→2+3; 9→4+5; etc.).
   - Active fib hire reserve (not full 9-hand $88).
   - `BUY_LAND` at h=0 on `BUY_LAND_DAY`.

5. **Kaggle episode download** ([`scripts/download_submission_logs.sh`](../../scripts/download_submission_logs.sh))
   - Default: **replays only**; optional `--with-logs` (often 403 on ladder).
   - Filters numeric episode IDs (Kaggle CSV footer line).

### Smoke (twoland_wsp, Sep 2)

~**87k** vs random; probe ~d7 → `BUY_LAND` d8 → hire5–9 active when affordable.

### Solver comparison

| Backend | Layout | Land | Smoke ~ |
| --- | --- | --- | --- |
| `zonewise_wsp` | FIVE | 1 | 81–85k |
| `twoland_wsp` | TWO | 1→2 probe+buy | **~87k** |
| `zonewise` | FIVE | 1 | ~107k |

### Replan (WSP family)

- Horizon = `NUM_DAYS - day`; vars = empty/WEED; locked = board + queue suffix.
- `track_shed=False`, `min_balance=0`, conservative handoff.
- twoland: probe 5s / full 15s; partial cascade OK (prefix apply).

## Immediate next steps

- Kaggle A/B twoland vs one-land WSP on same seeds.
- Tune hire9 INFEASIBLE late-season (partial prefix is working).
- Use `download_submission_logs.sh` for live episode replays (not stdout logs).
- Agents never submit without explicit ask.
