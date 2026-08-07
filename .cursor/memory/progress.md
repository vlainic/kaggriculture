# Progress

## What works

| Item | Status |
| --- | --- |
| Competition rules documented | Done — `docs/project_overview.md` |
| Strategy analysis archived | Done — `docs/claude_chat.md` |
| Cursor rules/skills/agents | Done |
| Memory bank | Updated Aug 6, 2026 (live packing agent) |
| Rollout templates | Done — `data/crop_rollouts.json` |
| Set-packing planner (CP-SAT + greedy fallback) | Done — `agent/planner.py` |
| Snake executor (sell / buy / plant / water / harvest) | Done — `agent/executor.py` |
| Thin `main.py` entry | Done |
| OR-Tools vendoring for Kaggle | Done — `vendor/` via `scripts/vendor_ortools.sh` |
| Submit script (`submission.tar.gz`) | Done — `scripts/smoke_and_submit.sh` |
| Local smoke vs `random` / `pass` | Done — ~21k reward after executor fixes |
| Ladder / ELO iteration | In progress — earlier submits Error or idle |

## What's left to build

### Phase 1 — Plant-only baseline (current)
- [x] 3×3 segment, no hires, set-packing schedule
- [x] Live price weights + harvest-day replan
- [x] Kaggle packaging with vendored ortools
- [ ] Stable ladder submission (validate replay shows farming)
- [ ] Beat `"starter"` consistently (measure win rate)

### Phase 2 — Scale
- [ ] Fertilizer (`with_fert`) profile
- [ ] Multi-segment / hire timing
- [ ] Land unlock

### Phase 3 — Animals & polish
- [ ] Animals module
- [ ] Town demand / sell timing beyond sell-all
- [ ] Master search if needed

## Known issues / risks

- **Kaggle has no `ortools`** — must vendor cp311 manylinux wheels in tar.gz (~55MB).
- **CP-SAT timeout** on weak sim CPU → empty plan if no fallback (mitigated: greedy + 8s + logs).
- **Plan storage:** never collapse to one placement per tile; keep full list and merge on replan.
- **Age-0 rollout** includes `PLANT`; executor must skip `PLANT` when tile already planted.
- Same-turn `BUY_SEED` then `PLANT` may need an idle turn for seeds to appear — buy ahead (today/tomorrow).
- Compute: replan on every harvest day; keep solves short.
- Shed cap 100; sell-all each turn mitigates for now.

## Baselines to track

| Opponent | Purpose | Notes |
| --- | --- | --- |
| `"pass"` | Sanity | Local DONE |
| `"random"` | Smoke | ~21k reward local after fixes |
| `"starter"` | Milestone | Not measured yet |
| Prior own submission | Regression | Idle/Error submits superseded |

## Submission archaeology (Aug 6)

| Issue | Cause |
| --- | --- |
| `submission.tar.gz` validation fail | Missing/wrong packaging; later `No module named 'ortools'` |
| Bundled single-file NameError | Leftover `rollouts.` / `planner.` prefixes after inline |
| Idle agent (`90458708`) | Empty/collapsed plan + PLANT-before-WATER stuck PASS |
