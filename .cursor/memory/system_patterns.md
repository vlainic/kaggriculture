# System Patterns

## Target architecture (converged design — not yet implemented)

```
Master (MCTS or shallow lookahead — TBD by branching factor)
  ├─ owns: money, hiring, land purchases, segment activation
  ├─ cadence: event-driven re-decisions; daily as floor
  └─ allocates budget + worker-time + tile quotas → segments

Per-Segment Daily Solve (CP-SAT / MILP)
  ├─ input: assigned worker, 24 turns/day, routing costs, action costs
  ├─ constraints: water→harvest precedence, fertilize windows, crop-type rules
  └─ output: turn-by-turn macro-action schedule for the day

Routing (shortest-path / BFS)
  └─ movement between shed ↔ tiles ↔ structures

Animals Module (heuristic first)
  └─ feed/care/harvest; care-bonus banking on production days

Execution Layer
  └─ macro-actions → raw per-turn agent(obs) return value
```

## Module coupling pattern

**Request/allocate contract** (must nail before module code):

- Plant/animal modules emit *requests* (cost, farmer-turns, tiles needed)
- Master arbitrates shared resources (money, hands, time)
- Modules execute only against allocated budget

Avoid autonomous per-module agents that double-book scarce resources.

## Spatial decomposition

Single 5×5 quadrant splits around central shed into sub-regions (3×3 near shed, 2×2 far, 3×2 sides). Each **segment** gets a worker + daily MILP schedule; master decides when to activate/hire for new segments.

## Staged rollout (planned)

1. Plant-only, no-hire, single 3×3 segment — hand-verify MILP output
2. Add hires + extra segments (still plant-only)
3. Master hire/land decisions (MCTS vs shallow enum — decide after counting branching factor)
4. Animals module after plant pipeline is stable

## Algorithm fit per module

| Module | Approach | Rationale |
| --- | --- | --- |
| Routing | Shortest-path | Deterministic, no branching |
| Plants (daily) | MILP/CP-SAT | Bounded: 1 worker, 24 turns, known costs |
| Animals | Heuristic | Mostly reactive; escalate only if care-bonus timing bites |
| Master | MCTS or shallow lookahead | Long-horizon hire/land/segment decisions |

## Repo layout (planned)

```
main.py
agent/
  state.py, planner.py, farm_actions.py, market_actions.py, pricing.py
eval/
  run_local.py
```

See `.cursor/skills/kaggriculture-agent-conventions/SKILL.md` for conventions.
