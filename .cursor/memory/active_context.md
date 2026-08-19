# Active Context

## Current focus (Aug 19, 2026)

**Runtime fertilizer from animals is in**, after a failed first pass (`docs/dp_master/fertilze_failure.md`). Planner still stamps **`no_fert`** chain weights. Executor inserts FERTILIZE from collected bags. Sell drip is still the next **agent** lever vs I0 vs dump.

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
| `agent/planner.py` | Count CP-SAT; `_decode_sort_key`; 20s/5s; no d=0 replan |
| `agent/tile_ops.py` | WATER then FERT; BUILD gated on inv |
| `agent/market.py` | Buy animals while tile empty; sell all shed fert |
| `agent/script.py` | Pickup animals for empty due slots |
| `agent/executor.py` | Snake; skip replan day 0 |
| `docs/dp_master/fertilze_failure.md` | First-pass failure notes |
| `agent/market.py` | Dump sells — next **agent** work vs glut |

## Immediate next steps

- Sell / drip policy for premium goods (melon first)
- Optional: bake assignment JSON so Kaggle import skips CP-SAT
- Do not revive WSP
