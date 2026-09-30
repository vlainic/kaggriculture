---
name: Four-man ThreeLand layout
overview: Switch the live default to 4-man ThreeLand, load the $2000 wsp4 prestart for NW, buy NE on day 0, and on day 1 accept every NE zone whose wheat/carrot plan passes the value gate and fits remaining cash. SW uses the same staple catalog to activate, with dusk cash $3000 and overage 20s.
todos:
  - id: layout-12
    content: "Add MILOS_THREELAND12: FOUR coords, NE/SW mirrors, zones, doc+1 caps, NW preambles, in-place spawn map in bind()"
    status: completed
  - id: default-env
    content: Default KAGGRI_LAYOUT to threeland12; keep threeland15/18/twoland12 explicit
    status: completed
  - id: day0-prestart-ne
    content: 4-man day-0 loads milos/wsp/wsp4_prestart.json and sets BUY_LAND_DAY=0 (no live NW MIP, no all-zone buy replan)
    status: completed
  - id: ne-staple-probe
    content: Day 1 accepts every NE zone that passes staples + value gate + remaining cash. SW activations are staples-only too. SW_BUY_MIN_CASH=3000, SW_MIN_OVERAGE=20. Full catalog only overwrites empty unstarted tiles.
    status: completed
  - id: docs-status
    content: Mark 4-man live in data/milos_zoning.md and kaggriculture-stack.mdc
    status: completed
  - id: bind-check
    content: Import-check layout, prestart tile keys 0-24, and day-1 probe gate
    status: completed
isProject: false
---

# Switch live layout to 4-man ThreeLand

`# Mode: PLAN`

Live default becomes **4 workers per land** (farmer + 11 hires, 75 tiles). Market hire clock, wheat feed, sell DP, and the zone value gate stay. [agent/solvers/wsp4_prestart.json](agent/solvers/wsp4_prestart.json) was solved at **$2000**, so day 0 buys NE immediately. Day 1 fills every NE zone whose wheat/carrot plan clears the value gate and the remaining cash. SW activations use that same staple catalog. The SW dusk gate is cash ≥ $3000 and overage ≥ 20s.

`MILOS_THREELAND15` / `threeland18` / `twoland12` remain selectable and keep today’s live day-0 MIP and dusk NE buy. Unset `KAGGRI_LAYOUT` resolves to the new layout.

## Layout

New `MILOS_THREELAND12` in [milos/zoning.py](milos/zoning.py). Coords are legacy [`FOUR`](agent/zoning.py), then mirrors:

- NE: `(x, y) → (9 − x, y)`, tiles 26–50, workers `hire4`–`hire7` (`hire4` is the 5th zone)
- SW: `(x, y) → (x, 9 − y)`, tiles 51–75, workers `hire8`–`hire11`

Visit order is the in-zone snake. The executor already walks it with `_step_toward`.

- NW farmer / hire1 / hire2 / hire3: doc ops 14 / 12 / 12 / 10, live caps **15 / 13 / 13 / 11**, hired h=0 (`NUM_ACTIVE_HIRES` becomes 3)
- NE hire4–hire7: doc 13 / 11 / 11 / 9, live caps **14 / 12 / 12 / 10**, hired h=1
- SW hire8–hire11: hired h=2 (existing clock), live caps **13 / 11 / 11 / 9**

The +1 matches current 5-man code vs its doc (farmer 18 written, `net_tile_ops=19` in code) because [milos/wsp/mip.py](milos/wsp/mip.py) also counts one shed-pickup flag per day. SW stays on hour 2 ([milos/market.py](milos/market.py), `_sw_slot_base` at hour 2). Hiring SW at h=1 would stack 8 hires into the 10-order cap and mis-bind slots.

`SPAWN_TO_HIRE` is one dict that [milos/workers.py](milos/workers.py) aliases at import. `bind()` mutates it in place. 4-man map: `(5,4)→hire1`, `(4,5)→hire2`, `(5,5)→hire3`. 5-man layouts keep the current four-corner map. `TWOFOLD_HIRE` stays `None`.

NW preambles use milos `"PICKUP"`:

- hire1: `WEST, PICKUP, NORTH, NORTH, NORTH`
- hire2: `NORTH, PICKUP, WEST, WEST, WEST`
- hire3: `WEST, NORTH, PICKUP, WEST, WEST, WEST, NORTH, NORTH, NORTH` (the extra `NORTH` lands on owned `(4,4)` before the corner snake; a bare pickup after SW is owned would stay on `(4,5)`)

Farmer preamble stays empty. NE/SW preambles stay `("PICKUP",)`.

Default `_resolve_layout()` returns `MILOS_THREELAND12` (`milos_threeland12`). `KAGGRI_LAYOUT=threeland15` still selects 15.

## Day-0 prestart and buy NE at start

