# Road to Two-Land Scaling — Chronology & Post-Mortem

**Status:** Zone-wise / TwoLand experiments from this arc are **discarded**.  
**Proven baseline to restore:** monolithic OneLand FIVE + dawn replan with `track_shed=False` → local smoke peak ~**98k**, typical ~**60–64k**.  
**Date arc:** 2026-08-26 (and related TwoLand attempts same day).  
**Chat transcript:** `9dd84cf7-234f-481c-a508-8e36c2f66920`.

This document records what was tried, what broke, what the notebook proved, and why the zone-wise rewrite never matched live OneLand scores — so the next attempt does not re-learn the same lessons from scratch.

Related docs (still useful):

- [`docs/two_land_approach.md`](two_land_approach.md) — why monolithic 50-tile replans go INFEASIBLE
- [`data/two_lands.md`](../data/two_lands.md) — target zone geometry / ops / hire batches for lands I–X
- [`experiments/OneL-Zonewise-CPSAT-Handmade-Catalog.ipynb`](../experiments/OneL-Zonewise-CPSAT-Handmade-Catalog.ipynb) — zone-wise MIP proof (~60–97k obj)

---

## 1. Starting point (what “good” meant)

Before TwoLand / zone-wise work, the live agent was:

| Knob | Day-0 | Dawn replan |
|------|-------|-------------|
| Model | Monolithic CP-SAT over 25 tiles / 5 workers | Same shape, empties only |
| `track_shed` | `True` (W/F ledger + hire cash) | **`False`** (ops + cash ≥ 0 only) |
| Layout | `CURRENT = FIVE` | same |
| Catalog | `dp_catalog` | live prices × demand / opp |

Smoke scoreboard from memory (`active_context.md`):

| Config | Reward | Notes |
|--------|--------|-------|
| FIVE + empty replan + IDLE wipe | ~37k | Destroyed day-0 suffixes |
| FIVE + preserve + shed **on** replan | ~51k | Replan never assigned (INFEASIBLE) |
| FIVE + `track_shed=False` | **~98.8k** peak | Replan assigns; do not bank peak |
| FIVE typical after switch | **~63–64k** | |
| FOUR same replan | ~71–74k | |

**Critical ablation (do not forget):** putting the W/F shed ledger back into dawn replan caused mass INFEASIBLE in ~0.001s. `track_shed=False` on replan was a *fix*, not unfinished glue.

Clean committed HEAD (end of this arc, A/B): **reward ≈ 98,599** vs `random`.

---

## 2. Motivation — why leave OneLand / monolithic

### Product goal

Buy a second land (NE, $1000) and staff zones VI–X so total bank beats one-land.

### Why “just add tiles to the same CP-SAT” failed

Documented in `docs/two_land_approach.md`:

1. **One over-budget zone kills all 50 tiles.** Monolithic replan ANDs 10 hard daily ops caps. Locked (already planted) work alone can exceed a zone’s cap by 1–3 ops; the solver cannot change locked work; the whole replan returns INFEASIBLE and preserves stale queues for the rest of the season.
2. **Late buy underperforms.** Mid-season Land2 gets short horizon + thin cash → smokes ~64–89k, not “2× one-land.”
3. **Hire burn.** Nine hands ≈ $88/day fib hire cost; land that cannot be scheduled is dead weight.

Seed comparison (from that doc):

| Seed | FIVE (25) | TWO (50) | TWO infeasible dawns |
|------|-----------|----------|----------------------|
| 11 | 83,262 | 66,300 | 17 |
| 22 | 75,155 | 72,123 | 18 |

### User pivot (~afternoon)

> Current OneLand approach is not scalable for 2+ lands.

Target architecture: **zone-wise sequential CP-SAT** — one small model per 5-tile zone, cash (and later W/F) cascaded zone→zone, broke zones skipped so they never hire. Then Land2 zones VI–X can be appended when cash allows without one global AND of 10 caps.

---

## 3. Early TwoLand attempts (pre zone-wise)

All of these were explored and later discarded with the arc:

| Approach | Idea | Approx smoke |
|----------|------|--------------|
| Dynamic expansion | FIVE → buy land mid-season → `bind(TWO)` | ~70k (wheat fallback) |
| Fix buy = NE once | One `BUY_LAND`, land2-only replan retry | ~89k |
| Dual 25-tile | Two independent solves, split cash | ~64k |
| Day-0 TWO + mirrors | Buy NE day-0; parallel ledgers | ~80k |
| Pickups ops fix | Load `animal_with_pickups.json`; stop double-counting pickups into ops cap | ~63–85k |
| OneLand + $6k threshold | Buy NE late when cash ≥ $6k | ~63–69k |

