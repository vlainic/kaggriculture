# Progress

## Strategic status (Sep 1, 2026)

| Track | Status |
| --- | --- |
| **WSP (atomic patterns)** | **Live again** — day-0 from `wsp_prestart.json`; replan via `build_patterns`; **conservative cash cascade** (Sep 1) |
| **Chain assignment (zonewise)** | **Live** — day-0 + replan via **`dp_catalog.build_catalog`** |
| **Solver backend** | **`CURRENT_SOLVER = "zonewise_wsp"`** (flip to `zonewise` for ~107k smoke path) |
| **WSP replan cash** | **Conservative handoff** — `opening = res["conservative"]`; not full bank ×5; not ops/78 slice on replan |
| **Zonewise replan cash** | Close balance handoff + `track_shed=True` + liquidity floor |
| **Dawn replan** | Lock commitments; empty/WEED vars; INFEASIBLE → preserve (WSP: break cascade) |
| **Day-0 cascade (zonewise)** | `cascade_reserve=True` + `min_close0`; partial apply if farmer solves |
| **Layout catalog** | **Live** — `FOUR` + `FIVE`; **`CURRENT = FIVE`**; ops **18/17/16/14/13** |
| **Executor FERT/wheat** | **Live** — gates + dawn wheat slack + shed-adjacent fetch |
| **Sell policy** | 50% floor; premium sell DP; WOOL daily cap; wheat feed reserve |
| **Competition submission** | Local smoke only unless user asks |

## What works

| Item | Notes |
| --- | --- |
| WSP conservative cascade | `spend_by_day` on patterns; balance vs conservative split; stepped `open0`/`cons0` in logs |
| WSP smoke | ~**81–85k** post-conservative handoff; ~81k pre-handoff with executor fixes only |
| Zonewise smoke | ~**107k** with same executor fixes; `solver=zonewise` replan lines |
| FERT runtime gates | Skip tape FERT; `_may_fertilize_today`; fewer bogus DIGs |
| Dawn wheat | `wheat_feed_need + 1`; correct feed need (not `live_animals + placing`) |
| Replan triage | WEED eligible; `qi==0` + queue still locked (waiting PLACE) |
| INFEASIBLE preserve | Keep old queues; WSP prefix apply if farmer solved |
| Pickups + single ops | Cap = `daily_tile_ops` only (+ hire preamble) |
| Smoke PLACE/BUILD | `startswith('BUILD_COOP')` / `BUILD_PASTURE` |

## Known issues

| Issue | Notes |
| --- | --- |
| WSP partial cascade | hire4 (or later) INFEASIBLE when conservative leftover tight — prefix assign only |
| WSP vs zonewise gap | ~85k WSP vs ~107k zonewise — pattern packing + no replan catalog chains |
| d=3 bank near zero | Market execution still drains; liquidity floor helps zonewise solver only |
| **Weeds from missed watering** | Occasional; much reduced vs pre-wheat-fix runs |
| `.cursor/` gitignore | Do not stage |

## Sep 1 session (WSP conservative handoff)

| Change | Result |
| --- | --- |
| Drop `_zone_banks(full money)` | Economically faithful shared pool |
| `spend_by_day` on WSP patterns | Conservative = setup + hire + W/F buys |
| `opening_balances` MIP | Balance uses harvests; handoff uses conservative only |
| `break` on INFEASIBLE | Same as zonewise cascade stop |
| Smoke | **84579** reward; replan logs show `farmer cons0=930` → `hire1 open0=930` etc. |

## Aug 31 session (executor + solver flip)

| Change | Result |
| --- | --- |
| Switch to zonewise + keep FERT/wheat fixes | ~107k; fixed 0-reward from aggressive pre-snake wheat PASS |
| WSP + executor fixes (before conservative) | ~81k, ~2 DIGs |
| `track_shed` conditional | True zonewise / False WSP |
| Strip debug NDJSON | Clean smoke logs |

## What's left

1. Optional: zonewise handoff → conservative (match notebooks) vs keep close balance
2. WSP: reduce hire-zone INFEASIBLE without restoring full-bank hack
3. Kaggle A/B on conservative WSP vs prior runs
4. **Later:** watering guardrails; two-land
5. Do not Kaggle submit without ask

## Do not do unless asked

- Restore **full live bank per WSP zone** (optimistic; broke accounting)
- Shed `PICKUP FERTILIZER` as default policy
- Replan on day 0
- Kaggle submit
- IDLE-wipe on replan INFEASIBLE
- Re-enable replan `track_shed=True` for WSP without ablation
- Re-add pickup/place/fert side terms to ops cap
- Commit `.cursor/`
