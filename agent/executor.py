"""Turn-by-turn execution: market, replan trigger, snake routing, tile ops."""

from __future__ import annotations

from collections import Counter

from agent import planner, rollouts

# Visit order from spawn (4,4); index 0..8
TILE_COORDS: list[tuple[int, int]] = [
    (4, 4),
    (3, 4),
    (2, 4),
    (2, 3),
    (3, 3),
    (4, 3),
    (4, 2),
    (3, 2),
    (2, 2),
]


class Executor:
    def __init__(self) -> None:
        # Full list of placements — multiple plantings per tile over the season.
        self.plan: list[dict] = []
        self.last_replan_day: int | None = None
        self._last_empty_tiles: frozenset[int] | None = None

    def step(self, obs: dict) -> dict:
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        day = obs["day"]
        hour = obs["hour"]
        fx, fy = me["farmer"]
        prices = obs["market"]["prices"]

        if hour == 0 and self._should_replan(obs, me, day):
            self._replan(obs, me, day, prices)

        market = self._market_orders(obs, me, private, day)

        target_idx, pending = self._next_work(obs, me, private, day)
        if target_idx is None:
            return {"farmer": ["PASS"], "hands": [], "market": market}

        tx, ty = TILE_COORDS[target_idx]
        if (fx, fy) != (tx, ty):
            move = _step_toward(fx, fy, tx, ty)
            return {"farmer": [move], "hands": [], "market": market}

        if pending:
            for act in pending:
                action = self._format_action(act, obs, me, private, target_idx, day)
                if action:
                    return {"farmer": action, "hands": [], "market": market}

        return {"farmer": ["PASS"], "hands": [], "market": market}

    def _should_replan(self, obs: dict, me: dict, day: int) -> bool:
        if self.last_replan_day is None:
            return True
        for idx in range(len(TILE_COORDS)):
            tile = self._tile_at(me, idx)
            if _harvest_today(tile, day):
                return True
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                return True
        empty = _empty_tile_indices(me)
        return (
            self._last_empty_tiles is not None
            and empty != self._last_empty_tiles
        )

    def _replan(self, obs: dict, me: dict, day: int, prices: dict) -> None:
        states: list[tuple[int, str, int] | None] = [None] * len(TILE_COORDS)
        weed_tiles: set[int] = set()

        for idx in range(len(TILE_COORDS)):
            tile = self._tile_at(me, idx)
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                states[idx] = (idx, tile["crop"], tile["planted_day"])
            elif isinstance(tile, dict) and tile.get("kind") == "WEED":
                weed_tiles.add(idx)

        plannable = set(range(len(TILE_COORDS)))
        self.plan = planner.solve_plan(
            plannable, states, day, prices, weed_tiles=weed_tiles or None
        )
        self.plan = sorted(self.plan, key=lambda e: (e["plant_day"], e["tile"]))
        self.last_replan_day = day
        self._last_empty_tiles = _empty_tile_indices(me)
        print(
            f"[executor] replan day={day} weeds={sorted(weed_tiles)} "
            f"plan={len(self.plan)} "
            f"plant_days={sorted({e['plant_day'] for e in self.plan})[:12]}"
        )

    def _placement_today(self, idx: int, day: int) -> dict | None:
        for entry in self.plan:
            if entry["tile"] == idx and entry["plant_day"] == day:
                return entry
        return None

    def _market_orders(self, obs: dict, me: dict, private: dict, day: int) -> list:
        orders: list = []
        for crop, count in private["shed"].items():
            if count > 0:
                orders.append(["SELL", crop, count])

        # Buy seeds for today's plantings (and tomorrow, so they land in time).
        seeds = private["seeds"]
        needed: Counter[str] = Counter()
        for entry in self.plan:
            if entry["plant_day"] in (day, day + 1):
                tile = self._tile_at(me, entry["tile"])
                if tile is None or entry["plant_day"] == day + 1:
                    # tomorrow: count even if currently occupied (harvest frees it)
                    if (
                        entry["plant_day"] == day
                        and tile is not None
                        and not (
                            isinstance(tile, dict) and tile.get("kind") == "WEED"
                        )
                    ):
                        continue
                    if (
                        entry["plant_day"] == day + 1
                        and tile is not None
                        and not (
                            isinstance(tile, dict)
                            and tile.get("kind") == "PLANT"
                            and _harvest_today(tile, day)
                        )
                    ):
                        continue
                    needed[entry["crop"]] += 1

        money = me["money"]
        for crop in rollouts.crop_names():
            deficit = needed[crop] - seeds.get(crop, 0)
            if deficit <= 0:
                continue
            cost = rollouts.seed_cost(crop)
            affordable = min(deficit, money // cost) if cost else 0
            if affordable > 0:
                orders.append(["BUY_SEED", crop, affordable])
                money -= affordable * cost

        return orders[:10]

    def _next_work(
        self, obs: dict, me: dict, private: dict, day: int
    ) -> tuple[int | None, list[str]]:
        for idx in range(len(TILE_COORDS)):
            tile = self._tile_at(me, idx)
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                return idx, ["DIG"]

        for idx in range(len(TILE_COORDS)):
            pending = self._pending_for_tile(obs, me, private, idx, day)
            if pending:
                return idx, pending
        return None, []

    def _pending_for_tile(
        self, obs: dict, me: dict, private: dict, idx: int, day: int
    ) -> list[str]:
        tile = self._tile_at(me, idx)

        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            return ["DIG"]

        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            crop = tile["crop"]
            age = day - tile["planted_day"]
            actions = [
                a for a in rollouts.actions_at_age(crop, age) if a != "PLANT"
            ]
            return _filter_pending(tile, actions)

        if tile is None:
            entry = self._placement_today(idx, day)
            if entry:
                crop = entry["crop"]
                if private["seeds"].get(crop, 0) <= 0:
                    return []
                return list(rollouts.actions_at_age(crop, 0))

        return []

    def _format_action(
        self,
        action: str,
        obs: dict,
        me: dict,
        private: dict,
        idx: int,
        day: int,
    ) -> list | None:
        if action == "PLANT":
            tile = self._tile_at(me, idx)
            if tile is not None:
                return None
            entry = self._placement_today(idx, day)
            crop = entry["crop"] if entry else None
            if not crop:
                return None
            if private["seeds"].get(crop, 0) <= 0:
                return None
            return ["PLANT", crop]
        if action in ("WATER", "HARVEST", "DIG"):
            return [action]
        return None

    @staticmethod
    def _tile_at(me: dict, idx: int):
        x, y = TILE_COORDS[idx]
        return me["tiles"][y][x]


def _empty_tile_indices(me: dict) -> frozenset[int]:
    empty: set[int] = set()
    for idx in range(len(TILE_COORDS)):
        if Executor._tile_at(me, idx) is None:
            empty.add(idx)
    return frozenset(empty)


def _harvest_today(tile, day: int) -> bool:
    if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
        return False
    crop = tile["crop"]
    age = day - tile["planted_day"]
    if age in rollouts.harvest_ages(crop):
        return True
    actions = rollouts.actions_at_age(crop, age)
    return "HARVEST" in actions and tile.get("yield_units", 0) > 0


def _filter_pending(tile: dict, actions: list[str]) -> list[str]:
    pending = []
    for action in actions:
        if action == "WATER" and tile.get("watered_today"):
            continue
        if action == "HARVEST" and tile.get("yield_units", 0) <= 0:
            continue
        pending.append(action)
    return pending


def _step_toward(fx: int, fy: int, tx: int, ty: int) -> str:
    if tx > fx:
        return "EAST"
    if tx < fx:
        return "WEST"
    if ty > fy:
        return "SOUTH"
    if ty < fy:
        return "NORTH"
    return "PASS"


_controller = Executor()


def step(obs: dict) -> dict:
    return _controller.step(obs)
