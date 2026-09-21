"""Milos farmer-only submission entry."""

from milos.executor import step as _step


def agent(obs):
    return _step(obs)
