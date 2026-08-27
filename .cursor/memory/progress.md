# Progress

## Strategic status (Aug 27, 2026)

| Track | Status |
| --- | --- |
| **WSP / season set packing** | Abandoned Aug 12 — `docs/weighted_set_packing_failer.md` |
| **Chain assignment** | **Live** — day-0 + replan via **`dp_catalog.build_catalog`** (not handmade JSON) |
| **Dawn replan overhaul** | **Live** — lock commitments; empty-only vars; `track_shed=False`; preserve on INFEASIBLE |
| **Layout catalog** | **Live** — `FOUR` + `FIVE`; **`CURRENT = FIVE`** |
| **Animal rollouts** | **Live** — `animal_with_pickups.json`; ops cap = `daily_tile_ops` only |
| **Zonewise notebooks** | **Live** — handmade + DP; conservative cash cascade |
| **Runtime fertilizer** | **Live** — collect from animals, FERTILIZE after WATER |
| **Snake executor** | Working; same-day BUILD/PLACE; skip d=0 replan |
| **Sell policy** | 50% floor; premium sell DP; wheat feed reserve; no SELL WHEAT h 0–4 |
| **Competition submission** | Local smoke only unless user asks |

## What works

| Item | Notes |
| --- | --- |
| Zone-count master | Counts per zone/chain; IDLE fills leftover slots |
| DP catalog | Lags + near-best insert variants (best pinned); greedy multi-extra prefix; no forced W/C prefix |
| Replan triage | Variable = `_replan_eligible`; else `_stamp_tile_commitment` → locked |
| Replan shed off | `track_shed=False` on dawn only |
| INFEASIBLE preserve | Keep old queues; never IDLE wipe |
| Pickups + single ops | Cap uses `daily_tile_ops` (+ hire preamble); no wheat/animal/fert side counters |
| Smoke PLACE/BUILD | Require `BUILD≥1` if any PLACE (pasture reuse OK) |
| Zonewise money | Conservative: prev start − loss (no sells between zones) |
| Fallback `_build_tile_queues()` | FOUR handmade only if `CURRENT is FOUR` |

## Known issues

| Issue | Notes |
| --- | --- |
| Pickups smoke dip | Pre-fix: double-count → sub-50k; post-fix needs fresh smoke |
| Late-day replan INFEASIBLE | Some dawns still fail under cash/ops; queues preserved |
| Score variance FIVE | Historical 98k then ~64k — do not bank peaks |
| Zoning vs two_lands ops | Live FIVE still 18/13/14/14/15; notebooks often 18/17/16/14/13 |
| **Weeds from missed watering** | Occasional; guardrail experiments reverted |
| **I0 vs dump sells** | Melon plan at $250; glut dumps still hurt |
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

## What's left

1. Re-smoke FIVE after pickups + ops fix; record new baseline
2. Optional: sync `zoning.FIVE` ops to `two_lands.md`
3. Optional: per-worker sequential replan when batch INFEASIBLE
4. **Later:** watering guardrails; two-land
5. Do not revive WSP

## Do not do unless asked

- Revive WSP
- Shed `PICKUP FERTILIZER`
- Replan on day 0
- Kaggle submit
- IDLE-wipe on replan INFEASIBLE
- Re-enable replan W/F shed without ablation
- Re-add pickup/place/fert side terms to ops cap while using pickups JSON
- Treat 80k/98k/83620 as achieved bank
- Delete `FOUR` when adding layouts — flip `CURRENT`
- Author zone geometry as JSON
- Commit `.cursor/`
