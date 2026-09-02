"""Replay analysis — parse Kaggle kaggriculture replays into JSON reports."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from replay_analysis.load import SEASON_DAYS, Replay, load_replay, resolve_us_index
from replay_analysis.metrics import (
    daily_money,
    daily_tile_counts,
    end_shed,
    harvest_yield,
    pass_counts,
    potential_yield,
    sold_units as compute_sold_units,
    submitted_sells,
)
from replay_analysis.kpi import executor_kpis, market_kpis, planner_kpis
from replay_analysis.sells import simulate_sells

__all__ = ["analyze", "summarize_dir", "plot_game", "load_replay"]


def plot_game(report, *, title: str | None = None):
    """Lazy import so CLI/batch works without matplotlib."""
    from replay_analysis.plot import plot_game as _plot_game

    return _plot_game(report, title=title)


def analyze(path: str | Path, *, us_name: str | None = None) -> dict[str, Any]:
    replay = load_replay(path)
    us_index = resolve_us_index(replay, us_name)
    n_players = len(replay.team_names)

    tiles_by_player = daily_tile_counts(replay)
    passes_by_player = pass_counts(replay)
    harvested_by_player = harvest_yield(replay)
    sold_by_player = compute_sold_units(replay)
    potential_by_player = potential_yield(replay)
    shed_by_player = end_shed(replay)
    money_by_player = daily_money(replay)
    submitted_by_player = submitted_sells(replay)
    sell_sim = simulate_sells(replay)
    executor_k = executor_kpis(replay)
    market_k = market_kpis(replay, sell_sim)
    planner_k = planner_kpis(replay, sell_sim, tiles_by_player)

    sells_by_player: dict[int, dict[str, Any]] = {}
    drift: dict[int, dict[str, Any]] = {}
    for p in range(n_players):
        sim = sell_sim["by_player"][p]
        actual_sold = sold_by_player.get(p, {})
        sells_by_player[p] = {
            "submitted_units": submitted_by_player.get(p, {}),
            "filled_units": actual_sold,
            "simulated_units": sim["filled_units"],
            "unfilled_units": sim["unfilled_units"],
            "revenue": sim["revenue"],
            "total_revenue": sim["total_revenue"],
            "price_pdf": sim["price_pdf"],
        }
        y = harvested_by_player.get(p, {})
        end = (shed_by_player.get(p) or {}).get("combined") or {}
        drift[p] = _yield_drift(y, actual_sold, end, potential_by_player.get(p, {}))

    return {
        "replay_path": str(replay.path),
        "replay_stem": replay.path.stem,
        "episode_id": replay.episode_id,
        "seed": replay.seed,
        "agents": replay.team_names,
        "rewards": replay.rewards,
        "us_index": us_index,
        "n_steps": replay.n_steps,
        "tiles": {"by_player": tiles_by_player},
        "passes": {"by_player": [passes_by_player[p] for p in range(n_players)]},
        "yield": {
            "potential": [potential_by_player.get(p, {}) for p in range(n_players)],
            "harvested": [harvested_by_player.get(p, {}) for p in range(n_players)],
            "by_player": [harvested_by_player.get(p, {}) for p in range(n_players)],
        },
        "shed_end": {"by_player": [shed_by_player.get(p, {}) for p in range(n_players)]},
        "money": {"by_player": [money_by_player[p] for p in range(n_players)]},
        "sells": {
            "by_player": [sells_by_player[p] for p in range(n_players)],
            "events": sell_sim["events"],
        },
        "drift": {"by_player": [drift[p] for p in range(n_players)]},
        "kpi": {
            "executor": [executor_k[p] for p in range(n_players)],
            "market": [market_k[p] for p in range(n_players)],
            "planner": [planner_k[p] for p in range(n_players)],
        },
    }


def _yield_drift(
    harvested: dict[str, int],
    sold: dict[str, int],
    end_combined: dict[str, int],
    potential: dict[str, int] | None = None,
) -> dict[str, Any]:
    potential = potential or {}
    products = sorted(set(potential) | set(harvested) | set(sold) | set(end_combined))
    rows = []
    for prod in products:
        pot = potential.get(prod, 0)
        h = harvested.get(prod, 0)
        s = sold.get(prod, 0)
        e = end_combined.get(prod, 0)
        rows.append(
            {
                "product": prod,
                "potential": pot,
                "harvested": h,
                "sold": s,
                "end_inventory": e,
                "harvest_gap": pot - h,
                "balance_gap": h - s - e,
            }
        )
    return {"products": rows}


def summarize_dir(
    dir_path: str | Path,
    *,
    us_name: str | None = None,
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    dir_path = Path(dir_path)
    replays_dir = dir_path / "replays" if (dir_path / "replays").is_dir() else dir_path
    paths = sorted(replays_dir.glob("episode-*-replay.json"))
    submission_id = dir_path.name if dir_path.name.isdigit() else replays_dir.parent.name

    games: list[dict[str, Any]] = []
    for path in paths:
        games.append(analyze(path, us_name=us_name))

    summary = {
        "submission_id": submission_id,
        "n_episodes": len(games),
        "games": games,
        "aggregate": _aggregate(games, us_name=us_name),
    }

    if out_path is None:
        out_path = dir_path / "summary.json" if dir_path.name.isdigit() else replays_dir.parent / "summary.json"
    out_path = Path(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    summary["summary_path"] = str(out_path)
    return summary


def _aggregate(games: list[dict[str, Any]], *, us_name: str | None) -> dict[str, Any]:
    if not games:
        return {}

    us_index = games[0].get("us_index")
    if us_index is None:
        us_index = 0

    wins = 0
    us_rewards: list[float] = []
    opp_rewards: list[float] = []
    occupied_by_day: list[list[float]] = [[] for _ in range(SEASON_DAYS)]
    empty_by_day: list[list[float]] = [[] for _ in range(SEASON_DAYS)]
    passes_by_day: list[list[float]] = [[] for _ in range(SEASON_DAYS)]

    sold_agg: Counter[str] = Counter()
    yield_units: Counter[str] = Counter()
    revenue: Counter[str] = Counter()
    price_pdf: dict[str, Counter[str]] = defaultdict(Counter)

    for game in games:
        rewards = game.get("rewards") or []
        if len(rewards) >= 2:
            us_rewards.append(float(rewards[us_index]))
            opp_rewards.append(float(rewards[1 - us_index]))
            if rewards[us_index] > rewards[1 - us_index]:
                wins += 1
            elif rewards[us_index] == rewards[1 - us_index]:
                wins += 0.5

        tiles = (game.get("tiles") or {}).get("by_player") or []
        if us_index < len(tiles):
            for day, counts in enumerate(tiles[us_index]):
                if day < SEASON_DAYS:
                    occupied_by_day[day].append(float(counts.get("occupied", 0)))
                    empty_by_day[day].append(float(counts.get("empty", 0)))

        passes = (game.get("passes") or {}).get("by_player") or []
        if us_index < len(passes):
            per_day = passes[us_index].get("per_day") or []
            for day, n in enumerate(per_day):
                if day < SEASON_DAYS:
                    passes_by_day[day].append(float(n))

        sells = (game.get("sells") or {}).get("by_player") or []
        yields = (game.get("yield") or {}).get("harvested") or (
            (game.get("yield") or {}).get("by_player") or []
        )
        if us_index < len(sells):
            s = sells[us_index]
            for prod, qty in (s.get("filled_units") or {}).items():
                sold_agg[prod] += qty
            for prod, rev in (s.get("revenue") or {}).items():
                revenue[prod] += rev
            for prod, pdf in (s.get("price_pdf") or {}).items():
                for price, cnt in pdf.items():
                    price_pdf[prod][price] += cnt
        if us_index < len(yields):
            for prod, qty in (yields[us_index] or {}).items():
                yield_units[prod] += qty

    def _mean_series(buckets: list[list[float]]) -> list[float]:
        return [
            sum(b) / len(b) if b else 0.0 for b in buckets
        ]

    def _stats(vals: list[float]) -> dict[str, float | None]:
        if not vals:
            return {"mean": None, "min": None, "max": None}
        return {
            "mean": sum(vals) / len(vals),
            "min": min(vals),
            "max": max(vals),
        }

    return {
        "us_index": us_index,
        "us_name": us_name,
        "win_rate": wins / len(games) if games else 0.0,
        "reward_us": _stats(us_rewards),
        "reward_opponent": _stats(opp_rewards),
        "mean_occupied_by_day": _mean_series(occupied_by_day),
        "mean_empty_by_day": _mean_series(empty_by_day),
        "mean_passes_by_day": _mean_series(passes_by_day),
        "sold_units": dict(sold_agg),
        "yield_units": dict(yield_units),
        "revenue": dict(revenue),
        "price_pdf": {p: dict(c) for p, c in price_pdf.items()},
    }
