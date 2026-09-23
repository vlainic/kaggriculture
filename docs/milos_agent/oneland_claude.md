---
name: OneLand — extend farmer to 5 zones
overview: "Extend farmer-only (zone I) to all 5 zones (farmer + hire1-4) per milos_zoning.md, within NW quadrant only — no BUY_LAND. New milos/wsp/oneland.py cascades zone solves; planner/market generalize off the static FARMER_TILES/FARMER references; movement stays pure scripted snake (preamble + 4xN), no detours. Hire identity bound once at first spawn sighting."
todos:
  - id: layout
    content: "zoning.py: add MILOS_ONELAND (5 zones per milos_zoning.md coords/ops/preamble), set CURRENT = MILOS_ONELAND, NUM_ACTIVE_HIRES = 4"
    status: pending
  - id: solver
    content: "New milos/wsp/oneland.py: build_day0 loads full 25-tile prestart; solve() cascades zoning.WORKERS via mip.solve_zone with running cash handoff; INFEASIBLE = skip zone, keep queue, continue. farmer.py untouched."
    status: pending
  - id: mip-pickup-cap
    content: "mip.py: _stamp_placement's daily_tile_ops currently includes literal PICKUP tokens (confirmed double-charge, one per animal/tile/day). Strip PICKUP from that count; add day-level per-item-type shed-pickup booleans (WHEAT, FERTILIZER, each animal type) into solve_zone's ops-cap sum instead — 1 turn/distinct-item-type/day/zone, since PICKUP <item> [n] can't mix item types in one turn"
    status: pending
  - id: planner-scope
    content: "planner.py: replace FARMER/FARMER_TILES-scoped board+solve calls with NUM_TILES/WORKER_TILES-scoped; swap solve import to oneland; replan day-gate to day<2"
    status: pending
  - id: market-wheat
    content: "Confirm script.total_wheat_feed_need sums all 25 tiles (not just zone I); market.py buy/reserve logic is already zone-agnostic via workers.NUM_TILES"
    status: pending
  - id: executor-snake
    content: "executor.py (not reviewed — need current file): per-worker scripted preamble + 4xN replayed every dawn (all workers respawn daily), hire bound to zone at first sighting each day and cached, PICKUP is shed-only but still a real turn — charge 1 turn/item-type at the shed step (not 1/animal) into net_tile_ops, market HIRE x4 first every day"
    status: pending
isProject: false
---

# OneLand — extend farmer to 5 zones

`# Mode: PLAN`

Farmer-only (zone I, 5 tiles) → farmer + 4 hires (25 tiles), all inside the **already-owned NW quadrant**. No `BUY_LAND`. Reuses the farmer pattern 5x; does not rewrite it.

## zoning.py

Add `MILOS_ONELAND` (`Layout`) alongside `MILOS_FARMER`, per `milos_zoning.md`:

- Zone order matters (drives `HAND_DAILY_COST` fib assignment in `bind()`): `(farmer, hire1, hire2, hire3, hire4)` → hire costs 1,1,2,3 (sum 7).
- Columns, x = zone: `farmer`=4 (existing), `hire1`(V)=0, `hire2`(IV)=1, `hire3`(III)=2, `hire4`(II)=3. Each column: `(x,4)→(x,0)`, tile indices `0–4 / 5–9 / 10–14 / 15–19 / 20–24` — matches `prestart.json` keys and doc ops `18/14/14/15/15`.
- Preamble per doc, as literal ops (PICKUP qty resolved at runtime by executor, not baked into the layout):
  - hire1: `PICKUP, W,W,W,W`
  - hire2: `W, PICKUP, W,W,W`
  - hire3: `N, PICKUP, W,W`
  - hire4: `W, N, PICKUP, W`
  - farmer: unchanged (`()`, already home-tile)
