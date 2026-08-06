---
name: kaggriculture-domain
description: >-
  Kaggriculture game mechanics — crops, animals, market pricing, town demand,
  turn order, config defaults. Load when analyzing strategy, economy, or
  agent behavior for this Kaggle competition.
---

# Kaggriculture Domain Reference

**Source of truth:** [docs/project_overview.md](../../docs/project_overview.md). Re-read that doc for action syntax, observation schema, submission format, and anything not summarized here.

## Season & win condition

- 720 turns (24 turns/day × 30 days); winner = most **bank coins** at end (shed/inventory unsold does not count).
- Ranking uses win/loss/tie only — coin margin does not affect rating.

## Object economics (condensed)

| Type | Yield | Seed | Base $ | First yield | Max yield day | Notes | Yield/tile/day |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Wheat | One-time | 10 | 25 | 2d | 4d | max 6 w/ fert, 4 without | 0.80 |
| Carrot | One-time | 20 | 35 | 2d | 3d | max 4 w/ fert, 3 without | 0.75 |
| Tomato | Ongoing | 50 | 60 | 8d | 11d | daily ×4 then decays | 0.33 |
| Strawberry | Ongoing | 100 | 120 | 10d | 16d | every other day ×4 | 0.24 |
| Melon | One-time | 80 | 250 | 10d | 10d | bonus window 6–12, cap at 10d | 0.55 |
| Goose/Egg | Ongoing | 300 | 50 | 4d | — | daily, max 4 held; +1 build coop | 1.00 |
| Cow/Milk | Ongoing | 400 | 160 | 8d | — | every 2d; max 6 held; +1 build pasture | 0.50 |
| Sheep/Wool | Ongoing | 500 | 200 | 6d | — | every 3d; max 6 held; +1 build pasture | 0.33 |
| Fertilizer | — | — | 100 | — | — | from animals; sellable | — |

**Care rules:** plants need water every day (2 missed → weed); animals need wheat feed daily (2 missed → escape). Fresh plantings start `consecutive_unwatered = 1` — no grace period.

## Market price function

```python
price(inv) = base + sign · amp · f(|inv − I0|)
  sign = +1 if inv < I0 else −1
  amp  = target · base / f(T)
  f ∈ {linear, sq, sqrt, log, log10}   # log = ln(1+x)
```

Floored at $1. Sell price at pre-sell inventory; buy price at post-buy. Immediate buy→sell nets zero.

| Resource | Base | T | Below | Above | P(I0−T) | P(I0+T) |
| --- | --- | --- | --- | --- | --- | --- |
| Wheat | 25 | 400 | sqrt/0.80 | log/0.20 | $45 | $20 |
| Carrot | 35 | 450 | log/0.20 | sqrt/0.70 | $42 | $10 |
| Tomato | 60 | 200 | linear/0.40 | sqrt/0.60 | $84 | $24 |
| Strawberry | 120 | 100 | sqrt/0.70 | linear/1.60 | $204 | $1 |
| Melon | 250 | 300 | log/0.20 | sq/3.60 | $300 | $1 |
| Egg | 50 | 332 | linear/0.40 | log/0.20 | $70 | $40 |
| Milk | 160 | 122 | sqrt/0.60 | linear/1.60 | $256 | $1 |
| Wool | 200 | 105 | log/0.20 | sq/3.20 | $240 | $1 |
| Fertilizer | 100 | 200 | linear/0.40 | linear/0.40 | $140 | $60 |

Premium resources (base > $100) crash to $1 floor quickly on glut — timing and bundling matter.

## Town demand

Shops unlock every 3 days (random, no duplicates). Each shop consumes 1 of each demanded product every 4 turns (6/day). Single-product shops consume 2×.

| Shop | Demands |
| --- | --- |
| Bakery | eggs, wheat |
| Pizza Shop | milk, tomatoes, wheat |
| Brunch Spot | eggs, wheat, strawberries |
| Yarn Store | wool (2×) |
| Ice Cream Shop | strawberries, milk, wheat |
| Pet Cafe | carrots (2×) |
| Smoothie Shop | strawberries, milk |
| Farmers Market | wheat, carrots, tomatoes, strawberries |

Town center: 1 of every product (excl. fertilizer) every 12 turns → 2/day after day 10, 4/day after day 20.

## Turn processing order

1. Action validation
2. Player actions (simultaneous)
3. Market queue (concurrent, one unit at a time across players; max 10 orders/turn)
4. Town consumption
5. Observations + day refresh (plants/animals, prices, bank, farm state)

## Config defaults

| Parameter | Default |
| --- | --- |
| episodeSteps | 720 |
| boardSize | 10 (four 5×5 quadrants) |
| startingMoney | 3000 |
| maxMarketOrdersPerTurn | 10 |
| turnsPerDay | 24 |
| shedCapacity | 100 |
| weedSpawnChance | 0.005 |
| townShopUnlockInterval | 3 |
| townShopSellInterval | 4 |
| townCenterSellInterval | 12 |

Land unlock costs: $1k, $2k, $4k. Farm hands: `farmHandCostMult × fib(n)` per day (default mult = 1).
