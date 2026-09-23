---
name: Five-zone hire cascade
overview: Add farmer + 4 hires using milos_zoning.md hire numbers and scripted snakes. Day-0 loads full prestart; dawn replan from day=2 is sequential zonewise. Last day only uses free movement (harvest then DROP).
todos:
  - id: layout
    content: "MILOS_FIVE in zoning.py: doc hire1–4 (V/IV/III/II), FIVE tile indices (prestart 0–24), ops 18/14/14/15/15, scripted preambles"
    status: completed
  - id: plan-replan
    content: Day-0 load full prestart; solve() cascades leftover zones; extend farmer replan (first d=2) to per-worker lock + sequential WSP
    status: pending
  - id: exec-snakes
    content: Play scripted snakes d=0–28; bind each hand to hire1–4 by spawn tile (NW/NE/SW/SE); last day endgame only; market HIRE x4 first
    status: pending
isProject: false
---

# Five-zone hire cascade

`# Mode: PLAN`

Farmer + **4 hires** per [data/milos_zoning.md](data/milos_zoning.md). Stay in `milos/`. Do not touch `agent/`. No tests.

## Hire numbers (doc, not env)

`hire1`–`hire4` are the **doc labels**, not `me["hands"][i]`.

- Farmer @ zone I, tiles 0–4 `(4,y)`, ops **18**
- Hire 1 @ **NW** → zone **V**, tiles 5–9 `(0,y)`, ops **14** — snake: pickup, 4xW, 4xN
- Hire 2 @ **NE** → zone **IV**, tiles 10–14 `(1,y)`, ops **14** — snake: 1xW, pickup, 3xW, 4xN
- Hire 3 @ **SW** → zone **III**, tiles 15–19 `(2,y)`, ops **15** — snake: 1xN, pickup, 2xW, 4xN
- Hire 4 @ **SE** → zone **II**, tiles 20–24 `(3,y)`, ops **15** — snake: 1xW, 1xN, pickup, 1xW, 4xN

Tile indices stay **FIVE / prestart** (farmer 0–4, west column 5–9, …) so [milos/wsp/prestart.json](milos/wsp/prestart.json) keys 0–24 apply as-is.

**Bind by spawn tile, never by `hands[i]`.** Each hour (or at first sighting that day), map `me["hands"][i]` position → hire label:

- `(4,4)` NW → hire1 / zone V
- `(5,4)` NE → hire2 / zone IV
- `(4,5)` SW → hire3 / zone III
- `(5,5)` SE → hire4 / zone II

Farmer also sits on NW; a second unit on `(4,4)` is hire1. Inventory follows the env slot that currently occupies that tile. Log if a hand is not on a spawn corner (do not silently run another zone’s snake). No static `hands[0]→hire2` table.

## Day-0 plan

Load **full** prestart (all 25 tiles, all five workers). No live day-0 MIP if JSON matches. [milos/planner.py](milos/planner.py) `NUM_ACTIVE_HIRES = 4`; `build_day0` / boards cover all tiles.

If a zone is missing from prestart, [milos/wsp/farmer.py](milos/wsp/farmer.py) `solve()` cascades `WORKERS` (farmer → hire1–4) via [milos/wsp/mip.py](milos/wsp/mip.py) `solve_zone` + conservative cash handoff (same loop as [agent/solvers/zonewise_wsp.py](agent/solvers/zonewise_wsp.py)). Subtract `HAND_DAILY_COST` on hire zones. INFEASIBLE: skip that zone, keep queues, continue.

## Dawn replan (already exists for farmer)

Farmer replan in [milos/planner.py](milos/planner.py) + [milos/replan_lock.py](milos/replan_lock.py) stays the path. Changes only:

- First run at **day=2** (`if day < 2: return`; still skip last day)
- `locked_by_worker` keyed by all `WORKERS`, not `{FARMER: ...}`
- Sequential per-zone solve on that zone’s eligible empties; `track_shed=False` (WSP, same as current farmer replan)
- INFEASIBLE: skip zone, keep its queues, continue cascade

## Scripted snakes (d=0–28)

No mid-season `_step_toward` / nearest-tile. h=0 all PASS. Then play `PREAMBLE` (pickup only on owned `(4,4)`), then 4xN along `WORKER_ROUTES`. Tile ops only when standing on the current route tile.

Last day (`SEASON_LAST_DAY`): existing `_endgame_action` only — harvest ASAP, walk to owned shed, DROP. No snake.

## Market

h=0: `["HIRE"]` ×4 first, then wheat → animals → seeds. No batch split.

## Out of scope

DEAD_HANDS, TWO/ThreeLand, `agent/` edits, tests/smoke/submit.
