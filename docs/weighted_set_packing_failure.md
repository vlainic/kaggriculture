# Weighted Set Packing (WSP) — Post-Mortem

**Scope:** One land (25 tiles), four workers (farmer + 3 daily hires), CP-SAT season planner + snake-route executor.  
**Outcome:** Architecture delivered ~19k–51k smoke rewards depending on patch iteration, but never reliably hit the ~50k+ target with stable behavior. The approach is judged **too slow, too brittle, and non-scalable** to 2–3 lands.

---

## 1. What the WSP approach was supposed to be

The idea (documented in `docs/weighted_set_packing.md`) was elegant:

1. **Enumerate candidates** — every feasible `(tile, crop/animal, profile, start_day)` lifecycle is a precomputed “subset” with fixed `(tile, day)` coverage, ops-by-day, and revenue weight.
2. **CP-SAT set packing** — binary `y[k]` per candidate; constraints:
   - at most one candidate per `(tile, day)` cell;
   - per-worker ops/day ≤ `NET_TILE_OPS` (~15 after one zone traversal);
   - (later) cash-on-hand never negative.
3. **Executor follows plan** — deterministic snake routes per worker zone; market buys seeds/animals from plan; replan on day 0 + patch when tiles free.

This mirrored a **FarmerOnly-Coupled-Open** notebook experiment that worked on **9 tiles, 1 worker** — small enough that the model was exact and debuggable.

Production scaled to **25 tiles, 4 workers, animals, hires, market timing, and shed/inventory physics** — a different problem class.

---

## 2. Architecture as built

```
day h=0:  replan/patch (CP-SAT, up to ~25s) → market (HIRE/BUY/SELL) → [PASS if market-hour] → snake h≥1
day h≥1:  snake route → tile ops → shed trips → h=23 DROP + sell
```

| Component | Role |
|-----------|------|
| `agent/planner.py` | CP-SAT + greedy fallback; ~8,775 candidates on day 0 (4,575 crop + 4,200 animal) |
| `agent/executor.py` | Zone snakes, plan blocking, market orders, end-of-day collection |
| `agent/workers.py` | Fixed 25-tile partition: farmer 9, hire1–3 six/six/four tiles |
| `agent/rollouts.py` | Precomputed lifecycle templates (ops, harvest ages, yields) |

**Solver budget:** `SOLVER_TIME_LIMIT_S = 25`, adaptive cap against Kaggle’s 60s overage bank on day 0. Typical day-0 solve: **3–6 seconds** — acceptable locally, painful inside a 720-step episode and catastrophic if repeated per land.

---

## 3. Core issues (root causes, not symptoms)

### 3.1 Planner model ≠ executor reality

The planner optimizes **tile operations** (PLANT, WATER, HARVEST, FEED, …) with a **single traversal subtracted** per worker-day (`NET_TILE_OPS ≈ 15`). The executor spends turns on:

- **Movement** along snake (3–15+ steps per pass depending on zone)
- **Shed round-trips** (PICKUP/DROP for fert, wheat, animals, harvest)
- **Plan-blocked waiting** (no seeds yet, no animal in inv)
- **h=0 market-hour PASS** (engine runs farmer before market — seeds bought *after* farmer acts)
- **Idle PASS** when route is “done” but nothing executable remains

So **15 “ops” in the model ≠ 15 productive turns in the game**. Workers routinely logged **8–15 PASSes per worker per day** — mostly `route=done`, not plan-blocked spam after later fixes.

The notebook never had: multi-worker zones, daily re-hire, compositional market+farm turn order, or inventory/shed as a separate state from “ops.”

### 3.2 Set packing on a long horizon overpacks (then underpacks)

**Phase A — stack everything on every tile**

Initial `solve_plan` used all 25 tiles as plannable and allowed **multiple sequential lifecycles per tile** in one solve (only `(tile, day)` cells couldn’t overlap). Day-0 plan: **~74 placements on 25 tiles** — physically impossible to execute with 4×15 ops/day.

