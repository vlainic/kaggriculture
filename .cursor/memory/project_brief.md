# Project Brief

## What this is

Kaggle Simulations competition **Kaggriculture** — a 720-turn, two-player turn-based farming sim. Each player runs a farm, trades on a dynamic market, and competes for the most bank coins at season end.

- **Competition:** https://www.kaggle.com/competitions/kaggriculture
- **Format:** `agent(obs) -> {"farmer": [...], "market": [...]}` via `kaggle-environments`
- **Deadline:** Final submission Sept 30, 2026; leaderboard finalizes ~Oct 15, 2026
- **Prize:** $5,000 × top 10

## Goal

Build a **heuristic/rule-based Python agent** (no ML/RL training pipeline) that consistently wins on the ELO ladder. Win/loss/tie outcome matters for rating; coin margin does not.

## Deliverable

- `main.py` at repo root with `def agent(obs)` entry point
- Optional helper modules in a minimal, Kaggle-compatible bundle (stdlib-first)
- Local validation against `"starter"`, `"random"`, and prior versions before submit

## Scope boundaries

- **In scope:** strategy analysis, observation parsing, farm/market heuristics, local eval, Kaggle submission
- **Current implementation:** coupled crop + animal CP-SAT on 3×3 NW tiles, no hires (Aug 2026)
- **Out of scope (for now):** full Deep RL training, live LLM inference per turn, Jupyter notebooks in submission bundle

## Key references

- Full rules & observation schema: [docs/project_overview.md](../../docs/project_overview.md)
- Strategy discussion archive: [docs/claude_chat.md](../../docs/claude_chat.md)
- Cursor config: `.cursor/rules/kaggriculture-stack.mdc`, skills `kaggriculture-domain`, `kaggriculture-agent-conventions`
