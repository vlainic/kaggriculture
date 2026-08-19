# Progress

## Strategic status (Aug 19, 2026)

| Track | Status |
| --- | --- |
| **WSP / season set packing** | Abandoned Aug 12 — `docs/weighted_set_packing_failer.md` |
| **Handmade-chain assignment** | **Live** — zone-count CP-SAT at import → `TILE_QUEUES`; dawn replan from **day 1** |
| **Runtime fertilizer** | **Live** — collect from animals, FERTILIZE after WATER; no shed pickup |
| **Mockup SCIP notebook** | Economy aligned with OneLand. SCIP, **no preamble**. Not faster than CP-SAT. |
| **Snake executor** | Working; same-day BUILD/PLACE; skip d=0 replan |
| **Sell policy** | Still greedy dump (fert: sell all shed — OK). Melon glut still the bank leak. |
| **Competition submission** | Local smoke only unless user asks |

## What works

| Item | Notes |
| --- | --- |
| Zone-count master | Counts per zone/chain; IDLE fills leftover slots |
| Decode sort | Animals by earliest start_day → IDLE → crops (route-first animals) |
| Replan | Dawn fill of exhausted/empty queues; **not day 0** |
| Fert | Collect from tape; apply after WATER if inv bag > 0 + zone has animal |
| Same-day pasture | Buy/pickup while empty; BUILD only with animal in inv |
| Smoke vs random (Aug 19) | ~**58k** after IDLE-middle + skip d=0 |
| Mockup SCIP economy | OPTIMAL obj **83910**; 10s gap **83820** |
| Fallback `_build_tile_queues()` | If JSON/ortools/solve fails |

## Known issues

| Issue | Notes |
| --- | --- |
| **I0 vs dump sells** | Melon plan at $250; greedy glut ~$7. Fix sells, not assignment. |
| **80k callback vs ~49k obj** | Import often hits 20s FEASIBLE; `good_enough` rarely true. Still use 80k. |
| IDLE leftover | One tile may stay empty until d=1 replan — intended now (middle of zone). |
| OPTIMAL still slow to prove | Notebook ~66s; live 20s cap on Kaggle |
| Per-tile binaries | Do not revert |
| `.cursor/` gitignore | Do not stage |

## Fertilizer archaeology

| Change | Effect |
| --- | --- |
| Inject FERTILIZE before tape + gate COLLECT | Stole WATER; extra complexity |
| Animal-boolean sort | Late sheep as “has animal” on t1; animal-only pastures too early |
| Exclude tile 0 | `empty=24`, worse d=0 replan |
| Blanket 10s solve | FEASIBLE junk (5 sheep, $9) |
| Sort by earliest animal day + BUILD-on-inv | Animals on first tiles; pasture same day as PLACE |
| FERT after WATER | Tomato age 10 keeps HARVEST |
| Skip d=0 replan + IDLE between animals/crops | Stops t9 sheep from IDLE leftover |

Details: `docs/dp_master/fertilze_failure.md`.

## What's left

1. **Sell drip** for melon / premium — agent
2. Optional: export assignment JSON so Kaggle import skips CP-SAT
3. Catalog quality — secondary to sells
4. Multi-land — not started
5. Mockup: leave SCIP unless asked

## Do not do unless asked

- Revive WSP
- Shed `PICKUP FERTILIZER`
- Replan on day 0
- Kaggle submit
- Treat 80k/83620/83910 as achieved bank
- Switch mockup SCIP → CP-SAT
- Add hire preamble / extra PICKUPs to the mockup
