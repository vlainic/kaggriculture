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
| **Competition submission** | Local smoke only unless user asks |

## What works

| Item | Notes |
| --- | --- |
| twoland_wsp smoke | ~**87352**; land2 buy ~d8; up to 9 hires when cascade allows |
| Land2 probe | hire5 only on probe day; no queue commit until buy morning |
| TWO layout | Zones I–X; land1 = FIVE geometry; land2 NE snakes |
| WSP conservative cascade | Unchanged from Sep 1 one-land work |
| download_submission_logs.sh | Replays bulk; `--with-logs` optional; skips CSV footer junk |
| `kaggle_logs/` | Gitignored |

## Known issues

| Issue | Notes |
| --- | --- |
| hire9 INFEASIBLE late season | Partial prefix OK; common after land2 expansion |
| Kaggle agent logs API | 403 on ladder episodes; replays work |
| WSP vs zonewise gap | ~87k twoland vs ~107k zonewise one-land |
| hire5 probe UNKNOWN | Occasional 5s timeout; retry next dawn |

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

1. Kaggle A/B twoland vs one-land on matched episodes
2. Reduce late hire9 INFEASIBLE without over-hiring day 0
3. Analyze live replays from `download_submission_logs.sh`
4. Lands 3–4 out of scope for now
5. Do not Kaggle submit without ask

## Do not do unless asked

- Restore full-bank-per-zone WSP hack
- Buy SW/SE (land 3–4) in twoland_wsp
- Runtime `bind()` layout switch mid-game
- Kaggle submit
- Commit `.cursor/` or `kaggle_logs/`
