# Progress

## What works

| Item | Status |
| --- | --- |
| Competition rules documented | Done — `docs/project_overview.md` |
| Strategy analysis archived | Done — `docs/claude_chat.md` |
| Cursor rules/skills/agents | Done |
| Memory bank | Updated Aug 11, 2026 |
| Rollout templates (crops + animals) | Done — `data/crop_rollouts.json`, `data/animal_rollouts.json` |
| Half-open packing + split horizons + day-0 op reserve | Done — `agent/rollouts.py`, `planner.py` |
| Full forward replan (crops + animals, live prices) | Done — `agent/planner.py`, `executor.py` |
| Coupled CP-SAT set packing (crops + animals) | Done — shared `DAILY_OP_BUDGET=16` |
| Shop demand on yield×price / revenue weights | Done — crops + animal products |
| Sticky snake executor + animal BUILD/PLACE/FEED/HARVEST | Done — `agent/executor.py` |
| Live animal replan pricing (EGG/MILK/WOOL + WHEAT feed) | Done — Aug 11 |
| End-of-day tomorrow market buys (seeds, fert, wheat) | Done — Aug 11 |
| Op budget alignment (no double snake count) | Done — Aug 11 |
| Replan plan-coverage fix (animals not dropped) | Done — Aug 11 |
| Wool catch-up HARVEST + FEED wheat gate + same-day seeds | Done — Aug 11 |
| OR-Tools vendoring for Kaggle | Done — `vendor/` via `scripts/vendor_ortools.sh` |
| Submit script (`submission.tar.gz` + both JSON data files) | Done — `scripts/smoke_and_submit.sh` |
| Local smoke vs `random` | ~32–35k after Aug 11 fixes (variance) |
| Ladder / ELO iteration | In progress |

## What's left to build

### Phase 1 — Coupled 3×3 baseline (current)
- [x] 3×3 segment, no hires, set-packing schedule
- [x] Live price weights + forward replan
- [x] Same-day handoff (half-open + sticky)
- [x] Unlocked-shop demand boost (no forecast)
- [x] Kaggle packaging with vendored ortools + animal rollouts
- [x] Animals in planner + executor (no_care profile)
- [x] Op budget / replan / market executor fixes (Aug 11)
- [ ] Stable ladder submission after Aug 11 fixes
- [ ] Beat `"starter"` consistently

### Phase 2 — Scale
- [ ] Fertilizer (`with_fert`) profile
- [ ] Multi-segment / hire timing
- [ ] Land unlock (5×5 full quadrant)
- [ ] Plan-aware tomorrow fert/wheat for future placements
- [ ] Town-center demand in weights (optional)

### Phase 3 — Polish
- [ ] Animal tile recycling mid-season (hard — needs escape/DIG path)
- [ ] Sell timing beyond sell-all
- [ ] Master search if needed

## Known issues / risks

- **Kaggle has no `ortools`** — vendor cp311 manylinux wheels (~55MB).
- **CP-SAT timeout** → greedy fallback + 8s + logs.
- **Plan storage:** full list of placements; replan **replaces** future plan.
- **Placed animals lock tiles** until season end — no mid-season swap without game escape mechanics.
- **Orphan seeds:** same-day BUY_SEED then replan drop before snake reaches tile still possible.
- **Tomorrow fert/wheat:** only counted for live tiles, not plan-only future crop/animal placements.
- **Age-0 rollout** includes `PLANT`; executor skips `PLANT` when tile already planted.
- Half-open: occupancy excludes free day; ops include it — capacity couples handoff.
- Sticky required so harvest→plant does not walk the snake between ops.
- Shed cap 100; sell-all each turn mitigates for now.
- Smoke reward varies vs `random` (~28k broken → ~32–35k fixed).

## Baselines to track

| Opponent | Purpose | Notes |
| --- | --- | --- |
| `"pass"` | Sanity | Local DONE |
| `"random"` | Smoke | ~21k Aug 7 plant-only; ~32–35k Aug 11 coupled |
| `"starter"` | Milestone | Not measured yet |
| Prior own submission | Regression | 260811_1 broken; 260811_2 ~27k win side |

## Submission archaeology

| Submit / issue | Cause / fix |
| --- | --- |
| `submission.tar.gz` validation fail (Aug 6) | Missing ortools / packaging |
| Idle agent (`90458708`) | Empty/collapsed plan + PLANT-before-WATER stuck PASS |
| Harvest leave/return (Aug 7) | `_next_work` rescanned from tile 0 — fixed by sticky |
| **260811_1** — semi-empty tiles, no animals, many PASSes | Double snake op budget + daily replan dropping animal plans — fixed Aug 11 |
| **260811_2** — ~27k, wool on sheep, orphan carrot seed, FEED loops | Catch-up HARVEST, FEED wheat gate, same-day BUY_SEED — fixed Aug 11 |
| Missing `animal_rollouts.json` in bundle | Added to `smoke_and_submit.sh` |
