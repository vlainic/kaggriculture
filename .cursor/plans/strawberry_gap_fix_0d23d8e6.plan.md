---
name: Strawberry gap fix
overview: Re-enable strawberry cultivation with fertilizer (the opponent made ~58k from 293 strawberries; we sold 8) and adjust melon selling timing to capture same-day harvest value.
todos:
  - id: enable-strawberry-fert
    content: CROP_PROFILES add with_fert; filter catalog to keep with_fert only for STRAWBERRY
    status: completed
  - id: queue-driven-fertilize
    content: "Add soft-lock guard in FERTILIZE: skip if no fert in inv or tile already fertilized; keep _may_fertilize_today returning False"
    status: completed
  - id: reserve-fert-for-strawberry
    content: Use script.horizon_fert_shed_need for reserve (capped ~30); verify zone_fert_pickup_needed fires
    status: completed
  - id: strawberry-forecast-floor
    content: "Add strawberry forecast floor now: max(forecast, 0.9*quote) in price_forecast.py"
    status: completed
  - id: melon-theta
    content: "Add GREEDY_THETA_BY_PRODUCT with MELON: 0.65; use product-specific theta in greedy_premium_sells"
    status: completed
  - id: smoke-verify-strawberry
    content: py_compile + 1-2 V55 smokes; grep wsp_plan for STRAWBERRY_with_fert and FERTILIZE; compare vs 98k baseline
    status: completed
isProject: false
---

# Strawberry gap fix (target +40–55k)

Based on [.cursor/logs.txt](.cursor/logs.txt). The greedy seller fix brought us from 52k to 98k. The remaining 74k gap is mostly strawberries (~58k for opponent vs negligible for us) and melon timing.

## Root cause

The opponent sold **293 strawberries** (~$200 → ~58k revenue) with fertilizer (8 units/harvest). We sold **8** because we disabled crop fertilization. The price held at 196–235 despite heavy opponent supply because four shops plus town center absorb it. Strawberry is the best drain sink in the game.

We removed `with_fert` crop profiles, which halved strawberry value (4 units/harvest vs 8), so the planner never picked it. We sold 410 fertilizer instead of using it on strawberries.

## Fix 1: Re-enable STRAWBERRY_with_fert only

In [milos/wsp/mip.py](milos/wsp/mip.py):

- Change `CROP_PROFILES = ("no_fert",)` to `CROP_PROFILES = ("no_fert", "with_fert")`
- In `build_catalog(...)`, after building the catalog, **filter out `with_fert` for all crops except STRAWBERRY**:
  ```python
  # Keep with_fert only for STRAWBERRY
  filtered = [row for row in catalog 
              if row["profile"] == "no_fert" or 
                 (row["profile"] == "with_fert" and row["crop"] == "STRAWBERRY")]
  ```

This keeps other crops cheap while allowing strawberry to show its true fertilized value.

## Fix 2: Make FERTILIZE queue-driven (with soft-lock guard)

Currently FERTILIZE is blocked. In [milos/tile_ops.py](milos/tile_ops.py):

- In `_crop_action(...)`, replace the `if act == "FERTILIZE": continue` block with a **soft-lock guard**:
  ```python
  if act == "FERTILIZE":
      if inv.get("FERTILIZER", 0) <= 0 or tile.get("fertilized_until_day", -1) >= day:
          continue  # skip if no fert in hand or tile already fertilized
  ```
  This prevents the worker from getting stuck on a FERTILIZE no-op that loops forever.
  
- Keep `_may_fertilize_today(...)` returning `False` (queue is the only driver; no dual paths).

## Fix 3: Reserve fertilizer for strawberries (horizon-based)

In [milos/market.py](milos/market.py):

- In `_sell_orders(...)` where `fert_reserve` is computed, use:
  ```python
  from milos import script
  fert_need = script.horizon_fert_shed_need(me, tile_state, day)
  fert_reserve = min(30, max(10, fert_need))
  ```
  `horizon_fert_shed_need` already counts remaining fert ops for queued `with_fert` tiles.
  
- Verify that `zone_fert_pickup_needed` (profile-aware) fires for zones with strawberries. This should already be wired; grep the smoke log for PICKUP FERTILIZER orders.

- Pass `fert_reserve` into `greedy_premium_sells` (already wired from the greedy seller fix).

## Fix 4: Strawberry forecast floor (apply now)

The forecast may be killing strawberries by over-projecting opponent supply. Apply this now (saves a smoke cycle).

In [milos/price_forecast.py](milos/price_forecast.py) or wherever the planner consumes forecast prices:

- For product `"STRAWBERRY"` only, floor the forecast at 90% of the current quote:
  ```python
  if product == "STRAWBERRY":
      forecast_price = max(forecast_price, 0.9 * current_quote)
  ```
- This prevents bearish opponent-supply over-projection while keeping the forecast for other products unchanged.

## Fix 5: Melon same-day sell (THETA 0.65)

In [milos/sell_dp.py](milos/sell_dp.py):

- Add a product-specific theta map:
  ```python
  GREEDY_THETA_BY_PRODUCT = {
      "MELON": 0.65,
      # others default to 0.85
  }
  ```
- In `greedy_premium_sells(...)`, when checking `theta * base`, use:
  ```python
  theta_p = GREEDY_THETA_BY_PRODUCT.get(product, theta)
  good_price = marginal >= theta_p * base
  ```

This makes melons sell on harvest day (opponent made 15.7k on d10; we made 3.4k on d11 by waiting).

## Verification

1. `py_compile` on touched modules
2. 1-2 V55 smokes: grep `wsp_plan` for STRAWBERRY_with_fert counts and FERTILIZE ops; grep sell log for melon d10–11 timing; check PICKUP FERTILIZER orders
3. Check final rewards: us vs 98k baseline and opp ~182k
4. Report best margin
5. Submit the better of current 98k vs strawberry-fix (agent does not submit)

## Out of scope (cosmetic, skip if short on time)

- `replan_lock._stamp_locked_tile` hardcodes `no_fert` for locked plants, so live strawberries are undervalued in the lock. Cosmetic for today.

## Out of scope (post-deadline)

- Wheat buying round-trip (379 units)
- 13-hand burn
- Day-0 live solve timeout (18.7s → template fallback)
- `replan_lock._stamp_locked_tile` hardcodes `no_fert` (cosmetic)

## Files

- [milos/wsp/mip.py](milos/wsp/mip.py) — `CROP_PROFILES`, catalog filter for STRAWBERRY only
- [milos/tile_ops.py](milos/tile_ops.py) — FERTILIZE soft-lock guard, keep `_may_fertilize_today` False
- [milos/market.py](milos/market.py) — horizon-based fert reserve via `script.horizon_fert_shed_need`
- [milos/price_forecast.py](milos/price_forecast.py) — strawberry forecast floor (90% of quote)
- [milos/sell_dp.py](milos/sell_dp.py) — melon THETA 0.65