- `CURRENT = MILOS_ONELAND`, `NUM_ACTIVE_HIRES = 4` (planner.py constant — presumably consumed by executor for HIRE count / hand-slot expectations, confirm there).
- Spawn corners are real board coords, not quadrant-local: hire1↔`(4,4)`, hire2↔`(5,4)`, hire3↔`(4,5)`, hire4↔`(5,5)` — the four shed-adjacent tiles across all quadrants (3 locked-but-passable since only NW is owned). This is *why* each hire's preamble differs — it's the walk-in from its actual spawn corner back onto owned land, not an arbitrary offset.

## milos/wsp/oneland.py (new)

Same shape as `farmer.py`, generalized to cascade:

- `build_day0()`: load `prestart.json` **unscoped** (all 25 tiles; `solved_workers` is already `["farmer","hire1","hire2","hire3","hire4"]` — no tile filtering needed, unlike `farmer._load_prestart(tiles=...)`).
- `solve(...)`: loop `zoning.WORKERS` in order; per worker call `mip.solve_zone(patterns, empty_tiles=that worker's tiles ∩ empty_tiles, locked=(locked_by_worker or {}).get(worker) or _empty_locked(horizon), opening_balances=[running_money]*horizon, ...)`. On `None` (INFEASIBLE): skip worker, don't add to `solved_workers`, keep cascading — never abort the whole solve. Advance `running_money` conservatively (closing balance of the zone just solved) before the next worker.
- Reuse `farmer._load_prestart_raw()` for the raw JSON read and the same `_empty_locked`/pattern-building helpers — don't build a third JSON loader.
- **Do not touch `farmer.py`.** Keep it as the zone-I sandbox — matches your own postmortem takeaway.

## mip.py — PICKUP is double-charged today, confirmed in code

