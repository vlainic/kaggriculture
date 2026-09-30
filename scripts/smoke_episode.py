#!/usr/bin/env python3
"""One kaggriculture smoke episode (used by smoke_test.sh)."""
from __future__ import annotations

import io
import os
import re
import sys
from collections import defaultdict
from contextlib import redirect_stdout

from kaggle_environments import make

SEASON_LAST_DAY = 29
BUILTINS = frozenset({"pass", "random", "starter"})
# Fixed seeds for local A/B (set SMOKE_SEEDS=11,22,33,44,55).
DEFAULT_PINNED_SMOKE_SEEDS = (11, 22, 33, 44, 55)


def _load_extract_module(root: str):
    import importlib.util

    script = os.path.join(root, "scripts", "extract_v55_opponent.py")
    spec = importlib.util.spec_from_file_location("extract_v55_opponent", script)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load {script}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _resolve_opponent(root: str, opponent: str) -> str:
    if opponent in BUILTINS:
        return opponent
    path = opponent if os.path.isabs(opponent) else os.path.join(root, opponent)
    path = os.path.abspath(path)
    v55_raw = os.path.abspath(os.path.join(root, "opponents", "v55", "main.py"))
    v55_logged = os.path.abspath(
        os.path.join(root, "scripts", "v55_logged_opponent.py")
    )
    needs_raw = path in (v55_raw, v55_logged) or path.endswith(
        "v55_logged_opponent.py"
    )
    if needs_raw and not os.path.isfile(v55_raw):
        _load_extract_module(root).extract(
            __import__("pathlib").Path(v55_raw)
        )
    if not os.path.isfile(path):
        raise SystemExit(f"SMOKE_OPPONENT not found: {path}")
    return path


def run_smoke(
    *, root: str, opponent: str, us_seat: int, seed: int | None = None
) -> tuple[int, float | None]:
    if us_seat not in (0, 1):
        raise SystemExit(f"SMOKE_US_SEAT must be 0 or 1, got {us_seat!r}")

    opp = _resolve_opponent(root, opponent)
    our_agent = os.path.join(root, "main.py")
    if us_seat == 0:
        agents = [our_agent, opp]
    else:
        agents = [opp, our_agent]

    cfg: dict = {"episodeSteps": 720}
    if seed is not None:
        cfg["seed"] = int(seed)
        print(f"seed={seed}", flush=True)
    print(
        f"[smoke] opponent={opp!r} us_seat={us_seat} "
        f"agents={agents!r} config={cfg}"
    )

    env = make("kaggriculture", debug=True, configuration=cfg)
    log_buf = io.StringIO()
    with redirect_stdout(log_buf):
        env.run(agents)
    run_log = log_buf.getvalue()
    sys.stdout.write(run_log)

    final = env.steps[-1]
    us_reward = final[us_seat].reward
    us_status = final[us_seat].status
    opp_seat = 1 - us_seat
    opp_reward = final[opp_seat].reward
    opp_status = final[opp_seat].status
    margin = us_reward - opp_reward

    print(f"Player {us_seat} (us): reward={us_reward}, status={us_status}")
    print(f"Player {opp_seat} (opp): reward={opp_reward}, status={opp_status}")
    print(f"margin_us_minus_opp={margin}")

    if us_status != "DONE" or opp_status != "DONE":
        raise SystemExit(
            f"Smoke failed: us status={us_status!r} opp status={opp_status!r}"
        )

    lines = run_log.splitlines()
    exec_re = re.compile(r"\[exec\] d=(\d+) h=(\d+)")
    by_day_hand2 = defaultdict(list)
    early_wheat_sells = []
    for line in lines:
        m = exec_re.search(line)
        if not m:
            continue
        day, hour = int(m.group(1)), int(m.group(2))
        if (
            day < SEASON_LAST_DAY
            and " market " in line
            and "SELL WHEAT" in line
            and hour < 5
            and day * 24 + hour >= 144
        ):
            early_wheat_sells.append(line.strip())
        if " hand2 " in line:
            act = line.split(" hand2 ", 1)[1].split(" farmer")[0].strip()
            by_day_hand2[day].append((hour, act))

    build = sum(
        1
        for acts in by_day_hand2.values()
        for _, a in acts
        if a.startswith("BUILD_COOP") or a.startswith("BUILD_PASTURE")
    )
    place = sum(
        1
        for acts in by_day_hand2.values()
        for _, a in acts
        if a.startswith("PLACE")
    )
    if place > 0 and build == 0:
        print(
            f"FAIL: hand2 PLACE={place} with BUILD_COOP/BUILD_PASTURE=0",
            file=sys.stderr,
        )
        return 1, None

    for day, acts in sorted(by_day_hand2.items()):
        if day < 6:
            continue
        place_hours = [h for h, a in acts if a.startswith("PLACE")]
        if not place_hours:
            continue
        feed_hours = [h for h, a in acts if a.startswith("FEED")]
        if not feed_hours:
            print(f"FAIL: d={day} hand2 PLACE without same-day FEED", file=sys.stderr)
            return 1, None

    if early_wheat_sells:
        print("FAIL: SELL WHEAT during hours 0-4:", file=sys.stderr)
        for line in early_wheat_sells[:5]:
            print(f"  {line}", file=sys.stderr)
        return 1, None

    day0_buy_seed = any(
        " market " in line and "BUY_SEED" in line
        for line in lines
        if line.startswith("[exec] d=0 ")
    )
    day0_plant = any(
        (" farmer PLANT" in line or " hand" in line and " PLANT" in line)
        for line in lines
        if line.startswith("[exec] d=0 ")
    )
    if not day0_buy_seed and not day0_plant:
        print("FAIL: day-0 had zero BUY_SEED and zero PLANT", file=sys.stderr)
        return 1, None

    print(
        f"Smoke checks passed: hand2 BUILD={build} PLACE={place}, "
        f"no early SELL WHEAT, day-0 productive"
    )
    print("Smoke test passed.")
    return 0, float(margin)


def _parse_smoke_seeds() -> list[int | None]:
    raw = os.environ.get("SMOKE_SEEDS")
    if raw is None or raw.strip() == "":
        return [None]
    if raw.strip().lower() in ("pinned", "default", "5"):
        return list(DEFAULT_PINNED_SMOKE_SEEDS)
    return [int(s.strip()) for s in raw.split(",") if s.strip()]


def main() -> None:
    root = os.environ.get("SMOKE_ROOT", os.getcwd())
    default_opp = os.path.join(root, "scripts", "v55_logged_opponent.py")
    opponent = os.environ.get("SMOKE_OPPONENT", default_opp)
    us_seat = int(os.environ.get("SMOKE_US_SEAT", "0"))
    seeds = _parse_smoke_seeds()
    margins: list[float] = []
    for seed in seeds:
        rc, margin = run_smoke(
            root=root, opponent=opponent, us_seat=us_seat, seed=seed
        )
        if rc != 0:
            raise SystemExit(rc)
        if margin is not None:
            margins.append(margin)
    if len(margins) > 1:
        mean_m = sum(margins) / len(margins)
        print(
            f"[smoke] mean margin_us_minus_opp={mean_m:.1f} over {len(margins)} seeds",
            flush=True,
        )
    raise SystemExit(0)


if __name__ == "__main__":
    main()
