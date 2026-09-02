# Tech Context

## Stack

| Layer | Choice |
| --- | --- |
| Runtime | Kaggle Simulations (`kaggle-environments`) |
| Language | Python 3, stdlib-first in submission |
| Optimizer | OR-Tools CP-SAT — import + dawn replan |
| Catalog | `agent/dp_catalog.py` WIS (not handmade JSON at runtime) |
| Animals | `data/animal_with_pickups.json` |
| Agent style | Heuristic executor + bounded CP-SAT — no RL |
| Bundle | `main.py` + `agent/` + `data/` (crop + animal_with_pickups + handmade for fallback) + vendored ortools |

## Local evaluation

```bash
bash scripts/smoke_test.sh   # copies crop_rollouts + animal_with_pickups + handmade_dp_candidates
bash scripts/download_submission_logs.sh <submission_id>   # replays; --with-logs optional
```

```python
from kaggle_environments import make
env = make("kaggriculture", configuration={"episodeSteps": 720}, debug=True)
env.run(["main.py", "random"])
```

Historical FIVE smoke (pre-pickups fix): peak ~**98k**, later ~**64k**. Pickups without ops de-dupe → sub-**50k**. Re-smoke after Aug 27 ops fix before banking.

## Kaggle submit

**Users only:** `bash scripts/smoke_and_submit.sh --submit "msg"`  
Agents never submit without explicit user request (`kaggle-submission.mdc`).

## Planner knobs (`agent/planner.py`)

| Knob | Value | Notes |
| --- | --- | --- |
| `num_workers` | 8 | |
| `max_time_in_seconds` | 20 import / **15 replan** | |
| `track_shed` | True day-0 / **False replan** | |
| `OBJECTIVE_GOOD_ENOUGH` | 80_000 | |
| Ops cap | **`daily_tile_ops` + hire preamble** | No wheat/animal/fert side counters with pickups JSON |
| Animals JSON | `animal_with_pickups.json` | |
| Catalog | `dp_catalog.build_catalog` | `lags`, insert tolerance / max_variants |
| Layout switch | `zoning.CURRENT` | `FOUR`, `FIVE`, or **`TWO`** (50 tiles) |
| Solver | `solvers.CURRENT_SOLVER` | **`twoland_wsp`** (default), `zonewise_wsp`, `zonewise`, `monolithic` |

## DP catalog knobs (`agent/dp_catalog.py`)

| Knob | Default | Notes |
| --- | --- | --- |
| `LAGS` | `(0, 1, 2)` | Also animal-only start days |
| `INSERT_TOLERANCE` | `0.05` | Near-best band |
| `INSERT_MAX_VARIANTS` | `4` | After best-pin + day thin |
| Insert crop | mono-greedy extra + mix suffix | Allows 2+ melons/tomatoes when fit |
| Insert animal | single placement | Overlaps animal-only after dedupe |

## Zonewise notebooks

| Notebook | Catalog | Money cascade |
| --- | --- | --- |
| `OneL-Zonewise-CPSAT-Handmade-Catalog.ipynb` | handmade JSON | Conservative (start − loss) |
| `OneL-Zonewise-CPSAT-DP-Catalog.ipynb` | `build_catalog(..., lags=DP_LAGS)` | Same |

## Diagnostics

- Logs: `[planner]`, `[exec]`, `[snap]`, `Player 0: reward=`
- Gantt: zonewise notebooks
- `docs/two_land_approach.md` — pickups / ops double-count history

## Key docs

| Doc | Purpose |
| --- | --- |
| `docs/project_overview.md` | Game rules |
| `docs/two_land_approach.md` | Pickups ops lesson |
| `data/two_lands.md` | TWO layout geometry / hire batches |
| `scripts/download_submission_logs.sh` | Bulk episode replays from Kaggle CLI |
| `.cursor/skills/kaggriculture-domain` | Mechanics |
| `.cursor/skills/kaggriculture-agent-conventions` | Agent conventions |

## Cursor config

- Rules: `kaggriculture-stack.mdc`, `kaggle-submission.mdc`
- Skills: `kaggriculture-domain`, `kaggriculture-agent-conventions`, `core-memory-bank`, `core-plan-act`
- `.gitignore` includes `.cursor/` — do not stage `logs.txt`
