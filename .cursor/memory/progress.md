# Progress

## Strategic status (Aug 15, 2026)

| Track | Status |
| --- | --- |
| **WSP / season set packing** | Abandoned Aug 12 — `docs/weighted_set_packing_failer.md` |
| **Handmade-chain assignment** | **Live** — zone-count CP-SAT at import → `TILE_QUEUES` |
| **Snake executor** | Working; preamble + SHED_DOOR kept |
| **Sell policy** | Still greedy dump — main bank leak vs opponents |
| **Competition submission** | Local smoke only unless user asks |

## What works

| Item | Notes |
| --- | --- |
| Zone-count master | ~436 ints vs ~2725 binaries; OPTIMAL ~66s in notebook (obj 83620) |
| Planner 80k callback | Import ~0.8s, obj 80100, 25 tiles assigned |
| Smoke vs random | ~60k, 720 DONE (Aug 15) |
| Ops caps 15/13/13/11 | Hire peaks include preamble; none over cap at OPTIMAL |
| Rollout JSON + candidates | Bundled in `smoke_test.sh` |
| SHED_DOOR / workers / routes | Reused from pre-assignment executor |
| Fallback `_build_tile_queues()` | If JSON/ortools/solve fails |

## Known issues

| Issue | Notes |
| --- | --- |
| **I0 vs dump sells** | Melon plan at $250; greedy glut ~$7; ~30k bank vs greedy. **Expected.** Fix sells, not assignment. |
| OPTIMAL still ~66s | Fine for notebook; planner must keep 80k stop (or cache assignment) |
| Per-tile binaries | Do not revert — permutation symmetry |
| `.cursor/` gitignore | Staging `logs.txt` blocks Cursor commit |

## Solve-time archaeology (assignment notebook)

| Change | Effect |
| --- | --- |
| `cum_terms` cash | ~100s, ~658 MB RSS |
| `balance_vars` + W/F levels | Memory OK (~272 MB); time still high if proving OPTIMAL |
| Drop preamble (`OnlyEnforceIf`) | Faster FEASIBLE but **more** symmetry; hire3 post-hoc 12/11 |
| `num_workers=1`, no timeout, prove OPTIMAL | ~183s then worse |
| Zone counts + linear preamble | OPTIMAL ~66s, obj 83620, ops ≤ cap |
| Planner 80k stop | ~0.8s FEASIBLE 80100 |

## What's left

1. **Sell drip** for melon / premium (highest EV vs greedy)
2. Optional: export OPTIMAL assignment JSON so Kaggle import skips CP-SAT
3. Catalog quality (tighter handmade chains) — secondary to sells
4. Multi-land — not started; zone-count pattern should extend

## Do not do unless asked

- Revive WSP
- `num_workers=8` on a busy machine
- Kaggle submit
- Treat 80k/83620 as achieved bank
