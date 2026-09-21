# Active Context

## Current focus (Sep 21, 2026)

**Live agent = TwoLand WSP** (`twoland_wsp` + `CURRENT = TWO`). Parallel sandbox: **`milos/`** — farmer-only WSP + replan Gantt (notebook), **not** in submission / not dispatched by `main.py`.

### Critical engine rule — shed-adjacent **ONLY IF OWNED**

The four center tiles `(4,4)`, `(5,4)`, `(4,5)`, `(5,5)` are “shed-adjacent” in the rules, but **PICKUP / DROP no-op on a `LOCKED` tile**.

| Tile | Quadrant | OneLand | TwoLand (NW+NE) | ThreeLand (+SW) |
| --- | --- | --- | --- | --- |
| `(4,4)` | NW | owned | owned | owned |
| `(5,4)` | NE | **LOCKED** | owned after 1st `BUY_LAND` | same |
| `(4,5)` | SW | **LOCKED** | **LOCKED all game** | owned after 2nd `BUY_LAND` ($2k) |
| `(5,5)` | SE | **LOCKED** | **LOCKED all game** | **LOCKED all game** |

Gate PICKUP/DROP on **owned** shed tiles (`executor._owned_shed_tiles`). Dawn: owned-shed first → PICKUP → compass. **Not** Sept02 mid-zone walk-to-shed.

### Status

| Item | State |
| --- | --- |
| Live agent | **`twoland_wsp` + `CURRENT = TWO`** |
| Land buys | NE $1k; `BUY_LAND_DAY` through buy day, cleared next dawn |
| Cascade | INFEASIBLE/`picks0` → **skip + continue** (not break); `zone_outcomes` |
| Dead zones | `DEAD_HANDS` after 3 stuck dawns; hire depth excludes them |
| Mix | `ZONE_OPS_MIX=1` construction swap; BUDGET/FILLER/RESIZE gone |
| ThreeLand | Opt-in `KAGGRI_LANDS=3` |
| **`milos/`** | Self-contained farmer WSP + Gantt; smoke still uses **agent/** |
| Smoke verbose | `KAGGRI_VERBOSE=1` in `scripts/smoke_test.sh` → `[wsp_plan]` lines |
| Sept02 overhaul | Still **FAILED** |

### Sep 18 — post-submit (shipped)

- EOD `[hands]` tiles-needing-work vs non-PASS (later: `tiles_dawn=` / `executed=` / `laps=`)
- Strip `ZONE_OPS_BUDGET` / `ZONE_IDLE_FILLER` / `ZONE_TILE_RESIZE`
- Keep **`ZONE_OPS_MIX`** (default on)
- Cascade **skip-not-break** + `DEAD_HANDS` N=3
- 5×5 ~110k; stop chasing idle-hours

### Sep 21 — milos + capacity diagnostics

**Zone capacity diagnostics (smoke_analysis):**
- Parse `[hands] h0 … est_ops=` (+ animal/crop) into `report["hands"]`
- EOD: `tiles_dawn=` + `executed=` + `laps=` — **no** apples-to-oranges `gap=`
- `plot_zone_capacity`: per-zone bars (tile ops + MOVE + **PASS** + reactive), red `est_ops` dots, green `net_tile_ops` hline
- Wired in `experiments/smoke_analysis.ipynb`

**`milos/` sandbox (not submission):**
- `milos/wsp/`: `config`, `data` (repo `data/*.json`), `types`, `common`, `mip`, `farmer`, `prestart.json` (zone I tiles 0–4), `gantt`, `log`
- **No `agent/` imports** inside milos
- `experiments/milos-simplification.ipynb`: milos farmer solve + smoke Gantts
- Smoke still runs live agent; notebook **accumulates** `[wsp_plan]` deltas → full farmer board; plot only if farmer delta nonempty
- Alphas: past **0.3**, unchanged future **0.6**, this-replan delta tiles **1.0**

**Verbose logging (agent, submission-safe):**
- `agent/flags.py`: `VERBOSE = (KAGGRI_VERBOSE == "1")` — default off on Kaggle
- `planner._log_wsp_plan` after day-0 + each replan (payload = changed tiles that dawn)

### Anti-patterns (still)

- Treating center tiles as shed doors without `LOCKED` check
- Mid-zone pathfind-to-shed; floor `conservative` / `cons >= min_balance`; WSP `track_shed=True` on replan
- Hard `break` on WSP cascade INFEASIBLE (use skip-continue)
- Re-enable killed idle/budget/resize flags
- Treating smoke `[wsp_plan]` as milos output (live solver tag is still `twoland_wsp`)
- Plotting replan **deltas alone** as if they were full Gantts — use `accumulate_absolute`

### Immediate next steps

1. Use milos Gantts + zone-capacity plots to name drowning zones / replan churn (behavior changes only when user asks)
2. Ladder / post-NE ops gap as user asks (`docs/twoland/diagnosis_0911.md`)
3. Agents never submit without explicit ask
