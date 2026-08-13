"""Scripted one-land farming agent."""

from agent.executor import step as _step


def agent(obs):
    return _step(obs)
