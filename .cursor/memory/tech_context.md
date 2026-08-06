# Tech Context

## Stack

| Layer | Choice |
| --- | --- |
| Runtime | Kaggle Simulations (`kaggle-environments`) |
| Language | Python 3 (stdlib-first in submission) |
| Local dev dep | `pip install -U kaggle-environments` |
| Agent style | Heuristic / bounded optimization — **no RL training pipeline** |
| Submission | `main.py` + optional helpers; tar.gz if multi-file |

## Local evaluation

```python
from kaggle_environments import make

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
env.run([agent, "starter"])  # also: "random", "pass", mirror self-play
```

Built-in baselines: `"pass"`, `"random"`, `"starter"`.

## Kaggle submission

```bash
kaggle competitions submit kaggriculture -f main.py -m "description"
```

Validation episode runs agent vs itself; errors → submission marked Error.

## Config defaults (env)

- `episodeSteps`: 720, `startingMoney`: 3000, `boardSize`: 10
- `maxMarketOrdersPerTurn`: 10, `turnsPerDay`: 24, `shedCapacity`: 100
- Town: shop unlock every 3 days; shop consume every 4 turns; center every 12 turns

Full table in `docs/project_overview.md` and `.cursor/skills/kaggriculture-domain/SKILL.md`.

## Compute constraints (submission runtime)

Kaggle runtime ~1.6 vCPU, 6.5 GiB RAM — profile early if using MCTS + daily MILP re-solves. May need shallow master lookahead instead of full MCTS.

## Cursor project config

- **Always-on rule:** `.cursor/rules/kaggriculture-stack.mdc`
- **Skills:** `kaggriculture-domain`, `kaggriculture-agent-conventions`
- **Subagents:** `strategy-analyst`, `kaggle-agent-dev`, `eval-runner`
- **Generic skills kept:** `core-plan-act`, `core-memory-bank`, `thinking-protocol`, `be-brief`

Legacy Godot/NSMK rules, skills, and agents were removed (Aug 2026).

## Repo contents (current)

```
docs/project_overview.md   # full competition rules + obs schema
docs/claude_chat.md        # strategy discussion archive
.cursor/                   # rules, skills, agents, memory
```

No agent code yet — greenfield implementation pending.
