---
name: Fix NE rollback bugs
overview: Fix the stale-bind rollback (Bug 1) and the activation queue wipe (Bug 2) in milos/planner.py, isolate Walk 1 and Walk 2 exceptions, add ok= to the reject log, then run 2-3 local smokes and submit only if they pass. Bug 3 (twoland import) is already done.
todos:
  - id: bug1
    content: Replace PREV/PENDING/ACTIVATED sets with NE_DUE_DAY; fix dawn_ne_bound_handoff check; drop _refresh_ne_pending_expect
    status: completed
  - id: bug2
    content: _write_ne_activation loops assigned.items() only
    status: completed
  - id: walks
    content: Separate try/except for Walk 1 and Walk 2 in replan(); add ok= to reject log
    status: completed
  - id: smoke-submit
    content: Run 2-3 smokes, grep NE lines; submit via smoke_and_submit.sh --submit only if all pass
    status: completed
isProject: false
---

# Fix NE rollback bugs, then smoke and submit

All code edits go in [milos/planner.py](milos/planner.py). Bug 3 is already fixed: the planner imports `milos.wsp.twoland.solve`.

## Bug 1: stale-bind rollback kills VII two days after acceptance
The current check at dawn compares `NE_PENDING_EXPECT` against `NE_BOUND_PREV_DAY`, and that set holds binds from two days ago. Replace the three tracking sets with one due-day map:

```python
NE_DUE_DAY: dict[str, int] = {}   # replaces NE_BOUND_PREV_DAY, NE_PENDING_EXPECT, NE_ACTIVATED_DAY

# dawn_ne_bound_handoff, after the unchanged land_fail / BUY_LAND_DAY block:
bound_yday = set(NE_BOUND_TODAY)
for w in list(ACTIVE_NE):
    if NE_DUE_DAY.get(w, day) <= day - 1 and w not in bound_yday:
        _rollback_ne_zone(w, me, day, tile_queues, tile_state)
NE_BOUND_TODAY.clear()
```

- In `_activate_next_ne`, on accept, set `NE_DUE_DAY[worker] = day + offset`. The due day is the hire day: d+1 for VII and d for zones VIII onward.
- In `_rollback_ne_zone`, call `NE_DUE_DAY.pop(worker, None)`.
- Delete `_refresh_ne_pending_expect` and its call in `replan()`, and remove the dead globals.

## Bug 2: re-activation wipes the queues of planted tiles
`_write_ne_activation` currently loops over `WORKER_TILES[worker]` and sets `[]` for every tile the solve didn't touch. Change it to loop over `assigned.items()`, which is only the solve's scope tiles, and skip empty chains without touching the queue.

## Isolate the two walks
In `replan()`, give `_replan_active` and `_activate_next_ne` separate `try/except Exception` blocks that log `[planner] walk1 failed d=..: exc` and `walk2 failed ...`. That way an exception in Walk 1 no longer skips Walk 2.

## Reject log
Add `ok={int(worker in result.solved_workers)}` to the `[ne] reject` line.

## Verify, then submit
- Run `scripts/smoke_test.sh` 2-3 times.
- Grep the output: `rg "\[ne\]|slot[0-9]+=hire.* ne|BUY_LAND|walk[12] failed|replan failed"`.
- Pass criteria:
  - no `[ne] rollback` right after the buy day
  - VIII and later zones get accepted
  - no `walk failed` lines
  - the smoke script reports passed
- If all runs pass, submit with `scripts/smoke_and_submit.sh --submit "NE-land: fix rollback + activation wipe"`, which the user approved.
- Do not submit if any smoke fails.