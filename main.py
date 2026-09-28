"""Milos farmer-only submission entry."""

from milos import envconfig
from milos.executor import step as _step


def agent(obs, config=None):
    envconfig.ingest(config)
    return _step(obs)
