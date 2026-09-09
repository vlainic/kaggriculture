"""Helpers for submission_analysis / submission_comparison notebooks."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

SEASON_DAYS = 30
EXPECTED_STEPS = 720
STEEP_GLUT_PRODUCTS = ("MELON", "WOOL")


def repo_root() -> Path:
    here = Path(__file__).resolve().parent
    if (here.parent / "agent").is_dir():
        return here.parent
    return here


def summary_path(submission_id: str, root: Path | None = None) -> Path:
    root = root or repo_root()
    return root / "kaggle_logs" / submission_id / f"{submission_id}.json"


def log_dir(submission_id: str, root: Path | None = None) -> Path:
    root = root or repo_root()
    return root / "kaggle_logs" / submission_id


def has_replays(submission_id: str, root: Path | None = None) -> bool:
    replays = log_dir(submission_id, root) / "replays"
    return replays.is_dir() and any(replays.glob("episode-*-replay.json"))


def _episode_ids_from_csv(text: str) -> list[str]:
    ids: list[str] = []
    for line in text.strip().splitlines()[1:]:
        if not line.strip():
            continue
        ep = line.split(",", 1)[0].strip().strip('"')
        if ep.isdigit():
            ids.append(ep)
    return ids


def download_replays(
    submission_id: str,
    root: Path | None = None,
    *,
    verbose: bool = True,
) -> Path:
    """Download episode replays via Kaggle CLI."""
    out = log_dir(submission_id, root)
    replays = out / "replays"
    replays.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["kaggle", "competitions", "episodes", submission_id, "-v"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "kaggle competitions episodes failed: "
            f"{result.stderr.strip() or result.stdout.strip()}\n"
            "Install the kaggle package and configure ~/.kaggle/kaggle.json."
        )
    (out / "episodes.csv").write_text(result.stdout, encoding="utf-8")
    episode_ids = _episode_ids_from_csv(result.stdout)
    if not episode_ids:
        raise FileNotFoundError(
            f"No episodes for submission {submission_id} "
            "(still queued or running on Kaggle)."
        )

    for i, ep in enumerate(episode_ids, start=1):
        if verbose:
            print(f"Downloading replay {i}/{len(episode_ids)} episode {ep}...")
        dl = subprocess.run(
            ["kaggle", "competitions", "replay", ep, "-p", str(replays)],
            capture_output=True,
            text=True,
            check=False,
        )
        if dl.returncode != 0:
            raise RuntimeError(
                f"Failed to download episode {ep}: "
                f"{dl.stderr.strip() or dl.stdout.strip()}"
            )
    return out


def summarize_submission(
    submission_id: str,
    us_name: str | None,
    root: Path | None = None,
    *,
    verbose: bool = True,
) -> Path:
    root = root or repo_root()
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from replay_analysis import summarize_dir

    def _progress(i: int, n: int, path: Path) -> None:
        if verbose:
            print(f"Analyzing {i}/{n} {path.name}")

    summary = summarize_dir(
        log_dir(submission_id, root),
        us_name=us_name,
        on_progress=_progress if verbose else None,
    )
    return Path(summary["summary_path"])


def ensure_summary(
    submission_id: str,
    us_name: str | None = None,
    root: Path | None = None,
    *,
    download: bool = True,
    refresh: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    """Load summary JSON; download replays and summarize in-notebook if needed."""
    root = root or repo_root()
    path = summary_path(submission_id, root)

    if path.is_file() and not refresh:
        if verbose:
            print(f"Using cached summary {path}")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    if not has_replays(submission_id, root):
        if not download:
            raise FileNotFoundError(
                f"No replays under {log_dir(submission_id, root) / 'replays'}. "
                "Set download=True."
            )
        if verbose:
            print(f"Downloading replays for {submission_id}...")
        download_replays(submission_id, root, verbose=verbose)

    if us_name is None:
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                us_name = json.load(f).get("us_name")
        if us_name is None:
            raise ValueError(
                "Set US_NAME in the config cell (your Kaggle team name)."
            )

    if verbose:
        print(f"Summarizing {submission_id} (us_name={us_name!r})...")
    summarize_submission(submission_id, us_name, root, verbose=verbose)
    return load_summary(submission_id, root)


def load_summary(submission_id: str, root: Path | None = None) -> dict[str, Any]:
    path = summary_path(submission_id, root)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Call snb.ensure_summary({submission_id!r}, US_NAME) first."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _kaggle_access_token() -> str:
    token_path = Path.home() / ".kaggle" / "access_token"
    if token_path.is_file():
        return token_path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(
        f"Missing {token_path}. Log in with the kaggle CLI so episode skill can be fetched."
    )


def fetch_episode_meta(episode_id: int | str) -> dict[str, Any]:
    """Kaggle GetEpisode — includes per-agent initialScore / updatedScore."""
    url = "https://www.kaggle.com/api/i/competitions.EpisodeService/GetEpisode"
    req = urllib.request.Request(
        url,
        data=json.dumps({"episodeId": int(episode_id)}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_kaggle_access_token()}",
            "User-Agent": "kaggriculture-submission-nb",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"GetEpisode failed for {episode_id}: {e.code} {e.read()[:200]!r}"
        ) from e


def skill_cache_path(submission_id: str, root: Path | None = None) -> Path:
    return log_dir(submission_id, root) / "episode_skills.json"


def ensure_episode_skills(
    submission_id: str,
    games: list[dict[str, Any]],
    root: Path | None = None,
    *,
    refresh: bool = False,
    verbose: bool = True,
    max_workers: int = 8,
) -> dict[str, dict[str, Any]]:
    """Fetch & cache per-episode initialSkill for our submission seat.

    Returns map episode_id(str) -> {initial_score_us, initial_score_opp, ...}.
    """
    root = root or repo_root()
    cache_path = skill_cache_path(submission_id, root)
    cache: dict[str, dict[str, Any]] = {}
    if cache_path.is_file() and not refresh:
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)

    sid = int(submission_id)
    by_eid = {str(g["episode_id"]): g for g in games if g.get("episode_id") is not None}
    needed = [eid for eid in by_eid if eid not in cache]
    if needed:
        if verbose:
            print(f"Fetching initialScore for {len(needed)} episode(s)...")

        def _one(eid: str) -> tuple[str, dict[str, Any]]:
            payload = fetch_episode_meta(eid)
            ep = payload.get("episode") or {}
            agents = list(ep.get("agents") or [])
            us_index = game_us_index(by_eid[eid])
            us = next(
                (
                    a
                    for a in agents
                    if int(a.get("submissionId", -1)) == sid
                    and int(a.get("index", -1)) == us_index
                ),
                None,
            )
            if us is None:
                us = next(
                    (a for a in agents if int(a.get("submissionId", -1)) == sid),
                    None,
                )
            if us is None and 0 <= us_index < len(agents):
                us = agents[us_index]
            opp = next((a for a in agents if a is not us), None)
            return eid, {
                "initial_score_us": (us or {}).get("initialScore"),
                "updated_score_us": (us or {}).get("updatedScore"),
                "initial_score_opp": (opp or {}).get("initialScore"),
                "updated_score_opp": (opp or {}).get("updatedScore"),
                "submission_id_us": (us or {}).get("submissionId"),
                "submission_id_opp": (opp or {}).get("submissionId"),
            }

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = [pool.submit(_one, eid) for eid in needed]
            for fut in as_completed(futs):
                eid, row = fut.result()
                cache[eid] = row
                if verbose:
                    print(
                        f"  episode {eid}: us_skill={row.get('initial_score_us')}"
                    )

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)

    return cache


def attach_skills(
    games: list[dict[str, Any]],
    skills: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Copy skill fields onto each game dict (in place) and return games."""
    for g in games:
        eid = g.get("episode_id")
        if eid is None:
            continue
        row = skills.get(str(eid)) or {}
        g["initial_score_us"] = row.get("initial_score_us")
        g["initial_score_opp"] = row.get("initial_score_opp")
    return games


