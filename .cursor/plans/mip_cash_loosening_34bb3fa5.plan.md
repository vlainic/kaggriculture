---
name: MIP cash loosening
overview: Loosen the planner's cash gates so a zone is judged on near-term spend and hire, and so later zones inherit the previous zone's real balance including harvest income. Keep the existing ablation flags, which already cover catalog, land timing, and shed cash.
todos:
  - id: b1-near-term
    content: _zone_plan_cost sums spend on days 0-1 plus one hire day
    status: completed
  - id: b2-gate
    content: Value gate subtracts hire only, not setup
    status: completed
  - id: g1-cascade
    content: Handoff uses solved balance series with income shifted +1 day; hire on occupied days
    status: completed
  - id: g4-walk3
    content: Run walk 3 every dawn, drop the NE-grew skip
    status: completed
isProject: false
---

# Loosen MIP cash gates

The MIP cash rows in [milos/wsp/mip.py](milos/wsp/mip.py) already enforce `balance[d] >= 0` with harvest credited on the harvest day. What blocks commitment is the judgment outside the solver. Two of the items in [.cursor/logs.txt](.cursor/logs.txt) are bugs; the rest are the cascade and the walk-3 gate.

## B1 — affordability is near-term only

In [milos/planner.py](milos/planner.py), `_zone_plan_cost` sums every `spend_by_day` entry over the horizon plus `hire × horizon`, and `_try_activate_ne_staple` / `_try_activate_sw` reject when `money < cost`. A zone that replants three times must hold all of that cash today.

Change `_zone_plan_cost` to sum spend on relative days 0–1 only, plus one day of hire. Apply that at both activation checks and at the per-zone checks inside `replan_after_buy` and `replan_after_buy_sw`. The solver's balance rows still block a plan that goes broke later.

## B2 — value gate subtracts setup twice

`_pattern_weight` returns `rev − setup_cost`, so `result.zone_objectives` is already net of setups. `_zone_value_ok` then computes `obj − cost`, and `cost` contains those setups again plus `hire × horizon`.

Pass the gate `obj − hire × horizon` (one day's hire when `abl_cash_enabled()`). Drop setup from the subtraction. Keep `KAGGRI_ZONE_MIN_NET` and `KAGGRI_ZONE_MARGIN_RATIO` applied against that hire figure.

## G1 — cascade credits income, hire on active days

In [milos/wsp/twoland.py](milos/wsp/twoland.py) the next zone receives `res["conservative"]`, which is opening cash minus spend and hire and never adds `cash_by_day` harvest income. With `abl_cash` it is worse: every zone is given a flat `bank` with no income at all.

After a solved zone, hand the next zone that zone's `balance` series (the `balance_vars` already solved in `solve_zone`; return them alongside `conservative`). The solver itself keeps same-day harvest credit. In the handoff only, shift credited income to harvest day + 1: sells land the next day, and premium stock is held under THETA, so a later zone must not plan against cash that has not arrived. Charge hire only on the days that hand has tile ops, taken from the picked patterns' `occupied_days`, in both `solve_zone` and `_locked_conservative_handoff`. Do this for the control path too, so it is not gated behind `KAGGRI_ABL_CASH`.

## Already done — leave the flags

`KAGGRI_ABL_CATALOG`, `KAGGRI_ABL_CASH` (shed-value cash is the remaining piece of R2; money-only is what the code passes today), and `KAGGRI_ABL_LAND` are in place and default on. R4 (all pending zones one dawn) and R6 (mid-day buys) are not in this pass.

## G4 — walk 3 every dawn

In `replan()`, drop `len(ACTIVE_NE) == n_ne` so `_activate_next_sw` runs even on a dawn that accepted an NE zone. Keep the `SW_BUY_DAY != day` guard.

## Check

One smoke. On the NE buy day the log should show `[ne] accept` with animals or strawberry in `wsp_plan`, `[cash] avail=` in the hundreds for later zones on days 6–11, and no `reason=low_value` on a fresh zone. Grep d6–11 for failed or partial buys: the engine stops an order when money runs out, which is where an optimistic G1 handoff shows up. No Kaggle submit.