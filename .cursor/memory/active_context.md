# Active Context

## Current focus (Sep 23, 2026)

**Live submission = `milos/` farmer-only** — `main.py` → `milos.executor.step`. Layout: `MILOS_FARMER` (5 tiles, zone I, **0 hires**). Target five-zone + 4 hires documented in [`data/milos_zoning.md`](../../data/milos_zoning.md) (not coded yet).

`agent/` TwoLand WSP remains in-repo as legacy / optional reference; **smoke builds `milos/` into the tarball**.

### Critical engine rule — shed-adjacent **ONLY IF OWNED**

The four center tiles are shed-adjacent in the rules, but **PICKUP / DROP no-op on `LOCKED`**. Milos farmer owns NW center `(4,4)` only. Gate via `_owned_shed_tiles`.

### Status

| Item | State |
| --- | --- |
| Live agent | **`milos/`** farmer-only (`NUM_ACTIVE_HIRES=0`) |
| Market dawn buys | **h=0 only:** wheat → animals → seeds (then sells) |
| Farmer h=0 | PASS (`defer_farmer_hour0`) so market fills shed first |
| Theo / capacity | Dawn `forecast_day_counts` dry-run → `[theo]` / `[theo_extra]` / `est_ops=` |
| Endgame d=29 | `_endgame_harvested` blocks re-HARVEST after DROP clears `_endgame_done` |
| Five-zone / hires | Spec only in `data/milos_zoning.md` |
| Agents submit | Never without explicit ask |

### Sep 22–23 — milos executor / market / smoke diagnostics (KEEP)

**Double HARVEST (d=29):** DROP cleared `_endgame_done` → retargeted same PLANT while yield still looked >0. Fix: `_endgame_harvested` on HARVEST (dawn-reset, not cleared on DROP); skip those plants in endgame targeting.

**Mid-day wheat buy → extra PICKUP:** `BUY_PRODUCT WHEAT` every hour after FEED emptied shed. Fix: wheat buy **hour==0 only**. Later: all dawn buys (wheat/animal/seed) **h=0 only**, order **wheat → animals → seeds** (animals need shed PICKUP; seeds do not).

**Theo vs act chart:** `est_ops=` = dry-run `tile_ops` (not animal×4+crop×1.5). `_zone_animal_crop_ops` returns counts only. `[theo_extra]` for shed PICKUP/DROP; plot prints totals + shed + per-tile mismatches.

**sim_apply:** BUILD before empty-tile early-return; ongoing-crop HARVEST takes 1 unit (not wipe). Forecast save/restore endgame sets.

**Ruff:** collapsible-if / isort cleanups in `milos/{executor,market,tile_ops}.py`.

### Anti-patterns (still)

- Mid-day `BUY_PRODUCT WHEAT` / animal / seed (reintroduces shed theo≠act)
- Clearing harvest-once sets on DROP (double HARVEST)
- Heuristic `est_ops = animal*4+crop*1.5` as capacity truth
- Treating center tiles as shed doors without `LOCKED` check
- Agents submitting without explicit ask

### Immediate next steps

1. Five-zone + 4 hires per `data/milos_zoning.md` when user asks (HIRE before wheat in h=0 list)
2. Capacity / theo alignment via smoke_analysis after behavior changes
3. Ladder / TwoLand `agent/` only if user switches live dispatch back
