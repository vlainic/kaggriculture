---
name: d6-11 ablation flags
overview: Wire three default-off flags from the d6–11 ablation guide, plus the smoke wheat-sell whitelist, so each arm can be turned on without touching the control path. Do not run the 15 smokes.
todos:
  - id: abl-flags
    content: Default-off KAGGRI_ABL_LAND/CATALOG/CASH plus [abl] log at step 0
    status: completed
  - id: arm-a
    content: Hourly BUY_LAND from d6 when money clears land+300; SW drops ne_not_full
    status: completed
  - id: arm-b
    content: Full catalog on walk 2, walk 3, and SW buy-replan; staple=0 in accept log
    status: completed
  - id: arm-c
    content: Log [cash] on d6-11 zone solves; flag gives each zone the full remaining balance and hire only on hire days
    status: completed
  - id: smoke-wheat
    content: Whitelist SELL WHEAT checks for step < 144
    status: completed
isProject: false
---

# d6–11 ablation flags

From [docs/milos_agent/Kaggriculture d6–11 ablation guide.md](docs/milos_agent/Kaggriculture%20d6%E2%80%9311%20ablation%20guide.md). The opener stays as it is. This pass only adds the three arms and the smoke whitelist. Flags default **off** (`unset` / `0` is the control). Do not run the 15 smokes and do not fill the results table.

Add `abl_enabled(name)` in [milos/fix_flags.py](milos/fix_flags.py): `KAGGRI_ABL_LAND`, `KAGGRI_ABL_CATALOG`, `KAGGRI_ABL_CASH`, true only when the env value is on. Log `[abl] land= catalog= cash=` once at step 0.

## Arm A — `KAGGRI_ABL_LAND`

Dusk-only at $1300 cannot buy NE on d6. Dawn cash is about $688; the opponent funds land with same-day sales. When the flag is on, check **every hour from day 6** in [milos/market.py](milos/market.py) and append `BUY_LAND` when it is still unowned:

- NE: `money >= 1300` after that hour’s sell orders are counted (sells first in the order list, so same-hour sales can fund the buy). A rejected order is harmless.
- SW: `money >= 2300`, NE already owned. Do not require `ne_not_full`. Leave the CPU overage check and `SW_BUY_FIRST_DAY` (8).

Control dusk thresholds stay as they are. The opener-tape dusk hook is not required for this arm.

## Arm B — `KAGGRI_ABL_CATALOG`

When the flag is on, pass `crops_allowlist=None` at the three threeland12 staple solves in [milos/planner.py](milos/planner.py):

- `_try_activate_sw` (walk 3)
- `_try_activate_ne_staple` (walk 2; day-1 fill uses the same function, and NE is unowned through the opener)
- `replan_after_buy_sw`

`[ne] accept` currently logs `staple=1` from `is_threeland12()`. Log `staple=0` when this flag is on.

## Arm C — `KAGGRI_ABL_CASH`

Do not move harvest credit to `hday + 1`. Same-day credit is already the optimistic timing; delaying it blocks more buys. Do not touch `BUY_REPLAN_OVERAGE_RESERVE`. That 12s figure is CPU time.

What holds cash is the per-zone bank. Walk 2/3 pass `starting_money` then `money - cost` into the next zone ([milos/planner.py](milos/planner.py) `_try_activate_ne_staple` returns `money - cost`). Inside [milos/wsp/twoland.py](milos/wsp/twoland.py), `charge_hire_daily=True` subtracts that hand’s daily cost on **every** horizon day in `_locked_conservative_handoff` and in [milos/wsp/mip.py](milos/wsp/mip.py) `solve_zone`, before later zones see a balance.

On every zone solve with calendar day in 6–11, log `[cash] d= zone= avail= spend_plan=` (`avail` = opening balance the zone was given; `spend_plan` = setup + hire the cascade reserved). This log is on for the control too, so a silent flag is obvious.

When `KAGGRI_ABL_CASH=1`:

- Each zone in the cascade is solved against the **full remaining** bank (farm money, then that minus earlier zones’ planned spend). Not an ops-weighted slice.
- Charge hire only on days that worker is actually hired, not on every day of the horizon.

## Smoke whitelist

[scripts/smoke_episode.py](scripts/smoke_episode.py) treats any `[exec] … SELL WHEAT` at hour 0–4 as a fail. The V55 tape sells wheat on day 0. Ignore those lines when `day * 24 + hour < 144`.

## Check

`KAGGRI_ABL_*=0` (or unset) must keep today’s dusk-only land buys, the staple allowlist, same-day harvest credit, and hire charged every horizon day. With cash flag on, `[cash]` `avail` for a later zone stays near the farm bank minus earlier spend, not a small slice. One smoke is the user’s; this pass does not run the protocol. No Kaggle submit.