**Ops double-counting (v1 → v2 diagnosis):** Cap summed `daily_tile_ops + wheat_pickup + animal_place + fert_pickup` while JSON already listed those actions inside `daily_tile_ops`. After pickups-inclusive rollouts + single-term ops, many “overflows” disappeared; remaining INFEASIBLEs were honest over-cap.

Extra bugs fixed then thrown away with TwoLand code: bought NE+SW+SE; Land2 bound to SE while tiles lived at NE; hire batches not intermixed per `two_lands.md`.

---

## 4. Zone-wise architecture (what was built)

### Core planner (`agent/planner.py`)

Replaced monolithic `_solve_assignment` (all workers × all tiles in one model) with:

```
_build_from_solver / replan
        │
        ▼
_solve_zones_sequential   # farmer → hire1 → hire2 → hire3 → hire4
        │
        ▼
_solve_zone(worker)       # CP-SAT over that zone's ~5 empty tiles
        │
        ├── count[chain] vars, sum == #empties
        ├── daily ops ≤ NET_TILE_OPS[worker] (+ locked load)
        ├── optional W/F shed ledger (track_shed)
        ├── cash ≥ 0 with opening balances from prior zone
        └── hire fee HAND_DAILY_COST[worker] when charge_hire_daily
```

Globals for execution:

- `NUM_ACTIVE_HIRES` — how many hands market should hire
- `ACTIVE_ZONES` — must stay a **contiguous prefix** of `WORKERS` (see hire routing)

### Zoning (`agent/zoning.py`)

- **FIVE** ops / preambles realigned to LandOne in `data/two_lands.md`: ops **18 / 17 / 16 / 14 / 13**, N×W snakes (old FIVE was **18 / 13 / 14 / 14 / 15** — layout + solver changed together, muddying ablations).
- **TEN** stub for zones I–X (Land2) — defined, **never bound**.
- `HAND_DAILY_COST` via fib terms: hire1=$1, hire2=$1, hire3=$2, hire4=$3 (farmer $0). Old bug charged full `$7/day` inside *every* zone including farmer.

### Market (`agent/market.py`)

- `_target_hires()` → `planner.NUM_ACTIVE_HIRES` (not hard-coded 4).
- Hire batching from `two_lands.md` (e.g. 3 → 2@h0 + 1@h1; 4 → 2+2; 5 → 2+3).

### Hands are positional

`workers.worker_for_hand_idx(i)` maps slot `i` → fixed `HAND_WORKERS[i]`. If the cascade reports `active=farmer,hire1,hire3` (skip hire2), physical hand2 still walks hire2’s tiles while the plan assumed hire3 — silent disaster. Hence **INFEASIBLE must `break`, not `continue`**, so `ACTIVE_ZONES == WORKERS[:k]`.

### Data / catalogs

| Artifact | Role |
|----------|------|
| `data/animal_with_pickups.json` | Agent animal tapes including PICKUP/PLACE/FEED in action lists |
| `data/animal_rollouts.json` | Tile-only tapes kept for notebooks |
| `data/handmade_dp_candidates.json` | 108 handmade chains — notebook menu; eventually used for agent day-0/replan via `_handmade_catalog(horizon)` |
| `agent/dp_catalog.py` | Procedural catalog; experiment set `LAGS = (0,)` → ~25 columns (thin MIP) |

### Notebook proof

`experiments/OneL-Zonewise-CPSAT-Handmade-Catalog.ipynb`:

- Same zone cascade as agent `_solve_zone` / sequential
- Handmade 108 chains, I0 prices
- With glut caps: MIP obj sum ~**60k**
- Glut commented out: ~**91–97k**
- Proves: **decomposition math can match / beat monolithic FOUR/FIVE paper objectives**
- Does **not** prove live Kaggle reward (no executor, no dawn replan, no market glut realization)

---

## 5. Bugs found during zone-wise (ordered by damage)

