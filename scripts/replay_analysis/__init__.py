"""Replay analysis — parse Kaggle kaggriculture replays into JSON reports."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

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


def analyze(
    path: str | Path,
    *,
    us_name: str | None = None,
    include_events: bool = True,
    slim_yield: bool = False,
) -> dict[str, Any]:
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

    yield_block: dict[str, Any] = {
        "potential": [potential_by_player.get(p, {}) for p in range(n_players)],
        "harvested": [harvested_by_player.get(p, {}) for p in range(n_players)],
    }
    if not slim_yield:
        yield_block["by_player"] = yield_block["harvested"]

    sells_block: dict[str, Any] = {
        "by_player": [sells_by_player[p] for p in range(n_players)],
    }
    if include_events:
        sells_block["events"] = sell_sim["events"]

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
        "yield": yield_block,
        "shed_end": {"by_player": [shed_by_player.get(p, {}) for p in range(n_players)]},
        "money": {"by_player": [money_by_player[p] for p in range(n_players)]},
        "sells": sells_block,
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
    include_events: bool = False,
    on_progress: Callable[[int, int, Path], None] | None = None,
) -> dict[str, Any]:
    dir_path = Path(dir_path)
    replays_dir = dir_path / "replays" if (dir_path / "replays").is_dir() else dir_path
    paths = sorted(replays_dir.glob("episode-*-replay.json"))
    submission_id = dir_path.name if dir_path.name.isdigit() else replays_dir.parent.name

    games: list[dict[str, Any]] = []
    n_paths = len(paths)
    for i, path in enumerate(paths, start=1):
        if on_progress is not None:
            on_progress(i, n_paths, path)
        games.append(
            analyze(
                path,
                us_name=us_name,
                include_events=include_events,
                slim_yield=True,
            )
        )

    summary = {
        "submission_id": submission_id,
        "n_episodes": len(games),
        "us_name": us_name,
        "us_index": games[0].get("us_index") if games else None,
        "seat_counts": _seat_counts(games),
        "games": games,
        "aggregate": _aggregate(games, us_name=us_name),
    }
    _check_episode_table(games, summary["aggregate"].get("episode_table") or [])

    if out_path is None:
        base = dir_path if dir_path.name.isdigit() else replays_dir.parent
        out_path = base / f"{submission_id}.json"
    out_path = Path(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    summary["summary_path"] = str(out_path)
    return summary


def _median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _stats(vals: list[float]) -> dict[str, float | None]:
    if not vals:
        return {"mean": None, "min": None, "max": None, "median": None}
    return {
        "mean": sum(vals) / len(vals),
        "min": min(vals),
        "max": max(vals),
        "median": _median(vals),
    }


def _mean_series(buckets: list[list[float]]) -> list[float]:
    return [sum(b) / len(b) if b else 0.0 for b in buckets]


def _kpi_us(game: dict[str, Any], us_index: int) -> tuple[dict, dict, dict]:
    kpi = game.get("kpi") or {}
    exec_k = _player_entry(kpi.get("executor"), us_index)
    mkt_k = _player_entry(kpi.get("market"), us_index)
    plan_k = _player_entry(kpi.get("planner"), us_index)
    return exec_k, mkt_k, plan_k


def _player_entry(by_player: list[Any] | dict[int, Any] | None, player: int) -> dict[str, Any]:
    if isinstance(by_player, dict):
        return by_player.get(player) or {}
    if by_player is None:
        return {}
    if player < len(by_player):
        entry = by_player[player]
        return entry if isinstance(entry, dict) else {}
    return {}


def _episode_row(game: dict[str, Any], us_index: int) -> dict[str, Any]:
    rewards = game.get("rewards") or []
    reward_us = float(rewards[us_index]) if us_index < len(rewards) else None
    reward_opp = float(rewards[1 - us_index]) if len(rewards) >= 2 else None
    win = (
        reward_us is not None
        and reward_opp is not None
        and reward_us > reward_opp
    )
    exec_k, mkt_k, plan_k = _kpi_us(game, us_index)
    ripe = exec_k.get("ripe_unharvested") or {}
    noop = exec_k.get("noop_ops") or {}
    hold = mkt_k.get("holding_time") or {}
    slot = mkt_k.get("order_slot_saturation") or {}
    idle = plan_k.get("idle_tile_days") or {}
    hire = plan_k.get("hire_profile") or {}
    return {
        "episode_id": game.get("episode_id"),
        "seed": game.get("seed"),
        "reward_us": reward_us,
        "reward_opp": reward_opp,
        "win": win,
        "noop_ops": noop.get("total", 0),
        "move_overhead": exec_k.get("move_overhead", 0.0),
        "ripe_tile_turns": ripe.get("total_tile_turns", 0),
        "mean_harvest_latency": ripe.get("mean_latency_turns", 0.0),
        "unexplained_delta": mkt_k.get("unexplained_delta", 0.0),
        "tile_day_utilization": idle.get("tile_day_utilization", 0.0),
        "total_hire_spend": hire.get("total_hire_spend", 0),
        "holding_time_mean": hold.get("mean_turns", 0.0),
        "order_slot_saturation": slot.get("saturation_rate", 0.0),
    }


def _check_episode_table(
    games: list[dict[str, Any]], episode_table: list[dict[str, Any]]
) -> None:
    mismatches: list[str] = []
    for i, (game, row) in enumerate(zip(games, episode_table)):
        u = _game_us_index(game)
        rewards = game.get("rewards") or []
        expected = float(rewards[u]) if u < len(rewards) else None
        actual = row.get("reward_us")
        if expected != actual:
            mismatches.append(
                f"episode {game.get('episode_id')} index {i}: "
                f"expected reward_us={expected} (seat {u}), got {actual}"
            )
    if mismatches:
        raise ValueError(
            f"episode_table reward mismatch in {len(mismatches)}/{len(games)} games: "
            + "; ".join(mismatches[:3])
            + (" ..." if len(mismatches) > 3 else "")
        )


def _game_us_index(game: dict[str, Any]) -> int:
    u = game.get("us_index")
    return 0 if u is None else int(u)


def _seat_counts(games: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[int] = Counter()
    for game in games:
        counts[_game_us_index(game)] += 1
    return {str(k): int(v) for k, v in sorted(counts.items())}


def _aggregate_kpi(games: list[dict[str, Any]]) -> dict[str, Any]:
    if not games:
        return {}

    noop_ops: list[float] = []
    move_overhead: list[float] = []
    ripe_tile_turns: list[float] = []
    mean_harvest_latency: list[float] = []
    unexplained_delta: list[float] = []
    tile_day_utilization: list[float] = []
    total_hire_spend: list[float] = []
    holding_time_mean: list[float] = []
    order_slot_saturation: list[float] = []

    for game in games:
        u = _game_us_index(game)
        exec_k, mkt_k, plan_k = _kpi_us(game, u)
        ripe = exec_k.get("ripe_unharvested") or {}
        noop = exec_k.get("noop_ops") or {}
        hold = mkt_k.get("holding_time") or {}
        slot = mkt_k.get("order_slot_saturation") or {}
        idle = plan_k.get("idle_tile_days") or {}
        hire = plan_k.get("hire_profile") or {}

        noop_ops.append(float(noop.get("total", 0)))
        move_overhead.append(float(exec_k.get("move_overhead", 0.0)))
        ripe_tile_turns.append(float(ripe.get("total_tile_turns", 0)))
        mean_harvest_latency.append(float(ripe.get("mean_latency_turns", 0.0)))
        unexplained_delta.append(float(mkt_k.get("unexplained_delta", 0.0)))
        tile_day_utilization.append(float(idle.get("tile_day_utilization", 0.0)))
        total_hire_spend.append(float(hire.get("total_hire_spend", 0)))
        holding_time_mean.append(float(hold.get("mean_turns", 0.0)))
        order_slot_saturation.append(float(slot.get("saturation_rate", 0.0)))

    def _mean(vals: list[float]) -> float | None:
        return sum(vals) / len(vals) if vals else None

    return {
        "executor": {
            "noop_ops_mean": _mean(noop_ops),
            "move_overhead_mean": _mean(move_overhead),
            "ripe_tile_turns_mean": _mean(ripe_tile_turns),
            "mean_harvest_latency_mean": _mean(mean_harvest_latency),
        },
        "market": {
            "unexplained_delta_mean": _mean(unexplained_delta),
            "holding_time_mean": _mean(holding_time_mean),
            "order_slot_saturation_mean": _mean(order_slot_saturation),
        },
        "planner": {
            "tile_day_utilization_mean": _mean(tile_day_utilization),
            "total_hire_spend_mean": _mean(total_hire_spend),
        },
    }


def _aggregate(games: list[dict[str, Any]], *, us_name: str | None) -> dict[str, Any]:
    if not games:
        return {}

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
    episode_table: list[dict[str, Any]] = []

    for game in games:
        u = _game_us_index(game)
        episode_table.append(_episode_row(game, u))

        rewards = game.get("rewards") or []
        if len(rewards) >= 2:
            us_rewards.append(float(rewards[u]))
            opp_rewards.append(float(rewards[1 - u]))
            if rewards[u] > rewards[1 - u]:
                wins += 1
            elif rewards[u] == rewards[1 - u]:
                wins += 0.5

        tiles = (game.get("tiles") or {}).get("by_player") or []
        if u < len(tiles):
            for day, counts in enumerate(tiles[u]):
                if day < SEASON_DAYS:
                    occupied_by_day[day].append(float(counts.get("occupied", 0)))
                    empty_by_day[day].append(float(counts.get("empty", 0)))

        passes = (game.get("passes") or {}).get("by_player") or []
        if u < len(passes):
            per_day = passes[u].get("per_day") or []
            for day, n in enumerate(per_day):
                if day < SEASON_DAYS:
                    passes_by_day[day].append(float(n))

        sells = (game.get("sells") or {}).get("by_player") or []
        yields = (game.get("yield") or {}).get("harvested") or (
            (game.get("yield") or {}).get("by_player") or []
        )
        if u < len(sells):
            s = sells[u]
            for prod, qty in (s.get("filled_units") or {}).items():
                sold_agg[prod] += qty
            for prod, rev in (s.get("revenue") or {}).items():
                revenue[prod] += rev
            for prod, pdf in (s.get("price_pdf") or {}).items():
                for price, cnt in pdf.items():
                    price_pdf[prod][price] += cnt
        if u < len(yields):
            for prod, qty in (yields[u] or {}).items():
                yield_units[prod] += qty

    return {
        "us_name": us_name,
        "seat_counts": _seat_counts(games),
        "win_rate": wins / len(games) if games else 0.0,
        "reward_us": _stats(us_rewards),
        "reward_opponent": _stats(opp_rewards),
        "episode_table": episode_table,
        "kpi": _aggregate_kpi(games),
        "mean_occupied_by_day": _mean_series(occupied_by_day),
        "mean_empty_by_day": _mean_series(empty_by_day),
        "mean_passes_by_day": _mean_series(passes_by_day),
        "sold_units": dict(sold_agg),
        "yield_units": dict(yield_units),
        "revenue": dict(revenue),
        "price_pdf": {p: dict(c) for p, c in price_pdf.items()},
    }
