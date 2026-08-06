# Product Context

## Why this project exists

Compete on Kaggriculture by shipping an autonomous agent that outplays typical heuristic and LLM-assisted submissions. The game models supply-chain dynamics — reactive pricing, town demand growth, labor scheduling, capital investment — which suits precise arithmetic and bounded optimization over language-model improvisation.

## Problem shape

Not a static allocation puzzle:

- **Market is endogenous** — sell volume moves prices in real time; opponents share the same pool.
- **State is time-coupled** — watering windows, ongoing-crop ticks, animal care-bonus banking, weed/flee risk.
- **Demand is non-stationary** — shops unlock randomly every 3 days; town center consumption steps up at days 10 and 20.
- **Action budget is tight** — 1 farm action per worker + ≤10 market orders per turn for 720 turns.

## Intended agent behavior

1. **Early season:** establish reliable crop loop on one 5×5 quadrant; avoid weed/flee losses.
2. **Mid season:** expand land, hire hands when Fibonacci hire cost is worth throughput gain, time sells before glut.
3. **Late season:** liquidate inventory; bank coins matter, not shed stockpile.

## Strategic hypotheses (from early analysis)

- Goose/egg has highest yield/tile/day (1.00) but needs wheat feed + coop build.
- Premium goods (strawberry, melon, milk, wool) crash to $1 on modest overproduction — smooth sells, avoid bullwhip.
- Town demand grows monotonically; forecasting shop-unlock scenarios (only 8 shop types) can inform sell timing.
- Exact obs JSON beats human UI — agent reads `private.shed`, `fertilized_until_day`, etc. directly.

## User workflow preferences

- Plain `.py` modules only (no notebooks)
- Plan/Act mode via `core-plan-act` skill
- Use subagents: `strategy-analyst` (economics), `kaggle-agent-dev` (code), `eval-runner` (backtests)
