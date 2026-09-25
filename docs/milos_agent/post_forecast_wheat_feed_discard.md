# Post-forecast wheat / animal-feed attempt — discard notes

Record of work **after** commit `085e7a7` (*Add daily price forecast plan and update pricing logic*). Intent: discard the working tree and re-land only the pieces that actually keep animals alive, without the failed detours.

Already **in** that commit (keep / do not discard as “unknown”):

- `milos/price_forecast.py` + planner replan wiring
- `_glut_unit_price` / `effective_price` removal from WSP weights
- related `mip.py` / `replan_lock.py` / `farmer.py` price_of signature changes

Everything below is the **uncommitted** follow-on (as of discard).

---

## Goal (what we tried)

Keep hire-zone animals (esp. hire4 t21 GOOSE) fed every day without mid-zone shed walks.

Secondary threads that came up in the same window:

1. Day-0 cascade cash handoff (`conservative` → `balance`) so hire zones are not INFEASIBLE under `FORCE_DAY0`.
2. Animal **BUILD** wrongly gated on carried wheat (empty tile never becomes COOP/PASTURE).
3. Hire ops-cap / animal selection (weight probe: animal ≫ crop but `NET_TILE_OPS` blocks).
4. Executor diagnostics (`OPS_TRACE`, `[theo_candidates]`).

---

## Files touched (uncommitted)

| Path | Role |
|------|------|
| `milos/market.py` | Dawn wheat buy: `total_zone_animal_wheat_consumers` + `hand_buffer`; sell reserve uses consumer count |
| `milos/script.py` | `total_zone_animal_wheat_consumers`, `total_wheat_in_private`; `total_wheat_feed_need` → consumer count (no longer sum of per-worker pickup shortfalls with wrong hire `inv_idx`) |
| `milos/tile_ops.py` | Drop BUILD wheat gate; FEED-first for live animals; block harvest-fallback while unfed |
| `milos/executor.py` | Shed-step pickup during preamble; zone-full wheat pickup; OPS_TRACE + theo skip reasons |
| `milos/flags.py` | `FORCE_DAY0`, `OPS_TRACE` |
| `milos/wsp/oneland.py` | Cascade: `opening = res["balance"]`, stop if `open0 < 0`; cascade logs; farmer shed_tax log; skip prestart when `FORCE_DAY0` |
| `milos/wsp/mip.py` | Return `buy_w` / `buy_f` spend when `track_shed` |
| `experiments/hire4_replan_weight_probe.py` | **New** — replan weight + ops bisect + ops digest |
| `experiments/hire4_*.txt` | Probe digests (disposable) |
| `experiments/smoke_analysis.ipynb` | Analysis notebook churn |
| `.cursor/logs.txt` | Scratch diagnosis notes |

Plans (Cursor, not submission): `animal_build_wheat_gate_*.plan.md`, `zone_wheat_carry_fix_*.plan.md`.

---

## Bugs found (keep these diagnoses)

### A. BUILD gated on wheat (`tile_ops._start_lifecycle`)

Empty tile + animal queue returned `None` when `inv["WHEAT"]==0`, so **BUILD never fired**. PLACE already has its own wheat check. Hire4 t24 sat `kind=None` for days.

**Fix that worked:** delete the animal wheat check before `build_action_for`. BUILD needs the animal unit in hand; wheat only for PLACE/FEED.

### B. FEED skipped → HARVEST (`tile_ops._animal_action`)

Age tape is `FEED, CARE, … HARVEST, COLLECT_FERTILIZER`. Code did:

```python
if act == "FEED" and inv WHEAT <= 0:
    continue  # then returned HARVEST
```

Day 8 smoke: hire4 `PICKUP WHEAT 1`, then **HARVEST** on live goose. Two missed FEEDs → escape. Chart: FEED days 2–7, hole 8–15, PLACE ~16.

**Contract:** unfed live animal must only FEED (or wait). Never fall through to HARVEST/COLLECT. Also stop harvest-fallback in `next_tile_action` while `tile_needs_feed`.

### C. Dawn wheat buy undercounted (`market` + `script`)

