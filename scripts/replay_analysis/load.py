"""Load Kaggle kaggriculture replay JSON."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

SEASON_DAYS = 30
NUM_PLAYERS = 2

EPISODE_RE = re.compile(r"episode-(\d+)-replay\.json$")


@dataclass
class StepRecord:
    step_index: int
    player: int
    observation: dict[str, Any]
    action: dict[str, Any]
    reward: float
    status: str


@dataclass
class Replay:
    path: Path
    raw: dict[str, Any]
    steps: list[list[StepRecord]] = field(default_factory=list)
    episode_id: int | None = None
    seed: int | None = None
    team_names: list[str] = field(default_factory=list)
    rewards: list[float] = field(default_factory=list)

    @property
    def n_steps(self) -> int:
        return len(self.steps)

    def iter_player(self, player: int) -> Iterator[StepRecord]:
        for step in self.steps:
            if player < len(step):
                yield step[player]


def _episode_id_from_path(path: Path) -> int | None:
    m = EPISODE_RE.search(path.name)
    return int(m.group(1)) if m else None


def load_replay(path: str | Path) -> Replay:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    info = raw.get("info") or {}
    episode_id = info.get("EpisodeId") or _episode_id_from_path(path)
    seed = info.get("seed")
    team_names = list(info.get("TeamNames") or [])
    if not team_names:
        team_names = [
            (a.get("Name") or f"player_{i}")
            for i, a in enumerate(info.get("Agents") or [])
        ]
    rewards = [float(x) for x in raw.get("rewards") or []]

    steps: list[list[StepRecord]] = []
    for si, step in enumerate(raw.get("steps") or []):
        records: list[StepRecord] = []
        for pi, rec in enumerate(step):
            records.append(
                StepRecord(
                    step_index=si,
                    player=pi,
                    observation=rec.get("observation") or {},
                    action=rec.get("action") or {},
                    reward=float(rec.get("reward") or 0),
                    status=str(rec.get("status") or ""),
                )
            )
        steps.append(records)

    return Replay(
        path=path,
        raw=raw,
        steps=steps,
        episode_id=episode_id,
        seed=seed,
        team_names=team_names,
        rewards=rewards,
    )


def resolve_us_index(replay: Replay, us_name: str | None) -> int | None:
    if us_name is None:
        return None
    target = us_name.strip().lower()
    for i, name in enumerate(replay.team_names):
        if name.strip().lower() == target:
            return i
    raise ValueError(f"us_name {us_name!r} not in {replay.team_names!r}")