Copy [agent/solvers/wsp4_prestart.json](agent/solvers/wsp4_prestart.json) to `milos/wsp/wsp4_prestart.json` so `scripts/smoke_test.sh` ships it (`cp -a milos`). It assigns tiles **0–24** for `farmer, hire1, hire2, hire3`, `complete: true`. Those indices match FOUR visit order, not the 5-man columns. Do not load [milos/wsp/prestart.json](milos/wsp/prestart.json).

For this layout only, [milos/planner.py](milos/planner.py) `get_tile_queues` / `_build_from_solver`:

- Load that JSON into NW queues. Skip the live `build_day0` MIP, `_day0_plan_ok` (the melon/cow gate), and the hardcoded melon template.
- Set `BUY_LAND_DAY = 0` before the first market call.

Starting bank is $3000 and NE land is $1000, which is why the prestart was solved at $2000. Existing hour-0 logic already emits `BUY_LAND` when `day == BUY_LAND_DAY` and NE is locked, ahead of the three NW `HIRE`s. Do not lower `NE_BUY_FIRST_DAY` for other layouts. Dusk scheduling stays as a backup if the day-0 buy does not land.

Do not run [replan_after_buy](milos/planner.py) on day 0. It still requires `2 <= day` and would try every NE zone at once. Day-0 buy only unlocks the quadrant.

## Day 1 fills NE; staples until a zone is active

Today [milos/executor.py](milos/executor.py) calls `planner.replan` only for `day >= 2`, and `replan()` returns immediately when `day < 2`. Walk 2 (`_activate_next_ne`) turns on one NE zone per dawn, so four zones would not all be live before about day 4. Staple seed is about $10 a tile, so the cash can cover all four on the morning after the land buy.

For `milos_threeland12`:

- Call `replan` from **day 1**. On day 1, no walk 1 (NW prestart stays) and no walk 3.
- Day 1 walks `hire4` through `hire7` in order. Each zone gets its own wheat/carrot solve. Accept it when `obj − cost >= 0`, `busy_day0 >= 1`, and running cash still covers `cost`. Subtract that cost before the next zone. A reject does not block the later zones; a rejected zone stays pending.
- From day 2, walk 1 runs on zones already in `ACTIVE_NE` / `ACTIVE_SW`. Walk 2 retries one still-pending NE zone per dawn. Walk 3 stays one pending SW zone per dawn.
- `SW_MIN_OVERAGE` goes from **40 to 20**. `SW_BUY_MIN_CASH` goes from **4000 to 3000** on this layout only (land is $2000, a staple fill is about $250; 5-man keeps $4000). Dusk still requires NE full and bound, and the buy day stays in 8–18. `SW_OVERAGE_RESERVE` stays 12.

Catalog split in [milos/wsp/mip.py](milos/wsp/mip.py) `build_patterns` (optional label allowlist, threaded through `twoland.solve`):

- Any solve that is deciding whether to **turn a zone on** uses **WHEAT and CARROT only** (wheat `no_fert` + `with_fert`, carrot `no_fert`). That is the day-1 NE loop, later walk 2, walk 3, and the SW zones inside `replan_after_buy_sw`. No animals, no melon/tomato/strawberry.
- On accept, write those queues and hire that day (`NE_DUE_DAY` / `SW_DUE_DAY = day`).
- Once the zone is in `ACTIVE_NE` or `ACTIVE_SW`, later walk 1 uses the **full** catalog, same as NW.

The full-catalog overwrite is only for tiles that are still empty. [milos/replan_lock.py](milos/replan_lock.py) `replan_eligible` already returns false unless `_tile_empty_for_replan` (tile is `None` or `WEED`). Keep that check first. The extra case is only: empty, `queue_idx == 0`, queue present, zone was accepted from the staple probe, and nothing has been planted. A growing plant, coop, or pasture stays locked until harvest even if the queue item is not finished. Do not treat “planted but not harvested” as eligible. After the full-catalog write, the normal lock applies again.

`replan_after_buy` is not the NE activation path for this layout. The SW buy-morning replan stays, and its not-yet-active zones use the staple catalog.

## Docs and check

Status lines only:

- [data/milos_zoning.md](data/milos_zoning.md) header and footer
- live-layout bullets in [.cursor/rules/kaggriculture-stack.mdc](.cursor/rules/kaggriculture-stack.mdc) (4-man default, day-0 NE buy, day-1 NE fill, staple NE/SW probe, SW cash $3000, overage floor 20s)

Import-check with the env unset: 75 coords, workers `farmer,hire1..hire11`, caps and spawn map above, prestart keys 0–24 and solved workers `farmer..hire3`, `BUY_LAND_DAY` starts at 0. `KAGGRI_LAYOUT=threeland15` still binds 15 workers and does not force a day-0 land buy. No Kaggle submit. A full episode only if you ask for one.
