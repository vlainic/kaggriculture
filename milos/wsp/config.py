"""Farmer-only WSP constants (FIVE zone I) — no agent imports."""

from __future__ import annotations

FARMER = "farmer"
NUM_DAYS = 30
FARMER_TILES: tuple[int, ...] = (0, 1, 2, 3, 4)
FARMER_NET_TILE_OPS = 19

# Est-ops weights (same order of magnitude as live zoning)
EST_OPS_ANIMAL = 4.0
EST_OPS_CROP = 1.5

ANIMAL_NAMES = frozenset({"GOOSE", "COW", "SHEEP"})
PROFILE_SUFFIXES = ("no_fert", "with_fert", "no_care", "with_care")

WHEAT_PRICE = 25
FERT_PRICE = 100
MAX_BUY = 50 * NUM_DAYS
OBJ_EARLY_STOP = 5_000

CROP_PROFILES = ("no_fert", "with_fert")
ANIMAL_PROFILES = ("no_care", "with_care")

GLUT_PRODUCTS: tuple[str, ...] = ("MELON", "STRAWBERRY", "MILK", "WOOL")

CONCAVE_PRODUCTS: tuple[str, ...] = (
    "MELON",
    "STRAWBERRY",
    "MILK",
    "WOOL",
    "CARROT",
    "TOMATO",
    "WHEAT",
)

# Crop tile_free_age defaults (fallback if data missing)
CROP_FREE_AGE = {
    ("WHEAT", "no_fert"): 4,
    ("WHEAT", "with_fert"): 4,
    ("CARROT", "no_fert"): 3,
    ("CARROT", "with_fert"): 3,
    ("TOMATO", "no_fert"): 10,
    ("TOMATO", "with_fert"): 11,
    ("MELON", "no_fert"): 11,
    ("MELON", "with_fert"): 16,
    ("STRAWBERRY", "no_fert"): 16,
    ("STRAWBERRY", "with_fert"): 16,
}
