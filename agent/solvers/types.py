"""Shared solver result types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SolveResult:
    assigned: dict[int, list]
    complete: bool
    solved_workers: tuple[str, ...]
