# Progress

## Strategic status (Aug 26, 2026)

| Track | Status |
| --- | --- |
| **WSP / season set packing** | Abandoned Aug 12 — `docs/weighted_set_packing_failer.md` |
| **Handmade-chain assignment** | **Live** — zone-count CP-SAT at import → `TILE_QUEUES` |
| **Dawn replan overhaul** | **Live** — lock commitments; empty-only vars; `track_shed=False`; preserve on INFEASIBLE |
| **Layout catalog** | **Live** — `FOUR` + `FIVE`; **`CURRENT = FIVE`** |
| **Runtime fertilizer** | **Live** — collect from animals, FERTILIZE after WATER |
| **Snake executor** | Working; same-day BUILD/PLACE; skip d=0 replan |
| **Sell policy** | 50% floor; premium sell DP; wheat feed reserve; no SELL WHEAT h 0–4 |
| **Competition submission** | Local smoke only unless user asks |

## What works

| Item | Notes |
| --- | --- |
| Zone-count master | Counts per zone/chain; IDLE fills leftover slots |
| Decode sort | Animals by earliest start_day → IDLE → crops |
| Replan triage | Variable = `_replan_eligible`; else `_stamp_tile_commitment` → locked |
| Replan shed off | `track_shed=False` on dawn only — batch assign succeeds |
| INFEASIBLE preserve | Keep old queues; never IDLE wipe |
| Smoke vs random (FIVE + shed-off, peak) | ~**98.8k** once |
| Smoke vs random (FIVE current) | ~**63.7k** |
| Smoke vs random (FOUR + shed-off) | ~**71–74k** |
| Smoke PLACE/BUILD | Require `BUILD≥1` if any PLACE (pasture reuse OK) |
| Fallback `_build_tile_queues()` | FOUR handmade only if `CURRENT is FOUR` |

## Known issues

| Issue | Notes |
| --- | --- |
| Late-day replan INFEASIBLE | Some dawns still fail under cash/ops even with shed off; queues preserved |
| Score variance FIVE | 98k then ~64k after layout flip round-trip — do not bank 98k |
| **Weeds from missed watering** | Occasional; guardrail experiments reverted |
| **I0 vs dump sells** | Melon plan at $250; glut dumps still hurt |
| **80k callback vs ~49–53k day-0 obj** | Import often FEASIBLE before OPTIMAL |
| `.cursor/` gitignore | Do not stage |

## Replan archaeology (Aug 25–26)

| Change | Effect |
| --- | --- |
| Empty-only + IDLE on INFEASIBLE | ~37k — wiped suffixes |
| `qi==0 and queue` not eligible | Stops daily sheep/cow churn |
| Lock board only (no suffix) | Still INFEASIBLE with shed on |
| Full commitment lock + shed on | Still INFEASIBLE (~0.001s) |
| Drop W/F shed + hire from replan (`track_shed=False`) | Replan assigns; ~98k FIVE |
| Smoke `PLACE ≤ BUILD+1` | False fail when structure reused — fixed |

## What's left

1. Understand FIVE score gap (98k vs 64k) — seed/opponent/replay
2. Optional: per-worker sequential replan when batch INFEASIBLE
3. Optional: export assignment JSON so Kaggle import skips CP-SAT
4. **Later:** watering guardrails; two-land from `data/two_lands.md`
5. Do not revive WSP

## Do not do unless asked

- Revive WSP
- Shed `PICKUP FERTILIZER`
- Replan on day 0
- Kaggle submit
- IDLE-wipe on replan INFEASIBLE
- Re-enable replan W/F shed without ablation (`track_shed=True` on replan was the blocker)
- Treat 80k/98k/83620 as achieved bank
- Delete `FOUR` when adding layouts — flip `CURRENT`
- Author zone geometry as JSON
