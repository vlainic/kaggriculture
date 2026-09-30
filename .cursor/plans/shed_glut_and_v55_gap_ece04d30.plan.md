---
name: Shed glut and V55 gap
overview: "Fast one-pass rollout with no new flags and no bisect (final deadline today 23:59 UTC): greedy seller anchored to the dawn quote, slot-aware orders, legacy guard removal, dead-hand stand-down, animal valuation fix, no geese, no crop fertilizer, live day-0 solve with a hardcoded fallback. Validate minimally with py_compile, smoke_test.sh and 2-3 V55 smokes."
todos:
  - id: a0-shed-log
    content: Shed composition + est_dropped logs (h0/h23); parse_shed composition/est_dropped/mean_dawn_shed
    status: completed
  - id: a1-greedy-sell
    content: Greedy water-fill premium seller, THETA anchored to dawn quote, dynamic shed target, liquidation from d27
    status: completed
  - id: a2-slot-budget
    content: Slot-aware MAX_ORDERS budgeting (sells fill leftover slots), assert total <= 10 incl. day-29 path
    status: completed
  - id: a3-remove-legacy
    content: Replace room_glut/opp_dump/sell_lead/animal product throttle with greedy path; keep simple room backstop + shed_full animal guard
    status: completed
  - id: e-no-crop-fert
    content: CROP_PROFILES no_fert only; _may_fertilize_today False; keep COLLECT_FERTILIZER
    status: completed
  - id: b-stand-down
    content: Rebinding check first, then N=3 dead-hand ratchet for NE/SW (skip NW) with 2-day cooldown
    status: completed
  - id: c1-animal-credit
    content: "Animal pattern weight: fert credit 90*max(0.2,(29-day)/29) minus feed wheat cost"
    status: completed
  - id: c2-no-goose
    content: Drop GOOSE from build_patterns and market animal needs
    status: completed
  - id: d-day0-live
    content: Live day-0 solve (bypass prestart.json), log solve time; hardcoded d0 template fallback if slow/odd
    status: completed
  - id: validate-min
    content: py_compile, scripts/smoke_test.sh, 2-3 V55 smokes; report mean margin vs -103k and opponent bank; no Kaggle submit
    status: completed
isProject: false
---

# Shed glut, dead hands, valuation, day-0: fast one-pass plan

Source: [.cursor/logs.txt](.cursor/logs.txt). Constraints: no Kaggle submit by the agent (user submits), no new test or eval harnesses, `track_shed=False` stays on WSP replan (Sept02 rejection). **No new env flags and no bisect** in this pass; changes replace the legacy behaviour directly. Existing flags in [milos/fix_flags.py](milos/fix_flags.py) stay untouched.

## Why the prior disposal pass failed

The local smoke `scripts/smoke_runs/v55_seat0_01.txt` shows `shed_total=100` at every dawn d15-d29 even with all disposal flags on, so this is not Kaggle-only.

- **Seller is throttled on purpose.** `sell_dp` logs `quota=MELON=1..2 MILK=3..9` while melon inventory is about 10,050 (quote about base $250). Cause: DP `HOLD_COST` (about 10 with `KAGGRI_FIX_SELL`) plus `allowed_sell_qty` headroom clamps. The engine sells n units per SELL order in one turn; the cap is 10 orders per turn, not units.
- **Sells are dropped.** `[market] overflow d=12..27 dropped=1..6 had=11..16 cap=10`: 4 HIRE at h0, NE hires at h1, SW hires at h2, buys, fert dump and sells exceed 10, and `sells[:MAX_ORDERS-len(orders)]` truncates the sells.
- **Overflow harvest is destroyed** by the engine's EOD `_drop_inventories_to_shed` / `DROP`; nothing logs it today.
- **Legacy guards fight the symptom** (`room_glut`, `opp_dump`, `sell_lead`, per-product animal cap all defer sells).
- **Leaks elsewhere:** `DEAD_HANDS` in [milos/planner.py](milos/planner.py) is never updated; WSP animal patterns have no fertilizer credit or feed cost; GOOSE is in the catalog; day 0 loads `milos/wsp/prestart.json`.

## A. Shed throughput

### A0. Logs (always on)

- At h=0 and h=23: `[shed] d= h= total= MELON:n MILK:n ...`.
- At h23: `[shed_drop] d= hand_inv=X room=Y est_dropped=max(0,X-Y)` from `private["inventories"]`.
- [scripts/smoke_analysis/parse_shed.py](scripts/smoke_analysis/parse_shed.py): dawn composition mean, total `est_dropped`, `mean_dawn_shed`.

### A1. Greedy water-fill seller

New `greedy_sell_plan` in [milos/sell_dp.py](milos/sell_dp.py), called from `_premium_sell_orders` in [milos/market.py](milos/market.py) for MELON, MILK, STRAWBERRY, WOOL.

