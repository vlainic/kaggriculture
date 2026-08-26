# Active Context

## Current focus (Aug 26, 2026)

**Layout catalog is live** in `agent/zoning.py`. Zones are no longer hardcoded only in `script`/`planner`.

```python
FOUR = Layout(...)   # classic 3-hand snake (9/6/6/4 tiles)
FIVE = Layout(...)   # column split, 4 hands (5×5 columns)
CURRENT = FIVE       # flip to FOUR to restore
bind(CURRENT)        # fills WORKERS, TILES, PREAMBLE, NET_TILE_OPS, HIRE_DAILY_COST, …
```

- **Python Layouts, not JSON** — preambles + ASCII maps stay in code; JSON would duplicate the same objects.
- Planner/executor/workers already consume derived tables — no zone-count MIP changes for a new layout.
- Market: h=0 and h=1 each hire `min(2, NUM_HIRES − len(hands))` → FOUR = 2+1, FIVE = 2+2. Reserve uses `zoning.HIRE_DAILY_COST` (fib: 4 for THREE hands, 7 for FOUR).
- Handmade fallback queues in `script.py` only when `CURRENT is FOUR`; otherwise empty `{idx: []}`. Live queues still from planner.

**Still live from prior arc:** dawn replan opponent price factor; feed-stay; fert after WATER; no d=0 replan; sell 50% floor + premium DP.

## FIVE geometry (active)

Doc: `data/five_zone_plan.md`. Tile 1 = shed `(4,4)`. Columns south→north (`4xN`):

| Zone | tiles (0-based) | ops | start_hour | preamble |
| --- | --- | --- | --- | --- |
| farmer | 0–4 | 18 | 0 | empty |
| hire1 | 5–9 | 13 | 1 | W, pickups, 4×W |
| hire2 | 10–14 | 14 | 1 | N, pickups, 3×W |
| hire3 | 15–19 | 14 | 2 | W, pickups, 2×W |
| hire4 | 20–24 | 15 | 2 | N, pickups, 1×W |

## Known issue: weeds from unwatering

Sometimes crops turn to weeds because the snake route runs out of hours before tail tiles get WATER. Root causes explored:

- `lag` / `gap` in tile state can block normal watering on some tiles
- Route capacity: farmer may finish zone before every tile is visited same day
- At-risk = `consecutive_unwatered >= 1` and not `watered_today`; weed at 2 missed days

**Do not repeat without user ask:**

- Route reorder / detour (`care_first_route`) — user rejected
- Aggressive action deferral (skip CARE, FERTILIZE zone-wide) — made things worse (~35k selfplay, sheep deaths in 260820_3)
- Zone-wide COLLECT_FERTILIZER skip — leaves workers idle on at-risk tiles

**If revisited later:** keep normal snake queue; skip only non-essential actions (primarily COLLECT_FERTILIZER) on **non-at-risk** tiles when zone has at-risk tiles; never skip HARVEST; urgent WATER/FEED may bypass lag/gap.

## What fertilizer actually does now

Planner stays `no_fert`. Animals sit on **route-first** tiles so collect happens early on the snake.

**Collect:** animal rollout tape already has `COLLECT_FERTILIZER` (age 1+). Always collect when `fertilizer_available`. **No shed `PICKUP FERTILIZER`.** Market already sells **all** shed fert.

**Apply:** in `_crop_action`, after WATER on that tile, if inv has FERTILIZER and zone has a placed animal and crop is on a `with_fert` age → `FERTILIZE`, then remaining tape (HARVEST). Tomato age 10 = WATER → FERTILIZE → HARVEST same day. MELON excluded. Do **not** steal PASS hours for a fert hunt.

**Ages (`with_fert`):** WHEAT/CARROT 2; TOMATO 7+10; STRAWBERRY 9+13.

**Same-day pasture:** BUILD only if the animal is already in that worker’s inventory. Market buys + shed pickup while the tile is still empty. Sequence: BUY → PICKUP → BUILD → PLACE.

## Decode + replan (IDLE trap)

CP-SAT assigns **counts**, including IDLE (`[]`). A leftover IDLE tile used to land last (farmer **t9**). Day-0 replan treated empty queue as “exhausted” and stuffed a sheep there (`260819_1`, `replan d=0 assign=1`).

**Now:**

- Decode sort: animals by earliest `start_day` over the **full chain** → **IDLE** → crop-only.
- **No replan on day 0** (`executor` + `planner.replan` early return). First fill is d=1+ when a queue is actually done (or IDLE sits until then).

Logs: `farmer t{idx+1}` — t1 = index 0 (shed door). Zone size depends on `CURRENT` (FOUR farmer t9 = index 8; FIVE farmer t5 = index 4).

## Solver knobs (live)

Kaggle import timed out at ~61s (`260818_2`). Live planner: `num_workers=8`, import `max_time=20s`, replan `max_time=5s`, `OBJECTIVE_GOOD_ENOUGH=80_000` (callback often never fires; obj scale ~49k). Local smoke after IDLE+d0 skip: **~58k** (FOUR era).

Do not treat 80k/83620 as bank. FIVE hire cash is **$7/day** (`1+1+2+3`), not $4.

## Failures to remember

| Run | What happened |
| --- | --- |
| First fert pass | Animal-boolean sort + tile-0 exclude + 10s all solves → 5 sheep, early pasture, $9 cash. Notes: `docs/dp_master/fertilze_failure.md` |
| `260819_1` | 20s FEASIBLE + IDLE last + **d=0 replan** → extra sheep on t9, tight cash |
| After d0 skip + IDLE-middle | Cow t1, sheep t2; no t9 sheep from d0; smoke ~58k |
| `260820_2` / `260820_3` | Occasional weeds from missed watering; guardrail attempts (deferral, zone skip) hurt score or caused animal deaths — **reverted** |

## User prefs (this arc)

- Layouts as Python `Layout` catalog — keep FOUR when adding FIVE; switch via `CURRENT`
- Fert from animals only; sell shed fert
- Animals on first tiles per zone; IDLE between animals and crops
- BUILD on PLACE day
- WATER then FERTILIZE (tomato also HARVEST)
- No d=0 replan
- Agents never Kaggle-submit without explicit ask
- Do not commit `.cursor/`

## Key files

| File | Role |
| --- | --- |
| `agent/zoning.py` | `FOUR` / `FIVE` / `CURRENT` + `bind()` — sole zone source of truth |
| `agent/planner.py` | Count CP-SAT; imports zones from `zoning` |
| `agent/workers.py` | Re-exports zoning tables |
| `agent/script.py` | Queues + helpers; FOUR-only handmade fallback |
| `agent/market.py` | 2+2 hire pattern; `HIRE_COST = HIRE_DAILY_COST` |
| `agent/tile_ops.py` | `tile_needs_feed`; PLACE needs wheat; WATER then FERT |
| `agent/executor.py` | Snake; skip replan day 0; **do not advance** off unfed pasture |
| `data/five_zone_plan.md` | FIVE design note |
| `data/two_lands.md` | Draft two-land / spawn notes — **not wired yet** |

## Immediate next steps

- Smoke / validate FIVE layout (ops caps, hire timing, empty fallback)
- Watch whether additive opponent term is the intended catalog vs earlier multiply form
- **Later:** watering guardrails (no snake detours); two-land from `data/two_lands.md`
- Do not revive WSP
