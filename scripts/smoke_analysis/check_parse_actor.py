"""Self-check: spawn-bound hire labels in exec lines map to the logged worker."""

from __future__ import annotations

from smoke_analysis.parse_actor import parse_exec_actor

_SAMPLE = (
    "[exec] d=1 h=5 hand0=hire2 WEST pos=(5, 4) adj=1 owned=0 hire2 ->t11"
)
_HAND_WORKERS = ("hire1", "hire2", "hire3", "hire4")


def main() -> None:
    parsed = parse_exec_actor(_SAMPLE, _HAND_WORKERS)
    assert parsed is not None, "expected parse"
    worker, rest = parsed
    assert worker == "hire2", f"expected hire2, got {worker!r}"
    assert rest.startswith("WEST"), rest
    wrong = parse_exec_actor(
        "[exec] d=1 h=5 hand0 WEST pos=(4, 4) adj=1 owned=1",
        _HAND_WORKERS,
    )
    assert wrong is not None and wrong[0] == "hire1", "slot fallback"
    print("parse_actor self-check OK")


if __name__ == "__main__":
    main()