**Phase B — one lifecycle per tile per solve**

Added `sum(y[k] for k on tile) ≤ 1` + greedy `used_tiles`. Day-0 plan: **25 placements** — correct count, but CP-SAT still **ignored zone balance**: most crops landed in hire zones; **farmer zone stayed 6–8 tiles empty until late season** (visible in live_analysis charts).

**Phase C — bonus hacks made it worse**

`ZONE_FILL_BONUS_PER_TILE` (later removed) pushed all placements to **days 24–25** — reward collapsed to ~5k. `FARMER_DAY0_BONUS` only nudged one day-0 animal; farmer crops still scheduled at **days 16–18** (MELON blocks) because ops/cash constraints bind per worker and hire zones absorb capacity first.

The planner optimizes **total season NPV under simplified constraints**, not **“fill every zone early”** or **“maximize day-0–10 revenue.”**

### 3.3 Plan → buy → execute ordering is engine-adversarial

Engine turn order (farmer/hands **then** market in the same hour):

1. At h=0, `_market_orders` correctly queues `HIRE` + `BUY_SEED`.
2. Farmer acts **before** those orders execute → no seeds in `private["seeds"]` yet.
3. Any logic that tries to PLANT at h=0 fails or blocks.

**Attempts:**

| Fix | Effect |
|-----|--------|
| Plan-blocked: don’t advance route without seeds | **931 PASSes/season**; workers stuck on tiles all day |
| h=0 aware: advance route, plant from h≥1 | PASSes down but **first PLANT ~h=11** — lost day 0 |
| **Blunt h=0 PASS for all workers** (`market-hour`) | First PLANT ~h=2, ~27k reward; **burns 1 hour every day** (30h/season) |
| Conditional h=0 PASS (only if today needs HIRE/BUY) | Still PASS every morning because **hands must re-hire daily** |

True “plan → buy → snake” in one hour is **impossible** without engine changes. Workarounds waste time or delay planting.

### 3.4 Executor didn’t follow the plan (initially)

Even with a good plan, early executor bugs caused **skip-advance** behavior:

- `_pending_for_tile` returned `[]` when seeds missing → route advanced past empty planned tiles
- No seed pickup path (seeds aren’t in shed — `BUY_SEED` goes to seed slot)
- `_route_idx` incremented on blocked plan work

Fixes (plan-unfulfilled vs plan-blocks-now, shed pickup for animals/fert, don’t advance when blocked) **increased correctness** but **increased waiting/PASS** until market-hour workaround.

### 3.5 End-of-day money collection was wrong

Harvest → **worker inventory**, not shed. Market **SELL** reads shed (+ optionally inv at h=23). Engine auto-dumps inv → shed at **day rollover** (after h=23 market).

So h=23 harvest often sold **next day h=0**, not same day. `[snap]` at h=0 logged **before** farmer+market → money charts showed ~30k while Kaggle score was ~39–51k.

**Fixes tried:** h=23 sell from inv; workers walk to shed and `DROP` when route done or h≥23; notebook plots “end of day” as next-day h=0 + Kaggle reward dot. **eod-drop** still rare (1 move/hour often can’t reach shed from far tiles in time).

### 3.6 Cash constraint came late; price model static

Early planner had **no cash feasibility** — it priced purchases but didn’t enforce `money + cumulative_cash ≥ 0`. Adding cash constraints stopped impossible buys but didn’t fix execution.

Weights use **current market prices × shop demand multiplier** at plan time — no modeling of **own sell impact** on prices (known issue from `docs/claude_chat.md`). Fine for notebook; wrong for competitive play.

### 3.7 Operational density cap (`MAX_ACTIVE_PER_WORKER_DAY`) — tried and reverted

Hypothesis: too many concurrent lifecycles → too many shed round-trips → PASS thrashing.

