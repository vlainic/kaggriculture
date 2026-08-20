# Sell-Scheduling DP — Codeless Blueprint

Goal: given known harvest inflow and the exact `price(inv)` formula, decide
how much of each product to sell each day to maximize total revenue —
without recreating the melon/wool crash.

---

## 1. Decompose by product first — this is the key simplification
`price(inv)` in the README is a function of **that resource's own inventory
only** — no cross-product terms in the formula. That means you don't need
one joint DP across 9 products; you need **9 independent, much smaller DPs**,
one per sellable product. Only one place breaks this independence (see
Step 6) — everywhere else, solve them separately.

## 2. Define the state (per product)
- `day` (0–29)
- `market_inventory` — discretized into buckets (e.g. steps of 25–50 units)
  around `I0`; you only need to cover the realistic range a single land's
  production could push it into, not the full 0–20,000 span
- `your_shed_stock` — how much of this product you're currently holding
  unsold, bounded by realistic single-land harvest volumes (much smaller
  than the whole-farm shed cap of 100)

## 3. Define the action
Units of this product to sell **today** — an integer from 0 up to
`your_shed_stock`.

## 4. Define the reward — don't use flat price × quantity
Selling N units in one order still walks the price down one unit at a time
(per the README's concurrent one-unit-at-a-time processing). Reward for
selling N units at market_inventory `m` is the **sum of the marginal prices**
as inventory rises unit by unit from `m`, not `N × price(m)`. This is exactly
the mechanism that makes small, frequent sells worth more in total than one
big dump — the DP needs to see that explicitly in its reward function, not
approximate it away.

## 5. Define the transition
- `market_inventory_next = market_inventory − your_sell − opponent_estimate + town_consumption`
  — `town_consumption` from the Monte Carlo shop-unlock forecast;
  `opponent_estimate` from the residual-tracking idea (observed drain minus
  known/town contribution), both already scoped earlier
- `your_shed_stock_next = your_shed_stock − your_sell + new_harvest_arriving_that_day`
  — the harvest inflow isn't guessed; it comes directly from the **already-
  solved tile planner's candidate schedule**, since that's fixed by the time
  you're deciding sells

## 6. Solve backward (standard DP)
Starting from day 29 back to today:
```
value(day, market_inv, stock) =
    max over sell_qty of [ reward(day, market_inv, sell_qty)
                            + value(day+1, next_market_inv, next_stock) ]
```
Backtrack to recover the actual sell schedule per product.

## 7. The one coupling point: whole-farm shed capacity (100 items, all products combined)
This is where per-product independence breaks. Handle it the same way the
tile planner handles its own shared constraint (zone caps on top of
per-tile DP):
1. Solve all 9 products' DPs independently first.
2. If projected combined shed occupancy on any day would exceed 100, run a
   light trim pass across products — sell down whichever product's
   *marginal* $/unit is currently lowest first, since that's the cheapest
   thing to give up.
This mirrors the DP-filter + master pattern already built for tiles —
independent cheap subproblems, one small shared-constraint pass on top.

## 8. Wrap in MPC
Re-solve all product DPs each replan cycle (same trigger discipline as the
tile planner, or its own finer trigger if price is moving faster than tile
state). Re-forecast `market_inventory` drift fresh each cycle; execute only
the near-term day's sell decision; discard and re-derive the rest at the
next replan.

## 9. Validation plan, in order
1. **Single product, by hand first — melon.** Worst offender, zero shop
   demand (cleanest isolated case, per the README's shop table). Confirm
   the DP naturally recommends spreading sells rather than dumping, and
   check that against your own intuition/handmade numbers.
2. **DP vs. current drip heuristic, same harvest schedule.** DP should
   match or beat the heuristic — if it doesn't, something's wrong in the
   formulation, not the concept.
3. **Full pipeline vs. your measured baselines** (39k → 41k with fertilize;
   40k with conservative caps at a 20–40% cost) — this is the real test of
   whether the extra complexity earns its keep.

## 10. Build order
1. Melon-only DP prototype, validated by hand (Step 9.1).
2. Generalize to remaining 8 products — same DP shape, different price
   parameters per the README's table.
3. Add the shed-cap coupling pass (Step 7).
4. Wire into the existing MPC replan loop alongside the tile planner.

Same discipline as everything else in this build: prove it small before
trusting it at full scale.