# Active Context

## Current focus (Sep 11, 2026)

**Keep full conservative handoff** in `twoland_wsp` — **no** per-zone spend / opening clamp. Static NW budget splits lost on the ladder; softest → hardest was monotonic worse.

Working agent: **two-land WSP** (`twoland_wsp` + `CURRENT = TWO`), pre-Sept02 / `d35bff5` cash semantics. Broken Sept02 stack: local `backup/sept02-recovery`.

Diagnosis writeup: [`docs/twoland/diagnosis_0911.md`](../../docs/twoland/diagnosis_0911.md) (A OneLand `55934103` vs B TwoLand `55938405`).

### Status

| Item | State |
| --- | --- |
| Live agent | `twoland_wsp` + `CURRENT = TWO`; **full** cascade `opening = res["conservative"]` |
| Zone money caps | **REJECTED** — no-cap best (rating ~555–561); `min(day_start/2, handoff)` ~533; `day_start/n_hands` ~509 |
| Sept02 overhaul | **FAILED** — do not resume |
| TwoLand vs OneLand gap | ~+7k only (not 30–50%); root cause = **post-NE ops/weed collapse**, not glut |

### Confirmed (diagnosis_0911)

1. **NE buy → ops crash → weeds** — `ops_utilization` drops on buy-day; occupied% bottoms +1 day; recovery lag ~half of NE lifespan. Opponent expands without PASS spike → our bug.
2. **Late NE buy correlates with worse score** — day timing (cash ≈9–10k proxy), not income rate alone.
3. **Premium glut ruled out** — MELON/WOOL fill & rv/q similar A vs B.
4. **Hard NW spend caps ruled out** — both capped variants lost to no-cap.

### Anti-patterns (still)

- Floor `conservative` at 0 / `cons >= min_balance`
- `track_shed=True` on WSP replan with W/F in conservative spend
- Static per-zone bank split (`money/N`, `min(money/2, handoff)`, etc.)
- Gate strategy on n=3 smoke; prefer ≥30 episodes / ladder

### What still stands

1. Two-land WSP — probe hire5 → `BUY_LAND` → cascade VI–X
2. Layout TWO — hand-calibrated `net_tile_ops`
3. Planner / market — `BUY_LAND_DAY`, `NUM_ACTIVE_HIRES`
4. Submission notebooks — `submission_analysis` / `submission_comparison` + `replay_analysis`

### Immediate next steps (from diagnosis priority)

1. Wire `_route_move_cost` into `_formula_net_tile_ops` (or keep hand caps but fix real buy-day ops) — root-cause candidate
2. Check `by_worker` PASS split (NE hand ~100% PASS?) — may outrank route-cost
3. Early-NE-buy heuristic (day-based, not cash) / trigger-based NW→NE reserve — **not** a gentler static cap
4. Fix comparison tooling (`noise_std` fallback, unexplained_delta, wool rv/q zero-fill)
5. Agents never submit without explicit ask
