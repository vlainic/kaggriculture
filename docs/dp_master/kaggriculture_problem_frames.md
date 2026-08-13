# Kaggriculture Scheduling — Problem Frames Discussed

Reference list of every formulation considered for the tile/crop/animal scheduling layer (not the master hire/land layer, which stayed MCTS throughout).

---

## 1. Assignment Problem
**Idea:** Decide `crop[tile]` and `plant_day[tile]` per tile/cycle. Ops per day are fully derived (looked up from the crop's rollout template), never decided directly.
**Fits:** Cheap, small decision space (~9 tiles × 5 crops × 30 days).
**Breaks:** Doesn't natively enforce "one crop cycle per tile at a time" across replanting — needs an extra non-overlap rule bolted on.

## 2. Job Shop Scheduling (JSSP)
**Idea (as first coded):** `machine = tile`, `job = (tile, crop)` lifecycle, `AddNoOverlap` per tile.
**Fits:** Machine-per-task structure loosely resembles tile-per-op.
**Breaks:** Classic JSSP schedules each job exactly once and searches free start times to minimize makespan. Here, start times aren't free once `plant_day` is chosen — op days are fixed by the template. Also "jobs have no limit of repeating" (replanting) isn't standard JSSP; would need **reentrant/recirculating job shop** (semiconductor-fab literature) — ruled unnecessary since set packing already handles repeated cycles for free.

## 3. Weighted Set Packing (WSP)
**Idea:** Enumerate every feasible `(tile, crop, plant_day)` lifecycle as a candidate with fixed `(tile, day)` coverage and a precomputed value. Binary `y[k]` per candidate. Constraints: (a) per-tile — at most one selected candidate covers a given `(tile, day)` cell; (b) cross-tile — sum of ops from all active candidates on a given day ≤ farmer capacity. Maximize total value.
**Fits:** Matches the problem's real shape — precedence is baked into each candidate's template, not searched for; "no overlap" reduces to a simple covering inequality.
**Status:** Built and shipped at 25-tile/4-worker scale. **Abandoned** — see the post-mortem (`weighted_set_packing_failer.md`). Root causes were not the WSP math itself (worked fine at 9×1) but: planner/executor mismatch (ops-in-model ≠ turns-in-game), season-long horizon overpacking/underpacking, engine turn-order (market resolves after player actions, so same-hour buy→plant fails), shed/inventory timing bugs (harvest→inventory, not shed, until day rollover), and candidate explosion at multi-land scale.

## 4. Model Predictive Control (MPC) / Rolling Horizon
**Idea:** Re-forecast and re-solve a bounded lookahead window periodically; execute only the near-term decisions; roll forward.
**Fits:** Directly answers the "market reacts to my own sales" problem that ruled out a single whole-game static solve. Also the right way to keep WSP-style candidate generation tractable without season-long overpacking.
**Correction made mid-discussion:** horizon length ≠ replan cadence. Horizon must span at least the longest crop lifecycle (~15 days for melon/strawberry) so the capacity constraint can see a distant harvest spike coming; replanning can and should happen far more often than that (every few days), locking in only near-term new decisions while already-growing crops carry forward as fixed future draws on capacity.

## 5. MCTS
**Where it fits:** Master layer only — hire timing, land purchases, segment activation. Long-horizon, uncertain, resource-tradeoff decisions with real branching.
**Where it doesn't:** Tile-level scheduling. Once `(crop, plant_day)` is chosen, each tile's future state is fully deterministic — no branching to search over, so MCTS buys nothing there.

## 6. Dynamic Programming (DP)
**Idea:** Per-tile, closed-form DP over `(day, state)` — deterministic transitions, no search needed.
**Fits:** Cheapest possible solve for a single tile's lifecycle chain, since tiles don't interact with each other directly.
**Limitation:** Doesn't natively express the cross-tile shared daily-ops-budget constraint — that coupling needs to be layered on separately (LP relaxation, greedy, or a small joint solve over just the coupling).

## 7. RCPSP (Resource-Constrained Project Scheduling)
**Idea:** The general umbrella that subsumes assignment, JSSP, and set packing — jobs/tasks consume renewable resources (worker-ops/day, cash) over time under precedence. Multi-mode RCPSP would also cover fertilized-vs-not as different "modes" of the same job.
**Use:** Framing term, not a separate implementation — useful for literature search, not a new solver to build.

## 8. VRP / Periodic VRP (PVRP)
**Idea:** Workers = vehicles, tiles = customers, shed = depot. Objection raised — "vehicles don't return to depot" — resolved: they do, every day (spawn at shed each morning, auto-drop at day-end), so it's **Periodic VRP**: same depot, a fresh route each period, customers only need visiting on days they have due ops.
**Significance:** This is the actual missing piece behind the post-mortem's §3.1/3.3 failures (planner ignoring movement/shed-trip cost) — WSP/assignment/JSSP all treat "reaching the tile" as free; PVRP is the paradigm built specifically not to assume that.

## 9. Automaton Constraint (CP-SAT `AddAutomaton`)
**Idea:** Encode each tile's day-to-day state as a DFA — state on day d+1 determined by state on day d, except HARVEST resets the chain. CP-SAT's regular constraint (Pesant) enforces this natively.
**Verdict:** Same underlying B&B solver as plain WSP — not a faster engine, just a more compact encoding of the per-tile precedence piece. Doesn't touch the actual hard part (cross-tile daily capacity coupling). Superseded by #6 (plain DP is cheaper and simpler for a deterministic, non-branching chain).

## 10. Multi-Mode Candidate Expansion
**Idea:** Fertilize/no-fertilize (and other day-count-changing options like harvest+plant same day) aren't a new constraint type — just add `fertilized=True/False` as another dimension when generating candidates, so WSP picks between modes like any other candidate.
**Verdict:** No new machinery needed; bigger candidate list, same solver.

## 11. Priority Dispatching Rules
**Idea:** Classic scheduling-theory fallback — SPT, EDD, "always do the most urgent unlocked op next." Not a framework, just the simplest possible heuristic layer.
**Role:** Matches the post-mortem's own recommendation — prove the executor with something dumb and reliable before adding any solver on top.

## 12. Metaheuristics + Vectorized/Matrix Evaluation
**Proposed:** As a way to speed up search.
**Pushback:** Post-mortem never identified solve time as the bottleneck (3–6s was fine). The actual failures were correctness/scope issues (turn-order bugs, shed timing, planner/executor drift, season-long candidate explosion). Metaheuristics solve "evaluate thousands of candidates fast" — a problem not yet encountered. Flagged as premature — only worth revisiting if profiling at multi-land scale actually shows solve time as the constraint.

## 13. "3D Tetris" (visual framing, not a new solver)
**Idea:** Tile × day = a 2D grid where pieces (crop/animal lifecycles) can't overlap cells — genuinely Tetris-like. Ops budget was initially framed as a 3rd stacking dimension.
**Correction:** Ops-per-day isn't a 3rd independent axis (unlike Tetris columns, which stack independently) — it's a *shared* budget every tile's active piece draws from simultaneously each day. Better model: 2D placement grid + one extra "row-sum ≤ capacity" constraint per day. Structurally: set packing with a knapsack constraint layered on top — i.e., restates WSP, doesn't replace it.

## 14. Set Packing — Theoretical Background
- On Karp's 1972 NP-complete list lineage (set packing itself proven NP-complete by reduction from independent set/clique, not one of the original 21).
- Dual of set cover (minimize sets to cover everything vs. maximize sets with zero overlap).
- Independent set = set packing with 2-element sets; interval scheduling (the calendar-block picture used earlier) = set packing restricted to 1D intervals — much easier than general set packing.
- Comprehensive references for gaps like this: Wikipedia "List of NP-complete problems," Garey & Johnson *Computers and Intractability* Appendix A, Crescenzi & Kann's *Compendium of NP Optimization Problems*.

## 15. Named Composite Term
**Field Operations Scheduling Problem** — agricultural OR literature studies almost exactly this shape (fields = tiles, farm equipment = workers, seasonal calendar = days). Suggested as a search term if revisiting the literature.

---

## Where it landed

Composite frame that was converged on before the WSP approach was shelved:
- **Routing/visit layer** → PVRP (who visits which tile, which day)
- **Tile-occupancy layer** → set packing over mode-expanded candidates
- **Shared daily capacity** → one linear constraint
- **Lookahead** → ~15 days (covers longest crop lifecycle), replanned far more often than that
- **Master (hire/land/animal placement)** → MCTS, separate cadence, separate module

**Current status:** WSP implementation abandoned per your last message. Post-mortem's own recommended next step (§8 of the post-mortem) was heuristics/rule-based first, executor-reliability-first, short-horizon DP/MILP only after that's proven — still on the table if you want a starting point.
