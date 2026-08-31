"""Market price curve helpers mirroring README / MARKET_PARAMS."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

I0_DEFAULT = 10_000


@dataclass(frozen=True)
class MarketParam:
    base: int
    i0: int
    t: int
    below_func: str
    below_target: float
    above_func: str
    above_target: float


MARKET_PARAMS: dict[str, MarketParam] = {
    "WHEAT": MarketParam(25, 10_000, 400, "sqrt", 0.80, "log", 0.20),
    "CARROT": MarketParam(35, 10_000, 450, "log", 0.20, "sqrt", 0.70),
    "TOMATO": MarketParam(60, 10_000, 200, "linear", 0.40, "sqrt", 0.60),
    "STRAWBERRY": MarketParam(120, 10_000, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": MarketParam(250, 10_000, 300, "log", 0.20, "sq", 3.60),
    "EGG": MarketParam(50, 10_000, 332, "linear", 0.40, "log", 0.20),
    "MILK": MarketParam(160, 10_000, 122, "sqrt", 0.60, "linear", 1.60),
    "WOOL": MarketParam(200, 10_000, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": MarketParam(100, 10_000, 200, "linear", 0.40, "linear", 0.40),
}


def _f(name: str, x: float) -> float:
    if name == "linear":
        return x
    if name == "sq":
        return x * x
    if name == "sqrt":
        return math.sqrt(x)
    if name == "log":
        return math.log(1.0 + x)
    raise ValueError(f"unknown curve func {name!r}")


def quoted(product: str, inv: int) -> int:
    """Quoted sell price at market inventory inv (pre-sell)."""
    p = MARKET_PARAMS[product]
    if inv > p.i0:
        d = inv - p.i0
        amp = p.above_target * p.base / _f(p.above_func, p.t)
        raw = p.base - amp * _f(p.above_func, d)
    elif inv < p.i0:
        d = p.i0 - inv
        amp = p.below_target * p.base / _f(p.below_func, p.t)
        raw = p.base + amp * _f(p.below_func, d)
    else:
        raw = p.base
    return max(1, round(raw))


@lru_cache(maxsize=512)
def _sell_prefix_table(
    product: str, inv: int, max_n: int
) -> tuple[tuple[int, int], ...]:
    """table[n] = (revenue selling n units, inv after n units). table[0]=(0,inv)."""
    rows: list[tuple[int, int]] = [(0, inv)]
    cur = inv
    rev = 0
    for _ in range(max_n):
        price = quoted(product, cur)
        rev += price
        if price > 1:
            cur += 1
        rows.append((rev, cur))
    return tuple(rows)


def sell_revenue_and_next_inv(product: str, inv: int, n: int) -> tuple[int, int]:
    """Walk n unit sells; return (total revenue, market inv after sells).

    At quoted $1, revenue is $1 per unit but inventory does not increase.
    """
    if n <= 0:
        return 0, inv
    table = _sell_prefix_table(product, inv, n)
    return table[n]


def sell_prefix_table(
    product: str, inv: int, max_n: int
) -> tuple[tuple[int, int], ...]:
    """Cached prefix revenues for sell sizes 0..max_n."""
    if max_n <= 0:
        return ((0, inv),)
    return _sell_prefix_table(product, inv, max_n)


def marginal_price(product: str, inv: int) -> int:
    """Price of the next unit sold at inventory inv."""
    return quoted(product, inv)


def base_price(product: str) -> int:
    return MARKET_PARAMS[product].base


def price_floor(product: str, ratio: float = 0.5) -> int:
    return max(1, round(base_price(product) * ratio))


def max_units_above_floor(
    product: str, inv: int, max_n: int, ratio: float = 0.5
) -> int:
    """Units sellable before first marginal quote drops below ratio * base."""
    if max_n <= 0:
        return 0
    floor = price_floor(product, ratio)
    count = 0
    cur = inv
    for _ in range(max_n):
        price = quoted(product, cur)
        if price < floor:
            break
        count += 1
        if price > 1:
            cur += 1
    return count


def allowed_sell_qty(
    product: str,
    market_inv: int,
    stock: int,
    abs_day: int,
    *,
    dp_quota: int = 0,
    mode: Literal["drip", "dump"] = "drip",
    wheat_reserve: int = 0,
    max_sell_per_day: int = 24,
    liquidate_from_day: int = 27,
    floor_ratio: float = 0.5,
) -> int:
    """Below floor → 0. Above floor → drip (premium) or dump (staples)."""
    if product == "WHEAT":
        stock = max(0, stock - wheat_reserve)
    if stock <= 0:
        return 0

    if abs_day >= liquidate_from_day:
        if mode == "dump":
            return stock
        cap = max_sell_per_day
        if product == "WOOL":
            cap = min(cap, max(4, MARKET_PARAMS["WOOL"].T // 8))
        return max(dp_quota, min(stock, cap))

    cap = max_sell_per_day if mode == "drip" else stock
    if product == "WOOL":
        cap = min(cap, max(4, MARKET_PARAMS["WOOL"].T // 8))
    headroom = max_units_above_floor(product, market_inv, min(stock, cap), floor_ratio)
    if headroom <= 0:
        return 0
    if mode == "dump":
        return min(stock, headroom)
    min_drip = min(stock, max_sell_per_day, headroom)
    return max(dp_quota, min_drip)
