---
name: Concave sink revenue
overview: Replace the linear per-pattern harvest revenue in the zone CP-SAT with a concave piecewise-linear revenue per product, with segments sized by market drain (town center plus shops). This should stop melon over-picking and let strawberry, carrot and tomato fill to their sink. Zone pooling is a separate later change.
todos:
  - id: concave-curves
    content: Add CONCAVE_PRODUCTS and build_revenue_curves (drain-sized flat block then declining blocks, non-increasing marginals) in milos/wsp/mip.py
    status: completed
  - id: concave-objective
    content: In solve_zone add segment vars u_{p,k} with sum == U_p and concave objective terms; drop harvest revenue for CONCAVE_PRODUCTS from _pattern_weight
    status: completed
  - id: sink-plumbing
    content: Add sink_units kwarg through twoland.solve/solve_zone; compute from build_drain_by_day / build_drain_horizon at planner call sites; add [concave] log line
    status: completed
  - id: concave-smoke
    content: py_compile + smoke_test; 3 V55 smokes; compare wsp_plan product mix, [concave] lines, zone solve time, and our reward vs ~95-103k baseline
    status: completed
isProject: false
---

# Concave, sink-aware revenue in the WSP MIP

Source: [.cursor/logs.txt](.cursor/logs.txt). Revenue gap is strawberry (-52k), wool, wheat, fertilizer; melon is +13k over the opponent. The WSP objective cannot see sinks, so it ranks products per tile-day. Zone pooling (PASS labor) is out of scope here.

## What the code does today

- [milos/wsp/mip.py](milos/wsp/mip.py) `_pattern_weight` walks `price_of(product, hday, n)` per pattern, starting at `locked_counts`. Every pattern is priced independently, so picking the same pattern on 5 tiles in one zone counts 5x the full price. Concavity exists only across zones (the `locked_harvest` carry in [milos/wsp/twoland.py](milos/wsp/twoland.py)).
- The only in-zone limit is the hard `product_caps` (`_glut_headroom`, stops at 0.5 x base price at mid-horizon). It is lax: the log shows `caps MELON=400`.
- `price_of` (from [milos/price_forecast.py](milos/price_forecast.py)) already bakes in drain and opponent supply in its baseline. `extra_units` only adds our own units, with no drain relief.
- The day-0 live solve is bypassed (INFEASIBLE, then hardcoded template), so this change affects dawn replans (d1+) and NE/SW zone solves.

## Change 1: concave revenue terms in `solve_zone`

In `solve_zone` ([milos/wsp/mip.py](milos/wsp/mip.py)), for each product in `CONCAVE_PRODUCTS = (MELON, STRAWBERRY, MILK, WOOL, CARROT, TOMATO)`:

- Total units this zone: `U_p = sum(x[pi, tile] * pat["harvest_units"][p])`.
- Segment variables `u_{p,k}` with `0 <= u_k <= B_k` and `sum_k u_k == U_p`. Objective adds `sum_k m_k * u_k`.
- Marginals `m_k` are non-increasing (enforce with a running min), so maximization fills segments in order and needs no binaries. Last segment is sized to cover the maximum possible `U_p` at the price floor (at least $1).
- In `_pattern_weight`, drop harvest revenue for `CONCAVE_PRODUCTS` (keep `-setup_cost` and `_animal_valuation_bonus`). WHEAT and FERTILIZER stay linear for now; wheat is coupled to feed and `buy_w`.
- Keep `product_caps` as a safety net; it becomes redundant.
- Cash and balance constraints (`cash_by_day`) are unchanged: they still use the per-pattern forecast price. Only the objective changes.

## Change 2: sink-aware segment builder

New helper `build_revenue_curves(price_of, horizon, locked_counts, sink_units)` in [milos/wsp/mip.py](milos/wsp/mip.py):

- Reference day `rel_ref = horizon // 2` (same convention as `_glut_headroom`).
- `D_p` = expected market drain of product p over `[rel_ref, horizon)`: town center plus unlocked shops plus the unlock prior.
- Units up to `D_p` are priced flat at `price_of(p, rel_ref, locked)`, since the market absorbs them. Beyond that, unit `u` is priced at `price_of(p, rel_ref, locked + (u - D_p))`, in blocks of about 5 units.
- This is the intended behavior: melon (town center only, about 140 units per game) gets a small flat block then a steep decline; strawberry (four shops) gets a large flat block.
- This is an approximation: all units are treated as sold at the reference day and early harvest cannot use later drain. Per-week buckets are a later refinement.

## Change 3: pass drain into the solver

- `sink_units` per product comes from `price_forecast.build_drain_by_day(obs, horizon)` (live replans) and `town_drain.build_drain_horizon(0, [], 30)` (day 0).
- Add an optional `sink_units` kwarg to `twoland.solve` and `mip.solve_zone`; call sites are in [milos/planner.py](milos/planner.py) (`build_day0`, `_replan_active`, and the NE/SW zone solves).
- `locked_harvest` carry across zones stays as is, so units used by earlier zones shift the start of the next zone's curve.
- Add a log line per zone: `[concave] zone=.. STRAWBERRY D=.. m0=.. mlast=.. MELON D=.. m0=.. mlast=..`.

## Verification

1. `py_compile` on touched modules; `smoke_test.sh` passes.
2. Three V55 smokes; judge by **our reward**, not margin (opponent bank swings 155-186k).
3. In `scripts/smoke.txt`:
   - `wsp_plan` pick counts: STRAWBERRY up, MELON down, carrot/tomato up.
   - `[concave]` lines look sane (melon D small, strawberry D large).
   - Per-product revenue by product (sold units x price): strawberry units should rise from about 61 toward the opponent's about 298.
   - Zone solve time stays inside the per-zone budget (no new INFEASIBLE/picks0 lines).
4. Compare against the current best (about 95-103k). If reward drops, revert; do not submit from the agent.

## Risks

- Solver time: about 6 products x about 12 segments adds about 70 integer vars per zone; expected trivial, but check `time=` in `[milos/wsp]` lines.
- Cash coupling still uses linear forecast prices, so early-cash behavior may not change much; if strawberry is still undervalued, apply the same segments to `cash_by_day` as a second step.
- `price_of` already models the opponent's supply; do not add a second haircut.

## Out of scope

- Zone pooling / merging to about 7 tiles per worker (the 75 PASS/day); separate change after this.
- WHEAT, EGG and FERTILIZER concave terms (feed and fertilizer coupling).
- Hire13/14 reassignment.

## Files

- [milos/wsp/mip.py](milos/wsp/mip.py): `CONCAVE_PRODUCTS`, `build_revenue_curves`, `solve_zone` objective, `_pattern_weight`
- [milos/wsp/twoland.py](milos/wsp/twoland.py): pass `sink_units` into `solve_zone`, log `[concave]`
- [milos/planner.py](milos/planner.py): compute and pass `sink_units` at solve call sites
- [milos/price_forecast.py](milos/price_forecast.py) and [milos/town_drain.py](milos/town_drain.py): read-only use for drain
