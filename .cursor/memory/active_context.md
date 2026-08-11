# Active Context

## Current focus

**5×5 NW multi-worker agent (Aug 11, 2026).** Four workers (farmer + 3 daily hires) each own a tile zone with per-worker snake routes and net tile-op caps. Day-0 CP-SAT full plan; greedy `patch_plan` for freed tiles thereafter (no daily CP-SAT). Latest fix: **SHED_DOOR routing** so hire2/hire3 can PICKUP from shed (was blocking all animal ops).

## Recent changes (Aug 11, 2026 — session 4)

### 5×5 multi-worker expansion

1. **`agent/workers.py`:** 25 tiles in NW 5×5; zones for farmer (9), hire1 (6), hire2 (6), hire3 (4); per-worker routes, `NET_TILE_OPS`, `DAILY_TURN_BUDGET`, `SPAWN_TO_WORKER`, `assign_hand_workers()`.
2. **`agent/planner.py`:** CP-SAT with per-worker/day op caps; `plan_ops_by_day()`, `patch_plan()` (greedy, free tiles only).
3. **`agent/executor.py`:** Multi-worker routing, dynamic hand→worker mapping, second-pass route reset when zone has pending work, market order priority (HIRE/BUY before SELL when over cap).

### Planner performance + replan strategy

4. **CP-SAT indexing:** Precomputed `element_to_vars` and `worker_day_terms` — removed ~8s Python overhead per solve.
5. **Solve once, patch many:** Full CP-SAT only on day 0 (`_should_full_replan`); subsequent days use `_patch_replan` / `patch_plan` for empty tiles only. `SOLVER_TIME_LIMIT_S = 8.0` (single solve per episode).

### SHED_DOOR fix (critical execution bug)

6. **Root cause:** Hands respawn daily at locked shed corners: hire1 `(5,4)`, hire2 `(4,5)`, hire3 `(5,5)`. Only `(4,4)` is unlocked in NW. Old lock-escape walked toward `route[0]` — hire1 accidentally crossed `(4,4)`; hire2/hire3 never did → **zero PICKUP** → empty pastures, no FEED/CARE/HARVEST on those zones.
7. **Fix:** `SHED_DOOR = (4, 4)` in `workers.py`; lock-escape in `_next_action` targets door first. Zero extra movement cost (door on rectilinear path to all zones). Local 720-step smoke: **59,654** reward (was ~52,523).

### Submission safety (user-mandated)

8. **`scripts/smoke_test.sh`:** Build + local smoke only — safe for agents.
9. **`scripts/smoke_and_submit.sh`:** Requires explicit `--submit "message"` or refuses upload.
10. **Rules/skills/docs:** `.cursor/rules/kaggle-submission.mdc`, updated stack/conventions/AGENTS.md — **agents must NEVER submit without explicit user request**.

## Active decisions

- Profiles: **`no_fert`** (crops), **`with_care`** (animals) in current 5×5 plan.
- Replan: full CP-SAT day 0 only; greedy patch on empty tiles after.
- Per-worker op caps from `workers.NET_TILE_OPS` (farmer/hire1/hire2=15, hire3=14).
- Market: drop SELLs first when over 10-order cap; prioritize HIRE + BUY.
- **`PICKUP` counted in planner** via `animal_rollouts.executor_ops_by_day` (+1 feed pickup, +1 animal setup).
- Multiple farmers can occupy same tile (engine has no collision check).
- **Agents:** local smoke via `scripts/smoke_test.sh` only; users submit via `scripts/smoke_and_submit.sh --submit "msg"`.

## Open questions / follow-ups

1. Greedy `patch_plan` sometimes `added=0` late season — day-0 plan saturates worker op caps; revisit if reward plateaus.
2. Ladder replay after SHED_DOOR fix — confirm ~60k+ holds vs opponents.
3. Fertilizer profile (`with_fert`) — deferred.
4. Town-center demand in weights — still out of scope.

## Immediate next steps

1. User submits manually when ready: `bash scripts/smoke_and_submit.sh --submit "message"`.
2. Monitor ladder logs for hire utilization parity and empty pastures.
3. Tune day-0 CP-SAT objective or patch slack if late-season tiles stay idle.

## Key files

- `main.py`, `agent/{workers,planner,executor,ops_budget,rollouts,animal_rollouts}.py`
- `data/{crop_rollouts,animal_rollouts}.json`
- `scripts/smoke_test.sh`, `scripts/smoke_and_submit.sh`, `scripts/vendor_ortools.sh`
- `submissions/260811_4/` (91915834 broken pre-door-fix; earlier timeout runs)
- `.cursor/rules/kaggle-submission.mdc`
