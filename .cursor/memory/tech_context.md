# Tech Context

## Stack

| Layer | Choice |
| --- | --- |
| Runtime | Kaggle Simulations (`kaggle-environments`) |
| Language | Python 3, stdlib-first in submission |
| Optimizer | OR-Tools CP-SAT — import + dawn replan |
| Catalog | `agent/dp_catalog.py` WIS (not handmade JSON at runtime) |
| Animals | `data/animal_with_pickups.json` |
| Agent style | Milos heuristic executor + dawn market + sell_dp + WSP replan — no RL (legacy CP-SAT in `agent/`) |
| Live layout | `threeland12` (`KAGGRI_LAYOUT`); V55 opener `KAGGRI_V55_OPENER`; abl `KAGGRI_ABL_LAND/CATALOG/CASH` (default on); SW `KAGGRI_SW` |
| Bundle | `main.py` + `milos/` + `data/` (crop + animal_with_pickups + handmade for fallback) + vendored ortools |

## Local evaluation

```bash
bash scripts/smoke_test.sh   # copies crop_rollouts + animal_with_pickups + handmade_dp_candidates
bash scripts/download_submission_logs.sh <submission_id>   # replays; --with-logs optional
bash scripts/summarize_replays.sh <submission_id> --us-name "Your Name"   # → kaggle_logs/<id>/<id>.json
cd scripts && python -m replay_analysis ../kaggle_logs/<id>/replays/episode-*.json   # single game
```

**Preferred for batch A/B:** open `experiments/submission_analysis.ipynb` or `submission_comparison.ipynb` — run all cells; set `SUBMISSION_ID` / `ID_A`/`ID_B` + `US_NAME`. Uses `submission_nb.ensure_summary()` (download replays + summarize if needed). Set `REFRESH=True` after `replay_analysis/kpi.py` changes to rewrite cached planner KPIs; for **revenue per tile-day by product**, `submission_nb.revenue_per_tile_day_by_product(game)` recomputes from sells + `crop_tile_days` without refresh. Initial TrueSkill: `ensure_episode_skills()` → Kaggle `GetEpisode` API, cache `kaggle_logs/<id>/episode_skills.json` (needs `~/.kaggle/access_token` or kaggle CLI auth).

```python
from kaggle_environments import make
# Pass full configuration when testing forecast/drain (intervals, marketParams):
env = make("kaggriculture", configuration={"episodeSteps": 720, "townCenterSellInterval": 24}, debug=True)
env.run(["main.py", "random"])
```

**Entry point:** `def agent(obs, config=None)` — kaggle-environments only passes `config` when `co_argcount == 2`.

Historical FIVE smoke (pre-pickups fix): peak ~**98k**, later ~**64k**. Pickups without ops de-dupe → sub-**50k**. Re-smoke after Aug 27 ops fix before banking.

## Kaggle submit

**Users only:** `bash scripts/smoke_and_submit.sh --submit "msg"`  
Agents never submit without explicit user request (`kaggle-submission.mdc`).

## Planner knobs (`agent/planner.py`)

| Knob | Value | Notes |
| --- | --- | --- |
| `num_workers` | 8 | |
| `max_time_in_seconds` | 20 import / **15 replan** | |
| `track_shed` | **False** on WSP replan; True on zonewise | No W/F in WSP conservative spend |
| `replan_min_balance` | **0** on WSP; liquidity floor on zonewise | Never floor `conservative` |
| `OBJECTIVE_GOOD_ENOUGH` | 80_000 | |
| Ops cap | **`daily_tile_ops` + hire preamble** | No wheat/animal/fert side counters with pickups JSON |
| Animals JSON | `animal_with_pickups.json` | |
| Catalog | `dp_catalog.build_catalog` | `lags`, insert tolerance / max_variants |
| Layout switch | `zoning.CURRENT` | **`TWO`** (live); `KAGGRI_LANDS=3` → THREE; catalog also `FOUR` / `FIVE` |
| Solver | `solvers.CURRENT_SOLVER` | **`twoland_wsp`** (live); also `threeland_wsp`, `zonewise_wsp`, `zonewise`, `monolithic` |
| Shed door | `_owned_shed_tiles` | Center tiles valid for PICKUP/DROP **only if `!= LOCKED`** |
| Cascade fail | skip-continue | INFEASIBLE/`picks0` → skip + locked handoff; not break |
| `DEAD_HANDS` | `STUCK_THRESHOLD=3` | Hire depth excludes; market/planner `dead=` |
| `ZONE_OPS_MIX` | default `1` | Construction chain swap; BUDGET/FILLER/RESIZE removed |

## DP catalog knobs (`agent/dp_catalog.py`)

