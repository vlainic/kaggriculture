---
name: Lower NE busy gate
overview: Buy NE land with no utilization gate (cash + solver-ok only). Later NE zones keep a lowered busy_day0 < 1 gate so one activation-day start is enough.
todos:
  - id: gate
    content: Skip busy_day0/busy_any on land buy (VII); later zones use busy_day0 < 1 plus cash and solver-ok
    status: pending
isProject: false
---

# Buy NE regardless of utilization; later zones need one day-0 start

Change the reject condition in [`milos/planner.py`](milos/planner.py) `_activate_next_ne` (~line 333).

**Land buy (zone VII, `land > 0` / NE unowned):** ignore `busy_day0` and `busy_any`. Accept if cash covers `cost + 1000` and the solve succeeded (`worker in result.solved_workers`). An idle or staggered VII plan still buys land.

**Later NE zones (`land == 0`):** `busy_day0 < 1` (was `< 2`), plus the same cash and solver-ok gates. One tile starting on the activation day is enough; `busy_day0=0` still rejects.

```python
thin = False if land else busy_day0 < 1
if thin or money - cost - land < 0 or worker not in result.solved_workers:
```

Keep the existing `[ne] reject` / `[ne] accept` logs (`ok=`, `busy_day0`, `busy_any`). Do not switch later zones to `busy_any`. Do not submit unless asked.
