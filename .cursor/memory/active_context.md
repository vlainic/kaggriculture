# Active Context

## Current focus (Aug 26, 2026)

**Dawn replan overhaul is live** in `agent/planner.py`, on top of the layout catalog (`CURRENT = FIVE`).

### Replan model (what changed)

1. **Tile triage at dawn**
   - **Variable:** `_replan_eligible` — empty/WEED, not `pending_dig`, and **not** (`qi==0` and queue non-empty). That last guard stops sheep/cow tiles waiting for PLACE from being reassigned every dawn.
   - **Locked:** everything else → `_stamp_tile_commitment` (board segment + remaining queue suffix) into `locked_by_worker`. Constraints see the full farm; only empties are decision vars.

2. **Commitment stamp**
   - `_queue_suffix_to_chain` walks lag/gap calendar (mirrors `sell_dp._simulate_queue_harvests`).
   - `_stamp_tile_commitment` stamps occupied board via `_stamp_locked_tile` then suffixes via `_stamp_chain`.

3. **INFEASIBLE = preserve** — never wipe queues to IDLE (that caused ~37k). Log `status` + elapsed on failure.

4. **`track_shed=False` on replan only** — wheat/fert shed ledger + hire daily cash **off** for dawn replan; day-0 `_build_from_solver` still uses `track_shed=True`. Ablation showed shed W/F was the main batch INFEASIBLE cause (presolve ~0.001s, not timeout). Replan `max_time=15s`; day-0 still 20s.

### Smoke scoreboard (this arc)

| Layout + config | Reward | Notes |
| --- | --- | --- |
| FIVE, empty replan + IDLE wipe | ~37k | Bad |
| FIVE, qi guard + INFEASIBLE preserve + shed on | ~51k | Replan never assigned |
| FIVE, + `track_shed=False` | **~98.8k** | Replan assign works (COW/STRAWBERRY); some late days still INFEASIBLE |
| FOUR, same replan | ~71–74k | Smoke PLACE≫BUILD false positive fixed |
| FIVE (current) | **~63.7k** | Smoke passed after PLACE check fix |

Do not treat 98k as bank — single local vs `random`; FIVE after switch was ~64k.

### Layout

```python
CURRENT = FIVE   # flip to FOUR to restore classic 3-hand
```

Still live: opponent price factor on replan; feed-stay; fert after WATER; no d=0 replan; sell 50% floor + premium DP.

## FIVE geometry (active)

Doc: `data/five_zone_plan.md`. Tile 1 = shed `(4,4)`. Columns south→north (`4xN`):

| Zone | tiles (0-based) | ops | start_hour | preamble |
| --- | --- | --- | --- | --- |
| farmer | 0–4 | 18 | 0 | empty |
| hire1 | 5–9 | 13 | 1 | W, pickups, 4×W |
| hire2 | 10–14 | 14 | 1 | N, pickups, 3×W |
| hire3 | 15–19 | 14 | 2 | W, pickups, 2×W |
| hire4 | 20–24 | 15 | 2 | N, pickups, 1×W |

## Smoke check: PLACE vs BUILD

`scripts/smoke_test.sh` used to require `PLACE <= BUILD + 1` on hand2. **Wrong** after replan: empty pasture/coop **persists**; later PLACE reuses structure without BUILD. Now: fail only if `PLACE > 0 and BUILD == 0`. Same-day FEED after PLACE kept.

## Known issue: weeds from unwatering

Sometimes crops turn to weeds because the snake runs out of hours before tail tiles get WATER. Guardrail experiments (route detour, defer CARE/FERT) reverted — do not repeat without user ask.

## What fertilizer actually does now

Planner stays `no_fert`. Collect from animal tape; FERTILIZE after WATER if inv has fert + zone has animal. No shed fert pickup. Market sells all shed fert.

## Decode + replan eligibility

- Decode sort: animals by earliest `start_day` → IDLE → crop-only.
- **No replan on day 0.**
- Replan variables: empty/WEED with segment done (`qi > 0` or empty queue), not waiting first PLACE.

## Solver knobs (live)

| Knob | Day-0 | Replan |
| --- | --- | --- |
| `max_time` | 20s | 15s |
| `track_shed` | True | **False** |
| `charge_hire_daily` | True | False (and shed-gated) |
| Constraints kept | zone counts, ops caps, locked load, cash ≥ 0 | same minus W/F ledger |

`OBJECTIVE_GOOD_ENOUGH=80_000`. FIVE hire cash **$7/day**.

## Failures to remember

| Run / mode | What happened |
| --- | --- |
| Empty-only replan + IDLE wipe | ~37k — destroyed day-0 suffixes |
| Batch replan with W/F shed | Always INFEASIBLE (~0.001s) despite locking |
| `track_shed=False` | Unlocks replan; ~98k FIVE smoke once |
| Smoke PLACE≤BUILD+1 | False fail on FOUR/FIVE when pasture reused |

## User prefs (this arc)

- Replan: lock committed horizon; variables = empty only; keep cash ≥ 0; shed W/F off for replan ablation (commented, not deleted)
- Layouts as Python `Layout` catalog — keep FOUR when adding FIVE; switch via `CURRENT`
- Agents never Kaggle-submit without explicit ask
- Do not commit `.cursor/`

## Key files

| File | Role |
| --- | --- |
| `agent/zoning.py` | `FOUR` / `FIVE` / `CURRENT` + `bind()` |
| `agent/planner.py` | Import + dawn replan; commitment stamp; `track_shed` |
| `agent/dp_catalog.py` | WIS catalog; `fits()` uses first harvest age |
| `scripts/smoke_test.sh` | Local smoke; PLACE/BUILD check = “≥1 build if any PLACE” |
| `data/two_lands.md` | Draft two-land notes — **not wired yet** |

## Immediate next steps

- Stabilize FIVE score (64k vs one-off 98k — variance / seed / opponent)
- Late-day replan still sometimes INFEASIBLE under cash/ops — optional per-worker sequential fallback
- **Later:** watering guardrails; two-land from `data/two_lands.md`
- Do not revive WSP
