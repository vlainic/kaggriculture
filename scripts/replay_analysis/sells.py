"""Concurrent market SELL fill simulation and price PDFs."""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.pricing import MARKET_PARAMS, quoted  # noqa: E402

from replay_analysis.load import Replay, StepRecord
from replay_analysis.metrics import _inventory_totals, _merge_inv, _total_private_stock

MAX_MARKET_ORDERS = 10


@dataclass
class SellEvent:
    step: int
    day: int
    hour: int
    player: int
    product: str
    price: int


@dataclass
class PlayerSellState:
    queues: list[list[str]] = field(default_factory=list)
    queue_idx: int = 0
    unit_idx: int = 0

    def current_product(self) -> str | None:
        while self.queue_idx < len(self.queues):
            q = self.queues[self.queue_idx]
            if self.unit_idx < len(q):
                return q[self.unit_idx]
            self.queue_idx += 1
            self.unit_idx = 0
        return None

    def advance(self) -> None:
        self.unit_idx += 1

    def remaining_units(self) -> int:
        total = 0
        for qi in range(self.queue_idx, len(self.queues)):
            q = self.queues[qi]
            if qi == self.queue_idx:
                total += len(q) - self.unit_idx
            else:
                total += len(q)
        return total


def _expand_sell_orders(orders: list[Any]) -> list[list[str]]:
    """Expand market SELL orders into per-order unit queues (max 10 orders)."""
    queues: list[list[str]] = []
    for order in (orders or [])[:MAX_MARKET_ORDERS]:
        if not isinstance(order, list) or len(order) < 3:
            continue
        if order[0] != "SELL":
            continue
        product = str(order[1])
        qty = max(0, int(order[2]))
        if qty:
            queues.append([product] * qty)
    return queues


def _sellable_stock_before_market(prev_rec: StepRecord | None, rec: StepRecord) -> Counter[str]:
    """Stock available when rec's market orders execute (prior obs + same-turn shed dumps)."""
    if prev_rec is not None:
        stock: Counter[str] = Counter(
            _total_private_stock(prev_rec.observation.get("private") or {})
        )
    else:
        stock = Counter(_total_private_stock(rec.observation.get("private") or {}))

    priv = rec.observation.get("private") or {}
    for _who, action in _iter_farm_actions(rec):
        if not action:
            continue
        op = action[0]
        if op == "DROP":
            _merge_inv(stock, _inventory_totals(priv))
        elif op == "PLACE" and len(action) >= 2:
            item = str(action[1])
            n = int(action[2]) if len(action) >= 3 else 1
            stock[item] += n
    return stock


def _iter_farm_actions(rec: StepRecord):
    act = rec.action
    farmer = act.get("farmer") or ["PASS"]
    if isinstance(farmer, list) and farmer:
        yield ("farmer", farmer)
    for hi, hand in enumerate(act.get("hands") or []):
        if isinstance(hand, list) and hand:
            yield (f"hand{hi}", hand)


def simulate_sells(replay: Replay) -> dict[str, Any]:
    """Lockstep concurrent fill; return per-player sold, revenue, price PDFs."""
    n_players = len(replay.team_names)
    filled: dict[int, Counter[str]] = {p: Counter() for p in range(n_players)}
    revenue: dict[int, Counter[str]] = {p: Counter() for p in range(n_players)}
    price_pdf: dict[int, dict[str, dict[str, int]]] = {
        p: defaultdict(lambda: defaultdict(int)) for p in range(n_players)
    }
    events: list[SellEvent] = []
    unfilled: dict[int, Counter[str]] = {p: Counter() for p in range(n_players)}

    for step_idx, step in enumerate(replay.steps):
        if len(step) < n_players:
            continue
        prev_step = replay.steps[step_idx - 1] if step_idx > 0 else None
        recs = [step[p] for p in range(n_players)]
        obs0 = recs[0].observation
        day = int(obs0.get("day", 0))
        hour = int(obs0.get("hour", 0))
        market = obs0.get("market") or {}
        inv: dict[str, int] = {
            k: int(v) for k, v in (market.get("inventory") or {}).items()
        }

        states = [
            PlayerSellState(queues=_expand_sell_orders(recs[p].action.get("market")))
            for p in range(n_players)
        ]
        stock = [
            _sellable_stock_before_market(
                prev_step[p] if prev_step else None,
                recs[p],
            )
            for p in range(n_players)
        ]

        while True:
            products = [s.current_product() for s in states]
            if not any(products):
                break

            # Same snapshot quote for all units sold this round (README rule).
            round_prices: dict[str, int] = {}
            for prod in products:
                if prod and prod not in round_prices and prod in MARKET_PARAMS:
                    round_prices[prod] = quoted(prod, inv.get(prod, 10_000))

            any_sold = False
            for p, state in enumerate(states):
                prod = state.current_product()
                if not prod:
                    continue
                if prod not in MARKET_PARAMS:
                    unfilled[p][prod] += 1
                    state.advance()
                    continue
                if stock[p].get(prod, 0) <= 0:
                    unfilled[p][prod] += 1
                    state.advance()
                    continue
                price = round_prices[prod]
                filled[p][prod] += 1
                revenue[p][prod] += price
                price_pdf[p][prod][str(price)] += 1
                stock[p][prod] -= 1
                events.append(
                    SellEvent(step_idx, day, hour, p, prod, price)
                )
                cur = inv.get(prod, 10_000)
                if price > 1:
                    inv[prod] = cur + 1
                state.advance()
                any_sold = True

            if not any_sold:
                # All remaining blocked on stock — count rest as unfilled.
                for p, state in enumerate(states):
                    while state.remaining_units() > 0:
                        prod = state.current_product()
                        if prod:
                            unfilled[p][prod] += 1
                        state.advance()
                break

    per_player: dict[int, dict[str, Any]] = {}
    for p in range(n_players):
        per_player[p] = {
            "filled_units": dict(filled[p]),
            "revenue": dict(revenue[p]),
            "price_pdf": {
                prod: dict(counts) for prod, counts in price_pdf[p].items()
            },
            "unfilled_units": dict(unfilled[p]),
            "total_revenue": sum(revenue[p].values()),
        }

    return {
        "by_player": per_player,
        "events": [
            {
                "step": e.step,
                "day": e.day,
                "hour": e.hour,
                "player": e.player,
                "product": e.product,
                "price": e.price,
            }
            for e in events
        ],
    }
