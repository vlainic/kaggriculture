#!/usr/bin/env python3
"""Decode V55 agent from kaggle_nbs notebook into opponents/v55/main.py."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

EXPECTED_MAIN_SHA256 = (
    "f09034624844da494669c4ab0e0d9a797da1a19db95eb138b875d309bd1aa01b"
)
EXPECTED_CALLABLE_NAME = "final_price_guard"
ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "kaggle_nbs" / "kaggriculture-v55-one-turn-market-race-edge.ipynb"
DEFAULT_OUT = ROOT / "opponents" / "v55" / "main.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_ke_callable(main_path: Path) -> str:
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.utils import read_file

    raw = read_file(str(main_path), str(main_path))
    fn = get_last_callable(raw, path=str(main_path))
    name = getattr(fn, "__name__", None)
    if name != EXPECTED_CALLABLE_NAME:
        raise SystemExit(
            f"KE loader picked {name!r}, expected {EXPECTED_CALLABLE_NAME!r}"
        )
    return name


def extract(out_path: Path = DEFAULT_OUT, *, force: bool = False) -> Path:
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if (
        not force
        and out_path.is_file()
        and _sha256(out_path) == EXPECTED_MAIN_SHA256
    ):
        _assert_ke_callable(out_path)
        print(f"OK (cached): {out_path}")
        return out_path

    if not NOTEBOOK.is_file():
        raise SystemExit(f"Notebook not found: {NOTEBOOK}")

    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cell2 = "".join(nb["cells"][2]["source"])
    ns: dict = {"Path": Path, "WORKDIR": out_path.parent}
    exec(cell2, ns)  # noqa: S102 — notebook decode cell

    if not out_path.is_file():
        raise SystemExit(f"Decode did not write {out_path}")

    digest = _sha256(out_path)
    if digest != EXPECTED_MAIN_SHA256:
        raise SystemExit(f"SHA256 mismatch: got {digest}")

    picked = _assert_ke_callable(out_path)
    print(f"Wrote {out_path} sha256={digest[:12]}… KE={picked}")
    return out_path


def main() -> None:
    out = DEFAULT_OUT
    force = "--force" in sys.argv
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            continue
        out = Path(arg)
    extract(out, force=force)


if __name__ == "__main__":
    main()
