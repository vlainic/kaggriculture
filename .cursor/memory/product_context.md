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

## Current agent scope (Aug 11)

- 3×3 tile snake near shed; no hires; no land unlock beyond default quadrant.
- Crops: `no_fert` profile only.
- Animals: `no_care` profile; BUILD + PLACE + FEED + HARVEST; tiles locked for season once placed.
- Sell-all shed products each turn (WHEAT reserve for live animals).

## User workflow preferences

- Plain `.py` modules only (no notebooks in submission)
- Plan/Act mode via `core-plan-act` skill
- Use subagents: `strategy-analyst` (economics), `kaggle-agent-dev` (code), `eval-runner` (backtests)