- **Marginal price** of the k-th unit = `pricing.quoted(inv + k)` (matches the engine's per-unit quoting).
- **THETA anchor (fixed):** store the **dawn quote** per product at h=0 each day (`_dawn_quote[p]`), and sell a unit only while `marginal >= 0.85 * _dawn_quote[p]`. Never re-anchor to the start-of-hour quote, so the price cannot ratchet down across 24 hours.
- **Target branch:** while `shed_total > target`, keep selling highest-marginal-first regardless of THETA, but never below `0.5 * base` (existing `PRICE_FLOOR_RATIO`).
- **Dynamic target** = `clamp(cap - projected_premium_inflow_today - margin, 40, 70)`.
- **Liquidation:** from `LIQUIDATE_FROM_DAY` (27) target 0 and THETA 0.3; day 29 keeps the existing full-rotation path.
- WOOL needs no special cap (the 0.85 marginal rule bounds it on the steep curve).
- One SELL order per product per hour; keep `sell_dp.commit_sell` / `record_sells` so forecast and opponent EMA stay fed. `sell_dp.replan` still runs; its quotas no longer gate premium sells.
- Skip WHEAT before hour 5 (existing smoke check "SELL WHEAT hours 0-4").

### A2. Slot-aware order budgeting

In `build_orders` ([milos/market.py](milos/market.py)): count HIRE, BUY_*, fert orders first; sells fill the remaining `MAX_ORDERS - used` slots, highest-value product first. Log `[market] sell_budget dropped_sells=`. Never silently truncate. **Assert total orders <= 10 on every path, including the day-29 rotation** (where `dropped=2` reappeared). HIREs are not moved.

### A3. Remove legacy guards

- `_shed_overflow_sells` becomes a simple backstop: if `total >= cap - ROOM_TRIGGER`, sell cheapest-first. Delete steep deferral, `opp_skip`, batch and day caps, and the `sell_lead` hook in `_premium_sell_orders`.
- `_cap_animal_buy_qty` keeps only the aggregate `shed_full` guard; remove `wool_glut` and per-product pressure skips.
- Leave the now-unused helpers and flag getters in place to avoid churn.

## E. Cut fertilize-on-crops

`CROP_PROFILES = ("no_fert",)` in [milos/wsp/config.py](milos/wsp/config.py); `_may_fertilize_today` in [milos/tile_ops.py](milos/tile_ops.py) returns False. Keep COLLECT_FERTILIZER and the fert dump.

## B. Dead-hand stand-down (NE/SW only)

1. **Do the rebinding check first, before writing the ratchet.** Read `_claim_worker` / slot binding in [milos/executor.py](milos/executor.py) (~lines 630-670) and confirm that removing a middle entry from `ACTIVE_NE` / `ACTIVE_SW` rebinds hands to the correct zones each day. If unsafe, only drop the tail hand.
2. **Leave NW out** (slots bind by spawn position); the savings are in NE and SW.
3. Port the N=3 ratchet from `agent/planner.py` (`update_zone_streaks`, `STUCK_THRESHOLD`): a zone with live=0 and nothing assigned (`picks0` / `empty`) for 3 consecutive dawns is removed via `_rollback_ne_zone` / `_rollback_sw_zone`; `build_orders` already derives hire counts from `len(ACTIVE_*)`.
4. Reactivation uses the existing Walk 2/3 gates (`money - cost >= 0`, `obj - cost >= min_net`) plus a 2-day cooldown to prevent flapping.
5. Log `[planner] zone_streak worker= d= streak= status=stuck|recovered`.

## C. Valuation

- **C1 animal credit** in `_stamp_placement` / `_pattern_weight` ([milos/wsp/mip.py](milos/wsp/mip.py)): add `fert_credit(day) * collect_days - feed_cost * feed_days` to the animal weight, where `fert_credit(day) = 90 * max(0.2, (29 - day) / 29)` (day = calendar day of the collect/feed) and `feed_cost` = wheat quote (config `WHEAT_PRICE = 25` on day 0). Keep cash-flow constraints on real cash; the credit only affects the objective / value gate.
- **C2 no geese:** filter GOOSE out of `build_patterns` and out of `needed_animals` users in [milos/market.py](milos/market.py).
- C3 (grow-own-feed wheat) is **dropped** from this pass.

## D. Day 0

- Bypass `_is_prestart_solve` in [milos/wsp/twoland.py](milos/wsp/twoland.py) so day 0 runs the live cascade with the C1/C2 valuation; log the solve time.
- **Fallback, no tuning:** if the solve is slow (well above about 20s) or the result is not "4+ big animals (COW/SHEEP) and 10+ melons on d0-1", use a hardcoded day-0 template right away (opponent-like: 2 COW + 2 SHEEP on d0, about 12 MELON seeds).

## Validation (minimum)

1. `python3 -m py_compile` on all touched modules, then `bash scripts/smoke_test.sh` (must not error).
2. 2-3 smokes vs V55. Report for each: our reward, **opponent final bank**, margin, `days_at_cap`, `mean_dawn_shed`, `est_dropped`, and any `[market] sell_budget` / overflow lines. Judge by mean margin beating -103k and no crash, keeping in mind that the opponent's variance can swing a single margin.
3. **Agent does not submit to Kaggle.** Safety net for the user: only the latest 2 submissions count, so keep the current best as one of them and use this build as the other.

## Files

- [milos/sell_dp.py](milos/sell_dp.py), [milos/market.py](milos/market.py), [milos/executor.py](milos/executor.py), [milos/planner.py](milos/planner.py), [milos/tile_ops.py](milos/tile_ops.py)
- [milos/wsp/mip.py](milos/wsp/mip.py), [milos/wsp/config.py](milos/wsp/config.py), [milos/wsp/twoland.py](milos/wsp/twoland.py)
- [scripts/smoke_analysis/parse_shed.py](scripts/smoke_analysis/parse_shed.py)
