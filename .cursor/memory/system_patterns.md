# System Patterns

## ⚠️ Legacy: WSP multi-worker agent (ABANDONED Aug 12, 2026)

The following was built and **judged a failure**. Documented for archeology only. **Do not extend** without explicit user request. See `docs/weighted_set_packing_failer.md`.

```
obs → Executor.step
  ├─ hour0: reset routes; assign_hand_workers
  ├─ replan: day 0 → CP-SAT solve_plan (~8.7k candidates, 3–25s)
  │          later → patch_plan (greedy, empty tiles)
  ├─ market: HIRE/BUY/SELL (≤10 orders)
  ├─ h=0: often PASS all workers (market-hour) — engine runs market after farmer
  └─ h≥1: per-worker snake → tile ops → shed trips → route=done PASS / eod DROP
```

**Failure modes:** planner calendar ≠ executor physics; zone-starved farmer; 8–15 PASS/worker/day; not scalable multi-land.

---

## Patterns worth keeping (any future agent)

### Worker spatial model (`agent/workers.py`)

| Worker | Tiles | NET_TILE_OPS | Spawn |
| --- | --- | --- | --- |
| farmer | 9 | 15 | `(4,4)` unlocked |
| hire1 | 6 | 15 | `(5,4)` LOCKED |
| hire2 | 6 | 15 | `(4,5)` LOCKED |
| hire3 | 4 | 14 | `(5,5)` LOCKED |

- **`SHED_DOOR = (4,4)`** — locked hands must route here for PICKUP.
- **`assign_hand_workers()`** — spawn position → worker zone.

### Engine facts (planner must respect)

- **Turn order:** farmer/hands act → then market → then farm update → day rollover.
- **h=0:** seeds bought by market are **not** in `private["seeds"]` during farmer action same hour.
- **Harvest** → worker inv; **SELL** from shed (unless explicitly including inv); engine dumps inv→shed at day rollover.
- **Daily re-hire** — hands cleared each day; HIRE at h=0 required.

### Diagnostics

- **`[snap]`** at h=0: money, `{worker}_empty`, prices, shop demand (`executor.py`).
- **`experiments/live_analysis.ipynb`:** PASS bars, zone empty, plan Gantt, money (end = next-day h=0), Kaggle reward dot.

### Submission workflow

| Script | Who |
| --- | --- |
| `scripts/smoke_test.sh` | Agents + users (local only) |
| `scripts/smoke_and_submit.sh --submit` | Users only |
| Agents never `kaggle competitions submit` without explicit user ask |

---

## Anti-patterns (learned from WSP)

1. **Season-long CP-SAT** on 25+ tiles with 4 workers — too slow, too brittle, wrong abstraction.
2. **Separate planner + executor** without shared movement/shed/market model — endless coupling bugs.
3. **Weight bonuses** to fix zone balance — games objective (e.g. all placements day 24–25).
4. **Trusting smoke reward** without live_analysis PASS/zone charts.
5. **`[snap]` h=23 as end-of-day money** — logs before actions; use next-day h=0 or Kaggle score.

---

## Recommended future architecture (not implemented)

- **Executor-first** or **short-horizon** (3–7 day) replan with bounded candidates.
- **Per-zone heuristics** or small MILP per worker, not one global season pack.
- **Farmer-first staging** before filling hire zones.
- Master layer (hire/land/shop) separate from tile ops.

---

## Repo layout (current — legacy WSP code present)

```
main.py → agent/executor.py → agent/planner.py (CP-SAT)
agent/{workers,rollouts,animal_rollouts,ops_budget}.py
data/{crop_rollouts,animal_rollouts}.json
docs/weighted_set_packing_failer.md   ← read this before touching planner
experiments/live_analysis.ipynb
scripts/{smoke_test,smoke_and_submit,vendor_ortools}.sh
```
