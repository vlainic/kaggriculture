---
name: Empty tiles and pricing
overview: Fill empty NW tiles with wheat chains (double-planting to cover d0-d10), reserve wheat feed before greedy seller sells it.
todos:
  - id: fill-nw-wheat
    content: "Modify _hardcoded_day0_queues: keep 10 melons + 4 animals, fill remaining ~11 tiles with WHEAT chains [d0, d5]"
    status: completed
  - id: reserve-wheat-feed
    content: In greedy_premium_sells room branch, reserve total_wheat_feed_need before selling WHEAT (h5+)
    status: completed
  - id: smoke-verify
    content: py_compile + 3 V55 smokes; check NW full from d1, wheat buys drop from ~332, report us reward
    status: completed
isProject: false
---

# Fill empty NW tiles with wheat chains

Based on [.cursor/logs.txt](/.cursor/logs.txt) item 1. The other items (melon pricing, sheep cutoff) were dropped after review.

## Root cause

**7-11 empty NW tiles from d1-d10**: Day-0 template places 10 melons + 4 animals on 14 tiles, leaving ~11 tiles idle. Meanwhile we buy 332 wheat at ~$45 (~15k) for feed. The real cost isn't the $25 sell price vs $45 buy price (same curve) — it's that buying 332 wheat pushes the price from $25 to $51.

## Fix 1: Fill remaining NW tiles with WHEAT chains

In [milos/planner.py](milos/planner.py) `_hardcoded_day0_queues()`:

**Keep the proven parts** — 10 melons and 4 animals on d0. Just fill the leftover ~11 tiles with wheat **chains**, not single plantings:

```python
def _hardcoded_day0_queues() -> dict[int, list]:
    nw_tiles = sorted({idx for w in NW_WORKERS for idx in WORKER_TILES[w]})
    chains: dict[int, list] = {}
    for i, idx in enumerate(nw_tiles):
        if i < 10:
            chains[idx] = [("MELON_no_fert", 0)]
        elif i in (10, 11):
            chains[idx] = [("COW_with_care", 0)]
        elif i in (12, 13):
            chains[idx] = [("SHEEP_with_care", 0)]
        else:
            # Double-plant wheat to cover d0-d10 (harvest ~d4, replant, harvest ~d9)
            chains[idx] = [("WHEAT_no_fert", 0), ("WHEAT_no_fert", 5)]
```

**Yield math**: 11 tiles x 4 units/planting = ~44 wheat per cycle, ~88 over 10 days (not 200). Still worth it: free land + feed grown instead of bought at inflated price.

## Fix 2: Reserve wheat feed before greedy sells it

The greedy seller's room branch sells WHEAT from h5 on. It will sell the wheat we just grew for feed.

In [milos/sell_dp.py](milos/sell_dp.py) `_greedy_room_products()` or in [milos/market.py](milos/market.py) `_sell_orders()`:

- Before allowing WHEAT in the room-sell candidates, check `script.total_wheat_feed_need(...)` and reserve that much.
- Only sell wheat above the reserve.

```python
# In greedy_premium_sells or _greedy_room_products, when product == "WHEAT":
wheat_reserve = script.total_wheat_feed_need(me, tile_state, day)
sellable_wheat = max(0, shed.get("WHEAT", 0) - wheat_reserve)
```

This ensures we don't sell feed wheat at $25-30 and then buy it back at $45-50.

## Dropped fixes

**Fix 2 (wheat feed credit)**: Dropped. Buy and sell quotes use the same curve, so `buy_price - sell_price` is ~0. The plan hardcoded $45 which was inaccurate. Fix 1 handles the real cost by growing wheat.

**Fix 3 (melon/wool cap)**: Dropped. The `fc_err` showed melon forecast *below* realized price (d28: 189 vs 245), so the forecast isn't inflating melon. The per-tile-day comparison may simply be true. A crude cap would distort the solver for no verified reason.

**Fix 4 (sheep d18 cutoff)**: Dropped as low-value. A sheep bought on d19 still pays back: first yield ~d25, ~6 wool, ~$1.2k against $500 cost.

## Verification

1. `py_compile` on touched modules
2. 3 V55 smokes:
   - NW full from d1 (should be 25/25, not 14-18/25)
   - `grep "BUY_PRODUCT WHEAT"` counts (should drop sharply from ~332)
   - Report **us reward** (not margin — opponent swings 155-186k independently)
3. If NW is full and wheat buys drop, next lever: fill NE/SW tiles the day they're bought (log showed 33 empty on d13)

## Files

- [milos/planner.py](milos/planner.py) — `_hardcoded_day0_queues` fills remaining tiles with wheat chains
- [milos/sell_dp.py](milos/sell_dp.py) or [milos/market.py](milos/market.py) — reserve `total_wheat_feed_need` before room-sell
