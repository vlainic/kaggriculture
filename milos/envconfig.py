"""Episode configuration from kaggle-environments (ingested via main.agent)."""

from __future__ import annotations

import json

from milos import rollouts

_INGESTED = False
_TURNS_PER_DAY = 24
_TOWN_CENTER_INTERVAL = 12
_SHOP_INTERVAL = 4
_SHOP_UNLOCK_INTERVAL = 3
_MAX_MARKET_ORDERS = 10
_SHED_CAP = 100


def _config_dict(config) -> dict:
    if config is None:
        return {}
    if isinstance(config, dict):
        return config
    if hasattr(config, "toDict"):
        return config.toDict()
    try:
        return dict(config)
    except (TypeError, ValueError):
        return {}


def _get(cfg: dict, key: str, default):
    val = cfg.get(key, default)
    if hasattr(val, "toDict"):
        return val.toDict()
    return val


def ingest(config) -> None:
    global _INGESTED, _TURNS_PER_DAY, _TOWN_CENTER_INTERVAL, _SHOP_INTERVAL
    global _SHOP_UNLOCK_INTERVAL, _MAX_MARKET_ORDERS, _SHED_CAP

    if _INGESTED:
        return
    cfg = _config_dict(config)
    if not cfg:
        return

    _TURNS_PER_DAY = max(1, int(_get(cfg, "turnsPerDay", _TURNS_PER_DAY)))
    _TOWN_CENTER_INTERVAL = max(
        1, int(_get(cfg, "townCenterSellInterval", _TOWN_CENTER_INTERVAL))
    )
    _SHOP_INTERVAL = max(1, int(_get(cfg, "townShopSellInterval", _SHOP_INTERVAL)))
    _SHOP_UNLOCK_INTERVAL = max(
        1, int(_get(cfg, "townShopUnlockInterval", _SHOP_UNLOCK_INTERVAL))
    )
    _MAX_MARKET_ORDERS = max(
        1, int(_get(cfg, "maxMarketOrdersPerTurn", _MAX_MARKET_ORDERS))
    )
    _SHED_CAP = max(1, int(_get(cfg, "shedCapacity", _SHED_CAP)))

    from milos import pricing

    market_params = _get(cfg, "marketParams", {}) or {}
    if market_params:
        pricing.apply_market_params_overrides(market_params)

    mp_json = json.dumps(market_params) if market_params else "{}"
    from milos import sell_dp as sell_dp_mod

    sell_dp_mod.SHED_CAP = _SHED_CAP

    print(
        f"[cfg] turnsPerDay={_TURNS_PER_DAY} "
        f"townCenterSellInterval={_TOWN_CENTER_INTERVAL} "
        f"townShopSellInterval={_SHOP_INTERVAL} "
        f"townShopUnlockInterval={_SHOP_UNLOCK_INTERVAL} "
        f"maxMarketOrders={_MAX_MARKET_ORDERS} shedCap={_SHED_CAP} "
        f"marketParams={mp_json}",
        flush=True,
    )
    _INGESTED = True


def turns_per_day() -> int:
    return _TURNS_PER_DAY


def town_center_interval() -> int:
    return _TOWN_CENTER_INTERVAL


def shop_interval() -> int:
    return _SHOP_INTERVAL


def shop_unlock_interval() -> int:
    return _SHOP_UNLOCK_INTERVAL


def max_market_orders() -> int:
    return _MAX_MARKET_ORDERS


def shed_capacity() -> int:
    return _SHED_CAP


def shops_dawn_log(day: int, unlocked_shops: list[str]) -> str:
    raw = list(unlocked_shops)
    distinct = set(raw)
    dupes = sorted({s for s in raw if raw.count(s) > 1})
    missing = sorted(set(rollouts.SHOP_PRODUCT_DEMAND.keys()) - distinct)
    dup_s = ",".join(dupes) if dupes else "none"
    miss_s = ",".join(missing) if missing else "none"
    return (
        f"[shops] d={day} raw={len(raw)} distinct={len(distinct)} "
        f"dupes={dup_s} missing={miss_s}"
    )