Two exact spots. (The other plan's "don't touch mip.py, don't strip PICKUP" is wrong — this needs both.)

- `_stamp_placement`: `daily_tile_ops[cal] += len(acts)` includes the literal `"PICKUP"` token straight from `animal_with_pickups.json`. Check `rollouts.crops()`'s data file too — `_parse_age_maps` computes `fert_use_by_age` for crops the same way it does for animals, so FERTILIZE likely has the identical PICKUP-FERTILIZER pattern on the crop side.
- `solve_zone`'s cap loop sums that per-tile-per-pattern count straight into `<= net_tile_ops` per day: `n = pat["daily_tile_ops"][day]; terms.append(x[pi, tile] * n)`, summed across every tile in the zone. As written, 3 animals needing feed the same zone/day = 3 ops charged for what's really 1 `PICKUP WHEAT <n>` turn. And **you can't combine item types in one PICKUP** — a day placing both a COW and a SHEEP is 2 separate turns, not 1, since `PICKUP <item> [n]` only ever takes one item type. Real cost = 1 turn per *distinct item type* needed that zone/day (WHEAT if any feed that day, FERTILIZER if any shed-sourced fert that day, +1 per distinct animal type being `PLACE`d that day) — not 0, not 1/animal, not a flat guess.
- Fix: (1) `daily_tile_ops[cal] += len([a for a in acts if a != "PICKUP"])` — strips the raw over-count. (2) In `solve_zone`, add per-day boolean indicators — `need_wheat[d]`, `need_fert[d]`, `need_animal[d, animal_name]` — each linked via `model.Add(need_x[d] >= x[pi, tile])` for every pattern/tile whose `daily_feed[d]` / `daily_fert[d]` / that-day placement is nonzero. Add `need_wheat[d] + need_fert[d] + sum(need_animal[d, :])` into the same `<= cap` constraint alongside the now-stripped `daily_tile_ops` sum. No objective term needed on these — as a pure capacity cost bounded below by `>=`, CP-SAT settles each at its minimum feasible value on its own.

## planner.py — the real gotcha

Several spots are hardcoded to the *old* `FARMER`/`FARMER_TILES` (a module-level constant frozen to `MILOS_FARMER.zones[0].tiles`, **not** rebound when `CURRENT` changes). Left as-is, these silently drop every hire tile:

- `empty_board()` — iterates `FARMER_TILES` (5) → needs `range(NUM_TILES)` (25).
- `apply_solver_result()` — `tile_set = set(FARMER_TILES)` → any hire-zone chain gets silently discarded on write. Needs `set(range(NUM_TILES))`.
- `merge_wsp_plan()` — same default-scope bug when `tiles=None`.
- `build_day0()` — `empty = list(FARMER_TILES)`, `empty_counts={FARMER: len(empty)}` → needs `empty = list(range(NUM_TILES))`, `empty_counts = {w: len(WORKER_TILES[w]) for w in WORKERS}`.
- `replan()` — same `empty_counts={FARMER: len(replan_tiles)}` fix; **day gate `day < 1` → `day < 2`** (first replan at day=2, per spec).
- Swap `from milos.wsp.farmer import solve` → `from milos.wsp.oneland import solve`. `apply_replan()` / `_build_from_solver()` already loop `result.solved_workers` / `WORKER_TILES[worker]` generically — no change needed there.
- `locked_by_worker` comes from `replan_lock.build_replan_lock` (not reviewed) — confirm it keys by all `zoning.WORKERS`, not just `{FARMER: ...}`.

## market.py — mostly already zone-agnostic

`_tile_at`, `_count_live_animals`, `needed_buys` all iterate `range(workers.NUM_TILES)` — once `zoning.bind(MILOS_ONELAND)` runs, these cover all 25 tiles for free. One thing to confirm (file not reviewed): **`script.total_wheat_feed_need`** must sum feed need across all 25 tiles, not just zone I. If it does, the existing `wheat_reserve = max(wheat_feed_need, live_animals)` + deficit-buy-at-h=0 logic is *already* "lock enough wheat, buy the gap" — system-level, per your spec. Nothing new to build here.

## executor.py — not reviewed, spec only

- **Hire identity bound fresh each dawn, at first sighting that day, never re-derived from position after.** Farmer + hands respawn at a shed-adjacent tile every morning per game rules, not just day 0 — so this binding runs once *per day*, not once ever. Cache `hand_slot → zone_name` (this is `workers.py`'s "spawn-tile hire binding helper" per your own file list) for the rest of that day, keyed off which of the 4 corner tiles each `hands[i]` is standing on. Log + skip (don't guess) if a hand isn't on a spawn corner that hour.
- Per-hand, every day: walk the corner-specific entry path back onto owned land (same doc-preamble as day 0 — it recurs daily because respawn is daily), then `WORKER_ROUTES[zone]` 4×N, executing the standing tile's queued action on arrival. No `_step_toward`, no *extra* mid-route shed detour beyond that day's own entry pass, no route wrap.
- **PICKUP is shed-only — but it still costs a turn.** `animal_with_pickups.json`'s own `meta.actions_are_tile_only: false` confirms PICKUP can't run on the animal's tile — that moves *where* it's charged, not whether. Skip `PICKUP` in `next_tile_action` (`FEED`/`CARE`/`HARVEST`/`COLLECT_FERTILIZER`/`BUILD_*`/`PLACE` stay tile-wise), and issue it instead during the preamble, once per *distinct item type* needed that day for the zone: one `PICKUP WHEAT <n>` covers every animal fed that day regardless of count, but each animal type being `PLACE`d that day is its own turn — two different animals placed same zone/day is two separate PICKUP calls, not one. See `mip.py` section below for the matching ops-cap fix — same accounting has to hold on both sides or the solver plans turns the executor can't actually spend.
- Market h=0, every day (not just day 0): `HIRE` ×4 first (order doesn't matter — identity comes from spawn-tile binding, not HIRE call order), then wheat → animals → seeds (existing `market.build_orders` order, unchanged).
- Day 29: existing endgame-only path, untouched.

## Out of scope

`BUY_LAND`, TwoLand, `DEAD_HANDS`, tests/smoke/submit, touching `farmer.py`.