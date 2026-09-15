"""Load stdout lines from smoke logs or Kaggle agent-log JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path

SEASON_DAYS = 30
SEED_HEADER_RE = re.compile(r"==>\s*seed:\s*(\d+)")
SEED_LINE_RE = re.compile(r"^seed=(\d+)$")


def load_lines(path: str | Path) -> list[str]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("[") or stripped.startswith("{"):
        return _load_json_log(text)
    return _load_plain_log(text)


def parse_seed(path: str | Path) -> int | None:
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        m = SEED_HEADER_RE.search(line)
        if m:
            return int(m.group(1))
        m = SEED_LINE_RE.match(line.strip())
        if m:
            return int(m.group(1))
    return None


def _load_plain_log(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("==>"):
            continue
        if SEED_LINE_RE.match(line.strip()):
            continue
        lines.append(line)
    return lines


def _load_json_log(text: str) -> list[str]:
    steps = json.loads(text)
    lines: list[str] = []
    for step in steps:
        if isinstance(step, list):
            for item in step:
                if isinstance(item, dict) and item.get("stdout"):
                    lines.extend(item["stdout"].splitlines())
        elif isinstance(step, dict) and step.get("stdout"):
            lines.extend(step["stdout"].splitlines())
    return lines
