---
name: V55 opener tape
overview: Play V55 route 0 exactly through the end of day 5, then hand the live board to the existing solver. Occupied tiles stay committed and get care; the solver only fills empty tiles.
todos:
  - id: extract-tape
    content: One-shot import of opponents/v55 routes[0][0:144] (day 5 hour 23 inclusive) into milos/v55_opener_d0_d5.json
    status: completed
  - id: playback
    content: executor.step returns the tape for step<144, logs tile/ops mismatches, skips planner; KAGGRI_V55_OPENER default on
    status: completed
  - id: adopt-board
    content: At day 6, replace TILE_QUEUES from the live farm, reset tile state, then normal replan on empty tiles
    status: completed
isProject: false
---

# V55 opener through day 5

Experiment from [.cursor/logs.txt](.cursor/logs.txt): early commitment is the gap. Copy the shared opener only. Shop routes split at step 144, so days 6–11 are not scripted. Judge later smoke on our reward against the current ~73–100k band, not the margin. No Kaggle submit.

Source: `opponents/v55/main.py` `_IMPL.chassis.routes[0]`. That file already runs `base64.b85decode` + `zlib.decompress` on import, so a one-shot import is the decode. Do not reimplement the notebook decoder. `_R110_OLD_SHOPS` is the shop-pair → route-id table (those pairs select route 0); it is not the action list. Route 0 matches the shop routes through index 143 (route 3 first differs at index 144).

Day boundary: index = `day * 24 + hour`. Index 143 is day 5, hour 23. Index 144 is day 6, hour 0, the first solver step. Dump `routes[0][0:144]` (144 actions, indices 0 through 143).

Days 0–5 of that tape: 12 melon seeds on day 0, 2 cows + 2 sheep on day 0, more cows on days 2–3, wheat seed/product for feed, 4 strawberry seeds on day 5, no `BUY_LAND`.

## Playback

Write that slice to [milos/v55_opener_d0_d5.json](milos/v55_opener_d0_d5.json) (ships inside `milos/`). Do not import V55 at runtime.

In [milos/executor.py](milos/executor.py) `step`, when `obs["step"] < 144`, return that action unchanged and skip planner, market, and bind. Hand counts in the tape vary by hour (0 then 3–5); they match the tape’s own `HIRE`s.

V55 has no runtime zones. Its offline tuner placed plants anywhere, so a verbatim replay can no-op on `threeland12`: `PLANT` / `BUILD_*` on a tile outside the acting worker’s `WORKER_TILES`, on `LOCKED`, or past that zone’s `NET_TILE_OPS`. Before returning each taped action, log `[opener] mismatch step= d= h= who= verb= tile=` when the farmer or hand target is not a tile that worker owns, or when the verb is a tile-op and that zone is already at its ops cap. Still return the tape action. The env is the judge; the log is what shows a day-6 board that is missing buys from the tape.

Gate with `KAGGRI_V55_OPENER` default **on** for threeland12 so `=0` restores the wsp4 day-0 path. One boolean. The JSON is read only when the flag is on.

If smoke shows those mismatches dropping the day-0 melons or animals, stop and hardcode the same buys onto `threeland12` zones (12 melons, 2 cows + 2 sheep on day 0, cows on days 2–3, strawberries on day 5) instead of replaying V55 tiles. That is a follow-up, not this pass.

## Day-6 adopt, then solver

First step with `step >= 144` (day 6, hour 0), before `_on_new_day` / `replan`:

- Write [milos/script.py](milos/script.py) `TILE_QUEUES` from the live farm. Occupied `PLANT` gets one `QueueItem` for that crop (`no_fert`, or `with_fert` if the tile is fertilized). `PASTURE` / `COOP` gets that animal at `with_care`. Empty and `WEED` tiles get `[]`.
- Reset executor tile state: `queue_idx=0`, `active` only on occupied tiles, lag/gap 0.
- Then the normal day-6 path runs. [milos/tile_ops.py](milos/tile_ops.py) `_crop_action` / `_animal_action` already water, feed, care, and harvest from age when the queue item matches the tile, and they do not re-`PLANT` / re-`PLACE`.
- Empty tiles are replan-eligible only with an empty queue (`replan_eligible` refuses a nonempty unstarted queue). Clearing them lets `_replan_active` fill NW. Occupied tiles stay locked.

Do not keep `BUY_LAND_DAY = 0` from [_build_threeland12_day0](milos/planner.py). Day-6 `dawn_ne_bound_handoff` already clears a missed day-0 buy when NE is unowned. Later NE/SW dusk triggers stay as they are.

Log `[opener] adopt d=6 plants= animals= empty=`.

## Check

Local smoke only. Through day 5 the market log should show the tape (12 `MELON` day 0, cows/sheep, no day-0 `BUY_LAND`). Grep `[opener] mismatch` before trusting the day-6 adopt counts. Day 6 should log adopt, then care on those tiles rather than a fresh wsp4 plant. No submit.
