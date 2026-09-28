"""Runtime town-drain calibration (clean-day inventory drops)."""

from __future__ import annotations

from collections import defaultdict

FACTOR_MIN = 0.1
FACTOR_MAX = 1.0

_factors: dict[str, float] = {}
_sells_today: dict[str, int] = defaultdict(int)

_TRACK_PRODUCTS = (
    "MELON",
    "STRAWBERRY",
    "MILK",
    "WOOL",
    "WHEAT",
    "CARROT",
    "TOMATO",
    "EGG",
    "FERTILIZER",
)


def note_sells(orders: list) -> None:
    for order in orders:
        if not order or order[0] != "SELL" or len(order) < 3:
            continue
        product = order[1]
        qty = int(order[2])
        if qty > 0:
            _sells_today[product] = _sells_today.get(product, 0) + qty


def sells_for_product(product: str) -> int:
    return _sells_today.get(product, 0)


def clear_sells_today() -> None:
    _sells_today.clear()


def update(product: str, observed: float, modelled: float) -> None:
    if modelled <= 0 or observed < 0:
        return
    ratio = observed / modelled
    ratio = max(FACTOR_MIN, min(FACTOR_MAX, ratio))
    prev = _factors.get(product, 1.0)
    _factors[product] = min(prev, ratio)


def factor(product: str) -> float:
    return _factors.get(product, 1.0)


def snapshot() -> str:
    parts = [f"{p}:{_factors.get(p, 1.0):.2f}" for p in _TRACK_PRODUCTS]
    return ",".join(parts)
