# Progress

## Strategic status (Aug 16, 2026)

| Track | Status |
| --- | --- |
| **WSP / season set packing** | Abandoned Aug 12 — `docs/weighted_set_packing_failer.md` |
| **Handmade-chain assignment** | **Live** — zone-count CP-SAT at import → `TILE_QUEUES` |
| **Mockup SCIP notebook** | Economy aligned with OneLand (yields, I0 W/F, $4/day hire). SCIP, **no preamble**. Not faster than CP-SAT. |
| **Snake executor** | Working; preamble + SHED_DOOR kept |
| **Sell policy** | Still greedy dump — main bank leak vs opponents |
| **Competition submission** | Local smoke only unless user asks |

## What works

| Item | Notes |
| --- | --- |
| Zone-count master (planner) | ~436 ints vs ~2725 binaries; OPTIMAL ~66s in OneLand notebook (obj 83620) |
| Planner 80k callback | Import ~0.8s, obj 80100, 25 tiles assigned |
| Smoke vs random | ~60k, 720 DONE (Aug 15) |
| Ops caps 15/13/13/11 | Hire peaks include preamble in OneLand; none over cap at OPTIMAL |
| Mockup SCIP economy | Harvest zip + open W/F + hire burn. 60s OPTIMAL obj **83910**; 10s gap obj **83820**. Cash floor 695, wheat buy 16. |
| Rollout JSON + candidates | Bundled in `smoke_test.sh` |
| SHED_DOOR / workers / routes | Reused from pre-assignment executor |
| Fallback `_build_tile_queues()` | If JSON/ortools/solve fails |

## Known issues

| Issue | Notes |
| --- | --- |
| **I0 vs dump sells** | Melon plan at $250; greedy glut ~$7; ~30k bank vs greedy. **Expected.** Fix sells, not assignment. |
| OPTIMAL still ~66s (CP-SAT) | Fine for notebook; planner must keep 80k stop (or cache assignment) |
| Mockup SCIP slower than OneLand CP-SAT | Same MIP class; ~10–20s vs ~0.8s. User kept SCIP. |
| Per-tile binaries | Do not revert — permutation symmetry |
| `.cursor/` gitignore | Staging `logs.txt` blocks Cursor commit |

## Solve-time archaeology (assignment notebooks)

| Change | Effect |
| --- | --- |
| `cum_terms` cash | ~100s, ~658 MB RSS |
| `balance_vars` + W/F levels | Memory OK (~272 MB); time still high if proving OPTIMAL |
| Drop preamble (`OnlyEnforceIf`) | Faster FEASIBLE but **more** symmetry; hire3 post-hoc 12/11 |
| `num_workers=1`, no timeout, prove OPTIMAL | ~183s then worse |
| Zone counts + linear preamble (OneLand CP-SAT) | OPTIMAL ~66s, obj 83620, ops ≤ cap |
| Planner 80k stop | ~0.8s FEASIBLE 80100 |
| Mockup count SCIP, wrong yields / FEED-as-seed / no hire-buy | obj ~105k, ~33s |
| Mockup count SCIP + economy fix | OPTIMAL ~20s obj 83910; 10s cap obj 83820. **Not faster than CP-SAT.** |

## What's left

1. **Sell drip** for melon / premium (highest EV vs greedy) — agent
2. Optional: export OPTIMAL assignment JSON so Kaggle import skips CP-SAT
3. Catalog quality (tighter handmade chains) — secondary to sells
4. Multi-land — not started; zone-count pattern should extend
5. Mockup: leave SCIP unless asked; no preamble unless asked

## Do not do unless asked

- Revive WSP
- `num_workers=8` on a busy machine
- Kaggle submit
- Treat 80k/83620/83910 as achieved bank
- Switch mockup SCIP → CP-SAT
- Add hire preamble / extra PICKUPs to the mockup
