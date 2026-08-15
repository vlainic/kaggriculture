# System Patterns

## Current: handmade-chain assignment + snake executor (Aug 15)

```
import:
  data/{crop,animal}_rollouts.json + handmade_dp_candidates.json
  stamp chains → CP-SAT count[zone][chain]
  decode counts onto WORKER_TILES → TILE_QUEUES

obs → executor.step
  ├─ hour0: reset routes; assign_hand_workers; HIRE / BUY
  ├─ market: dump SELL from shed (≤10 orders)
  └─ snake: preamble (hire wheat pickup if animals) → tile ops → shed
```

`main.py` → `executor.step`. Planner runs **once at import**, not per turn.

### Assignment master (planner + notebook)

- **Vars:** `count[zone][chain]` IntVar `0..zone_size`, `sum == zone_size`. Not `x[tile][chain]` — tiles in a zone are interchangeable; per-tile binaries explode permutation symmetry (183s–40min OPTIMAL proofs).
- **Ops:** stamped tile actions + per-chain pickups (animal place, wheat-on-FEED, fert). Hire preamble = zone-day 0/1: `preamble <=> animal_count >= 1` via `preamble <= animal_count` and `animal_count <= preamble * zsize`. Farmer zone: no preamble. Do **not** use 654-term `OnlyEnforceIf` over tiles.
- **Cash / W/F:** daily `balance` chain (domain 0–200k), inventory levels, buy shortfall at I0 ($25 wheat / $100 fert).
- **Decode:** pop tiles from `WORKER_TILES[zone]` in order; any matching assignment is valid.
- **Notebook** (`OneLand-Assignement-Handmade-Candidates.ipynb`): can prove OPTIMAL (~66s, obj 83620, `num_workers=1`, no timeout). Optional `OBJECTIVE_GOOD_ENOUGH`.
- **Planner:** `OBJECTIVE_GOOD_ENOUGH = 80_000` + callback, `num_workers=1`, **no** `max_time_in_seconds`. Import ~0.8s FEASIBLE.

### Executor (do not “fix” via planner)

- Snake routes, `SHED_DOOR = (4,4)` for locked-hand PICKUP
- Hire preamble at **runtime** (wheat pickup when zone has animals) — master also counts it now
- `market.py` sells entire shed each hour — Open-I0 plan vs glut is a **sell** problem

### Engine facts

- Turn order: farmer/hands → market → farm update → day rollover
- h=0: seeds from market are not in `private["seeds"]` during same-hour farmer action → PASS (`market-hour`)
- SELL from shed; harvest goes to worker inv; eod dump inv→shed
- Daily re-hire

---

## Anti-patterns

1. **Per-tile assignment binaries** when constraints are zone-shared — permutation symmetry, not model size.
2. **Reified OR via two `OnlyEnforceIf` linear sums** for preamble — use count + linear 0/1.
3. **Season-long WSP** (abandoned Aug 12) — tile ops ≠ executor turns; candidate explosion.
4. **Trusting solver obj as bank** — I0 prices; dump sells crash melon.
5. **CP-SAT `num_workers=8`** while the user has other jobs — keep 1 unless asked.
6. **Committing `.cursor/`** — gitignored; Cursor will refuse the commit.

---

## Legacy WSP (do not extend)

See `docs/weighted_set_packing_failer.md`. Old day-0 ~8.7k set-packing candidates. Current `planner.py` is **not** that code.

---

## Repo layout

```
main.py → agent/executor.py → script.TILE_QUEUES
agent/planner.py          # zone-count CP-SAT at import
agent/{script,workers,tile_ops,market,rollouts,animal_rollouts}.py
data/{crop_rollouts,animal_rollouts,handmade_dp_candidates}.json
experiments/OneLand-Assignement-Handmade-Candidates.ipynb
scripts/{smoke_test,smoke_and_submit,vendor_ortools}.sh
```
