# Progress

## What works

| Item | Status |
| --- | --- |
| Competition rules documented | Done — `docs/project_overview.md` with markdown tables |
| Strategy analysis archived | Done — `docs/claude_chat.md` |
| Cursor rules/skills/agents | Done — Kaggriculture-specific `.cursor/` config |
| Memory bank | Done — initialized Aug 6, 2026 |
| Submission agent (`main.py`) | **Not started** |
| Local eval harness | **Not started** |
| Observation dump / mechanics verification | **Not started** |

## What's left to build

### Phase 0 — Smoke test
- [ ] Minimal `main.py` that returns valid actions every turn
- [ ] `eval/run_local.py` vs `"starter"` / `"random"`
- [ ] Obs dump script; confirm SELL source, melon availability, shed mechanics

### Phase 1 — Plant-only baseline
- [ ] Routing (shortest-path to target tile)
- [ ] 3×3 segment, no hires, single crop loop (e.g. wheat or carrot)
- [ ] Daily action scheduling (heuristic, then MILP)
- [ ] Beat `"starter"` consistently

### Phase 2 — Scale
- [ ] Multi-segment layout; hire timing (Fibonacci cost awareness)
- [ ] Master module: land unlock, segment activation
- [ ] Market sell timing (avoid premium-good glut)

### Phase 3 — Animals & polish
- [ ] Animal module (goose/cow/sheep); feed/care/harvest
- [ ] Town demand forecasting for sell planning
- [ ] Master search (MCTS vs shallow lookahead — pick after profiling)
- [ ] Kaggle submission + ladder iteration

## Known issues / risks

- **Compute:** MCTS + daily MILP on 1.6 vCPU may be too slow — profile early
- **Price coupling:** static plans fail; need receding-horizon or reactive sell logic
- **Premium goods:** strawberry/melon/milk/wool hit $1 floor fast on overproduction
- **Fresh plantings:** `consecutive_unwatered = 1` on plant day — no grace period
- **Shed cap:** 100 items; end-of-day overflow discarded

## Baselines to track

| Opponent | Purpose |
| --- | --- |
| `"pass"` | Sanity (always lose) |
| `"random"` | Beat random actions |
| `"starter"` | First real milestone |
| Prior own submission | Regression on changes |

No eval numbers yet — agent code does not exist.
