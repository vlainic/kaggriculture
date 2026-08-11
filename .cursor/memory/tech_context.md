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
# Local only (agents + users)
bash scripts/smoke_test.sh

# Upload (USERS ONLY — requires explicit flag)
bash scripts/smoke_and_submit.sh --submit "description"
# builds submission.tar.gz: main.py, agent/, data/*.json, vendor/
# then: kaggle competitions submit kaggriculture -f submission.tar.gz -m "..."

# Or manual after smoke_test:
kaggle competitions submit kaggriculture -f submission.tar.gz -m "description"
```

**Agents must NEVER run submit** without explicit user request (see `.cursor/rules/kaggle-submission.mdc`).

Validation episode runs agent vs itself; errors → submission marked Error. **5 submissions/team/day**; only latest 2 tracked; cap resets ~midnight UTC.

## Config defaults (env)

- `episodeSteps`: 720, `startingMoney`: 3000, `boardSize`: 10
- `maxMarketOrdersPerTurn`: 10, `turnsPerDay`: 24, `shedCapacity`: 100
- Town: shop unlock every 3 days; shop consume every 4 turns; center every 12 turns

Full table in `docs/project_overview.md` and `.cursor/skills/kaggriculture-domain/SKILL.md`.

## Compute constraints (submission runtime)

Kaggle runtime ~1.6 vCPU, 6.5 GiB RAM — CP-SAT 8s time limit on **day-0 full solve only**; greedy patch thereafter; greedy fallback on timeout.

## Cursor project config

- **Always-on rule:** `.cursor/rules/kaggriculture-stack.mdc`
- **Skills:** `kaggriculture-domain`, `kaggriculture-agent-conventions`
- **Subagents:** `strategy-analyst`, `kaggle-agent-dev`, `eval-runner`
- **Generic skills kept:** `core-plan-act`, `core-memory-bank`, `thinking-protocol`, `be-brief`

## Repo contents (current)

```
main.py                    # thin agent(obs) → executor.step
agent/
  workers.py               # 5×5 zones, routes, SHED_DOOR, hand mapping
  rollouts.py              # crop templates, SHOP_PRODUCT_DEMAND
  animal_rollouts.py       # animal templates, revenue_in_window, executor ops
  ops_budget.py            # crop/animal executor_ops_by_day dispatch, peak_load
  planner.py               # CP-SAT day-0 + greedy patch_plan
  executor.py              # multi-worker replan, market, snake, SHED_DOOR escape
data/
  crop_rollouts.json
  animal_rollouts.json
docs/project_overview.md
docs/weighted_set_packing.md
scripts/smoke_test.sh       # local only (agent-safe)
scripts/smoke_and_submit.sh # --submit required
scripts/vendor_ortools.sh
vendor/ortools/
.cursor/rules/kaggle-submission.mdc
.cursor/memory/
submissions/260811_4/       # recent ladder logs
```

## Agent tuning knobs

| Knob | Location | Value / notes |
| --- | --- | --- |
| `PLAN_HORIZON` | `rollouts.py` | 28 |
| `SEASON_DAYS` | `rollouts.py` | 30 |
| Per-worker ops | `workers.py` | `NET_TILE_OPS`: farmer/hire1/hire2=15, hire3=14 |
| `SOLVER_TIME_LIMIT_S` | `planner.py` | 8.0 (day-0 only) |
| `SHED_DOOR` | `workers.py` | `(4,4)` — lock-escape target for all hires |
| Crop profile | planner/rollouts | `no_fert` |
| Animal profile | planner/animal_rollouts | `with_care` |
| `WHEAT_FEED_RESERVE_DAYS` | `executor.py` | 2 |
| Shop demand | `SHOP_PRODUCT_DEMAND` | unlocked shops only |