Added per-worker per-day cap on “active tiles needing attention.” User **reverted** — correct: **ops/day is the right constraint**; the cap was a band-aid on the planner/executor mismatch. It also didn’t address *why* passes happen (route done, market-hour, collection trips).

---

## 4. Chronology of what we tried

| # | Change | Planner | Executor | Smoke / logs |
|---|--------|---------|----------|--------------|
| 1 | Full WSP on all 25 tiles, multi-stack per tile | ~74 day-0 placements | Snake skips plan | Overpacked, holes in farm |
| 2 | `MAX_ACTIVE_PER_WORKER_DAY = 4` | Density cap | — | Reverted by user |
| 3 | Cash constraint + adaptive day-0 solve time | Feasible capital | — | Thinner plans, slower solve |
| 4 | Empty tiles only + one lifecycle per tile | ~25 placements | Still skipped | Plan shape OK, exec broken |
| 5 | Plan-following executor (pending, no skip on block) | — | Waits on tiles | ~27k, **931 PASSes** |
| 6 | h=0 seed timing (don’t block, plant h≥1) | — | Hour-aware | ~19k, first PLANT h=11 |
| 7 | h=0 **market-hour PASS** + buys before sells | — | Defer snake | ~27–36k, first PLANT h=2 |
| 8 | eod DROP + h=23 sell inv + snap/notebook fixes | — | Collection | ~32–39k chart vs ~39k Kaggle |
| 9 | Conditional h=0 PASS + early shed collection | — | Less waste? | Still market-hour daily (re-hire) |
| 10 | `FARMER_DAY0_BONUS` | Zone nudge | — | ~51k smoke best; farmer crops still day 16+ |

**Live analysis notebook** (`experiments/live_analysis.ipynb`) was essential — it exposed PASS counts, per-zone empty tiles, and the money logging bug. Without it, debugging was “watching videos and seeing holes.”

---

## 5. Why so many PASSes?

After later fixes, PASSes are **not** primarily “plan-blocked waiting for seeds.” Breakdown:

1. **`route=done`** — snake finished zone, no pending executable ops, not yet at shed with harvest (or nothing to drop). Worker PASSes until hour 23 or next day.
2. **`market-hour`** — every day h=0, all workers PASS while HIRE (+ sometimes BUY) runs. **Unavoidable** with daily re-hire unless snake starts h=1 always (current compromise).
3. **Shed / inventory trips** — partial implementation; long walks burn moves without counting as “ops” in planner.
4. **Plan start dates late in season** — farmer zone idle mid-game → entire passes with nothing to do.
5. **One action per worker per hour** — can’t plant and move same hour; route latency adds empty hours.

The planner assumes **~15 tile ops fit in a day**; the executor often has **~8–12 hours left** after one snake but **no modeled work** because plan entries are in the future or blocked on consumables.

---

## 6. Why WSP failed (judgment)

### 6.1 Wrong problem decomposition

WSP solves **“which lifecycles fit on the calendar grid?”**  
The game needs **“what do I do this hour, this worker, with this inventory?”**

Those are coupled: market timing, movement, shed capacity, re-hire, and price feedback aren’t reducible to static subset weights without rebuilding the same executor inside the solver.

### 6.2 Candidate explosion vs notebook

| Setting | Tiles | Workers | ~Candidates (day 0) | Solve time |
|---------|-------|---------|------------------------|------------|
| Notebook | 9 | 1 | ~1,500 (estimated) | Fast, exact |
| Live agent | 25 | 4 | **8,775** | 3–6s (+ patch replans) |

Scaling to **2–3 lands** (50–75+ tiles, more workers, land purchase decisions):

- Candidates ≈ **O(tiles × crops × profiles × days × animals)** → **tens of thousands+**
- Constraints ≈ **O(tiles × days + workers × days × candidates)** → CP-SAT memory/time blowup
- **Per-land replan** × 720 turns × 60s overage cap → **non-starter** on Kaggle

