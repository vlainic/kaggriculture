# Progress

## Strategic status (Aug 12, 2026)

| Track | Status |
| --- | --- |
| **WSP / CP-SAT season planner** | **Failed / abandoned** — see `docs/weighted_set_packing_failer.md` |
| **Replacement agent** | Not started — user to choose direction |
| **Competition submission** | Legacy WSP code in repo; ladder results inconsistent (~25k–51k in logs) |

## What worked (keep for future agents)

| Item | Notes |
| --- | --- |
| Competition docs + skills | `docs/project_overview.md`, domain/convention skills |
| Rollout JSON templates | `data/crop_rollouts.json`, `data/animal_rollouts.json` |
| **SHED_DOOR routing** | `(4,4)` lock-escape — hire2/hire3 can PICKUP; real engine fix |
| **`agent/workers.py`** zone map | 25-tile partition, routes, op budgets — reusable |
| Live analysis notebook | PASS / zone-empty / money / plan Gantt from Kaggle logs |
| Safe smoke + gated submit | `smoke_test.sh`, `smoke_and_submit.sh --submit`, `kaggle-submission.mdc` |
| OR-Tools vendoring | Still needed if any future bounded MILP |

## WSP experiment — what we built (legacy)

| Item | Outcome |
| --- | --- |
| Day-0 CP-SAT + greedy patch | Works mechanically; **plans often unexecutable or zone-unbalanced** |
| Empty tiles + one lifecycle/tile/solve | Fixed ~74-placement overpack → 25 placements |
| Cash constraint | Stops impossible buys; doesn't fix execution |
| Plan-following executor | Correctness up; PASS count up until market-hour workaround |
| h=0 market-hour PASS | Plan→buy→snake workaround; **burns 1h/day** (re-hire) |
| eod DROP + h=23 sell inv | Partial; few `eod-drop` in logs |
| `MAX_ACTIVE_PER_WORKER_DAY` | Tried → **reverted** |
| `FARMER_DAY0_BONUS` | Minor nudge; farmer crops still late (days 16–18) |
| `ZONE_FILL_BONUS` | **Disaster** — all placements day 24–25, ~5k reward |

## WSP smoke / log outcomes (not reliable baselines)

| Run / note | Approx reward | Problem |
| --- | --- | --- |
| Aug 11 post SHED_DOOR (optimistic) | ~59k | Pre–live-analysis; not reproduced under WSP iteration |
| Plan-following, no h=0 fix | ~27k / high PASS | Plan-blocked spam |
| h=0 aware, no market-hour | ~19k | First PLANT h=11 |
| market-hour + buys first | ~27–36k | Farmer zone idle, 12+ PASS/day |
| Best late WSP patch | ~51k smoke | Unstable; late farmer MELON starts |
| Kaggle validation (user) | ~39k | Money chart ~30k (snap timing) |

## Known issues (WSP-specific — why we stopped)

- **Planner ops ≠ executor turns** — `NET_TILE_OPS` ignores shed trips, h=0 defer, idle PASS.
- **Engine order** — farmer before market same hour; true plan→buy→execute impossible without wasting h=0.
- **Zone imbalance** — CP-SAT fills hire zones; farmer tiles empty mid-season.
- **Scale** — ~8.7k candidates @ 1 land; **unusable at 2–3 lands**.
- **Two-system drift** — every executor fix invalidated planner assumptions.
- **Static prices in weights** — no sell-impact modeling.

## Submission archaeology (updated)

| Submit / issue | Cause |
| --- | --- |
| 260811_4 / 91915834 ~25k | SHED_DOOR bug (fixed Aug 11) |
| 260811_4 timeout ~day 15–17 | Daily CP-SAT — later solve-once |
| 260812_* series | WSP iteration — PASS/zone/money issues documented in failer.md |
| Accidental agent submit (Aug 11) | `--submit` gate + rules |

## What's left (NOT WSP)

Await user decision. Likely directions (from failer.md): per-zone heuristics, 3–5 day rolling MILP, farmer-first staging, executor-first policy. **Do not auto-continue WSP todos.**
