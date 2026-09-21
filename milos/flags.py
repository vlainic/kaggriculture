"""Runtime flags — off by default for Kaggle submission."""

from __future__ import annotations

import os

VERBOSE = os.environ.get("KAGGRI_VERBOSE", "0") == "1"
