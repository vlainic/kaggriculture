"""Parse dawn [fc_err] forecast vs actual price lines."""

from __future__ import annotations

import re
from typing import Any

FC_ERR_RE = re.compile(
    r"\[fc_err\] d=(\d+) "
    r"((?:[A-Z_]+=\d+/\d+\s*)+)"
)

PAIR_RE = re.compile(r"([A-Z_]+)=(\d+)/(\d+)")

PREMIUM_FC_PRODUCTS: tuple[str, ...] = (
    "MELON",
    "STRAWBERRY",
    "MILK",
    "WOOL",
)


def _mean_abs_err(values: list[float | None], *, from_day: int) -> float | None:
    errs = [v for i, v in enumerate(values) if i >= from_day and v is not None]
    if not errs:
        return None
    return sum(errs) / len(errs)


def _stats(values: list[float | None], *, from_day: int) -> tuple[float | None, float | None, float | None]:
    errs = [v for i, v in enumerate(values) if i >= from_day and v is not None]
    if not errs:
        return None, None, None
    mean = sum(errs) / len(errs)
    var = sum((x - mean) ** 2 for x in errs) / len(errs)
    std = var**0.5
    return mean, std, max(errs) - min(errs)


def parse_fc_err(lines: list[str], *, season_days: int = 30) -> dict[str, Any]:
    by_day: dict[int, dict[str, dict[str, int]]] = {}
    for line in lines:
        m = FC_ERR_RE.search(line)
        if not m:
            continue
        day = int(m.group(1))
        if day < 0 or day >= season_days:
            continue
        row: dict[str, dict[str, int]] = {}
        for prod, fc_s, act_s in PAIR_RE.findall(m.group(2)):
            row[prod] = {"forecast": int(fc_s), "actual": int(act_s)}
        by_day[day] = row

    products: set[str] = set()
    for row in by_day.values():
        products.update(row.keys())
    prod_list = sorted(products)

    abs_err_by_product: dict[str, list[float | None]] = {
        p: [None] * season_days for p in prod_list
    }
    for day, row in by_day.items():
        for p in prod_list:
            if p not in row:
                continue
            fc = row[p]["forecast"]
            act = row[p]["actual"]
            abs_err_by_product[p][day] = float(abs(fc - act))

    premium_abs_err_by_day: list[float | None] = [None] * season_days
    for day in range(season_days):
        row = by_day.get(day)
        if not row:
            continue
        errs = [
            abs(row[p]["forecast"] - row[p]["actual"])
            for p in PREMIUM_FC_PRODUCTS
            if p in row
        ]
        if errs:
            premium_abs_err_by_day[day] = sum(errs) / len(errs)

    err_std_by_product_d3_plus: dict[str, float | None] = {}
    err_range_by_product_d3_plus: dict[str, float | None] = {}
    for p in prod_list:
        _, std, rng = _stats(abs_err_by_product[p], from_day=3)
        err_std_by_product_d3_plus[p] = std
        err_range_by_product_d3_plus[p] = rng

    return {
        "by_day": by_day,
        "products": prod_list,
        "abs_err_by_product_by_day": abs_err_by_product,
        "premium_fc_products": list(PREMIUM_FC_PRODUCTS),
        "premium_abs_err_by_day": premium_abs_err_by_day,
        "mean_premium_abs_err_d3_plus": _mean_abs_err(
            premium_abs_err_by_day, from_day=3
        ),
        "err_std_by_product_d3_plus": err_std_by_product_d3_plus,
        "err_range_by_product_d3_plus": err_range_by_product_d3_plus,
    }
