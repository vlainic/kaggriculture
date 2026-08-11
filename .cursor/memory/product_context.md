# Product Context

## Why this project exists

Compete on Kaggriculture by shipping an autonomous agent that outplays typical heuristic and LLM-assisted submissions. The game models supply-chain dynamics — reactive pricing, town demand growth, labor scheduling, capital investment — which suits precise arithmetic and bounded optimization over language-model improvisation.

## Problem shape

Not a static allocation puzzle:

- **Market is endogenous** — sell volume moves prices in real time; opponents share the same pool.
- **State is time-coupled** — watering windows, ongoing-crop ticks, animal care-bonus banking, weed/flee risk.
- **Demand is non-stationary** — shops unlock randomly every 3 days; town center consumption steps up at days 10 and 20.
- **Action budget is tight** — 1 farm action per worker + ≤10 market orders per turn for 720 turns.
- **Farmer vs market are decoupled** — market orders do not consume the single farmer op per turn.

## Intended agent behavior

1. **Early season:** establish reliable crop loop on one 5×5 quadrant; place animals where CP-SAT weights justify feed/build cost.
2. **Mid season:** expand land, hire hands when Fibonacci hire cost is worth throughput gain, time sells before glut.
3. **Late season:** liquidate inventory; bank coins matter, not shed stockpile; catch-up animal harvests (wool/eggs/milk).

## Strategic hypotheses (validated in agent)

- Goose/egg, cow/milk, sheep/wool compete with crops in shared daily op budget — planner picks mix via live-weighted CP-SAT.
- Premium goods crash to $1 on modest overproduction — sell-all each turn mitigates for now.
- Town demand grows monotonically; **unlocked shops** boost weights via `(1 + demand)` on revenue (crops + EGG/MILK/WOOL).
- Seed/animal purchase costs are **fixed**; product sell prices and WHEAT feed cost are **dynamic** — replan uses live `obs["market"]["prices"]`.
- End-of-day idle farmer hours still allow market buys — agent pre-buys tomorrow seeds/fert/wheat after snake completes.

## Current agent scope (Aug 11, 2026)

- **5×5 NW quadrant**, farmer + 3 daily hires; per-worker tile zones and snake routes.
- Day-0 CP-SAT full plan; greedy `patch_plan` for freed tiles (no daily CP-SAT).
- Crops: `no_fert`; animals: `with_care` (BUILD + PLACE + FEED + CARE + HARVEST).
- Locked hand spawns must route via **`SHED_DOOR (4,4)`** for shed PICKUP — critical for hire2/hire3 animal ops.
- Sell-all shed products each turn (WHEAT reserve for live animals).
- **Submit:** users only — `scripts/smoke_and_submit.sh --submit "msg"`; agents use `smoke_test.sh`.

## User workflow preferences

- Plain `.py` modules only (no notebooks in submission)
- Plan/Act mode via `core-plan-act` skill
- Use subagents: `strategy-analyst` (economics), `kaggle-agent-dev` (code), `eval-runner` (backtests)
