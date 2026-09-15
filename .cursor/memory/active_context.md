# Active Context

## Current focus (Sep 15, 2026)

**Live agent = one-land WSP.** `CURRENT_SOLVER = "zonewise_wsp"`, `zoning.CURRENT = FIVE`. TwoLand runtime wiring stripped (third discard of TwoLand agent experiments this stretch).

`agent/solvers/twoland_wsp.py` is a **stub** (not imported). `TWO` layout stays in the zoning catalog only. Re-add path / notes: [`docs/twolands/twoland_readd.md`](../../docs/twolands/twoland_readd.md).

### Status

| Item | State |
| --- | --- |
| Live agent | **`zonewise_wsp` + `CURRENT = FIVE`** |
| TwoLand runtime | **REMOVED** — no `BUY_LAND_DAY`, no land2 probe, no `LAND1_`/`LAND2_` constants |
| `twoland_wsp.py` | Stub file kept; not in `_BACKENDS` |
| `TWO` layout | Catalog only (unused at runtime) |
| Kept from TwoLand era | `NUM_ACTIVE_HIRES`, hire batches, WSP cash semantics, smoke/replay tooling |
| Smoke (post-strip) | ~**85k** one-land on `scripts/smoke.txt` |
| Sept02 overhaul | Still **FAILED** — do not resume |
| Parity / queue-lock / min-overhaul | **DISCARDED** (third reset) — do not re-litigate without a new plan |

### What was done this session (Sep 14–15)

1. **Hard reset** toward pre-parity tip (`5b58c07` era) after parity / overhaul thrash.
2. **One-land strip plan** — remove all `twoland_wsp` + TWO *runtime* glue; keep catalog + stub file.
3. Implemented strip in `solvers/__init__.py`, `types.py`, `planner.py`, `market.py`, `zoning.py`.
4. Restored `scripts/smoke_analysis/` (lost on reset) and made it **layout-aware** via `smoke_analysis/layout.py` (no hard `LAND2_WORKERS`).

### Anti-patterns (still)

- Floor `conservative` at 0 / `cons >= min_balance`
- `track_shed=True` on WSP replan with W/F in conservative spend
- Static per-zone bank split
- Another eligibility / queue-lock chase for TwoLand stuck hands
- Treating “parity” / “min overhaul” as green light without a fresh approved plan
- Hardcoding land2 workers in analysis tooling

### Immediate next steps

1. Stabilize one-land (`zonewise_wsp` + FIVE) — smoke / ladder as user asks
2. Only re-open TwoLand from [`docs/twolands/twoland_readd.md`](../../docs/twolands/twoland_readd.md) when user asks — do not sneak `twoland_wsp` back into the dispatcher
3. Agents never submit without explicit ask
