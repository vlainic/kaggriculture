"""Parse [wsp_plan] lines from smoke / verbose agent logs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_WSP_PLAN_RE = re.compile(
    r"^\[wsp_plan\] d=(\d+) horizon=(\d+) solver=(\S+) complete=(\d+) "
    r"assigned=(\{.*\})\s*$"
)


@dataclass(frozen=True)
class WspPlan:
    day: int
    horizon: int
    solver: str
    complete: bool
    assigned: dict[int, list]


def _parse_assigned(raw: dict) -> dict[int, list]:
    out: dict[int, list] = {}
    for k, v in raw.items():
        out[int(k)] = [list(pair) for pair in v]
    return out


def parse_wsp_plan_line(line: str) -> WspPlan | None:
    m = _WSP_PLAN_RE.match(line.strip())
    if not m:
        return None
    assigned_raw = json.loads(m.group(5))
    return WspPlan(
        day=int(m.group(1)),
        horizon=int(m.group(2)),
        solver=m.group(3),
        complete=bool(int(m.group(4))),
        assigned=_parse_assigned(assigned_raw),
    )


def parse_wsp_plan_lines(lines: list[str] | str) -> list[WspPlan]:
    if isinstance(lines, str):
        text = lines
    else:
        text = "\n".join(lines)
    plans: list[WspPlan] = []
    for line in text.splitlines():
        p = parse_wsp_plan_line(line)
        if p is not None:
            plans.append(p)
    return plans


def load_wsp_plans(path: str | Path) -> list[WspPlan]:
    return parse_wsp_plan_lines(Path(path).read_text(encoding="utf-8"))
