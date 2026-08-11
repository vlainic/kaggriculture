# Tech Context

## Stack

| Layer | Choice |
| --- | --- |
| Runtime | Kaggle Simulations (`kaggle-environments`) |
| Language | Python 3 (stdlib-first in submission) |
| Local dev dep | `pip install -U kaggle-environments` |
| Optimizer | OR-Tools CP-SAT (vendored for Kaggle) |
| Agent style | Heuristic / bounded optimization — **no RL training pipeline** |
| Submission | `main.py` + `agent/` + `data/` + vendored ortools; tar.gz |

## Local evaluation

```python
from kaggle_environments import make

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
env.run(["main.py", "random"])  # also: "starter", "pass", mirror self-play
```

Built-in baselines: `"pass"`, `"random"`, `"starter"`.

## Kaggle submission

```bash
bash scripts/smoke_and_submit.sh [message]
# builds submission.tar.gz: main.py, agent/, data/*.json, vendor/
kaggle competitions submit kaggriculture -f submission.tar.gz -m "description"
```

Validation episode runs agent vs itself; errors → submission marked Error.

## Config defaults (env)

- `episodeSteps`: 720, `startingMoney`: 3000, `boardSize`: 10
- `maxMarketOrdersPerTurn`: 10, `turnsPerDay`: 24, `shedCapacity`: 100
- Town: shop unlock every 3 days; shop consume every 4 turns; center every 12 turns

Full table in `docs/project_overview.md` and `.cursor/skills/kaggriculture-domain/SKILL.md`.

## Compute constraints (submission runtime)

Kaggle runtime ~1.6 vCPU, 6.5 GiB RAM — CP-SAT 8s time limit per replan; greedy fallback on timeout.

## Cursor project config

- **Always-on rule:** `.cursor/rules/kaggriculture-stack.mdc`
- **Skills:** `kaggriculture-domain`, `kaggriculture-agent-conventions`
- **Subagents:** `strategy-analyst`, `kaggle-agent-dev`, `eval-runner`
- **Generic skills kept:** `core-plan-act`, `core-memory-bank`, `thinking-protocol`, `be-brief`

## Repo contents (current)

```
main.py                    # thin agent(obs) → executor.step
agent/
  rollouts.py              # crop templates, SHOP_PRODUCT_DEMAND, DAILY_OP_BUDGET
  animal_rollouts.py       # animal templates, revenue_in_window, executor ops
  ops_budget.py            # crop/animal executor_ops_by_day dispatch, peak_load
  planner.py               # CP-SAT set packing (crops + animals)
  executor.py              # replan, market, sticky snake, animal pending
data/
  crop_rollouts.json
  animal_rollouts.json
docs/project_overview.md
docs/weighted_set_packing.md
scripts/vendor_ortools.sh
scripts/smoke_and_submit.sh
vendor/ortools/            # vendored wheels for Kaggle
.cursor/memory/            # this memory bank
submissions/260811_1/      # broken run logs
submissions/260811_2/      # improved run + debug artifacts
```

## Agent tuning knobs

| Knob | Location | Value / notes |
| --- | --- | --- |
| `PLAN_HORIZON` | `rollouts.py` | 28 |
| `SEASON_DAYS` | `rollouts.py` | 30 |
| `DAILY_OP_BUDGET` | `rollouts.py` | 16 (snake moves implicit) |
| `FIRST_DAY_OP_RESERVE` | `rollouts.py` | 1 |
| `SOLVER_TIME_LIMIT_S` | `planner.py` | 8.0 |
| Crop profile | planner/rollouts | `no_fert` |
| Animal profile | planner/animal_rollouts | `no_care` |
| `WHEAT_FEED_RESERVE_DAYS` | `executor.py` | 2 |
| Shop demand | `SHOP_PRODUCT_DEMAND` | unlocked shops only |
