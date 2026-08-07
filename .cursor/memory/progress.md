# Progress

## What works

| Item | Status |
| --- | --- |
| Competition rules documented | Done — `docs/project_overview.md` |
| Strategy analysis archived | Done — `docs/claude_chat.md` |
| Cursor rules/skills/agents | Done |
| Memory bank | Updated Aug 7, 2026 |
| Rollout templates (+ DIG on tomato/strawberry free day) | Done — `data/crop_rollouts.json` |
| Half-open packing + split horizons + day-0 op reserve | Done — `agent/rollouts.py`, `planner.py` |
| Full forward replan (earliest_plant, weed DIG ops) | Done — `agent/planner.py`, `executor.py` |
| Shop demand on yield×price weights | Done — `shop_demand_by_crop` |
| Sticky snake executor | Done — finish tile before leave |
| OR-Tools vendoring for Kaggle | Done — `vendor/` via `scripts/vendor_ortools.sh` |
| Submit script (`submission.tar.gz`) | Done — `scripts/smoke_and_submit.sh` |
| Local smoke vs `random` / `pass` | Done earlier (~21k); re-smoke after Aug 7 changes TBD |
| Ladder / ELO iteration | In progress |

## What's left to build

### Phase 1 — Plant-only baseline (current)
- [x] 3×3 segment, no hires, set-packing schedule
- [x] Live price weights + forward replan
- [x] Same-day handoff (half-open + sticky)
- [x] Unlocked-shop demand boost (no forecast)
- [x] Kaggle packaging with vendored ortools
- [ ] Stable ladder submission after Aug 7 fixes
- [ ] Beat `"starter"` consistently

### Phase 2 — Scale
- [ ] Fertilizer (`with_fert`) profile
- [ ] Multi-segment / hire timing
- [ ] Land unlock
- [ ] Town-center demand in weights (optional)

### Phase 3 — Animals & polish
- [ ] Animals module
- [ ] Sell timing beyond sell-all
- [ ] Master search if needed

## Known issues / risks

- **Kaggle has no `ortools`** — vendor cp311 manylinux wheels (~55MB).
- **CP-SAT timeout** → greedy fallback + 8s + logs.
- **Plan storage:** full list of placements; replan **replaces** future plan (do not freeze kept futures — prices must shift all tiles).
- **Age-0 rollout** includes `PLANT`; executor skips `PLANT` when tile already planted.
- Buy seeds ahead (today/tomorrow); WEED tiles count as plantable today for buys.
- Half-open: occupancy excludes free day; ops include it — capacity couples handoff.
- Sticky required so harvest→plant does not walk the snake between ops.
- Shed cap 100; sell-all each turn mitigates for now.

## Baselines to track

| Opponent | Purpose | Notes |
| --- | --- | --- |
| `"pass"` | Sanity | Local DONE |
| `"random"` | Smoke | ~21k earlier; re-check Aug 7 |
| `"starter"` | Milestone | Not measured yet |
| Prior own submission | Regression | Idle/Error submits superseded |

## Submission archaeology (Aug 6)

| Issue | Cause |
| --- | --- |
| `submission.tar.gz` validation fail | Missing ortools / packaging |
| Idle agent (`90458708`) | Empty/collapsed plan + PLANT-before-WATER stuck PASS |
| Harvest leave/return (Aug 7) | `_next_work` rescanned from tile 0 after harvest — fixed by sticky |
