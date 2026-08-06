---
name: kaggriculture-agent-conventions
description: >-
  Conventions for Kaggriculture Python submission agents — entry point, module
  layout, action/market handling, local eval. Load before generating or
  refactoring agent code.
---

# Kaggriculture Agent Conventions

## Scope (read first)

- **Do exactly what was requested.** A JSON/data request does not imply Python loaders, `agent/` modules, or verification scripts.
- **No tests or eval unless the user explicitly asks** — do not run `kaggle-environments`, add `eval/` files, or create verification harnesses proactively.
- **Do not create `.venv`** unless the user asks for local environment setup.

## Entry point

`main.py` at submission root:

```python
def agent(obs):
    return {
        "farmer": ["PASS"],           # one action per active farmer/hand
        "market": [],                 # up to maxMarketOrdersPerTurn orders
    }
```

- `"farmer"` list length = 1 (main farmer) + hired hands for current day.
- Market orders are tuples like `["BUY_SEED", "WHEAT", 1]`, `["SELL", "CARROT", 5]`, `["HIRE"]`, `["BUY_LAND"]`.
- Excess market orders beyond limit are silently dropped — prioritize order.

## Suggested module layout

Only when building/refactoring the submission agent (not for standalone data files):

```
main.py              # thin entry: agent(obs) delegates to controller
agent/
  state.py           # parse obs → typed/named view (farm, shed, market, town)
  planner.py         # high-level daily/seasonal plan
  farm_actions.py    # tile-level: plant, water, harvest, build, dig
  market_actions.py  # sell timing, buy wheat/fertilizer, hire, land
  pricing.py         # price-curve helpers mirroring MARKET_PARAMS logic
```

Optional `eval/run_local.py` **only if the user asks** for local backtesting.

Keep files under ~300 lines; split when a module grows.

## Observation parsing

Key paths (see full schema in `docs/project_overview.md`):

- `obs["player"]`, `obs["day"]`, `obs["hour"]`
- `obs["farms"][player_id]` — public farm state (both players visible)
- `obs["market"]["inventory"]`, `obs["market"]["prices"]`
- `obs["town"]["unlocked_shops"]`
- `obs["private"]["shed"]`, `obs["seeds"]`, `obs["private"]["inventories"]`

Opponent shed is hidden; opponent farm tiles are visible.

## Design constraints

- **Heuristic only** — no training loops, model weights, or RL dependencies in submission.
- **Stdlib-first** — avoid heavy third-party deps beyond what Kaggle provides.
- **Deterministic when possible** — use obs state, not randomness, unless exploring locally.
- **Action budget** — 1 farmer action + ≤10 market orders per turn; coordinate hires with farm workload.
- **Shed cap** — 100 items; overflow discarded at end-of-day; do not over-harvest without sell plan.

## Local evaluation

**Only when the user explicitly requests testing or eval.**

```python
from kaggle_environments import make

env = make("kaggriculture", configuration={"episodeSteps": 720})
env.run([agent, "starter"])
final = env.steps[-1]
for i, s in enumerate(final):
    print(f"P{i}: reward={s.reward}, status={s.status}")
```

Compare against `"random"`, `"starter"`, and prior agent versions. Use `eval-runner` agent for systematic backtests **when the user asks**.

## Handoff

- Strategic crop/market/timing decisions → `strategy-analyst` agent.
- Implementation and refactors → stay in this repo following these conventions.
