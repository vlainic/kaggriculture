# Active Context

## Current focus

Project setup phase complete; **agent implementation not started**. Next work is building the plant-only baseline (3×3 segment, no hires) and validating observation/action mechanics locally.

## Recent changes (Aug 6, 2026)

1. **Formatted** `docs/project_overview.md` tab-separated tables as proper markdown tables (object types, town shops, market params, config defaults).
2. **Reconfigured `.cursor/`** for Kaggriculture:
   - Removed Godot/NSMK legacy rules, skills, agents
   - Added `kaggriculture-stack.mdc` rule
   - Added `kaggriculture-domain` and `kaggriculture-agent-conventions` skills
   - Added `strategy-analyst`, `kaggle-agent-dev`, `eval-runner` subagents
3. **Initialized memory bank** (this update).

## Active decisions

- **Approach:** heuristic Python bot, not Deep RL or live LLM per turn
- **Architecture:** hierarchical master + per-segment daily MILP + routing; staged rollout plant-first
- **Master search:** MCTS vs shallow enumeration — **decide after measuring branching factor**
- **No notebooks** — all logic in `.py` modules

## Open questions (from strategy doc)

1. Does `SELL` draw from **shed** or **carried inventory**? (affects mid-day `DROP` necessity)
2. Confirm melon and all seed types available turn 0 via obs dump (UI may omit them)
3. Finalize request/allocate contract between modules before coding
4. Profile compute on Kaggle runtime before committing to MCTS + MILP every turn

## Immediate next steps

1. Create minimal `main.py` PASS/starter-smoke agent + `eval/run_local.py`
2. Dump obs on turn 0 to confirm market/shed/action semantics
3. Implement routing + plant-only 3×3 daily schedule (heuristic first, MILP second)
4. Run vs `"starter"` and `"random"`; document baseline win rate

## Key files to read each session

- [docs/project_overview.md](../../docs/project_overview.md) — rules & obs schema
- [docs/claude_chat.md](../../docs/claude_chat.md) — architecture rationale
- `.cursor/skills/kaggriculture-domain/SKILL.md` — condensed mechanics
