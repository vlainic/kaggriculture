# Progress

## What works

| Item | Status |
| --- | --- |
| Competition rules documented | Done — `docs/project_overview.md` |
| Strategy analysis archived | Done — `docs/claude_chat.md` |
| Cursor rules/skills/agents | Done — incl. `kaggle-submission.mdc` |
| Memory bank | Updated Aug 11, 2026 (session 4) |
| Rollout templates (crops + animals) | Done |
| **5×5 NW multi-worker layout** | Done — `agent/workers.py` (25 tiles, 4 workers) |
| Per-worker CP-SAT + op caps | Done — `agent/planner.py` |
| Multi-worker executor + hand mapping | Done — `agent/executor.py` |
| Solve-once / greedy-patch replan | Done — day 0 CP-SAT only |
| CP-SAT constraint indexing (perf) | Done — no ~8s Python overhead |
| **SHED_DOOR lock-escape fix** | Done — hire2/hire3 PICKUP/PLACE/FEED work |
| Safe local smoke script | Done — `scripts/smoke_test.sh` |
| Gated submit script (`--submit`) | Done — `scripts/smoke_and_submit.sh` |
| OR-Tools vendoring for Kaggle | Done |
| Local smoke vs `pass` (720 steps) | ~59,654 after SHED_DOOR fix |
| Ladder / ELO iteration | In progress — user submits manually |

## What's left to build

### Phase 2 — 5×5 polish (current)
- [x] 5×5 NW, 3 daily hires, per-worker zones/routes
- [x] Day-0 CP-SAT + greedy patch
- [x] SHED_DOOR routing for all hires
- [ ] Stable ladder submission after door fix
- [ ] Late-season patch slack (op-cap saturation)
- [ ] Beat `"starter"` consistently on ladder

### Phase 3 — Optimize
- [ ] Fertilizer (`with_fert`) profile
- [ ] Plan-aware tomorrow fert/wheat for future placements
- [ ] Town-center demand in weights (optional)
- [ ] Sell timing beyond sell-all

## Known issues / risks

- **Kaggle has no `ortools`** — vendor cp311 manylinux wheels (~55MB).
- **Accidental agent submit** — mitigated by `--submit` gate + `kaggle-submission.mdc`; user burned submission slot Aug 11.
- **Submission cap:** 5 agents/team/day; only latest 2 tracked; resets ~midnight UTC.
- **Greedy patch `added=0`:** day-0 plan fills worker op caps — freed tiles late season may stay empty.
- **Hand spawn on LOCKED tiles:** hire2 `(4,5)`, hire3 `(5,5)` — must route via `SHED_DOOR (4,4)` every day for PICKUP.
- **hire1 was accidentally OK** before fix — X-first walk from `(5,4)` crossed unlocked door; do not revert to `route[0]` lock-escape.
- CP-SAT timeout → greedy fallback; full solve runs once per episode (8s limit).
- Placed animals lock tiles until season end.
- Shed cap 100; sell-all each turn mitigates for now.

## Baselines to track

| Opponent | Purpose | Notes |
| --- | --- | --- |
| `"pass"` | Sanity | Local DONE |
| `"random"` | Smoke | ~59k Aug 11 post SHED_DOOR fix (self-play in smoke_test) |
| `"starter"` | Milestone | Not measured yet |
| Pre-door-fix submission | Regression | 91915834 ~25k — empty pastures, hire3 idle |

## Submission archaeology

| Submit / issue | Cause / fix |
| --- | --- |
| `submission.tar.gz` validation fail (Aug 6) | Missing ortools / packaging |
| **260811_4 / 91915834** — hire3 empty pastures, hire2 underused, ~25k | Locked spawn never reached `(4,4)` for PICKUP — **SHED_DOOR fix** |
| **260811_4 / 91910203** — planner timeout ~day 15–17 | Daily CP-SAT + Python overhead — **solve-once + indexing** |
| **Accidental agent submit** (Aug 11) | Agent ran `smoke_and_submit.sh` without user consent — **`--submit` gate + rules** |
| Missing `animal_rollouts.json` in bundle | Added to smoke scripts |
| 260811_1 — semi-empty tiles, no animals | Double snake op budget — fixed earlier |
| 260811_2 — wool/FEED loops | Catch-up HARVEST, FEED gate — fixed earlier |
