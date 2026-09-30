"""Shared town + shop drain (forecast + sell_dp)."""

from __future__ import annotations

from milos import drain_calib, envconfig, rollouts
from milos.fix_flags import fix_calib, fix_prior
from milos.price_forecast import (
    SELL_PRODUCTS,
    raw_drain_for_day,
    shop_drain_per_day,
)

_ALL_SHOPS = tuple(rollouts.SHOP_PRODUCT_DEMAND.keys())


def _shop_ticks_per_day() -> float:
    return envconfig.turns_per_day() / envconfig.shop_interval()


def _expected_unlock_addon(
    unlocked: list[str],
    *,
    through_abs_day: int,
    origin_day: int,
) -> dict[str, float]:
    seen = set(unlocked)
    locked = [s for s in _ALL_SHOPS if s not in seen]
    n_locked = len(locked)
    if n_locked <= 0:
        return {p: 0.0 for p in SELL_PRODUCTS}
    locked_demand = rollouts.shop_demand_by_product(locked)
    per_unlock = _shop_ticks_per_day() / n_locked
    addon = {p: 0.0 for p in SELL_PRODUCTS}
    unlock_iv = envconfig.shop_unlock_interval()
    for u in range(origin_day, through_abs_day + 1):
        if u <= 0 or u % unlock_iv != 0:
            continue
        for p in SELL_PRODUCTS:
            addon[p] += locked_demand.get(p, 0) * per_unlock
    return addon


def drain_row(
    *,
    origin_day: int,
    abs_day: int,
    unlocked_shops: list[str],
    use_prior: bool,
) -> dict[str, float]:
    row = dict(raw_drain_for_day(unlocked_shops, abs_day))
    if use_prior:
        extra = _expected_unlock_addon(
            unlocked_shops,
            through_abs_day=abs_day,
            origin_day=origin_day,
        )
        for p in SELL_PRODUCTS:
            row[p] = row.get(p, 0.0) + extra.get(p, 0.0)
    if fix_calib():
        return {p: row.get(p, 0.0) for p in SELL_PRODUCTS}
    return {
        p: row.get(p, 0.0) * drain_calib.factor(p) for p in SELL_PRODUCTS
    }


def build_drain_horizon(
    origin_day: int,
    unlocked_shops: list[str],
    horizon: int,
    *,
    use_prior: bool | None = None,
) -> list[dict[str, float]]:
    if use_prior is None:
        use_prior = fix_prior()
    rows: list[dict[str, float]] = []
    for rel in range(horizon):
        abs_day = origin_day + rel
        if use_prior:
            rows.append(
                drain_row(
                    origin_day=origin_day,
                    abs_day=abs_day,
                    unlocked_shops=unlocked_shops,
                    use_prior=True,
                )
            )
        else:
            rows.append(
                drain_row(
                    origin_day=origin_day,
                    abs_day=abs_day,
                    unlocked_shops=unlocked_shops,
                    use_prior=False,
                )
            )
    return rows


def town_drain_yesterday(
    prev_unlocked: list[str] | None,
    current_unlocked: list[str],
    yesterday_abs_day: int,
) -> dict[str, float]:
    shops = prev_unlocked if prev_unlocked is not None else current_unlocked
    row = raw_drain_for_day(shops, yesterday_abs_day)
    if fix_prior():
        extra = _expected_unlock_addon(
            list(current_unlocked),
            through_abs_day=yesterday_abs_day,
            origin_day=max(0, yesterday_abs_day),
        )
        for p in SELL_PRODUCTS:
            row[p] = row.get(p, 0.0) + extra.get(p, 0.0)
    return row
