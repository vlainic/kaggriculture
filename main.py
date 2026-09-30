"""Milos farmer-only submission entry."""

from milos import envconfig, fix_flags, market, price_forecast, sell_dp
from milos.executor import step as _step


def agent(obs, config=None):
    envconfig.ingest(config)
    fix_flags.log_abl_flags_once(int(obs.get("step", 0)))
    if fix_flags.fix_reset() and obs.get("step") == 0:
        price_forecast.reset_episode()
        sell_dp.reset_episode()
        market.reset_room_state()
    return _step(obs)
