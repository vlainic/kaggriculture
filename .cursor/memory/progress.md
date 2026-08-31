# Progress

## Strategic status (Aug 31, 2026)

| Track | Status |
| --- | --- |
| **WSP / season set packing** | Abandoned Aug 12 — `docs/weighted_set_packing_failer.md` |
| **Chain assignment** | **Live** — day-0 + replan via **`dp_catalog.build_catalog`** (not handmade JSON) |
| **Solver backend** | **Live** — `CURRENT_SOLVER = "zonewise"`; drop-in for monolithic |
| **Dawn replan** | **Live** — lock commitments; empty-only vars; **`track_shed=True`** + shed seeding + liquidity floor; preserve on INFEASIBLE |
| **Day-0 cascade** | **Live** — `cascade_reserve=True` + `min_close0`; partial apply if farmer solves |
| **Layout catalog** | **Live** — `FOUR` + `FIVE`; **`CURRENT = FIVE`**; ops **18/17/16/14/13** (two_lands) |
| **Animal rollouts** | **Live** — `animal_with_pickups.json`; ops cap = `daily_tile_ops` only |
| **Zonewise cash handoff** | **Live** — close balance (not conservative); stop cascade if `open0 < 0` |
| **Runtime fertilizer** | **Live** — collect from animals, FERTILIZE after WATER |
| **Snake executor** | Working; same-day BUILD/PLACE; skip d=0 replan; day-0 productivity check |
| **Sell policy** | 50% floor; premium sell DP; **WOOL daily cap** `max(4, T//8)`; wheat feed reserve |
| **Competition submission** | Local smoke only unless user asks |

## What works

| Item | Notes |
| --- | --- |
| Zone-count master | Counts per zone/chain; IDLE fills leftover slots |
| DP catalog | Lags + near-best insert variants (best pinned); greedy multi-extra prefix; no forced W/C prefix |
| Replan triage | Variable = `_replan_eligible`; else `_stamp_tile_commitment` → locked |
| Replan shed + liquidity | `track_shed=True`; W/F from obs; `min_balance` floor on dawn |
| INFEASIBLE preserve | Keep old queues; never IDLE wipe |
| Pickups + single ops | Cap uses `daily_tile_ops` (+ hire preamble); no wheat/animal/fert side counters |
| Smoke PLACE/BUILD | Require `BUILD≥1` if any PLACE (pasture reuse OK) |
| Zonewise money | Close balance handoff; `cascade_reserve` reserves downstream cash on day-0 |
| Replan liquidity | `min_balance = hire_reserve + feed_reserve × 3` in zonewise solve |
| Day-0 partial apply | Farmer prefix OK; FIVE no script fallback on solver fail |
| Wool sell pacing | `sell_dp` + `pricing`: WOOL cap 13/day (T=100) |
| Fallback `_build_tile_queues()` | FOUR handmade only if `CURRENT is FOUR` |

## Known issues

| Issue | Notes |
| --- | --- |
| Late-day replan INFEASIBLE | **2** `active=none` days in smoke (d=11–12); was 6–8 on Kaggle logs |
| d=3 bank near zero | Liquidity floor helps solver; market execution still drains to ~$1 |
| Score variance FIVE | Smoke ~91–107k post-fix; historical 98k then ~64k — do not bank peaks |
| **Weeds from missed watering** | Occasional; guardrail experiments reverted |
| **I0 vs dump sells** | Wool cap helps; melon glut dumps still hurt |
| `.cursor/` gitignore | Do not stage |

## Session archaeology (Aug 27)

| Change | Effect |
| --- | --- |
| Conservative zone cash cascade (notebook) | Next zone can't spend unbanked mid-day sells |
| DP notebook ← `dp_catalog` | `lags=` knob; ~45–70+ chains depending on insert knobs |
| Insert thin without best-pin | Dropped argmax chains → worse MIP ceiling |
| Best-pin + multi-extra mono | 2× MELON/TOMATO when they fit |
| Agent ← `animal_with_pickups.json` | Honest PICKUP/BUILD/PLACE in tapes |
| Cap still summed pickups side-channels | ~90k → sub-50k |
| Cap = `daily_tile_ops` only | Removes double-count |

## Aug 31 session (Kaggle log three fixes)

| Fix | Change | Smoke result |
| --- | --- | --- |
| **1 — Day-0 cascade reserve** | `_downstream_cash_reserve()` → `min_close0`; `cascade_reserve=True` from `_build_from_solver` | All 5 zones OPTIMAL day-0; no `hire1 INFEASIBLE` |
| **2 — Replan liquidity floor** | `min_balance` in zonewise; hire + 3× feed reserve from `planner.replan` | `active=none` days 2 vs 6–8; d=3 bank still tight |
| **3 — Wool sell pacing** | `_premium_daily_cap()` in `sell_dp` + `pricing.allowed_sell_qty` | ~231 wool sold/game vs burst dumps to $1 |

Also: zonewise drop-in simplification; replan `track_shed=True`; FIVE ops synced; circular import fix (`STARTING_MONEY` in planner); `experiments/hire1_idle_repro.py` diagnostic.

## What's left

1. Kaggle A/B: Fix 1 alone vs Fix 1+2 (metrics: `active=none`, d=3 bank, d=12 empties, wool revenue)
2. If d=3 still ~$0: raise `LIQUIDITY_DAYS` or tighten `min_balance`
3. Optional: per-zone hire targeting if empty tiles persist at d=12
4. **Later:** watering guardrails; two-land
5. Do not revive WSP

## Do not do unless asked

- Revive WSP
- Shed `PICKUP FERTILIZER`
- Replan on day 0
- Kaggle submit
- IDLE-wipe on replan INFEASIBLE
- Re-enable replan `track_shed=False` without ablation
- Re-add pickup/place/fert side terms to ops cap while using pickups JSON
- Treat 80k/98k/83620 as achieved bank
- Delete `FOUR` when adding layouts — flip `CURRENT`
- Author zone geometry as JSON
- Commit `.cursor/`
