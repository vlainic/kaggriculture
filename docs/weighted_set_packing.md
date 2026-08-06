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