`total_wheat_feed_need` used `inventory_index(worker)` **without** `hand_slot`, so hire inventories were wrong and need looked smaller than real zone feed count. Multiple hands + farmer all draw shed wheat at h≈1–3; one wheat in shed is not enough for N animals / N hands.

**Direction that worked in last smoke:**

- Need = `sum(zone_animal_feed_count)` across workers (live + pending PLACE).
- Buy so **shed** has at least that (+ buffer for concurrent hand pickups).
- Do **not** sell the feed reserve.

### D. Pickup too small / too late (`executor`)

`wheat_pickup_needed = zone_count - inv` under-picked when inv was stale or contested. Preamble `PICKUP` step could advance after a failed/partial pickup; worker left `(4,4)` without zone wheat, then single-pass snake skipped t21.

**Direction that worked in last smoke:**

- On owned shed tile during preamble, run `_next_shed_pickup` before later moves.
- Pickup wheat amount = **full** `zone_animal_feed_count` (capped by shed), not “leftover after inv”.
- **No mid-day walk back to shed** (user constraint; also matches `oneland_failure.md`).

### E. Cascade handoff (`oneland.py`)

`opening = res["conservative"]` (setup spend only) made hire zones INFEASIBLE under live day-0. **`opening = res["balance"]`** + break if `open0 < 0` fixed FEASIBLE cascade. Farmer `track_shed` spends still cascade downstream — log `opening[0:5]` + farmer `buy_w/f` if cash-tight animals reappear.

### F. Ops cap vs 2nd animal (probe, not fixed)

`experiments/hire4_replan_weight_probe.py`: animal weight ≫ crop but hire `NET_TILE_OPS` (14–15) blocks; farmer 18 admits animals. Separate from feed bug. Optional later: raise hire ops or animal surcharge.

---

## Approaches that failed / rejected

| Approach | Why not |
|----------|---------|
| Mid-route shed detour when FEED blocked | User ban; burns hours; violates snake contract |
| End-of-snake `route_idx` reset / multi-lap | Papers over missing wheat; loops |
| `return None` forever on unfed without stocking wheat | Starves animal unless pickup+stock fixed |
| Counting hand wheat toward dawn **buy** deficit (then under-buying shed) | Hands draw from shed; shed must be full before pickups |
| Treating theo `no_wheat_blocks_place` as a separate route planner | Label only; live path is `WORKER_ROUTES` + skip on no-op |

---

## Validation that mattered

From last good smoke after stock + full-zone pickup + FEED-first:

- `d=8` / `d=9`: `hire4 FEED` on **t21**
- `d=10`: coop still **HARVESTABLE** (goose alive), not empty + queued replacement
- No hire4 walk-back to shed after leaving preamble

Env flags for digs: `KAGGRI_OPS_TRACE=1`, `KAGGRI_VERBOSE=1`, `KAGGRI_FORCE_DAY0=1` (day-0 live solve).

---

## Minimal re-land checklist (after discard)

Do **not** reintroduce detours. Land in this order:

1. **`tile_ops`:** remove BUILD wheat gate; FEED-only when unfed; no harvest-fallback while unfed.
2. **`script` + `market`:** consumer-count dawn buy; shed covers all zone feeds (+ concurrent-hand buffer); protect sell reserve.
3. **`executor`:** on `(4,4)` / owned shed during preamble, pick **full zone wheat** before leaving; keep PLACE wheat gate as-is.
4. **`oneland`:** cascade `balance` handoff (if still needed under FORCE_DAY0 / live day-0).
5. Smoke: hire4 t21 FEED on days that previously starved; goose alive through day 10+.
6. Defer: `NET_TILE_OPS` animal surcharge, theo/OPS_TRACE polish (nice-to-have).

---

## Related docs

- [`oneland_failure.md`](oneland_failure.md) — earlier OneLand movement failures (same “no shed detour” lesson).
- [`oneland_claude.md`](oneland_claude.md) — five-zone design notes.
- `.cursor/plans/daily_price_forecast_*.plan.md` — already committed forecast work.
- `.cursor/plans/zone_wheat_carry_fix_*.plan.md` — last feed plan (stock + NW pickup + tape).
