# Active Context

## Current focus (Aug 24, 2026)

**Planner opponent price factor is live** on dawn `replan` only (not day-0 `_build_from_solver`). Catalog `quoted` uses **live** `obs["market"]["prices"]` at replan; i0 only as missing-key fallback.

Live formula in `agent/planner.py` `effective_price`:

```python
opp_bonus = -opp_tiles / 10.0
price_factor = 1 + shop_demand + opp_bonus
return int(quoted * max(0.1, price_factor))
```

i.e. `quoted * max(0.1, 1 + shop_demand - opp_tiles/10)`. Count opponent `PLANT` crops and live animals (`product_for`). Day-0 solver catalog stays `i0 * (1 + demand)` with no opp counts.

**Feed-stay (hire3 sheep deaths) is live.** Do not treat `FEED`+empty wheat as “tile done.” Stay on unfed pasture; PLACE requires inv wheat; dawn buy wheat vs live+placing; no `SELL WHEAT` at hour 0–4.

Occasional **weeds from missed watering** still known — no snake detours. Sell 50% floor + premium sell DP still live.

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

Logs: `farmer t{idx+1}` — t1 = index 0 (shed door), t9 = index 8. Not a 0/1 mapping bug.

## Solver knobs (live)

Kaggle import timed out at ~61s (`260818_2`). Live planner: `num_workers=8`, import `max_time=20s`, replan `max_time=5s`, `OBJECTIVE_GOOD_ENOUGH=80_000` (callback often never fires; obj scale ~49k). Local smoke after IDLE+d0 skip: **~58k**.

Do not treat 80k/83620 as bank.

## Failures to remember

| Run | What happened |
| --- | --- |
| First fert pass | Animal-boolean sort + tile-0 exclude + 10s all solves → 5 sheep, early pasture, $9 cash. Notes: `docs/dp_master/fertilze_failure.md` |
| `260819_1` | 20s FEASIBLE + IDLE last + **d=0 replan** → extra sheep on t9, tight cash |
| After d0 skip + IDLE-middle | Cow t1, sheep t2; no t9 sheep from d0; smoke ~58k |
| `260820_2` / `260820_3` | Occasional weeds from missed watering; guardrail attempts (deferral, zone skip) hurt score or caused animal deaths — **reverted** |

## User prefs (this arc)

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
| `agent/planner.py` | Count CP-SAT; live `effective_price` + opp tile counts on `replan`; `NET_TILE_OPS` −1 vs old |
| `agent/tile_ops.py` | `tile_needs_feed`; PLACE needs wheat; WATER then FERT |
| `agent/executor.py` | Snake; skip replan day 0; **do not advance** off unfed pasture |
| `agent/market.py` | h=0 wheat vs live+placing; no WHEAT sell h<5; 50% floor sells |
| `agent/sell_dp.py` | Premium drip DP; wheat feed reserve |
| `agent/script.py` | Zone wheat pickup = live + placing today |

## Immediate next steps

- Watch whether additive opponent term (`-opp/10` inside `1+demand`, floor 0.1) is the intended catalog vs earlier multiply form
- Confirm hire3 `PLACE ≈ BUILD` and same-day `FEED` on next smoke / submission
- **Later:** minimal watering guardrails (no snake detours)
- Do not revive WSP
