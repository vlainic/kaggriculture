# Tech Context

## Stack

| Layer | Choice |
| --- | --- |
| Runtime | Kaggle Simulations (`kaggle-environments`) |
| Language | Python 3, stdlib-first in submission |
| Optimizer | OR-Tools CP-SAT — **once at import**, zone-count assignment |
| Agent style | Heuristic executor + bounded CP-SAT plan — no RL |
| Bundle | `main.py` + `agent/` + `data/` (rollouts + `handmade_dp_candidates.json`) + vendored ortools |

## Local evaluation

```bash
bash scripts/smoke_test.sh   # agents: use this only (copies handmade_dp_candidates.json)
```

```python
from kaggle_environments import make
env = make("kaggriculture", configuration={"episodeSteps": 720}, debug=True)
env.run(["main.py", "random"])
```

Vs `random` smoke (Aug 19 fert + skip d=0 replan): planner import ~2–4s, reward ~**58k**. Vs greedy opponent: melon glut still expected with dump sells.

## Kaggle submit

**Users only:** `bash scripts/smoke_and_submit.sh --submit "msg"`  
Agents never submit without explicit user request (`kaggle-submission.mdc`).

## Planner knobs (`agent/planner.py`)

| Knob | Value | Notes |
| --- | --- | --- |
| `num_workers` | 8 | Kaggle import timed out with `os.cpu_count()` / 1 worker ~61s |
| `max_time_in_seconds` | 20 import / 5 replan | Split; do not blanket-cap all solves at 10s |
| `OBJECTIVE_GOOD_ENOUGH` | 80_000 | Keep; live obj ~49k so callback often misses |
| `NET_TILE_OPS` | from `zoning` | FOUR: 14/12/12/10; FIVE: 18/13/14/14/15 |
| `HIRE_DAILY_COST` | from `zoning` | fib sum of hands: FOUR=4, FIVE=7 |
| Balance domain | 0–200_000 | not ±1e6 |
| Catalog | ~109 chains | handmade + IDLE |
| Layout switch | `zoning.CURRENT` | `FOUR` or `FIVE`; call `bind()` |

Notebook OPTIMAL (same model, threshold 0): ~66s, obj 83620. Do not expect that at Kaggle import.

## Mockup SCIP (`Assignement-Master-Mockup.ipynb`)

Same zone-count MIP as OneLand (counts, daily W/F, cash chain, I0 buys $25/$100, hire fib-sum/day — notebook still assumes 3 hands / $4). **SCIP via `pywraplp`**, not CP-SAT. No hire preamble. Yields via `harvest_map`. FEED is inventory, not seed cost.

| Knob | Value |
| --- | --- |
| Backend | SCIP |
| TimeLimit (notebook) | 10s + `limits/gap=0.15` |
| Typical 10s | obj ~83820, 588 vars |
| 60s smoke OPTIMAL | obj ~83910, cash floor 695, wheat buy 16 |

SCIP is slower than OneLand CP-SAT (~0.8s to 80k). Do not switch backends unless asked.

## Diagnostics

- Logs: `[planner]`, `[exec]`, `[snap]`, `Player 0: reward=`
- `experiments/live_analysis.ipynb` — Kaggle logs
- Assignment Gantt: `OneLand-Assignement-Handmade-Candidates.ipynb`

## Compute

- Kaggle ~60s/turn — import must stay under 20s cap (80k callback does not reliably stop this MIP)
- Live planner uses 8 CP-SAT workers; notebook OPTIMAL still fine at 1 worker

## Key docs

| Doc | Purpose |
| --- | --- |
| `docs/project_overview.md` | Game rules |
| `experiments/OneLand-Assignement-Handmade-Candidates.ipynb` | Zone-count CP-SAT master (source of planner model) |
| `experiments/Assignement-Master-Mockup.ipynb` | SCIP sibling — economy aligned, no preamble |
| `docs/weighted_set_packing_failer.md` | Old WSP — do not resume |
| `docs/dp_master/fertilze_failure.md` | First fert/planner regression notes |
| `data/five_zone_plan.md` | FIVE column layout design |
| `data/two_lands.md` | Two-land / spawn draft (not in code yet) |
| `.cursor/skills/kaggriculture-domain` | Mechanics |
| `.cursor/skills/kaggriculture-agent-conventions` | Agent conventions |

## Cursor config

- Rules: `kaggriculture-stack.mdc`, `kaggle-submission.mdc`
- Skills: `kaggriculture-domain`, `kaggriculture-agent-conventions`, `core-memory-bank`, `core-plan-act`
- `.gitignore` includes `.cursor/` — do not stage `logs.txt`
