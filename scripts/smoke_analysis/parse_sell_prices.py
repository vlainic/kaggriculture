"""Sells vs relative market price (dawn snap quote / base)."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from smoke_analysis.parse_snap import dawn_snaps

SELL_TOKEN_RE = re.compile(r"\bSELL\s+([A-Z_]+)\s+(\d+)\b")
MARKET_LINE_RE = re.compile(r"\[(exec|opp)\] d=(\d+) h=(\d+) market (.+)")

# Mirror milos.pricing.MARKET_PARAMS.base — keep local so parsers stay light.
BASE_PRICE: dict[str, int] = {
    "WHEAT": 25,
    "CARROT": 35,
    "TOMATO": 60,
    "STRAWBERRY": 120,
    "MELON": 250,
    "EGG": 50,
    "MILK": 160,
    "WOOL": 200,
    "FERTILIZER": 100,
}

PRODUCTS: tuple[str, ...] = tuple(BASE_PRICE.keys())


def _dawn_prices_by_day(
    snaps: list[dict[str, Any]], *, season_days: int
) -> dict[int, dict[str, int]]:
    dawn = {int(s["day"]): s for s in dawn_snaps(snaps)}
    out: dict[int, dict[str, int]] = {}
    for day in range(season_days):
        row = dawn.get(day) or {}
        prices = {
            p: int(row[p])
            for p in PRODUCTS
            if p in row and isinstance(row[p], (int, float))
        }
        if prices:
            out[day] = prices
    return out


def parse_sell_price_heatmap(
    lines: list[str],
    snaps: list[dict[str, Any]],
    *,
    season_days: int = 30,
    rel_bin: float = 0.05,
) -> dict[str, Any]:
    """Aggregate sold units by (side, product, relative_price_bin).

    Relative price = dawn snap quote / base. Same-day sells share the dawn quote
    (snaps are h=0 only).
    """
    quotes = _dawn_prices_by_day(snaps, season_days=season_days)
    # side -> product -> rel_bin -> amount
    buckets: dict[str, dict[str, dict[float, float]]] = {
        "us": defaultdict(lambda: defaultdict(float)),
        "opp": defaultdict(lambda: defaultdict(float)),
    }
    n_sells = {"us": 0, "opp": 0}

    for line in lines:
        m = MARKET_LINE_RE.search(line)
        if not m:
            continue
        tag, day_s, _hour, rest = m.group(1), m.group(2), m.group(3), m.group(4)
        day = int(day_s)
        if not (0 <= day < season_days):
            continue
        side = "us" if tag == "exec" else "opp"
        day_prices = quotes.get(day) or quotes.get(max(quotes) if quotes else 0, {})
        for sm in SELL_TOKEN_RE.finditer(rest):
            product, qty = sm.group(1), int(sm.group(2))
            if qty <= 0 or product not in BASE_PRICE:
                continue
            base = BASE_PRICE[product]
            quote = int(day_prices.get(product, base))
            rel = quote / base
            # Snap to bin centers so heatmap columns align.
            binned = round(rel / rel_bin) * rel_bin
            buckets[side][product][binned] += qty
            n_sells[side] += 1

    all_bins: set[float] = set()
    for side_map in buckets.values():
        for prod_map in side_map.values():
            all_bins.update(prod_map.keys())
    rel_bins = sorted(all_bins) if all_bins else [1.0]

    def _matrix(side: str) -> list[list[float]]:
        grid = [[0.0] * len(rel_bins) for _ in PRODUCTS]
        bin_idx = {b: i for i, b in enumerate(rel_bins)}
        for pi, product in enumerate(PRODUCTS):
            for b, amt in buckets[side][product].items():
                grid[pi][bin_idx[b]] += amt
        return grid

    return {
        "products": list(PRODUCTS),
        "base_price": dict(BASE_PRICE),
        "rel_bins": rel_bins,
        "rel_bin_width": rel_bin,
        "us_amount": _matrix("us"),
        "opp_amount": _matrix("opp"),
        "n_sell_events": dict(n_sells),
        "present_us": n_sells["us"] > 0,
        "present_opp": n_sells["opp"] > 0,
    }