| # | Bug | Symptom | Fix attempted |
|---|-----|---------|---------------|
| 1 | Hire cost charged per zone (incl. farmer) | Cash cascade crushed (`~$1848→81→14`) | Per-hand `HAND_DAILY_COST`; farmer pays 0 |
| 2 | W/F opened at 0 every zone; cash handoff wrong | Feed/cash incoherent across cascade | Carry `w_levels[1]` / `f_levels[1]` + closing balance vectors |
| 3 | INFEASIBLE used `continue` | Holes in `ACTIVE_ZONES` vs positional hands | Change to **`break`** |
| 4 | `allow_zone_skip` unused / asymmetric | Dead parameter; replan all-or-nothing unclear | Wire True→break, False→raise (preserve queues) |
| 5 | Replan wrote IDLE / empty chains | Wiped remaining day-0 work (`t15:IDLE`, …) | Skip applying empty/IDLE when writing queues |
| 6 | Day-0 used thin `dp_catalog` lag-0 | Day-0 MIP ~38k vs notebook ~87k | Switch to `_handmade_catalog` (108 chains) |
| 7 | Replan `track_shed=True` (mis-aimed “glue” plan) | Farmer INFEASIBLE many dawns; score **~575–2.8k** | Restore `track_shed=False` on replan |
| 8 | `has_work` hire gating | Fee only if non-IDLE planted | Added then removed with shed-off restore |
| 9 | Live shed W/F into replan cascade | Needed only if shed-on | Added then removed |
| 10 | Empty cascade set `NUM_ACTIVE_HIRES=0` | Mid-season fire all hands | Brief `prev_hires` sticky; removed on restore |

First zone-wise ship after refactor: live **~31k**. Cascade bugfixes did **not** recover to 60k+; they mostly stopped the model from being nonsense while replan still destroyed execution.

---

## 6. Score history (honest timeline)

| Phase | Metric | Number |
|-------|--------|--------|
| Monolithic FIVE (memory / HEAD) | Live smoke | Peak **~98.8k**; typical **~63–64k**; clean HEAD **~98.6k** |
| TWO late-buy / dual / day-0 | Live | **~64 / 70 / 80 / 89k** |
| Zone-wise first ship | Live | **~31,284** |
| After cascade hire/cash fixes | Live | **~30,820** |
| After skip-logic relax | Live | **~29,774** |
| Contiguous + lag0 + pickups | Live | **~24,491** (day-0 obj sum ~38k) |
| Handmade catalog day-0 | MIP obj sum | **~87k** (notebook-like) |
| Same handmade run | **Live reward** | **~14,210** |
| Replan `track_shed=True` (broken) | Live | **~575** mid-bug; then **~13.7k / ~2.8k** |
| Restore `track_shed=False` zone-wise | Live | **~2–9k** (e.g. 8712) |
| Notebook FIVE zone-wise + glut | MIP | ~**60–61k** |
| Notebook FIVE no glut | MIP | ~**91–97k** |

### The hard lesson

**MIP objective ≠ Kaggle reward.**

Handmade day-0 hitting ~87k paper obj proved the *assignment menu and zone math* could look like the notebook. Live ~14k (and later worse) proved **dawn replan + executor + market** still ate the plan. Treating “replan uses a different model” as a bug to “fix” with `track_shed=True` made live *worse*, because that ablation was already known for monolithic.

---

## 7. Notebook vs agent — gap analysis

| Factor | Notebook | Agent (zone-wise) |
|--------|----------|-------------------|
| Catalog | Handmade 108 | Often lag-0 DP (~25) until switched; then handmade |
| Solve quality | OPTIMAL / zone | `_GoodEnoughCallback` ~16k/zone → early FEASIBLE, cash-hungry |
| Glut | Caps in MIP or off for A/B | Real market glut |
| Animals | Often tile-only | `animal_with_pickups` → denser ops |
| Replan | **None** | Every dawn: lock + reassign empties |
| Replan shed | N/A | Must stay **off** or mass INFEASIBLE |
| Execution | N/A | Snake hours, hire timing, sells, feed |

After handmade day-0 matched notebook (~87k), logs still showed replan from ~d4 rewriting tiles (`SHEEP@0`, IDLE assigns, truncated `active=`). That is the destroyer of live reward — not “zone cascade can’t sum to 87k on paper.”

---

## 8. Plans written this arc

| Plan | Intent | Outcome |
|------|--------|---------|
| Zone-Wise Sequential Planner | `_solve_zone` + cascade; FIVE from `two_lands.md`; TEN stub; `NUM_ACTIVE_HIRES` | Shipped → ~31k live |
| Fix Zone Cascade Bugs | Per-hand hire; W/F+cash carry; honest hires | Necessary; still ~30k |
| Fix Zone Skip Logic | Skip rules on replan; drop broke/1-tile prechecks | ~29k |
| Contiguous Zones + Pickups | `break` not `continue`; pickups JSON; `LAGS=(0,)` | ~24k live; day-0 MIP thinner until handmade |
| Replan Shed And Glue | Replan `track_shed=True`; wire skip; `has_work`; no IDLE wipe | Misdiagnosed; crashed live to ~0.5–3k |
| Restore Working Baseline | Put replan shed **back off**; keep IDLE-skip + skip wiring | Necessary; zone-wise still ~2–9k vs monolithic ~98k |

