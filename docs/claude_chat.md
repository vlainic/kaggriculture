# Kaggriculture Agent Strategy — Discussion Summary

**Competition:** [Kaggriculture](https://kaggle.com/competitions/kaggriculture) (Kaggle Simulations)
**Format:** Turn-based farming sim, 2-player head-to-head, 720 turns (24 turns/day × 30 days), ELO-style ladder leaderboard
**Deadline:** Entry/final submission Sept 30, 2026; leaderboard finalizes ~Oct 15, 2026
**Prize pool:** $5,000 × top 10 places

---

## 1. Framing the Problem

### Is this required to be an LLM-based agent?
No. The rules only require *"design, build, and deploy an autonomous AI agent"* — confirmed by the `agent(obs) -> actions` function signature in the docs. The "AI Agent" course context primed an assumption of LLM-based agents, but nothing in the competition spec requires it. RL, MCTS, DP, CP-SAT/MILP, or plain heuristics are all valid.

### Why not go full Deep RL?
Ruled out early — 2 months is not enough runway. Key reasons:
- Action space is **compositional**: farmer action + hand actions + up to 10 market orders, every turn, for 720 turns.
- Long horizon + reward shaping + self-play infra would consume most of the project time on plumbing, not strategy.

### Is beating LLM-based agents realistic?
Yes, and arguably favored:
- Exact numeric state tracking (price curves, yield formulas, care-bonus banking) rewards precise arithmetic/search over language-model "vibes."
- 100 MiB submission cap and likely no live network access in the runtime strongly suggest submissions can't call an LLM API live each turn — course participants' "LLM-based agents" are probably local/small models or LLM-assisted *authoring* of a scripted policy, not live LLM inference.
- 720-turn coupled-constraint resource allocation is exactly the shape classical search/optimization is built for, and exactly where LLMs are weakest without heavy scaffolding.
- Leaderboard is relative (ELO), not absolute — just need to consistently outperform typical heuristic-in-a-prompt submissions.

---

## 2. Why the Game Isn't a Simple Static Allocation Problem

Initial instinct (a single whole-game CP-SAT/MILP allocation) was rejected on good grounds:
- **Market is endogenous & reactive** — prices move with your own sell volume in real time, and opponent orders hit the same shared pool concurrently. A static plan can't see the price-impact of its own execution.
- **Growth/decay is time-coupled**, not a knapsack — watering bonus windows, ongoing-crop production ticks, animal care-bonus banking are stateful dynamics, not one-shot picks.
- **Long, partly stochastic horizon** — weed spawns, random shop-unlock order. Re-solving a full MILP every few turns to chase this is expensive and still myopic between solves.
- Even the deterministic single-agent version isn't hand-solvable by a human — the price-impact-of-own-sales coupling alone makes it a genuine control problem, not a puzzle (confirmed by ~30 min of manual play only reaching day 6 with a carrot-only strategy).

**Conclusion:** this is closer to a **reactive scheduling/control problem** than a one-shot allocation problem — but *local, bounded, and re-solved-often* optimization is still useful as a sub-tool (see §4).

---

## 3. Architecture: Hierarchical, Modular Design

### Top-level structure
Modular decomposition into 4 parts:
1. **Routing** — deterministic pathing (BFS/greedy on grid). No search needed; it's shortest-path given a target tile.
2. **Plants module**
3. **Animals module**
4. **Master module** — owns money, hiring, land purchases, segment activation

### Coupling risk flagged early
Plant/animal modules shouldn't act autonomously — they'd double-book shared scarce resources (money, farmer/hand time) the same way naive per-sector MCTS would. Design should use a **request/allocate contract**:
- Plant/animal modules emit *requests* ("want to plant 3 wheat, costs $30, needs 1 farmer-turn")
- Master arbitrates and allocates
- Modules execute against the allocation

This contract was flagged as worth nailing down **before** writing module code.

### Per-module algorithm fit (evolved over the conversation)
| Module | Algorithm | Rationale |
|---|---|---|
| Routing | Heuristic / shortest-path | Deterministic, no strategic branching |
| Plants (per-worker daily schedule) | **MILP/CP-SAT** (settled on this over DP) | Small, bounded (single worker, 24 turns/day, known segment, known action costs) — exact and re-solved daily |
| Animals | Heuristic first; escalate only if care-bonus banking timing gets non-trivial | Mostly reactive, low branching |
| Master (hire/land/segment activation) | MCTS, or possibly MPC-only / shallow lookahead | Long-horizon, uncertain, resource-tradeoff decisions |

**Staged rollout plan (user's plan):**
1. Ablated heuristics first — plant-only, animal-only, then combined — to see how episodes evolve quickly, and to double as MCTS rollout policies later.
2. Plant-only first (isolates MILP/routing logic before animal complexity like feed/care banking stacks on).
3. Within plant-only: **no-hire / single 3×3 segment first** (small enough to brute-force/hand-verify the MILP output for debugging), **then** add hires and additional segments.
4. Add action-sequencing versatility (harvest/fertilize not forced simultaneous, etc.) — flagged as a *structural* MILP constraint (precedence: water-before-harvest, fertilize timing windows) to model correctly from the start rather than retrofit.

---

## 4. The "MCTS + MPC" Framing (Corrected for This Domain)

User raised the general MCTS+MPC combination used in robotics/autonomous driving (MCTS = high-level strategic search, MPC = low-level continuous control, receding horizon execution).

**Correction discussed:** this game has no continuous control (no steering/torque-style actuators) — everything is discrete. So the standard robotics mapping doesn't translate 1:1. Adjusted mapping:
- **MCTS = master (strategic/discrete)** — sector allocation, hire timing, land purchases. Maps cleanly.
- **"MPC" slot = short-horizon *discrete* re-planning**, filled by CP-SAT/MILP (or DP) rather than continuous control — same receding-horizon pattern (solve → execute first step → re-solve), just discrete-in-discrete.

Final skeleton: **MCTS (master) → CP-SAT/MILP (local daily per-worker solve) → execute first macro-action → replan.**

### Master's decision cadence — open design question raised
Two options discussed:
- **Event-driven**: master re-decides only on triggers (hand hired, land bought, shop unlocked) — cheaper, but sectors run open-loop between triggers.
- **Fixed cadence** (e.g. daily): simpler, but risks wasted search on no-change days.
- Leaning: event-driven + daily as a floor, since "a day" is already a natural macro-boundary (watering/feeding cycle).

### Later refinement: does master even need MCTS?
Once the daily MILP became the per-segment solve, it was noted that **if the master's branching factor stays small** (hire N∈{0..~3}, buy land y/n, activate segment y/n), a shallow brute-force lookahead using the segment MILP's forecasted value may be cheaper than full MCTS and give the same result. Suggested next step: **count the actual master branching factor** before committing to MCTS vs. simpler enumeration — could save building unneeded search infrastructure.

---

## 5. Non-Stationary Demand — "Bigger, More Complex Beer Game"

User reframed the problem as a supply-chain "beer game" analog with non-stationary demand (town shops unlock stochastically every 3 days; town center consumption steps up at day 10 and day 20). Algorithms discussed:

- **MPC / rolling-horizon control** — re-plan every few turns against a forecast rather than a fixed plan; directly addresses the "market reacts to my own sells" issue.
- **Demand forecasting via Monte Carlo over shop-unlock scenarios** — only 8 shop types exist, so it's cheap to simulate plausible unlock orders and derive an expected demand curve per product to feed into MPC/replanning.
- **Base-stock / order-up-to policies** — good as a heuristic baseline/ablation tier, but assumes stationary demand, so not the final answer.
- **Bullwhip-effect discipline** — sector agents shouldn't overreact to short-term price swings; this is exactly what tanks price for premium goods (strawberry, melon, milk, wool all crash hard on gluts per the price table). Smooth sell decisions.

---

## 6. Spatial Layout Insight (User's Own Analysis)

User worked out how a single 5×5 quadrant naturally splits into sub-regions relative to the shed:
- 3×3 block adjacent to the shed
- 2×2 block on the far side from the shed
- 3×2 blocks filling the remaining sides

This spatial decomposition is what motivated the "segment" concept — each segment gets its own worker + daily MILP schedule, with the master deciding when to activate/hire for a new segment based on money/state. Plant-only segments were proposed first, with "specialization" (plant vs. animal segments) as a later addition.

---

## 7. Throughput & Capacity Numbers (Empirical + Theoretical)

- **Theoretical max**: 24 turns/day ÷ 2 turns/tile (1 move + 1 action) = **12 tiles/day** for a lone farmer, assuming perfectly adjacent tiles.
- **Reduced by real constraints:**
  - Farmer spawns at the shed each day — first hop isn't free.
  - Any tile needing 2 actions same day (e.g. water + harvest) costs 3 turns, not 2.
  - Non-adjacent tiles (shed trips, scattered plants) cost extra movement.
- **User's empirical result from manual play:** lone farmer realistically handles **~9 fields**, vs. the 12-tile theoretical max — roughly 25% overhead. Noted as good input to bake into the master's capacity planning (rather than assuming theoretical max), and likely to shift with tile adjacency/layout — worth re-measuring per layout once routing is implemented.
- **Hiring cost** follows `farmHandCostMult × fib(n)` (n = hires already made that day): 1, 1, 2, 3, 5, 8, 13, 21… (resets daily). A 2nd hand roughly doubles tile throughput cheaply; scaling past ~3–4 hands/day gets expensive fast — relevant to master's hire-timing logic.

---

## 8. Practical / UI Observations from Manual Play

- Manual play is tedious and not very user-friendly — after ~30 minutes of carrot-only play, only reached day 6.
- **Render doesn't surface everything the game actually tracks** — e.g., carrot count next to the shed isn't shown, no visible fertilize-status feedback in the UI.
- **This is not a problem for the agent**, since it reads `obs` directly (`private.shed`, `fertilized_until_day`, etc.) — structured JSON state, not the rendered board. The UI gap is a rendering limitation for humans only, consistent with the game likely being built agent-first.
- **Melon absence in the play UI**: nothing in the rules gates melon behind an unlock — it should be available from turn 0 like everything else (`BUY_SEED MELON 1`, `obs["market"]["prices"]["MELON"]` / `inventory["MELON"]`). Likely another UI/rendering omission rather than a game restriction; worth confirming directly via observation dump rather than trusting the play UI.

### Shed interaction mechanics clarified
- `DROP` (while orthogonally adjacent to the shed) dumps the farmer/hand's **entire** inventory into the shed at once — no partial/targeted drop.
- Inventory also auto-drops to the shed **at end of each day** regardless of `DROP` — manual `DROP` is only needed mid-day (e.g., to free inventory or make items sellable immediately, since `SELL` likely pulls from shed, not carried inventory — flagged as worth confirming empirically).

---

## 9. Open Questions / Next Steps (as of this conversation)

1. Confirm whether `SELL` orders draw from **shed** or **carried inventory** (affects whether mid-day `DROP` is a hard prerequisite for selling).
~~2. Confirm melon (and any other seemingly "missing" types) are genuinely available from turn 0 via direct observation inspection, not just play-UI absence.~~ [CONFIRMED - it was my bad]
3. Design and finalize the **request/allocate contract** between plant/animal modules and the master, before writing module code.
4. Build and validate the **3×3, no-hire, plant-only** baseline first — small enough to hand-verify the MILP's daily schedule output.
5. Then extend to **hires + additional segments** (still plant-only).
6. Add **action-sequencing constraints** (water-before-harvest, fertilize bonus timing windows, one-time vs. ongoing crop differences) into the MILP formulation from the start.
7. Measure the master's **actual branching factor** to decide MCTS vs. a cheaper shallow-lookahead/enumeration approach.
8. Profile compute early — MCTS *and* a re-solved optimizer every decision point, on Kaggle's constrained submission runtime (1.6 vCPU, 6.5 GiB RAM), is a real risk.
9. Only after plant-only pipeline is working: add animal segments/specialization.

---

## 10. Final Architecture Skeleton (as currently converged)

```
Master (MCTS or shallow lookahead — TBD by branching factor)
  ├─ owns: money, hiring, land purchases, segment activation
  ├─ decision cadence: event-driven, daily as floor
  └─ allocates: budget + farmer/hand-time + tile quotas → segments

Per-Segment Daily Solve (CP-SAT / MILP)
  ├─ input: assigned worker(s), 24 turns/day, known routing costs, known per-action costs
  ├─ constraints: action precedence (water→harvest, fertilize windows), one-time vs ongoing crop rules
  └─ output: worker's turn-by-turn macro-action schedule for the day

Routing (heuristic / shortest-path)
  └─ executes movement between shed ↔ tiles ↔ structures

Animals Module (heuristic → escalate only if needed)
  └─ feed/care/harvest reactive logic, care-bonus banking

Execution Layer
  └─ translates macro-actions into raw per-turn obs→action calls
```