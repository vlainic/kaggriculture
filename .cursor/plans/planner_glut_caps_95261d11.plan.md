---
name: Planner Glut Caps
overview: Copy the notebook GLUT_CAPS rolling-window harvest constraints into the live CP-SAT planner, with harvest stamped on chains and locked tiles.
todos:
  - id: stamp-harvest
    content: Stamp daily_harvest on segments, chains, locked tiles
    status: completed
  - id: glut-constraint
    content: Add GLUT_CAPS rolling-window constraints in _solve_assignment
    status: completed
  - id: good-enough
    content: Set OBJECTIVE_GOOD_ENOUGH = 57_000
    status: completed
isProject: false
---

# Planner glut caps (notebook windows)

Add the notebook cell’s **rolling-window** caps to [`agent/planner.py`](agent/planner.py) only. Same table:

```python
GLUT_CAPS = {
    "MELON":      {"window": 12, "cap": 52},
    "STRAWBERRY": {"window": 18, "cap": 20},
    "MILK":       {"window":  3, "cap": 25},
    "WOOL":       {"window":  4, "cap": 19},
}
```

Also set `OBJECTIVE_GOOD_ENOUGH = 57_000` (from last request).

## Stamp harvest

Planner chains have no per-product harvest today. In `_stamp_profile_segment`, accumulate yield from `harvest_ages` / `yield_per_harvest` onto `daily_harvest[product][rel]` for `product = _product_for_label(...)`. Carry that dict through `_stamp_chain` / IDLE / `_aggregate_locked` (locked remaining yield counts toward the cap on replan).

## Constraint in `_solve_assignment`

Same loop as the notebook, plus locked harvest:

```python
for product, spec in GLUT_CAPS.items():
    W, cap = spec["window"], spec["cap"]
    for d0 in range(max(0, horizon - W + 1)):
        harvest = sum(
            count[w][ci] * chains[ci]["daily_harvest"][product][d]
            for w in WORKERS for ci, chain in enumerate(chains)
            for d in range(d0, min(d0 + W, horizon))
            if chains[ci]["daily_harvest"][product][d]
        ) + sum(locked_by_worker[w]["daily_harvest"][product][d]
                for w in WORKERS for d in range(d0, min(d0 + W, horizon)))
        model.Add(harvest <= cap)
```

If `horizon < W`, one constraint over the remaining days with the same cap.

No executor/market changes.