Earlier TwoLand plans same day (also discarded): Dynamic Expansion, Fix Land2 Buy, Dual 25-Tile, Day-0 Two Land, Pickups ops fix, One-Land Start + Land2 Threshold.

---

## 9. Final disposition

1. **Zone-wise did not beat monolithic OneLand on live smoke.**
2. Restoring `track_shed=False` on replan was correct and necessary, but **not sufficient** to recover 60–98k under the zone-wise stack.
3. The ~60–98k numbers people remembered were almost entirely **monolithic FIVE + shed-off replan**, not zone-wise.
4. Decision: **discard** uncommitted zone-wise / TwoLand agent changes; restore committed monolithic planner (and align market/zoning if they still expect `NUM_ACTIVE_HIRES`).
5. Keep this doc + `two_land_approach.md` + the zone-wise notebook as the knowledge base for the next scaling attempt.

Restore command (when ready; do **not** Kaggle-submit from agents without explicit ask):

```bash
# Inspect first — market.py / zoning.py may still reference zone-wise symbols
git checkout HEAD -- agent/planner.py
# then fix or also restore agent/market.py, agent/zoning.py as needed
bash scripts/smoke_test.sh
```

---

## 10. Lessons for the next TwoLand attempt

1. **Never AND ten hard ops caps in one replan.** One locked overflow freezes all empties for the season. Prefer soft slack, per-land replan, or true zone independence with careful hire binding (`two_land_approach.md` Plans A–D).
2. **Measure live reward, not MIP obj.** I0 handmade sums (~87–97k) are paper harvest−buys.
3. **Day-0 and replan must stay coherent with execution.** Notebook has no replan. Agent replan that rewrites queues without matching shed/ops physics will erase a good day-0 plan.
4. **`track_shed=False` on replan is proven.** Do not “unify” day-0 and replan models without a new ablation that beats shed-off on *reward*.
5. **Cascade glue is where decomposition fails quietly.** Hire×zones, zeroed W/F, wrong cash handoff, `continue` holes — each looks like “solver ran” while score dies.
6. **Hire routing is positional.** `ACTIVE_ZONES` must be a contiguous `WORKERS` prefix.
7. **Catalog diversity matters for column generation.** Lag-0 WIS (~25) ≪ handmade 108 for zone MIP quality.
8. **Don’t ship layout + solver shape in one diff.** Old vs new FIVE ops made every score story ambiguous.
9. **Late Land2 is structurally weak.** Short horizon + hire burn rarely beat full-season OneLand.
10. **Scale zone-wise only after live OneLand parity.** Notebook ~60–91k MIP is a *necessary* check, not a *sufficient* one. Need smoke near monolithic (~60–98k) *before* binding zones VI–X.

---

## 11. Key file map (as of discard)

| Path | Role in this arc |
|------|------------------|
| `agent/planner.py` | Zone-wise rewrite (discard) vs monolithic HEAD (keep) |
| `agent/zoning.py` | FIVE/TEN layouts, `HAND_DAILY_COST`, ops |
| `agent/market.py` | `NUM_ACTIVE_HIRES` hire target + batches |
| `agent/animal_rollouts.py` | Load pickups JSON for agent |
| `agent/dp_catalog.py` | Lag experiment (`LAGS=(0,)`) |
| `data/two_lands.md` | Target geometry / hire batches |
| `data/animal_with_pickups.json` | Honest animal ops tapes |
| `data/handmade_dp_candidates.json` | 108-chain handmade menu |
| `docs/two_land_approach.md` | Monolithic 50-tile INFEASIBLE diagnosis |
| `experiments/OneL-Zonewise-CPSAT-Handmade-Catalog.ipynb` | Zone MIP proof |
| `.cursor/memory/active_context.md` | Monolithic replan knobs + 98k ablation |

---

## 12. One-paragraph epitaph

We tried to scale beyond OneLand by (1) buying a second land inside a monolithic 50-tile CP-SAT, then (2) decomposing into sequential per-zone solves so Land2 could be appended without AND-ing ten hard caps. The notebook showed zone-wise MIP math can print ~60–97k. The agent never delivered matching live reward: cascade hire/cash bugs, thin catalogs, and especially dawn replan (shed-off + queue overwrite, then a mistaken shed-on “unify”) kept smoke in the ~2–31k band while clean monolithic HEAD still printed ~98k. **Discard zone-wise for now; restore monolithic; only revisit TwoLand after a zone-wise agent can match OneLand live scores without rewriting the proven replan ablation.**
