# Tech Context

## Stack

| Layer | Choice |
| --- | --- |
| Runtime | Kaggle Simulations (`kaggle-environments`) |
| Language | Python 3, stdlib-first in submission |
| Optimizer (legacy WSP) | OR-Tools CP-SAT — **abandoned for season planning** |
| Agent style | Heuristic / bounded optimization — no RL |
| Bundle | `main.py` + `agent/` + `data/` + vendored ortools |

## Local evaluation

```bash
bash scripts/smoke_test.sh   # agents: use this only
```

```python
from kaggle_environments import make
env = make("kaggriculture", configuration={"episodeSteps": 720}, debug=True)
env.run(["main.py", "random"])
```

## Kaggle submit

**Users only:** `bash scripts/smoke_and_submit.sh --submit "msg"`  
Agents must never submit without explicit user request (`kaggle-submission.mdc`).

## Legacy WSP tuning (do not treat as targets)

| Knob | Location | Notes |
| --- | --- | --- |
| `SOLVER_TIME_LIMIT_S` | `planner.py` | Was 8s → 25s during WSP iteration |
| Day-0 candidates | `planner.py` | ~8775 @ 25 tiles |
| `NET_TILE_OPS` | `workers.py` | 15/15/15/14 — planner only; executor uses more turns |
| `FARMER_DAY0_BONUS` | `planner.py` | Hack; insufficient |
| `PLAN_HORIZON` | `rollouts.py` | 28 |

## Diagnostics tooling

- **`experiments/live_analysis.ipynb`** — parse Kaggle log JSON; needs `[snap]` + `[exec]` lines
- Log patterns: `[planner]`, `[exec]`, `[snap]`, `Player 0: reward=`

## Compute constraints

- Kaggle ~1.6 vCPU, 60s overage bank per episode
- WSP day-0 solve 3–6s (sometimes 25s cap) — **too heavy for multi-land**

## Key docs

| Doc | Purpose |
| --- | --- |
| `docs/weighted_set_packing_failer.md` | WSP post-mortem — **read before planner work** |
| `docs/weighted_set_packing.md` | Original 9×1 formulation |
| `docs/project_overview.md` | Game rules |
| `.cursor/skills/kaggriculture-domain` | Mechanics |
| `.cursor/skills/kaggriculture-agent-conventions` | Agent conventions |

## Repo layout

```
main.py
agent/{workers,rollouts,animal_rollouts,ops_budget,planner,executor}.py  # WSP legacy
data/{crop_rollouts,animal_rollouts}.json
docs/weighted_set_packing_failer.md
experiments/live_analysis.ipynb
scripts/{smoke_test,smoke_and_submit,vendor_ortools}.sh
.cursor/memory/
submissions/260812_*/
```

## Cursor config

- Rules: `kaggriculture-stack.mdc`, `kaggle-submission.mdc`
- Skills: `kaggriculture-domain`, `kaggriculture-agent-conventions`, `core-memory-bank`, `core-plan-act`