Greedy fallback avoids timeout but **ignores global structure** — back to heuristics with expensive preprocessing.

### 6.3 Two-system drift

Planner and executor were developed as separate modules. Every executor fix (market-hour, plan-block split, eod DROP) **invalidated planner assumptions** without updating the model. Debugging became whack-a-mole across 1,100+ lines of executor + 730 lines of planner.

The notebook worked because **one worker, one zone, one pass** made plan ≈ schedule ≈ execution.

### 6.4 Incremental patches masked strategic failure

We could raise smoke reward from ~19k → ~51k by:

- Not planting until seeds exist
- Wasting h=0
- Selling earlier / DROP hacks
- Bonus weights that game the objective

None of that fixes **“CP-SAT chooses a season plan the snake can’t execute efficiently on day 3.”** Best run still shows **farmer zone empty for 20+ days** and **12+ PASSes/worker/day** in charts.

### 6.5 Competitive gaps remain

- No opponent modeling
- No dynamic pricing / sell scheduling
- No integrated hire/land decision (always hire 3, one land)
- No weed / stochastic handling in planner
- Animals + crops competing for same worker-day budget without spatial coupling

---

## 7. What would have been needed for WSP to work (probably not worth it)

1. **Joint plan+route model** — embed movement and shed trips in ops budget (or simulate executor inside candidate generation).
2. **Rolling horizon, not season pack** — plan 3–7 days ahead, replan daily; keep candidates << 2000.
3. **Zone-fair constraints** — explicit `≥ k placements per worker zone in first N days` or separate solves per zone.
4. **Market-hour as first-class state** — model h=0 as “market only” in ops accounting.
5. **Single-land proof** before multi-land — hit 50k stable on 25 tiles with <4 PASSes/worker/day before scaling.

Even then, **2–3 lands** likely needs a **hierarchical** approach (master: land/hire/segment; local: small MILP or hand-tuned heuristics per segment), not one monolithic season CP-SAT.

---

## 8. Recommended direction after WSP

Based on failure mode:

| Approach | Rationale |
|----------|-----------|
| **Greedy / rule-based per zone** | Notebook math for crop ROI; plant when cash and ops allow; no 25s solve |
| **Short-horizon DP/MILP (3–5 days)** | Bounded candidates; re-solve cheaply; adapts to price changes |
| **Farmer-first staging** | Prove cash on 9 tiles; hire when marginal worker clears threshold |
| **Executor-first development** | Build reliable hour-by-hour policy; plan only what executor consumes |
| **MCTS at master level only** | Hire/land/shop timing; leaves low-level to heuristics |

The WSP **idea** (pre-enumerated lifecycles as candidates) remains useful as a **offline analysis tool** or **small subproblem solver** — not as the live season brain for multi-worker, multi-land Kaggriculture.

---

## 9. Key files (for archeology)

| File | WSP role |
|------|----------|
| `docs/weighted_set_packing.md` | Original 9-tile / 1-worker formulation |
| `agent/planner.py` | CP-SAT set packing, cash, greedy fallback |
| `agent/executor.py` | Snake, market, plan blocking, eod collection |
| `agent/workers.py` | Zone partition, `NET_TILE_OPS` |
| `experiments/FarmerOnly-Coupled-Open.ipynb` | Reference experiment (small scale) |
| `experiments/live_analysis.ipynb` | PASS / zone-empty / money diagnostics |
| `docs/claude_chat.md` | Early warning: not a static allocation problem |

---

## 10. One-sentence summary

**Weighted set packing failed because we optimized a static, season-long calendar abstraction that didn’t include movement, market turn order, shed physics, or zone fairness — and scaling CP-SAT candidates to multiple lands would multiply an already slow, brittle planner–executor split that only worked at 9×1 scale in a notebook.**