def game_us_index(game: dict[str, Any]) -> int:
    u = game.get("us_index")
    return 0 if u is None else int(u)


def _player_entry(by_player: list[Any] | None, player: int) -> dict[str, Any]:
    if not by_player or player >= len(by_player):
        return {}
    entry = by_player[player]
    return entry if isinstance(entry, dict) else {}


def us_kpi(game: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return (executor, market, planner) KPI dicts for this game's us seat."""
    u = game_us_index(game)
    kpi = game.get("kpi") or {}
    return (
        _player_entry(kpi.get("executor"), u),
        _player_entry(kpi.get("market"), u),
        _player_entry(kpi.get("planner"), u),
    )


def reward_us(game: dict[str, Any]) -> float | None:
    u = game_us_index(game)
    rewards = game.get("rewards") or []
    if u >= len(rewards):
        return None
    return float(rewards[u])


def episode_row(game: dict[str, Any]) -> dict[str, Any]:
    u = game_us_index(game)
    exec_k, mkt_k, plan_k = us_kpi(game)
    ripe = exec_k.get("ripe_unharvested") or {}
    noop = exec_k.get("noop_ops") or {}
    idle = plan_k.get("idle_tile_days") or {}
    hire = plan_k.get("hire_profile") or {}
    r_us = reward_us(game)
    rewards = game.get("rewards") or []
    r_opp = float(rewards[1 - u]) if len(rewards) >= 2 else None
    return {
        "episode_id": game.get("episode_id"),
        "seed": game.get("seed"),
        "reward_us": r_us,
        "reward_opp": r_opp,
        "win": r_us is not None and r_opp is not None and r_us > r_opp,
        "noop_ops": noop.get("total", 0),
        "move_overhead": exec_k.get("move_overhead", 0.0),
        "ripe_mean_latency": ripe.get("mean_latency_turns", 0.0),
        "unexplained_delta": mkt_k.get("unexplained_delta", 0.0),
        "tile_day_utilization": idle.get("tile_day_utilization", 0.0),
        "idle_empty": idle.get("empty", 0),
        "idle_weed": idle.get("weed", 0),
        "total_hire_spend": hire.get("total_hire_spend", 0),
        "days_below_floor": plan_k.get("days_below_floor", 0),
        "n_steps": game.get("n_steps"),
    }


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else float("nan")


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0 if len(vals) == 1 else float("nan")
    m = _mean(vals)
    var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
    return math.sqrt(var)


def day_band(
    games: list[dict[str, Any]],
    series_fn: Callable[[dict[str, Any]], list[float]],
    *,
    days: int = SEASON_DAYS,
) -> tuple[list[float], list[float]]:
    """Per-day mean and std across episodes."""
    buckets: list[list[float]] = [[] for _ in range(days)]
    for game in games:
        series = series_fn(game)
        for d in range(min(days, len(series))):
            v = series[d]
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                buckets[d].append(float(v))
    means = [_mean(b) if b else float("nan") for b in buckets]
    stds = [_std(b) if len(b) >= 2 else (0.0 if b else float("nan")) for b in buckets]
    return means, stds


def tile_pct_series(game: dict[str, Any], field: str) -> list[float]:
    u = game_us_index(game)
    tiles = (game.get("tiles") or {}).get("by_player") or []
    if u >= len(tiles):
        return [float("nan")] * SEASON_DAYS
    out: list[float] = []
    for day in tiles[u][:SEASON_DAYS]:
        unlocked = (
            day.get("occupied", 0)
            + day.get("empty", 0)
            + day.get("weed", 0)
            + day.get("empty_structure", 0)
        )
        if unlocked <= 0:
            out.append(float("nan"))
        else:
            out.append(100.0 * day.get(field, 0) / unlocked)
    while len(out) < SEASON_DAYS:
        out.append(float("nan"))
    return out


def bank_end_series(game: dict[str, Any]) -> list[float]:
    u = game_us_index(game)
    money = (game.get("money") or {}).get("by_player") or []
    if u >= len(money):
        return [float("nan")] * SEASON_DAYS
    end = money[u].get("end") or []
    return [float(x) if x is not None else float("nan") for x in end[:SEASON_DAYS]]


def min_cash_series(game: dict[str, Any]) -> list[float]:
    _, _, plan_k = us_kpi(game)
    s = plan_k.get("min_cash_by_day") or []
    return [float(x) if x is not None else float("nan") for x in s[:SEASON_DAYS]]


def revenue_series(game: dict[str, Any]) -> list[float]:
    _, mkt_k, _ = us_kpi(game)
    s = mkt_k.get("revenue_by_day") or []
    return [float(x) for x in s[:SEASON_DAYS]]


def spend_series(game: dict[str, Any]) -> list[float]:
    _, mkt_k, _ = us_kpi(game)
    s = mkt_k.get("spend_by_day") or []
    return [float(x) for x in s[:SEASON_DAYS]]


def ops_util_series(game: dict[str, Any]) -> list[float]:
    exec_k, _, _ = us_kpi(game)
    s = exec_k.get("ops_utilization_by_day") or []
    return [float(x) for x in s[:SEASON_DAYS]]


def occupied_pct_series(game: dict[str, Any]) -> list[float]:
    return tile_pct_series(game, "occupied")


def effect_size(a: list[float], b: list[float]) -> float:
    """Cohen's d with pooled std; returns nan if undefined."""
    if not a or not b:
        return float("nan")
    ma, mb = _mean(a), _mean(b)
    na, nb = len(a), len(b)
    if na < 2 and nb < 2:
        return float("nan")
    va = sum((x - ma) ** 2 for x in a) / max(na - 1, 1) if na > 1 else 0.0
    vb = sum((x - mb) ** 2 for x in b) / max(nb - 1, 1) if nb > 1 else 0.0
    pooled = math.sqrt(((na - 1) * va + (nb - 1) * vb) / max(na + nb - 2, 1))
    if pooled < 1e-9:
        return float("inf") if ma != mb else 0.0
    return (ma - mb) / pooled


def noise_floor_from_games(games: list[dict[str, Any]]) -> dict[str, float]:
    """Std of scalar KPIs across episodes (noise floor for comparison)."""
    rows = [episode_row(g) for g in games]
    keys = [
        "reward_us",
        "move_overhead",
        "noop_ops",
        "ripe_mean_latency",
        "unexplained_delta",
        "tile_day_utilization",
        "total_hire_spend",
        "days_below_floor",
    ]
    out: dict[str, float] = {}
    for key in keys:
        vals = [float(r[key]) for r in rows if r.get(key) is not None]
        out[key] = _std(vals)
    out["score_std"] = out.get("reward_us", float("nan"))
    return out


def fill_rate_for(game: dict[str, Any], product: str) -> float:
    _, mkt_k, _ = us_kpi(game)
    fr = (mkt_k.get("fill_rate") or {}).get(product) or {}
    return float(fr.get("fill_rate", 0.0))


def realized_quote_for(game: dict[str, Any], product: str) -> float:
    _, mkt_k, _ = us_kpi(game)
    rvq = mkt_k.get("realized_vs_quote") or {}
    return float(rvq.get(product, 0.0))


def land_purchase_rows(game: dict[str, Any]) -> list[dict[str, Any]]:
    u = game_us_index(game)
    _, _, plan_k = us_kpi(game)
    money = (game.get("money") or {}).get("by_player") or []
    cash_start: list[float] = []
    cash_end: list[float] = []
    if u < len(money):
        cash_start = money[u].get("start") or []
        cash_end = money[u].get("end") or []

    rows: list[dict[str, Any]] = []
    for ev in plan_k.get("land_events") or []:
        day = int(ev.get("day", 0))
        before = float(cash_start[day]) if day < len(cash_start) else float("nan")
        after = float(cash_end[day]) if day < len(cash_end) else float("nan")
        rows.append(
            {
                "episode_id": game.get("episode_id"),
                "seed": game.get("seed"),
                "day": day,
                "quadrant": ev.get("quadrant"),
                "cost": ev.get("cost"),
                "cash_before": before,
                "cash_after": after,
                "days_below_floor": plan_k.get("days_below_floor", 0),
            }
        )
    return rows


def anomaly_rows(
    games: list[dict[str, Any]],
    *,
    delta_sigma: float = 3.0,
    delta_abs: float = 1000.0,
) -> list[dict[str, Any]]:
    rows = [episode_row(g) for g in games]
    deltas = [abs(r["unexplained_delta"]) for r in rows]
    mu = _mean(deltas)
    sd = _std(deltas)
    thresh = max(delta_abs, mu + delta_sigma * sd if not math.isnan(sd) else delta_abs)

    out: list[dict[str, Any]] = []
    for g, r in zip(games, rows):
        reasons: list[str] = []
        if r.get("reward_us") is None:
            reasons.append("missing_reward")
        if r.get("n_steps") not in (None, EXPECTED_STEPS):
            reasons.append(f"n_steps={r.get('n_steps')}")
        if abs(r["unexplained_delta"]) > thresh:
            reasons.append(f"|unexplained_delta|>{thresh:.0f}")
        if r["days_below_floor"] > 0:
            reasons.append("days_below_floor>0")
        if reasons:
            out.append(
                {
                    "episode_id": r.get("episode_id"),
                    "seed": r.get("seed"),
                    "reward_us": r.get("reward_us"),
                    "reasons": "; ".join(reasons),
                }
            )
    return out


def paired_by_seed(
    games_a: list[dict[str, Any]], games_b: list[dict[str, Any]]
) -> tuple[list[tuple[float, float]], list[dict], list[dict]]:
    """Return (paired rewards, unpaired_a, unpaired_b)."""
    by_seed_a = {g.get("seed"): g for g in games_a if g.get("seed") is not None}
    by_seed_b = {g.get("seed"): g for g in games_b if g.get("seed") is not None}
    paired: list[tuple[float, float]] = []
    used_b: set[Any] = set()
    for seed, ga in by_seed_a.items():
        if seed in by_seed_b:
            rb = reward_us(by_seed_b[seed])
            ra = reward_us(ga)
            if ra is not None and rb is not None:
                paired.append((ra, rb))
                used_b.add(seed)
    unpaired_a = [g for s, g in by_seed_a.items() if s not in used_b]
    unpaired_b = [g for s, g in by_seed_b.items() if s not in used_b]
    return paired, unpaired_a, unpaired_b


def ne_buy_day(game: dict[str, Any]) -> int | None:
    _, _, plan_k = us_kpi(game)
    for ev in plan_k.get("land_events") or []:
        if ev.get("quadrant") == "NE":
            return int(ev.get("day", 0))
    return None


def aligned_series(
    game: dict[str, Any],
    series_fn: Callable[[dict[str, Any]], list[float]],
    anchor_day: int,
    *,
    pre: int = 5,
    post: int = 10,
) -> dict[int, float]:
    """Map relative day offset -> value."""
    series = series_fn(game)
    out: dict[int, float] = {}
    for rel in range(-pre, post + 1):
        d = anchor_day + rel
        if 0 <= d < len(series):
            v = series[d]
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                out[rel] = float(v)
    return out


def ensure_agent_path(root: Path | None = None) -> None:
    root = root or repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
