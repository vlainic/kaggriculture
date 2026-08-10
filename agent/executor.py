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

# Shed-adjacent tiles (default boardSize=10).
SHED_ADJACENT: frozenset[tuple[int, int]] = frozenset(
    {(4, 4), (5, 4), (4, 5), (5, 5)}
)


class Executor:
    def __init__(self) -> None:
        # Full list of placements — multiple plantings per tile over the season.
        self.plan: list[dict] = []
        # Persisted profile for live plants: (tile_idx, planted_day) -> profile
        self.plant_profiles: dict[tuple[int, int], str] = {}
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

        market = self._market_orders(obs, me, private, day, prices)

        ops_today = self._fert_ops_today(me, day)
        if ops_today > 0 and (fx, fy) in SHED_ADJACENT:
            pickup_n = self._fert_pickup_count(private, ops_today)
            if pickup_n > 0:
                return {
                    "farmer": ["PICKUP", "FERTILIZER", pickup_n],
                    "hands": [],
                    "market": market,
                }

        target_idx, pending = self._next_work(obs, me, private, day)
        if target_idx is None:
            return {"farmer": ["PASS"], "hands": [], "market": market}

        tx, ty = TILE_COORDS[target_idx]
        if (fx, fy) != (tx, ty):
            move = _step_toward(fx, fy, tx, ty)
            return {"farmer": [move], "hands": [], "market": market}

        if pending:
            for act in pending:
                action = self._format_action(
                    act, obs, me, private, target_idx, day
                )
                if action:
                    return {"farmer": action, "hands": [], "market": market}

        return {"farmer": ["PASS"], "hands": [], "market": market}

    def _sync_plant_profiles(self, me: dict) -> None:
        live = {
            (idx, tile["planted_day"])
            for idx in range(len(TILE_COORDS))
            if isinstance(tile := self._tile_at(me, idx), dict)
            and tile.get("kind") == "PLANT"
        }
        self.plant_profiles = {
            k: v for k, v in self.plant_profiles.items() if k in live
        }

    def _profile_for_plant(self, idx: int, planted_day: int) -> str:
        key = (idx, planted_day)
        if key in self.plant_profiles:
            return self.plant_profiles[key]
        for entry in self.plan:
            if entry["tile"] == idx and entry["plant_day"] == planted_day:
                return entry.get("profile", "no_fert")
        return "no_fert"

    def _profile_for_tile(self, idx: int, tile: dict | None, day: int) -> str:
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            return self._profile_for_plant(idx, tile["planted_day"])
        entry = self._placement_today(idx, day)
        if entry:
            return entry.get("profile", "no_fert")
        return "no_fert"

    def _should_replan(self, obs: dict, me: dict, day: int) -> bool:
        if self.last_replan_day is None:
            return True
        for idx in range(len(TILE_COORDS)):
            tile = self._tile_at(me, idx)
            profile = self._profile_for_tile(idx, tile, day)
            if self._harvest_today(tile, day, profile):
                return True
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                return True
        empty = _empty_tile_indices(me)
        return (
            self._last_empty_tiles is not None
            and empty != self._last_empty_tiles
        )

    def _replan(self, obs: dict, me: dict, day: int, prices: dict) -> None:
        self._sync_plant_profiles(me)
        states: list[planner.TileState | None] = [None] * len(TILE_COORDS)
        weed_tiles: set[int] = set()

        for idx in range(len(TILE_COORDS)):
            tile = self._tile_at(me, idx)
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                profile = self._profile_for_plant(idx, tile["planted_day"])
                states[idx] = (idx, tile["crop"], tile["planted_day"], profile)
            elif isinstance(tile, dict) and tile.get("kind") == "WEED":
                weed_tiles.add(idx)

        plannable = set(range(len(TILE_COORDS)))
        shops = obs.get("town", {}).get("unlocked_shops", [])
        demand = rollouts.shop_demand_by_crop(shops)
        self.plan = planner.solve_plan(
            plannable,
            states,
            day,
            prices,
            weed_tiles=weed_tiles or None,
            shop_demand=demand,
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

    def _fert_ops_today(self, me: dict, day: int) -> int:
        count = 0
        for idx in range(len(TILE_COORDS)):
            tile = self._tile_at(me, idx)
            if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
                continue
            profile = self._profile_for_tile(idx, tile, day)
            crop = tile["crop"]
            age = day - tile["planted_day"]
            actions = rollouts.actions_at_age(crop, age, profile)
            if "FERTILIZE" in actions:
                count += 1
        return count

    @staticmethod
    def _fert_inv_shortfall(private: dict, ops_today: int) -> int:
        inv = private["inventories"][0].get("FERTILIZER", 0)
        return max(0, ops_today - inv)

    @staticmethod
    def _fert_buy_deficit(private: dict, ops_today: int) -> int:
        if ops_today <= 0:
            return 0
        available = private["shed"].get("FERTILIZER", 0) + private[
            "inventories"
        ][0].get("FERTILIZER", 0)
        return max(0, ops_today - available)

    @staticmethod
    def _fert_pickup_count(private: dict, ops_today: int) -> int:
        shortfall = Executor._fert_inv_shortfall(private, ops_today)
        shed = private["shed"].get("FERTILIZER", 0)
        return min(shortfall, shed)

    def _market_orders(
        self, obs: dict, me: dict, private: dict, day: int, prices: dict
    ) -> list:
        orders: list = []
        for crop, count in private["shed"].items():
            if count > 0 and crop != "FERTILIZER":
                orders.append(["SELL", crop, count])

        seeds = private["seeds"]
        needed: Counter[str] = Counter()
        for entry in self.plan:
            if entry["plant_day"] in (day, day + 1):
                tile = self._tile_at(me, entry["tile"])
                if tile is None or entry["plant_day"] == day + 1:
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
                            and self._harvest_today(
                                tile,
                                day,
                                self._profile_for_tile(entry["tile"], tile, day),
                            )
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

        ops_today = self._fert_ops_today(me, day)
        fert_deficit = self._fert_buy_deficit(private, ops_today)
        if fert_deficit > 0:
            fert_cost = int(prices.get("FERTILIZER", 0) or 0)
            affordable = min(fert_deficit, money // fert_cost) if fert_cost else 0
            if affordable > 0:
                orders.append(["BUY_PRODUCT", "FERTILIZER", affordable])

        return orders[:10]

    def _next_work(
        self, obs: dict, me: dict, private: dict, day: int
    ) -> tuple[int | None, list[str]]:
        fx, fy = me["farmer"]
        for idx, (tx, ty) in enumerate(TILE_COORDS):
            if (fx, fy) == (tx, ty):
                pending = self._pending_for_tile(obs, me, private, idx, day)
                if pending:
                    return idx, pending
                break

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
            profile = self._profile_for_tile(idx, tile, day)
            actions = [
                a
                for a in rollouts.actions_at_age(crop, age, profile)
                if a != "PLANT"
            ]
            return _filter_pending(tile, actions, private)

        if tile is None:
            entry = self._placement_today(idx, day)
            if entry:
                crop = entry["crop"]
                profile = entry.get("profile", "no_fert")
                if private["seeds"].get(crop, 0) <= 0:
                    return []
                return list(rollouts.actions_at_age(crop, 0, profile))

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
            profile = entry.get("profile", "no_fert") if entry else "no_fert"
            self.plant_profiles[(idx, day)] = profile
            return ["PLANT", crop]
        if action == "FERTILIZE":
            if private["inventories"][0].get("FERTILIZER", 0) <= 0:
                return None
            return ["FERTILIZE"]
        if action in ("WATER", "HARVEST", "DIG"):
            return [action]
        return None

    @staticmethod
    def _harvest_today(tile, day: int, profile: str = "no_fert") -> bool:
        if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
            return False
        crop = tile["crop"]
        age = day - tile["planted_day"]
        if age in rollouts.harvest_ages(crop, profile):
            return True
        actions = rollouts.actions_at_age(crop, age, profile)
        return "HARVEST" in actions and tile.get("yield_units", 0) > 0

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


def _filter_pending(
    tile: dict, actions: list[str], private: dict | None = None
) -> list[str]:
    pending = []
    for action in actions:
        if action == "WATER" and tile.get("watered_today"):
            continue
        if action == "HARVEST" and tile.get("yield_units", 0) <= 0:
            continue
        if (
            action == "FERTILIZE"
            and private is not None
            and private["inventories"][0].get("FERTILIZER", 0) <= 0
        ):
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
