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

## Sep 3 session (Sept02 overhaul — feat/sept02-all, waves 0–8 + §7)

3× smoke medians (`scripts/smoke_test.sh`, twoland_wsp vs random):

| Wave | Median | Notes |
| --- | ---: | --- |
| BASE (d35bff5) | **85,599** | 88,811 / 60,016 / 85,599 |
| 0 instrumentation | ~77,882 | PASS counters, drift, tile_ops peaks |
| 1 E1+§7.3+P3 | ~59,795 | geometry preambles; animal-preamble loop fix |
| 2 S2+S6 | (stacked) | liquidity floor, cons≥0, apply_replan reset |
| 3 P1+P2+S3 | (stacked) | marginal pricing, GLUT removal |
| 4 E2+§7.5 | (stacked) | animal-first routes; formula net_tile_ops |
| 5a/5b S1+E3+M1 | (stacked) | track_shed + hire-only min_balance; fert B1/B6 |
| 6 S4+S5+§7.4 | (stacked) | weighted time, all-LAND2 ROI probe |
| 7 M2 | (stacked) | PRICE_FLOOR_RATIO 0.35, wool T//5 |
| 8 §7.1+§7.2 | (stacked) | layout builder, hand→zone map |
| **Final merged** | **~34,398** | 30,341 / 34,398 / 35,706 — **regressed vs BASE** |

Gate post-mortem: early farmer INFEASIBLE spikes with `track_shed=True` + spawn-agnostic preambles; tune hire_reserve / fert demand coupling before Kaggle A/B.

## Sep 4 session (Sept02 regression recovery — corrected re-ladder)

Root cause confirmed: `cons >= min_balance` on spend-only conservative ledger + `track_shed=True` on WSP replan (W/F buys in `spend_terms`).

3× smoke medians after recovery (`scripts/smoke_test.sh`, twoland_wsp vs random):

| Step | Median | Notes |
| --- | ---: | --- |
| d35bff5 BASE | **~79,013** | single run post-reset |
| Hotfix (cons unbounded, track_shed off) | ~33,123 | stacked features still broken |
| W0–2 + formula net_tile_ops fix | **63,968** | 54,613 / 63,968 / 64,898 |
| W3 marginal pricing | **71,302** | 65,890 / 71,302 / 73,626 |
| W4 animal-first | **73,026** | 62,472 / 73,026 / 76,617 |
| W5a W/F handoff | **68,707** | 54,874 / 68,707 / 71,607 |
| W5b track_shed + fert | **~27–34k** | **deferred** — enable breaks cascade even with hire-only min_balance and W/F off conservative spend |
| **Recovery final (0–5a)** | **~68,707** | commit `0278e01`; competitive vs pre-overhaul, below BASE ~79k |

Fixes landed: pickup-only §7.3 + `_formula_net_tile_ops` in `bind()`; unbounded `cons` + runtime `open0<0` break only; S6 `fert_today` reset; marginal pricing; animal-first routes; 5a `w_levels`/`f_levels` handoff with `track_shed=False` on replan.

Still open: Wave 5b ledger (`track_shed=True`, hire_reserve on balance only) without conservative W/F spend coupling; Waves 6–8 ROI probe / M2 / hand map without regression.

## Sep 2 session (Sept02 overhaul — prior partial ladder)

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
