# Active Context

## Current focus (Sep 23, 2026)

**Live submission = `milos/` OneLand** — `main.py` → `milos.executor.step`. Layout: **`MILOS_ONELAND`** (25 tiles, farmer + **4 hires** via `milos/zoning.py` `CURRENT = MILOS_ONELAND`). Five-zone spec also in [`data/milos_zoning.md`](../../data/milos_zoning.md).

`agent/` TwoLand WSP remains in-repo as legacy / optional reference; **smoke builds `milos/` into the tarball**.

### Critical engine rule — shed-adjacent **ONLY IF OWNED**

The four center tiles are shed-adjacent in the rules, but **PICKUP / DROP no-op on `LOCKED`**. Milos farmer owns NW center `(4,4)` only. Gate via `_owned_shed_tiles`.

### Status

| Item | State |
| --- | --- |
| Live agent | **`milos/`** OneLand (`MILOS_ONELAND`, 4 hires) |
| **Dawn replan** | **`planner.replan`** — eligible empties/WEED; lock board+queue suffix; `milos/wsp/farmer.solve` **`track_shed=False`**, `min_balance=0`, live `make_price_of`; INFEASIBLE → keep queues |
| Day-0 queues | Prestart via `get_tile_queues` / `farmer.solve` (full 5-tile horizon) |
| Market dawn buys | **h=0 only:** wheat → animals → seeds (then sells) |
| Farmer h=0 | PASS (`defer_farmer_hour0`) so market fills shed first |
| Theo / capacity | After replan: `forecast_day_counts` → `[theo]` / `[theo_extra]` / `est_ops=`; **`compare_theo_act` mismatches=0** (±3 slack) after HARVEST sim + **hire4 CARE gate**; exec attribution via `parse_exec_actor` (`hand0=hireN`) |
| Endgame d=29 | `_endgame_harvested` blocks re-HARVEST after DROP clears `_endgame_done` |
| OneLand WSP | `milos/wsp/oneland.py` cascade; hire4 zone IV (e.g. t22 animal tile) |
| Agents submit | Never without explicit ask |

### Sep 23 — hire4 t22 CARE spam + theo/act alignment (KEEP)

**Symptom:** `[theo]` for **hire4** showed **many `CARE` on one tile in one day** (e.g. 14× on t22, d=24–25) while rules allow one CARE per animal per day. **Not** bad JSON in `animal_with_pickups.json` (one CARE per age in rollouts).

**Root cause:** Hourly replay loop — `_animal_action` could return **CARE** after **FEED** was skipped (no wheat in hand). `sim_apply` no-ops CARE when `not fed_today` → worker stayed on tile → forecast appended CARE every hour → theo inflation and hire4 **NET_TILE_OPS** eaten (missing **WATER** on t23–25). Live act often showed ≤1 CARE; bug was forecast + live offer path.

**Fix (no JSON edit):**
- `milos/tile_ops.py` — `CARE` only if `tile.get("fed_today")` (after existing `cared_today` skip).
- `milos/executor.py` — mirror FEED filter: drop live `CARE` when tile not `fed_today`.

**Diagnostics:** `scripts/smoke_analysis/parse_actor.py` (`parse_exec_actor`, `hand0=hireN`); `python3 -m smoke_analysis.compare_theo_act` from `scripts/`. Post-fix smoke: no multi-CARE t22 in theo; hire4 reaches crop ops on formerly bad days. MIP `_stamp_placement` unchanged (one op per calendar day per pattern).

### Sep 23 — milos dawn replan + theo HARVEST (KEEP)

**Dawn replan (live):** [`milos/replan_lock.py`](../../milos/replan_lock.py) eligibility + commitment stamp; [`milos/planner.py`](../../milos/planner.py) `make_price_of`, `apply_replan`, `replan()` at h0 d=1..28. No `agent/` imports; lazy import `replan_lock` / no `script` import at planner load (cycle). Executor call unchanged.

**Duplicate HARVEST in theo (not replan):** Dry-run used `min(y,1)` on ongoing crops → double HARVEST when `yield_units>1`. Fix: `plant_harvest_transfer` in `tile_ops` — **one HARVEST clears full harvestable stack** (rollouts: units per age, not per action); `sim_apply` sets `yield_units=0` for ongoing crops.

**Noisy PICKUP in mismatch print:** `plot_zone_capacity` printed shed lines whenever any tile mismatched. Fix: shed theo/act **only if `theo_x != act_x`**.

### Sep 22–23 — milos executor / market / smoke diagnostics (KEEP)

**Double HARVEST (d=29 live):** DROP cleared `_endgame_done` → retargeted same PLANT. Fix: `_endgame_harvested` on HARVEST.

**Mid-day wheat buy → extra PICKUP:** Fix: all dawn buys **hour==0 only**; order **wheat → animals → seeds**.

**Theo vs act chart:** `est_ops=` = dry-run `tile_ops`. `[theo_extra]` for shed PICKUP/DROP; plot prints per-tile mismatches + shed only on shed mismatch.

**sim_apply:** BUILD before empty-tile early-return; **plant HARVEST via `plant_harvest_transfer`** (full stack). Forecast save/restore endgame sets.

### Anti-patterns (still)

- Mid-day `BUY_PRODUCT WHEAT` / animal / seed (reintroduces shed theo≠act)
- **`min(y,1)` plant HARVEST in sim** (inflates theo tile_ops)
- Clearing harvest-once sets on DROP (double HARVEST live)
- Heuristic `est_ops = animal*4+crop*1.5` as capacity truth
- Treating center tiles as shed doors without `LOCKED` check
- Offering **CARE** without same-day **FEED** success (`fed_today`) — causes stuck-tile CARE spam in theo
- Agents submitting without explicit ask
- Importing `milos.script` from `milos.planner` at module load (circular with `get_tile_queues`)

### Immediate next steps

1. Keep theo/act aligned after executor or animal-path changes (`compare_theo_act`, smoke notebook)
2. Ladder / TwoLand `agent/` only if user switches live dispatch back
3. Watch replan INFEASIBLE logs; queues preserved by design
