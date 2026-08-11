"""Turn-by-turn execution: market, replan trigger, snake routing, tile ops."""

from __future__ import annotations

from collections import Counter

from agent import animal_rollouts, planner, rollouts

# Visit order from spawn (4,4); index 0..8 — bottom row, mid row, top row.
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

WHEAT_FEED_RESERVE_DAYS = 2


def _log(msg: str) -> None:
    print(msg, flush=True)


def _format_farmer(action: list) -> str:
    return " ".join(str(x) for x in action)


def _format_market(orders: list) -> str:
    parts = []
    for order in orders:
        parts.append(" ".join(str(x) for x in order))
    return " ".join(parts)


class Executor:
    def __init__(self) -> None:
        self.plan: list[dict] = []
        self.plant_profiles: dict[tuple[int, int], str] = {}
        self.animal_profiles: dict[tuple[int, int], str] = {}
        self.last_replan_day: int | None = None
        self._route_idx: int = 0

    def step(self, obs: dict) -> dict:
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        day = obs["day"]
        hour = obs["hour"]
        prices = obs["market"]["prices"]

        if hour == 0:
            self._route_idx = 0

        if hour == 0 and self._should_replan(obs, me, day):
            self._replan(obs, me, day, prices)

        market = self._market_orders(obs, me, private, day, prices)

        farmer_action, tile_note = self._next_action(obs, me, private, day)
        if market:
            _log(f"[exec] d={day} h={hour} market {_format_market(market)}")
        _log(
            f"[exec] d={day} h={hour} farmer {_format_farmer(farmer_action)}"
            + (f" {tile_note}" if tile_note else "")
        )

        return {"farmer": farmer_action, "hands": [], "market": market}

    @staticmethod
    def _entry_start(entry: dict) -> int:
        return entry.get("start_day", entry.get("plant_day", -1))

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

    def _sync_animal_profiles(self, me: dict) -> None:
        live = {
            (idx, tile["placed_day"])
            for idx in range(len(TILE_COORDS))
            if isinstance(tile := self._tile_at(me, idx), dict)
            and tile.get("kind") in ("COOP", "PASTURE")
            and tile.get("animal")
        }
        self.animal_profiles = {
            k: v for k, v in self.animal_profiles.items() if k in live
        }

    def _profile_for_plant(self, idx: int, planted_day: int) -> str:
        key = (idx, planted_day)
        if key in self.plant_profiles:
            return self.plant_profiles[key]
        for entry in self.plan:
            if (
                entry.get("kind", "crop") == "crop"
                and entry["tile"] == idx
                and self._entry_start(entry) == planted_day
            ):
                return entry.get("profile", "no_fert")
        return "no_fert"

    def _profile_for_animal(self, idx: int, placed_day: int) -> str:
        key = (idx, placed_day)
        if key in self.animal_profiles:
            return self.animal_profiles[key]
        for entry in self.plan:
            if (
                entry.get("kind") == "animal"
                and entry["tile"] == idx
                and self._entry_start(entry) == placed_day
            ):
                return entry.get("profile", "no_care")
        return "no_care"

    def _profile_for_tile(self, idx: int, tile: dict | None, day: int) -> str:
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            return self._profile_for_plant(idx, tile["planted_day"])
        if (
            isinstance(tile, dict)
            and tile.get("kind") in ("COOP", "PASTURE")
            and tile.get("animal")
            and tile.get("placed_day") is not None
        ):
            return self._profile_for_animal(idx, tile["placed_day"])
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
            if (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
                and self._crop_harvest_today(tile, day, profile)
            ):
                return True
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                return True
            if (
                isinstance(tile, dict)
                and tile.get("kind") in ("COOP", "PASTURE")
                and tile.get("animal")
            ):
                if self._animal_harvest_today(tile, day, profile):
                    return True
                if tile.get("consecutive_unfed", 0) >= 1:
                    return True
        for idx in _empty_tile_indices(me):
            if not any(
                entry["tile"] == idx and self._entry_start(entry) >= day
                for entry in self.plan
            ):
                return True
        return False

    def _replan(self, obs: dict, me: dict, day: int, prices: dict) -> None:
        self._sync_plant_profiles(me)
        self._sync_animal_profiles(me)
        states: list[planner.TileState | None] = [None] * len(TILE_COORDS)
        weed_tiles: set[int] = set()

        for idx in range(len(TILE_COORDS)):
            tile = self._tile_at(me, idx)
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                profile = self._profile_for_plant(idx, tile["planted_day"])
                states[idx] = (
                    idx,
                    tile["crop"],
                    tile["planted_day"],
                    profile,
                    "crop",
                )
            elif (
                isinstance(tile, dict)
                and tile.get("kind") in ("COOP", "PASTURE")
                and tile.get("animal")
            ):
                profile = self._profile_for_animal(idx, tile["placed_day"])
                states[idx] = (
                    idx,
                    tile["animal"],
                    tile["placed_day"],
                    profile,
                    "animal",
                )
            elif isinstance(tile, dict) and tile.get("kind") == "WEED":
                weed_tiles.add(idx)

        plannable = set(range(len(TILE_COORDS)))
        shops = obs.get("town", {}).get("unlocked_shops", [])
        demand = rollouts.shop_demand_by_product(shops)
        self.plan = planner.solve_plan(
            plannable,
            states,
            day,
            prices,
            weed_tiles=weed_tiles or None,
            shop_demand=demand,
        )
        self.plan = sorted(
            self.plan, key=lambda e: (self._entry_start(e), e["tile"])
        )
        self.last_replan_day = day
        _log(
            f"[executor] replan day={day} weeds={sorted(weed_tiles)} "
            f"plan={len(self.plan)}"
        )
        for entry in self.plan:
            if entry.get("kind") == "animal":
                _log(
                    f"  animal {entry['animal']} {entry['profile']} "
                    f"tile={entry['tile']} start={entry['start_day']}"
                )
            else:
                _log(
                    f"  crop {entry['crop']} {entry['profile']} "
                    f"tile={entry['tile']} start={entry['start_day']}"
                )

    def _placement_today(self, idx: int, day: int) -> dict | None:
        for entry in self.plan:
            if entry["tile"] == idx and self._entry_start(entry) == day:
                return entry
        return None

    def _build_entry_today(self, idx: int, day: int) -> dict | None:
        for entry in self.plan:
            if entry.get("kind") != "animal":
                continue
            if entry["tile"] == idx and self._entry_start(entry) == day + 1:
                return entry
        return None

    def _live_animal_count(self, me: dict) -> int:
        n = 0
        for idx in range(len(TILE_COORDS)):
            tile = self._tile_at(me, idx)
            if (
                isinstance(tile, dict)
                and tile.get("kind") in ("COOP", "PASTURE")
                and tile.get("animal")
            ):
                n += 1
        return n

    def _feed_ops_today(self, me: dict, day: int) -> int:
        count = 0
        for idx in range(len(TILE_COORDS)):
            tile = self._tile_at(me, idx)
            if not isinstance(tile, dict) or tile.get("kind") not in (
                "COOP",
                "PASTURE",
            ):
                continue
            if not tile.get("animal"):
                continue
            profile = self._profile_for_animal(idx, tile["placed_day"])
            age = day - tile["placed_day"]
            if "FEED" in animal_rollouts.actions_at_age(
                tile["animal"], age, profile
            ) and not tile.get("fed_today"):
                count += 1
        return count

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
    def _inv_shortfall(private: dict, product: str, need: int) -> int:
        inv = private["inventories"][0].get(product, 0)
        return max(0, need - inv)

    @staticmethod
    def _buy_deficit(private: dict, product: str, need: int) -> int:
        if need <= 0:
            return 0
        available = private["shed"].get(product, 0) + private["inventories"][
            0
        ].get(product, 0)
        return max(0, need - available)

    @staticmethod
    def _pickup_count(private: dict, product: str, need: int) -> int:
        shortfall = Executor._inv_shortfall(private, product, need)
        shed = private["shed"].get(product, 0)
        return min(shortfall, shed)

    def _tile0_pickup(self, me: dict, private: dict, day: int) -> list | None:
        """Shed-adjacent pickups when visiting tile 0 in snake order."""
        if (me["farmer"][0], me["farmer"][1]) not in SHED_ADJACENT:
            return None

        fert_ops = self._fert_ops_today(me, day)
        if fert_ops > 0:
            n = self._pickup_count(private, "FERTILIZER", fert_ops)
            if n > 0:
                return ["PICKUP", "FERTILIZER", n]

        feed_ops = self._feed_ops_today(me, day)
        if feed_ops > 0:
            n = self._pickup_count(private, "WHEAT", feed_ops)
            if n > 0:
                return ["PICKUP", "WHEAT", n]

        for entry in self.plan:
            if entry.get("kind") != "animal":
                continue
            if self._entry_start(entry) != day:
                continue
            animal = entry["animal"]
            if private["inventories"][0].get(animal, 0) <= 0:
                n = self._pickup_count(private, animal, 1)
                if n > 0:
                    return ["PICKUP", animal, n]
        return None

    def _market_orders(
        self, obs: dict, me: dict, private: dict, day: int, prices: dict
    ) -> list:
        orders: list = []
        live_animals = self._live_animal_count(me)
        wheat_reserve = live_animals * WHEAT_FEED_RESERVE_DAYS

        if day == rollouts.SEASON_DAYS - 1:
            fert = private["shed"].get("FERTILIZER", 0)
            if fert > 0:
                orders.append(["SELL", "FERTILIZER", fert])

        for crop, count in private["shed"].items():
            if count <= 0 or crop == "FERTILIZER":
                continue
            if crop == "WHEAT":
                sellable = max(0, count - wheat_reserve)
                if sellable > 0:
                    orders.append(["SELL", crop, sellable])
            else:
                orders.append(["SELL", crop, count])

        seeds = private["seeds"]
        needed_seeds: Counter[str] = Counter()
        for entry in self.plan:
            if entry.get("kind") != "crop":
                continue
            start = self._entry_start(entry)
            if start != day:
                continue
            tile = self._tile_at(me, entry["tile"])
            if tile is None or (
                isinstance(tile, dict) and tile.get("kind") == "WEED"
            ):
                needed_seeds[entry["crop"]] += 1

        money = me["money"]
        for crop in rollouts.crop_names():
            deficit = needed_seeds[crop] - seeds.get(crop, 0)
            if deficit <= 0:
                continue
            cost = rollouts.seed_cost(crop)
            affordable = min(deficit, money // cost) if cost else 0
            if affordable > 0:
                orders.append(["BUY_SEED", crop, affordable])
                money -= affordable * cost

        needed_animals: Counter[str] = Counter()
        for entry in self.plan:
            if entry.get("kind") != "animal":
                continue
            start = self._entry_start(entry)
            if start not in (day, day + 1):
                continue
            tile = self._tile_at(me, entry["tile"])
            if start == day:
                if isinstance(tile, dict) and tile.get("kind") in (
                    "COOP",
                    "PASTURE",
                ) and not tile.get("animal"):
                    needed_animals[entry["animal"]] += 1
            elif tile is None:
                needed_animals[entry["animal"]] += 1

        for animal in animal_rollouts.animal_names():
            shed_count = private["shed"].get(animal, 0)
            inv_count = private["inventories"][0].get(animal, 0)
            deficit = needed_animals[animal] - shed_count - inv_count
            if deficit <= 0:
                continue
            cost = animal_rollouts.animal_cost(animal)
            affordable = min(deficit, money // cost) if cost else 0
            if affordable > 0:
                orders.append(["BUY_ANIMAL", animal, affordable])
                money -= affordable * cost

        fert_ops = self._fert_ops_today(me, day)
        fert_deficit = self._buy_deficit(private, "FERTILIZER", fert_ops)
        if fert_deficit > 0:
            fert_cost = int(prices.get("FERTILIZER", 0) or 0)
            affordable = min(fert_deficit, money // fert_cost) if fert_cost else 0
            if affordable > 0:
                orders.append(["BUY_PRODUCT", "FERTILIZER", affordable])
                money -= affordable * fert_cost

        feed_ops = self._feed_ops_today(me, day)
        wheat_deficit = self._buy_deficit(private, "WHEAT", feed_ops)
        if wheat_deficit > 0:
            wheat_cost = int(prices.get("WHEAT", 0) or 0)
            affordable = min(wheat_deficit, money // wheat_cost) if wheat_cost else 0
            if affordable > 0:
                orders.append(["BUY_PRODUCT", "WHEAT", affordable])
                money -= affordable * wheat_cost

        return orders[:10]

    def _next_action(
        self, obs: dict, me: dict, private: dict, day: int
    ) -> tuple[list, str]:
        """Strict daily snake: tiles 0..8 in order; one farmer action per turn."""
        fx, fy = me["farmer"]

        if self._route_idx >= len(TILE_COORDS):
            return ["PASS"], "route=done"

        idx = self._route_idx
        tx, ty = TILE_COORDS[idx]
        tile_note = f"tile={idx} route={self._route_idx}"

        if (fx, fy) != (tx, ty):
            move = _step_toward(fx, fy, tx, ty)
            return [move], f"{tile_note} move"

        if idx == 0:
            pickup = self._tile0_pickup(me, private, day)
            if pickup:
                return pickup, f"{tile_note} pickup"

        pending = self._pending_for_tile(obs, me, private, idx, day)
        if pending:
            for act in pending:
                action = self._format_action(
                    act, obs, me, private, idx, day
                )
                if action:
                    return action, f"{tile_note} op={act}"

        # Empty tile: advance route and move toward next tile (no PASS stop).
        self._route_idx += 1
        if self._route_idx >= len(TILE_COORDS):
            return ["PASS"], "route=done"

        next_idx = self._route_idx
        ntx, nty = TILE_COORDS[next_idx]
        if (fx, fy) != (ntx, nty):
            move = _step_toward(fx, fy, ntx, nty)
            return [move], f"tile={next_idx} route={self._route_idx} skip->move"
        return ["PASS"], f"tile={next_idx} route={self._route_idx} skip"

    def _pending_for_tile(
        self, obs: dict, me: dict, private: dict, idx: int, day: int
    ) -> list[str]:
        tile = self._tile_at(me, idx)

        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            return ["DIG"]

        build_entry = self._build_entry_today(idx, day)
        if tile is None and build_entry:
            animal = build_entry["animal"]
            return [animal_rollouts.build_action_for(animal)]

        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            crop = tile["crop"]
            age = day - tile["planted_day"]
            profile = self._profile_for_tile(idx, tile, day)
            actions = [
                a
                for a in rollouts.actions_at_age(crop, age, profile)
                if a != "PLANT"
            ]
            return _filter_crop_pending(tile, actions, private)

        if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
            if tile.get("animal"):
                return self._animal_pending_for_tile(idx, tile, day, private)
            entry = self._placement_today(idx, day)
            if entry and entry.get("kind") == "animal":
                animal = entry["animal"]
                if private["inventories"][0].get(animal, 0) > 0:
                    return [f"PLACE {animal}"]
            return []

        if tile is None:
            entry = self._placement_today(idx, day)
            if entry and entry.get("kind") == "crop":
                crop = entry["crop"]
                profile = entry.get("profile", "no_fert")
                if private["seeds"].get(crop, 0) <= 0:
                    return []
                return list(rollouts.actions_at_age(crop, 0, profile))

        return []

    def _animal_pending_for_tile(
        self, idx: int, tile: dict, day: int, private: dict
    ) -> list[str]:
        animal = tile["animal"]
        profile = self._profile_for_animal(idx, tile["placed_day"])
        age = day - tile["placed_day"]
        raw = animal_rollouts.actions_at_age(animal, age, profile)
        wheat = private["inventories"][0].get("WHEAT", 0)
        pending: list[str] = []
        for action in raw:
            if action == "PLACE":
                continue
            if action == "FEED" and (
                tile.get("fed_today") or wheat <= 0
            ):
                continue
            if action == "CARE" and tile.get("cared_today"):
                continue
            if action == "HARVEST" and tile.get("yield_units", 0) <= 0:
                continue
            if action == "COLLECT_FERTILIZER" and not tile.get(
                "fertilizer_available"
            ):
                continue
            pending.append(action)
        if tile.get("yield_units", 0) > 0 and "HARVEST" not in pending:
            pending.insert(0, "HARVEST")
        return pending

    def _format_action(
        self,
        action: str,
        obs: dict,
        me: dict,
        private: dict,
        idx: int,
        day: int,
    ) -> list | None:
        tile = self._tile_at(me, idx)

        if action in ("BUILD_COOP", "BUILD_PASTURE"):
            if tile is not None:
                return None
            return [action]

        if action.startswith("PLACE"):
            animal = action.split()[1] if " " in action else None
            if not animal:
                entry = self._placement_today(idx, day)
                if not entry or entry.get("kind") != "animal":
                    return None
                animal = entry["animal"]
            if private["inventories"][0].get(animal, 0) <= 0:
                return None
            if not isinstance(tile, dict) or tile.get("kind") not in (
                "COOP",
                "PASTURE",
            ):
                return None
            if tile.get("animal"):
                return None
            profile = "no_care"
            entry = self._placement_today(idx, day)
            if entry:
                profile = entry.get("profile", "no_care")
            self.animal_profiles[(idx, day)] = profile
            return ["PLACE", animal]

        if action == "PLANT":
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

        if action == "FEED":
            if private["inventories"][0].get("WHEAT", 0) <= 0:
                return None
            return ["FEED"]

        if action in ("WATER", "HARVEST", "DIG", "CARE", "COLLECT_FERTILIZER"):
            return [action]

        return None

    @staticmethod
    def _crop_harvest_today(tile, day: int, profile: str = "no_fert") -> bool:
        if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
            return False
        crop = tile["crop"]
        age = day - tile["planted_day"]
        if age in rollouts.harvest_ages(crop, profile):
            return True
        actions = rollouts.actions_at_age(crop, age, profile)
        return "HARVEST" in actions and tile.get("yield_units", 0) > 0

    @staticmethod
    def _animal_harvest_today(tile, day: int, profile: str = "no_care") -> bool:
        if not isinstance(tile, dict) or tile.get("kind") not in ("COOP", "PASTURE"):
            return False
        if not tile.get("animal"):
            return False
        animal = tile["animal"]
        age = day - tile["placed_day"]
        if age in animal_rollouts.harvest_ages(animal, profile):
            return tile.get("yield_units", 0) > 0
        actions = animal_rollouts.actions_at_age(animal, age, profile)
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


def _filter_crop_pending(
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
