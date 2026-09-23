# OneLand / five-zone attempt — discard notes

High-level record of the **MILOS_ONELAND** experiment (farmer + 4 hires, `data/milos_zoning.md`). Intent: discard the working tree and start over with a clearer movement/supply contract.

## Goal (what we tried)

- One land, **5 zones**: farmer @ I, hire1–4 @ V/IV/III/II per spawn corners `(4,4)/(5,4)/(4,5)/(5,5)`.
- Day-0: full prestart + cascade MIP; market **HIRE×4 → wheat → animals → seeds** at h=0.
- Movement: **scripted snakes only** (doc preamble + daily 4×N column). No free pathfind, no shed detours mid-season.
- Dawn replan from day=2, sequential zonewise WSP.
- Last day only: free endgame harvest → shed → DROP.

## Files touched (uncommitted / new)

| Path | Role |
|------|------|
| `milos/zoning.py` | `MILOS_FARMER` vs `MILOS_ONELAND`; `SPAWN_TO_HIRE`; ops 18/14/14/15/15; hire preambles |
| `milos/workers.py` | Spawn-tile hire binding helpers |
| `milos/wsp/oneland.py` | **New** — sequential 5-zone cascade solve |
| `milos/wsp/farmer.py` | Restored zone-I-only / farmer sandbox |
| `milos/wsp/mip.py` | Hire daily fib cost on hire zones |
| `milos/wsp/__init__.py` | Export wiring |
| `milos/planner.py` | `milos_oneland`, `NUM_ACTIVE_HIRES=4`, day-0 all tiles, replan day≥2 |
| `milos/replan_lock.py` | Lock per `worker_for_tile`, all workers |
| `milos/executor.py` | Biggest churn — snakes, bindings, pickup, daily laps |
| `milos/market.py` | HIRE×4 first; zone-sum wheat buy |
| `milos/script.py` | `zone_wheat_buy_need` / hand target; `total_wheat_feed_need` = zone sum |
| `scripts/smoke_analysis/layout.py` | Layout name when hires present |
| `scripts/smoke_analysis/parse_actions.py` | Parse `hand0=hire2` from logs |
| `data/milos_zoning.md` | Spec source (movement + ops) |

Plans (Cursor, not submission code): `five-zone_hire_cascade_*.plan.md`, `strict_doc_snakes_*.plan.md`, `daily_lap_wheat_fix_*.plan.md`.

## What was deleted / removed along the way

- **`_try_shed_detour`** — mid-zone walk to `(4,4)` for wheat/animals (anti-doc; burned hours).
- **`_seek_route_work` wrap / multi-lap skip** — pathfinding to arbitrary pending tiles (not “4×N only”).
- Mid-route **`_shed_pickup`** except scripted preamble / farmer-on-tile-0.
- Permanent **`snake-done` PASS for days 1–28** (“play snake once then idle”) — crushed score (~429).
- **`_filter_no_wheat_feed`** — skip FEED and advance north when hand empty (papered over missing pickup/supply).
- Dawn **reset of `_preamble_idx`** (kept route reset later; preamble stays once-per-season entry).

## Bugs / wrong assumptions found

1. **Hire identity from current tile**  
   Mapping hire via `SPAWN_TO_HIRE[pos]` every hour: any hand on `(4,4)` became hire1. Fixed with **slot→worker bind at first spawn sighting** (`_slot_to_worker`). Without this, hires looked dead (~15–20k).

2. **“Doc snake” ≠ season movement**  
   Doc only defines **entry** (W/N into column + pickup) + conceptual **4×N**. We oscillated:
   - free pathfind + shed detours → too much MOVE (~71k but not “strict”)
   - snake once then PASS → chart all gray PASS days 1–28 (~429)
   - daily lap: dawn `_route_idx=0`, walk south to bottom then north again (~27k)

3. **Wheat / FEED**  
   User rule: after shed pickup, hand wheat ≥ zone animal count; market must stock shed enough for all zones; pickup only at doc steps. FEED-with-no-wheat must not happen. Zone-sum buy + in-place PICKUP loops were added late; hires still **cannot** re-pickup wheat daily without visiting shed (no detour) — open hole if day-0 pickup doesn’t cover full season feed.

4. **Smoke theo dots for hires**  
   Dawn dry-run `forecast_day_counts` / `[theo]` only for **farmer**; hire `est_ops=0` → red dots on floor. Chart noise, not just strategy.

5. **Score vs capacity**  
   Even with daily laps + wheat fix, smoke ~**27k** vs earlier broken-but-busy ~**71k** or farmer-only prestart potential ~**60k**. Ops caps (green dash) not filled; hire/farmer still underworked relative to net_tile_ops.

## Final executor contract (before discard)

- h=0: workers PASS; market HIRE → wheat → animals → seeds.
- Day 0: literal PREAMBLE (pickup in place on owned shed only), then column.
- Days 1–28: reset **route only**; walk to `route[0]` then north; PASS after top of column until next dawn.
- Day 29: existing endgame free walk.
- No shed detour, no route wrap to skipped tiles.

## Likely takeaways if restarting

- Bind hire by **spawn once**, invent by **hand slot** — never re-infer from position.
- Decide **daily column policy** up front (reset lap vs wrap vs idle) and stick to it; don’t layer detours on top of a “strict snake” story.
- Wheat: either **day-0 carry enough for the season in hand**, or allow a **scripted** daily shed visit in the doc snake — not ad-hoc `_try_shed_detour`.
- Wire multi-worker theo dry-run before trusting capacity charts for hires.
- Keep `MILOS_FARMER` / `farmer.solve` as a sandbox; don’t blur it with oneland until movement is boring and correct.

## Discard scope

Safe to throw away the listed `milos/*` + smoke_analysis layout/parse edits relative to the last good commit. Keep this file (and `data/milos_zoning.md` as the product intent) if useful for the next design pass.
