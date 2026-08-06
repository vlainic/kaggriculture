# IDEA

Right — three dimensions collapses cleanly once you enumerate candidates instead of decision-per-cell. Here's the mechanism:

**Step 1 — Enumerate candidates (not decision vars yet).**
For each tile, list every `(crop, plant_day)` combo that fits in the 30-day horizon. Each candidate `k` is a *complete, fixed* lifecycle block: its rollout template gives you exactly which days it occupies the tile (`plant_day` → decay day) and exactly which ops fall on which day. With 9 tiles × ~5 crops × ~30 possible plant-days, that's under ~1,500 candidates — trivial to generate.

**Step 2 — This is now literally set packing.**
Think of it as: elements = `(tile, day)` cells on your calendar grid. Each candidate `k` "covers" the set of cells it occupies on its tile. You want to pick the max-value collection of candidates whose covered cell-sets never overlap. That's the textbook definition of weighted set packing — you don't need to invoke interval vars or a solver-specific "no-overlap" primitive to get there, it falls out as one linear constraint family:

- **Occupancy constraint** (per tile, per day): sum of `y[k]` over all candidates `k` on that tile that cover that day ≤ 1. This *is* the no-overlap — two candidates covering the same `(tile, day)` cell can't both be selected.
- **Capacity constraint** (per day, across all tiles): sum of `ops(k, d) · y[k]` over every selected candidate active that day ≤ farmer's daily op budget.
- **Objective**: maximize sum of `value(k) · y[k]` (yield/revenue per candidate).

`y[k] ∈ {0,1}` is your only decision variable family — one binary per candidate, not per cell. No start-time variables, no intervals — the start time is baked into which candidate you picked.

Why this replaces interval no-overlap: interval vars exist to let the solver *discover* a start time. You don't need that — plant_day is already enumerated as part of the candidate's identity, so "no overlap" reduces to a plain covering inequality over a small binary set. It's an assignment problem in the sense you wanted, just assigning whole placements instead of day-cells.

# CODE

from ortools.sat.python import cp_model

# Universe of elements, and subsets with weights
elements = ["e0", "e1", "e2", "e3", "e4"]

subsets = [
    {"id": "S0", "items": {"e0", "e1"},       "weight": 5},
    {"id": "S1", "items": {"e1", "e2"},       "weight": 3},
    {"id": "S2", "items": {"e2", "e3", "e4"}, "weight": 8},
    {"id": "S3", "items": {"e0"},             "weight": 2},
    {"id": "S4", "items": {"e3"},             "weight": 4},
]

model = cp_model.CpModel()

# One binary decision var per candidate subset
y = {s["id"]: model.NewBoolVar(s["id"]) for s in subsets}

# Packing constraint: each element covered by at most one selected subset
for e in elements:
    covering = [y[s["id"]] for s in subsets if e in s["items"]]
    if covering:
        model.Add(sum(covering) <= 1)

# Objective: maximize total weight of selected subsets
model.Maximize(sum(s["weight"] * y[s["id"]] for s in subsets))

solver = cp_model.CpSolver()
status = solver.Solve(model)

if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    selected = [s["id"] for s in subsets if solver.Value(y[s["id"]]) == 1]
    print("Selected:", selected)
    print("Total weight:", solver.ObjectiveValue())
else:
    print("No solution found.")