| Knob | Default | Notes |
| --- | --- | --- |
| `LAGS` | `(0, 1, 2)` | Also animal-only start days |
| `INSERT_TOLERANCE` | `0.05` | Near-best band |
| `INSERT_MAX_VARIANTS` | `4` | After best-pin + day thin |
| Insert crop | mono-greedy extra + mix suffix | Allows 2+ melons/tomatoes when fit |
| Insert animal | single placement | Overlaps animal-only after dedupe |

## Zonewise notebooks

| Notebook | Catalog | Money cascade |
| --- | --- | --- |
| `OneL-Zonewise-CPSAT-Handmade-Catalog.ipynb` | handmade JSON | Conservative (start − loss) |
| `OneL-Zonewise-CPSAT-DP-Catalog.ipynb` | `build_catalog(..., lags=DP_LAGS)` | Same |

## Diagnostics

- Logs: `[planner]`, `[exec]`, `[snap]`, `[hands]`, `[wsp_plan]` (if `KAGGRI_VERBOSE=1`), `Player 0: reward=`
- Gantt: zonewise notebooks; **`milos/wsp/gantt.py`** + `experiments/milos-simplification.ipynb` (farmer accumulate)
- Smoke capacity: `plot_zone_capacity` — shed lines only on shed mismatch; farmer **all days match** after full-stack HARVEST sim
- **Replay analysis:** `kaggle_logs/<id>/<id>.json` — `aggregate.episode_table`, `aggregate.kpi`, per-game `drift`, `kpi.*`
- Replay obs timing: `obs[i]` is post-`action[i]`; sold units from stock delta `obs[i-1]→obs[i]`
- `docs/two_land_approach.md` — pickups / ops double-count history

## Flags

| Env | Effect |
| --- | --- |
| `KAGGRI_VERBOSE=1` | Emit `[wsp_plan]` (smoke_test.sh sets this; submission does not) |
| `KAGGRI_LAYOUT` | `threeland12` (default live), `threeland15`, oneland variants |
| `KAGGRI_V55_OPENER` | Default on — tape d0–5 |
| `KAGGRI_ABL_LAND` / `CATALOG` / `CASH` | Default **on**; `=0` for control |
| `KAGGRI_SW` | `"1"` default — enable SW land path when layout has SW workers |
| `KAGGRI_ZONE_MIN_NET` | Local — min `obj−hire` for activation (ship default 0) |
| `KAGGRI_ZONE_MARGIN_RATIO` | Local — if >0 require vs hire cost |
| `SMOKE_SEEDS` | Optional `pinned` or comma list for multi-seed mean margin (local only) |
| `KAGGRI_LANDS=3` | Legacy **agent/** ThreeLand + `threeland_wsp` (not milos) |

## Key docs

| Doc | Purpose |
| --- | --- |
| `docs/project_overview.md` | Game rules |
| `data/milos_zoning.md` | Target five-zone + **six-man** + h=0 buy order |
| `docs/two_land_approach.md` | Pickups ops lesson |
| `docs/twoland/diagnosis_0911.md` | OneLand vs TwoLand diagnosis; reject static NW caps; post-NE ops crash |
| `docs/twolands/twoland_readd.md` | TwoLand re-add spec (probe + NE glue + LOCKED carve-out) |
| `scripts/smoke_analysis/` | Local smoke log KPIs/plots; **layout-aware** via `layout.py` |
| `milos/` | Live **threeland12**; V55 opener; abl flags; committed concave; GOOSE/EGG |
| `data/milos_zoning.md` | Layout / ops heuristics (may lag code ops +1) |
| `scripts/smoke_analysis/` | Smoke KPIs + `plot_zone_earnings_vs_cost` |
| `scripts/download_submission_logs.sh` | Bulk episode replays from Kaggle CLI |
| `scripts/summarize_replays.sh` | Batch replay analysis → `<id>.json` |
| `scripts/replay_analysis/` | Replay metrics/KPI module |
| `experiments/replay_analysis.ipynb` | Single-episode charts |
| `experiments/submission_nb.py` | Notebook helpers: summary load, day bands, land rows, skill fetch |
| `experiments/submission_analysis.ipynb` | N-episode one-submission deep-dive + noise floor |
| `experiments/submission_comparison.ipynb` | OneLand vs TwoLand KPI comparison |
| `.cursor/skills/kaggriculture-domain` | Mechanics |
| `.cursor/skills/kaggriculture-agent-conventions` | Agent conventions |

## Cursor config

- Rules: `kaggriculture-stack.mdc`, `kaggle-submission.mdc`
- Skills: `kaggriculture-domain`, `kaggriculture-agent-conventions`, `core-memory-bank`, `core-plan-act`
- `.gitignore` includes `.cursor/` — do not stage `logs.txt`
