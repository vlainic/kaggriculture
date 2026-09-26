# Active Context

## Current focus (Sep 26, 2026)

**Live submission = `milos/` OneLand 6-man** — `main.py` → `milos.executor.step`. Layout: **`MILOS_ONELAND6`** (`CURRENT` in `milos/zoning.py`): 25 tiles, farmer + **5 hires** (hire5 = north row / zone VI). Spec in [`data/milos_zoning.md`](../../data/milos_zoning.md). Ops caps (live): **19/16/16/17/17/14**. Hire fib sum = **12**/day. `NUM_ACTIVE_HIRES = NUM_HIRES` (5).

`agent/` TwoLand WSP remains legacy. Smoke builds `milos/` into the tarball.

### Critical engine rules

1. **Shed-adjacent ONLY IF OWNED** — PICKUP/DROP no-op on `LOCKED`. Gate via `_owned_shed_tiles`.
2. **Shed capacity 100** — env silently rejects `BUY_PRODUCT` / `BUY_ANIMAL` when `sum(shed) >= 100`. 6-man collects more fertilizer; floor-blocked FERT sells filled the shed and starved dawn wheat buys (days ~25–27). Fix: aggressive FERT dump + dawn make-room sells.

### Status

| Item | State |
| --- | --- |
| Live agent | **`milos/`** `MILOS_ONELAND6` (farmer + hire1–5) |
| Hire5 bind | `TWOFOLD_HIRE="hire5"` — 5th hand reuses spawn corner; `_claim_worker` on duplicate |
| Day-0 queues | Load `prestart.json` (5-man chains by tile idx); write via **`result.assigned`** (not `solved_workers`×`WORKER_TILES`) |
| Dawn replan write | **`apply_replan`** iterates `replan_set` / `assigned` the same way |
| Market dawn | HIRE×5 + room sells + **wheat → animals → seeds**; then sells |
| **Wheat buy** | `total_wheat_feed_need` = raw animal feed sum + **one** global `(zones+1)//2` buffer |
| **Wheat PICKUP** | `wheat_pickup_needed` = **raw zone need − inv only** (no per-zone buffer — kills FCFS race) |
| **Fert dump** | `FERT_SHED_CAP=10`; every market hour dump excess first (ignore price floor); reserve = `max(10, fert pickup need)` |
| Shed diagnostic | `[snap] … shed_total=N` |
| Smoke (post-shed fix) | ~**130k** vs random; FEED every day 1–28; h=1 WHEAT≈24 FERT≈10 |
| Agents submit | Never without explicit ask |

### Sep 26 — 6-man + shed-cap (KEEP)

**Layout:** `MILOS_ONELAND6` reuses 5-man tile indices; zone VI = tiles 9/14/19/24 (`t10,t15,t20,t25`). hire5 preamble `("PICKUP",)`; `_step_to_owned_shed` covers NE spawn.

**Bug chain (fixed in order):**
1. **Missing hire5 queues** — `_build_from_solver` / `apply_replan` looped `solved_workers` × new `WORKER_TILES` → north-row tiles never queued. Fix: iterate `result.assigned` / `replan_set`.
2. **Wheat FCFS race** — per-zone buffer in `wheat_pickup_needed` × 6 zones over-claimed shed; hire4 last in preamble starved. Fix: buffer only in `total_wheat_feed_need`; pickup = raw need.
3. **Uniform zero FEED days 25–27** — not wheat math; shed full of floor-blocked **FERTILIZER** → silent buy reject → 0 wheat for everyone. Fix A: hourly fert dump to cap 10. Fix B: dawn `_make_room_sells` before buys.

**Do not:** put buffer back into per-zone pickup; trust logged `BUY_PRODUCT WHEAT` without checking `shed_total`; let FERT pile past ~10 under price floor.

### Sep 25 — wheat padding (SUPERSEDED shape)

Original zone-buffer-in-`wheat_pickup_needed` caused 6-man races. **Current:** global buffer on buy only; pickup is raw. Intent (margin vs exact need) remains via `total_wheat_feed_need`.

### Sep 23 — hire4 CARE / theo / replan (KEEP)

CARE requires `fed_today`; dawn replan + full-stack HARVEST sim; see prior notes in git history / progress.md.

### Anti-patterns (still)

- Mid-day BUY wheat/animal/seed
- **Per-zone wheat buffer** in `wheat_pickup_needed` (6-man FCFS race)
- Ignoring **shed_total ≥ 100** when diagnosing “no FEED”
- Letting FERT sell only via price floor (fills shed on 6-man)
- Freezing routes waiting for wheat/PLACE
- Offering CARE without `fed_today`
- Agents submitting without explicit ask
- Building day-0 queues via `WORKER_TILES[solved_worker]` when layout ≠ prestart worker map

### Immediate next steps

1. Optional: regenerate `milos/wsp/prestart.json` under 6-man caps/zones (still reusing 5-man prestart by tile idx)
2. Keep theo/act + shed_total monitoring after market/executor changes
3. TwoLand `agent/` only if user re-points `main.py`
