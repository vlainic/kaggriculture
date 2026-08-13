# DP-filter + Master-assignment — implementation plan

Companion code: `dp_filter_master.py` (tested — DP and CP-SAT master both verified working on synthetic data, including a case where the master correctly idles a tile to respect a binding zone cap).

## Architecture recap

```
Per tile:  DP-filter   -> a handful of "variants" (crop sequence + timing),
                           each tagged with an ops-by-day profile and a
                           cash-by-day profile
Master:    assignment   -> pick exactly one variant per tile, subject to
                            (a) each zone's daily ops cap
                            (b) one global running cash-balance constraint
                           maximize total selected value
```

This replaces full WSP (which enumerated every atomic `(tile, crop, plant_day)`
placement across all 25 tiles at once) with two much smaller, exact steps.

## Build order

### Step 1 — Crop/animal templates (`load_templates_from_rollouts`)
Wire your existing `crop_rollouts.json` + a current market-price snapshot into
`CropTemplate` objects. The stub in the code counts ops correctly but uses a
flat `price_snapshot[crop]` per harvest — replace with your real yield
formulas (fertilized bonus window, one-time vs ongoing production). Re-price
every replan, not once per game — this is the same point from the MPC
discussion: static weights go stale as the market moves.

**Animals — handle separately, don't fold into this step.** An animal
placement isn't a bounded interval like a crop; it persists to the end of the
horizon (or game), and its value depends on ongoing CARE-bonus banking, not a
single harvest formula. Per the earlier conclusion: treat animal placement as
a one-off master-level (MCTS) decision made rarely, not something re-decided
by this per-cycle DP/assignment loop. Once an animal is placed, drop that
tile from `generate_tile_candidates` entirely and just subtract its known
daily ops draw from the zone's effective cap for the rest of the horizon.

### Step 2 — Per-tile DP (`weighted_interval_dp`, `build_tile_variants`)
Already implemented and tested. One thing to watch: in the demo, every
crop had exactly 1 op/day whenever active, so `min_gap` only ever traded
"tile active" vs "tile idle" — it didn't get to show off spacing out
*multi-op* days (e.g. a day with both WATER+HARVEST = 2 ops). That's exactly
where `min_gap` variants earn their keep for real crops like tomato/melon —
worth eyeballing the variant outputs against your handmade plan's "3 day
break between harvest and plant" cases once real rollout data is in, to
confirm the spacing matches your hand-derived intuition.

### Step 3 — Master (`solve_master`)
Already implemented and tested, including the cash-balance chain. Two things
to add before wiring it into the executor:

- **Hiring cost as part of the cash chain.** Right now the master only sees
  crop/animal cash flows. Fold in the fib-cost hire schedule as a known,
  fixed daily cost per active worker (deduct from the running balance the
  same way seed costs are), so the master won't pick a plan that starves
  cash once hiring is accounted for — this was the exact failure mode your
  handmade plan's "CHANGES" section fixed by hand (animals dying from cash
  starvation).
- **Shed capacity (100 items, whole-farm).** Not modeled yet. If harvest
  volume across all zones could realistically exceed 100 unsold items at
  once, add one more global per-day constraint the same way cash was added —
  same pattern, just a second running quantity to cap instead of floor at
  zero.

### Step 4 — Rolling horizon wiring
Re-run the whole pipeline (Steps 1–3) on a cadence shorter than the horizon
itself (horizon ≈ 15 days to cover melon/strawberry; replan every 2–3 days).
Each replan:

1. Exclude tiles locked by an animal or a still-growing crop from
   `generate_tile_candidates` — they carry forward as fixed ops/cash draws,
   not re-decided.
2. Re-snapshot market prices into fresh `CropTemplate`s.
3. Re-run DP + master over the remaining open tiles.
4. Hand the chosen variants' `placements` (crop, start day, end day) to the
   executor as the near-term plan; only the next 2–3 days actually get
   executed before the next replan overwrites the rest.

## What to validate before trusting it

- **Sanity-check zone totals against your handmade sheets.** Feed the master
  the same zone caps (15/13/11) and tile counts from your screenshots and
  confirm it reaches value in the same ballpark — if it's wildly higher,
  something's missing from the cost side (likely hiring or shed capacity,
  per Step 3's TODOs); if wildly lower, a constraint is probably too tight.
- **Solve time at real scale.** 3 zones × ~9/12/4 tiles × ~5 variants each is
  tiny for CP-SAT — should solve in well under a second, unlike the
  season-long WSP's 2-minute timeout. Worth timing once real data is in, as
  a direct before/after number for the post-mortem.
- **Compare against the handmade plan's 90105 objective / actual banked
  total**, the same way the WSP comparison was made — but this time check
  the *achieved* bank, not just the solver's optimistic objective, since
  that gap was exactly what made the WSP number untrustworthy.
