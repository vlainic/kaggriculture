# System Patterns

## Implemented multi-worker agent (Aug 11, 2026)

```
obs → Executor.step
  ├─ hour0: reset route_idx per worker; assign_hand_workers from spawn pos
  ├─ replan triggers:
  │    day 0 only → Planner.solve_plan (CP-SAT, 8s)
  │    later days → patch_plan (greedy, free tiles only, no CP-SAT)
  ├─ Planner (day 0):
  │    ├─ candidates per worker zone (crops + animals)
  │    ├─ per-worker/day op caps (NET_TILE_OPS)
  │    ├─ indexed constraints (element_to_vars, worker_day_terms)
  │    └─ output: full forward placement list
  ├─ market (≤10 orders): HIRE → (drop SELL if over cap) → BUY seeds/animals/fert/wheat
  └─ per worker: lock-escape → SHED_DOOR → shed PICKUP → approach route[0] → snake
```

### Worker spatial model (`agent/workers.py`)

| Worker | Tiles | NET_TILE_OPS | Spawn (locked?) |
| --- | --- | --- | --- |
| farmer | 9 (SE block) | 15 | `(4,4)` unlocked |
| hire1 | 6 (SW strip) | 15 | `(5,4)` LOCKED |
| hire2 | 6 (N strip) | 15 | `(4,5)` LOCKED |
| hire3 | 4 (NW corner) | 14 | `(5,5)` LOCKED |

- **`SHED_DOOR = (4,4)`** — only unlocked shed-adjacent tile; all locked hands must route here before zone work (enables PICKUP).
- **`SPAWN_TO_WORKER`** + **`assign_hand_workers()`** — map hand list index ↔ worker from spawn position.
- **`WORKER_ROUTE_GLOBAL`** — per-worker snake through owned tiles.

### Replan semantics

**Full replan (`_should_full_replan`):** `last_replan_day is None` (day 0 only).

**Patch replan (`_should_patch`):** empty tiles needing new plan entries; calls `patch_plan()` greedy pack.

**Not used anymore:** daily full CP-SAT on harvest/weed triggers (removed to avoid cumulative timeout).

### Executor routing (per worker)

1. If on LOCKED tile → move toward **`SHED_DOOR`**, not `route[0]`.
2. If on `SHED_ADJACENT` → `_shed_pickup` (fert, wheat, animals for today's placements).
3. If not at `route[0]` → approach first route tile.
4. Snake through route; sticky pending ops on current tile.
5. When route done but zone has pending → reset `route_idx` to 0 (second pass).

### Shed / spawn mechanics (engine)

- Daily reset: farmer → `(4,4)`; hands cleared then re-hired to shed corners NWSE.
- `(5,4)`, `(4,5)`, `(5,5)` are LOCKED (outside NW quadrant) — movement allowed, tile ops no-op.
- PICKUP requires standing on shed-adjacent tile; shed inventory shared.
- No tile occupancy collision — multiple units can share a cell.

### Market buying semantics

- Order cap 10: drop SELLs first to preserve HIRE/BUY.
- WHEAT sell reserve: `live_animals × WHEAT_FEED_RESERVE_DAYS`.
- Livestock excluded from sell loop.

## Submission workflow

| Script | Who | Action |
| --- | --- | --- |
| `scripts/smoke_test.sh` | Agents + users | Build tar + local 720-step smoke |
| `scripts/smoke_and_submit.sh --submit "msg"` | **Users only** | Smoke + Kaggle upload |
| `kaggle competitions submit ...` | Users | Manual upload |

**Agents must never run submit** unless user explicitly asks in that conversation.

## Target architecture (later)

- Fert profiles, sell timing, town demand in weights
- Optional master search for hire/land timing

## Repo layout (current)

```
main.py
agent/{workers,rollouts,planner,executor,ops_budget,animal_rollouts}.py
data/{crop_rollouts,animal_rollouts}.json
scripts/{smoke_test,smoke_and_submit,vendor_ortools}.sh
vendor/ortools/...
.cursor/rules/kaggle-submission.mdc
```
