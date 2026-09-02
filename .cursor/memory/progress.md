# Progress

## Strategic status (Sep 2, 2026)

| Track | Status |
| --- | --- |
| **Two-land WSP** | **Live** — `twoland_wsp.py`; `CURRENT = TWO`; probe hire5 → buy NE → cascade VI–X |
| **One-land WSP** | **Live** — flip `CURRENT_SOLVER = zonewise_wsp`, `CURRENT = FIVE` |
| **Chain assignment (zonewise)** | **Live** — `dp_catalog.build_catalog`; ~107k smoke on FIVE |
| **Solver backend** | **`CURRENT_SOLVER = "twoland_wsp"`** |
| **Land buy** | Probe: hire5 feasible + ≥$1k conservative → `BUY_LAND` next dawn |
| **Hiring** | `NUM_ACTIVE_HIRES` from solved prefix; batches per `two_lands.md` |
| **Dawn replan** | Lock commitments; WSP conservative cascade; INFEASIBLE → break |
| **Layout catalog** | `FOUR` + `FIVE` + **`TWO`** (50 tiles); **`CURRENT = TWO`** |
| **Episode download** | `scripts/download_submission_logs.sh` (replays default) |
| **Replay analysis** | `scripts/replay_analysis/` + `scripts/summarize_replays.sh` → `<id>.json` |
| **Competition submission** | Local smoke only unless user asks |

## What works

| Item | Notes |
| --- | --- |
| twoland_wsp smoke | ~**87352**; land2 buy ~d8; up to 9 hires when cascade allows |
| Land2 probe | hire5 only on probe day; no queue commit until buy morning |
| TWO layout | Zones I–X; land1 = FIVE geometry; land2 NE snakes |
| WSP conservative cascade | Unchanged from Sep 1 one-land work |
| download_submission_logs.sh | Replays bulk; `--with-logs` optional; skips CSV footer junk |
| replay_analysis + summarize_replays.sh | Batch JSON per submission; KPIs; slim default (no sell events) |
| Corrected A/B ONE vs TWO | 55934103: 42.1% / 64k; 55938405: 51.2% / 71k (per-game us_index) |
| `kaggle_logs/` | Gitignored; `<submission_id>/<submission_id>.json` |

## Known issues

| Issue | Notes |
| --- | --- |
| hire9 INFEASIBLE late season | Partial prefix OK; common after land2 expansion |
| Kaggle agent logs API | 403 on ladder episodes; replays work |
| WSP vs zonewise gap | ~87k twoland vs ~107k zonewise one-land |
| hire5 probe UNKNOWN | Occasional 5s timeout; retry next dawn |
| Replay self-play us_index | Both `TeamNames` = same name → `resolve_us_index` always 0 (rare) |
| TwoLand conversion leaks | Sept 2 overhaul: E1 walk-to-shed, pricing, track_shed, fert pipeline |

## Sep 2 session (Sept02 overhaul — all waves)

| Change | Result |
| --- | --- |
| Wave 0 instrumentation | PASS note counters, solver early_stopped logs, day-29 drift |
| Wave 1 E1+P3 | pickup-first preambles, walk-to-shed, NUM_ACTIVE_HIRES after INFEASIBLE |
| Wave 2 S2+S6 | conservative floor 0, negative handoff break, apply_replan state reset |
| Wave 3 P1+P2+S3 | forecast-inventory effective_price, marginal glut pricing |
| Wave 4 E2 | animal-first routes at dawn |
| Wave 5 S1+E3+M1 | W/F handoff, track_shed=True, PICKUP_FERTILIZER, BUY FERTILIZER |
| Wave 6 S4+S5 | PER_TILE_FLOOR early stop, weighted time, ROI land probe |
| Wave 7 M2 | PRICE_FLOOR_RATIO 0.35, wool cap T//5 |

## Sep 2 session (replay analysis + us_index fix)

| Change | Result |
| --- | --- |
| `scripts/replay_analysis/` (metrics, sells, kpi, plot) | Per-game + batch JSON; executor/market/planner KPIs |
| `sold_units()` from stock deltas | Fixed undercount vs ~80k bank |
| `potential_yield` replant key | `(player,x,y,planted_day)` not tile-only |
| `summarize_replays.sh` | `kaggle_logs/<id>/<id>.json`; slim batch (no events) |
| `_aggregate()` per-game `us_index` | Fixed 50% opponent contamination in rollups |
| A/B 55934103 vs 55938405 | TwoLand +11% bank, +9pp win (corrected) |

## Sep 2 session (two-land WSP + download script)

| Change | Result |
| --- | --- |
| `TWO` layout + `twoland_wsp.py` | 50-tile solver with probe/buy split |
| `BUY_LAND_DAY` / `NUM_ACTIVE_HIRES` | Planner + market glue |
| `download_submission_logs.sh` | Replay bulk; numeric ID filter |
| Smoke twoland_wsp | ~87k |

## Sep 1 session (WSP conservative handoff)

| Change | Result |
| --- | --- |
| Conservative cascade in `zonewise_wsp` | ~81–85k one-land |
| Executor FERT/wheat fixes | Lifted both backends |

## What's left

1. **Agent fixes from replay KPIs:** hand3→zone routing, marginal crop mix, SW buy timing
2. Reduce late hire9 INFEASIBLE without over-hiring day 0
3. Lands 3–4 out of scope for now
4. Do not Kaggle submit without ask

## Do not do unless asked

- Restore full-bank-per-zone WSP hack
- Buy SW/SE (land 3–4) in twoland_wsp
- Runtime `bind()` layout switch mid-game
- Kaggle submit
- Commit `.cursor/` or `kaggle_logs/`
