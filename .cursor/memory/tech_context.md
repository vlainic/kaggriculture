# Tech Context

## Stack

| Layer | Choice |
| --- | --- |
| Runtime | Kaggle Simulations (`kaggle-environments`) |
| Language | Python 3, stdlib-first in submission |
| Optimizer | OR-Tools CP-SAT — **once at import**, zone-count assignment |
| Agent style | Heuristic executor + bounded CP-SAT plan — no RL |
| Bundle | `main.py` + `agent/` + `data/` (rollouts + `handmade_dp_candidates.json`) + vendored ortools |

## Local evaluation

```bash
bash scripts/smoke_test.sh   # agents: use this only (copies handmade_dp_candidates.json)
```

```python
from kaggle_environments import make
env = make("kaggriculture", configuration={"episodeSteps": 720}, debug=True)
env.run(["main.py", "random"])
```

Vs `random` smoke (Aug 15 zone-count + 80k stop): planner ~0.8s, reward ~60k. Vs greedy opponent: ~30k (melon glut) — expected with dump sells.

## Kaggle submit

**Users only:** `bash scripts/smoke_and_submit.sh --submit "msg"`  
Agents never submit without explicit user request (`kaggle-submission.mdc`).

## Planner knobs (`agent/planner.py`)

| Knob | Value | Notes |
| --- | --- | --- |
| `num_workers` | 1 | CPU-polite; user often has other jobs |
| `max_time_in_seconds` | unset | stop via callback or natural OPTIMAL |
| `OBJECTIVE_GOOD_ENOUGH` | 80_000 | import-time early stop |
| `NET_TILE_OPS` | 15 / 13 / 13 / 11 | farmer / hire1 / hire2 / hire3 |
| Balance domain | 0–200_000 | not ±1e6 |
| Catalog | ~109 chains | 108 handmade + IDLE |

Notebook OPTIMAL (same model, threshold 0): ~66s, obj 83620. Do not expect that at Kaggle import.

## Diagnostics

- Logs: `[planner]`, `[exec]`, `[snap]`, `Player 0: reward=`
- `experiments/live_analysis.ipynb` — Kaggle logs
- Assignment Gantt: `OneLand-Assignement-Handmade-Candidates.ipynb`

## Compute

- Kaggle ~1.6 vCPU, 60s overage bank — import solve must stay well under that (80k callback does)
- Do not set CP-SAT `num_workers` to 8 unless the machine is free

## Key docs

| Doc | Purpose |
| --- | --- |
| `docs/project_overview.md` | Game rules |
| `experiments/OneLand-Assignement-Handmade-Candidates.ipynb` | Zone-count master (source of planner model) |
| `docs/weighted_set_packing_failer.md` | Old WSP — do not resume |
| `.cursor/skills/kaggriculture-domain` | Mechanics |
| `.cursor/skills/kaggriculture-agent-conventions` | Agent conventions |

## Cursor config

- Rules: `kaggriculture-stack.mdc`, `kaggle-submission.mdc`
- Skills: `kaggriculture-domain`, `kaggriculture-agent-conventions`, `core-memory-bank`, `core-plan-act`
- `.gitignore` includes `.cursor/` — do not stage `logs.txt`
