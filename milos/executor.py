"""Milos farmer executor — fixed tile cursor + rollout-driven tile ops."""

from __future__ import annotations

import copy
import re

from milos import (
    market,
    planner,
    rollouts,
    script,
    sell_dp,
    sim_apply,
    tile_ops,
    workers,
    zoning,
)
from milos.zoning import NET_TILE_OPS

_DEBUG = True

_EXECUTOR: Executor | None = None

_TILE_OP_VERBS = frozenset({
    "PLANT", "WATER", "FERTILIZE", "HARVEST", "FEED", "CARE", "DIG", "PLACE",
    "BUILD_COOP", "BUILD_PASTURE", "COLLECT_FERTILIZER", "PICKUP", "DROP",
})
_MOVE_VERBS = frozenset({"NORTH", "SOUTH", "EAST", "WEST"})


def _log(msg: str) -> None:
    print(msg, flush=True)


def _dbg(msg: str) -> None:
    if _DEBUG:
        print(msg, flush=True)


def _fmt(action: list) -> str:
    return " ".join(str(x) for x in action)


def _step_toward(fx: int, fy: int, tx: int, ty: int) -> str:
    if fx < tx:
        return "EAST"
    if fx > tx:
        return "WEST"
    if fy < ty:
        return "SOUTH"
    if fy > ty:
        return "NORTH"
    return "PASS"


def _owned_shed_tiles(me: dict) -> frozenset[tuple[int, int]]:
    return frozenset(
        (x, y)
        for x, y in workers.SHED_ADJACENT
        if me["tiles"][y][x] != "LOCKED"
    )


def _step_to_owned_shed(me: dict, fx: int, fy: int) -> str | None:
    owned = _owned_shed_tiles(me)
    if not owned or (fx, fy) in owned:
        return None
    tx, ty = min(owned, key=lambda p: abs(p[0] - fx) + abs(p[1] - fy))
    return _step_toward(fx, fy, tx, ty)


def _tile_at(me: dict, idx: int):
    x, y = workers.TILE_COORDS[idx]
    return me["tiles"][y][x]


def _zone_animal_crop_ops(me: dict, worker: str) -> tuple[int, int]:
    """Count COOP/PASTURE and PLANT structures in a zone (for [hands] diagnostics)."""
    animal = 0
    crop = 0
    for idx in workers.WORKER_TILES[worker]:
        tile = _tile_at(me, idx)
        if not isinstance(tile, dict):
            continue
        kind = tile.get("kind")
        if kind in ("COOP", "PASTURE"):
            animal += 1
        elif kind == "PLANT":
            crop += 1
    return animal, crop


def _dawn_empty(me: dict, idx: int, day: int) -> bool:
    tile = _tile_at(me, idx)
    if tile is None:
        return True
    return planner.is_buy_morning_locked(tile, idx, day, me)


def _zone_empty(me: dict, worker: str) -> int:
    n = 0
    for idx in workers.WORKER_TILES[worker]:
        tile = _tile_at(me, idx)
        if tile is None:
            n += 1
    return n


def _manhattan(fx: int, fy: int, tx: int, ty: int) -> int:
    return abs(fx - tx) + abs(fy - ty)


def _inv_nonempty(private: dict, inv_idx: int) -> bool:
    inv = (
        private["inventories"][inv_idx]
        if inv_idx < len(private["inventories"])
        else {}
    )
    return any(v > 0 for v in inv.values())


class Executor:
    def __init__(self) -> None:
        self._cursor = 0
        self._endgame_done = {w: set() for w in workers.WORKERS}
        self._endgame_exhausted = {w: set() for w in workers.WORKERS}
        self._endgame_harvested = {w: set() for w in workers.WORKERS}
        self._tile_state: dict[int, dict] = {}
        self._empty_at_dawn: set[int] = set()
        self._day0_productive = False
        self._day = 0
        self._hour = 0
        self._tile_ops_today = {w: 0 for w in workers.WORKERS}
        for idx in range(workers.NUM_TILES):
            queue = script.TILE_QUEUES.get(idx, [])
            first_lag = queue[0].start_lag if queue else 0
            self._tile_state[idx] = {
                "queue_idx": 0,
                "lag": first_lag,
                "gap": 0,
                "pending_dig": False,
                "dig_plant_ok": False,
                "active": False,
                "fert_today": False,
            }

    def step(self, obs: dict) -> dict:
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        day = obs["day"]
        hour = obs["hour"]
        self._day, self._hour = day, hour

        if hour == 0:
            self._on_new_day(me, day)
            if day == 1 and not self._day0_productive:
                _log("[exec] WARN day-0 had zero BUY_SEED and zero PLANT")
            if day <= script.SEASON_LAST_DAY:
                if 0 < day < script.SEASON_LAST_DAY:
                    try:
                        planner.replan(obs, script.TILE_QUEUES, self._tile_state)
                    except Exception as exc:
                        _log(f"[planner] replan failed d={day}: {exc}")
                try:
                    wheat_feed = script.total_wheat_feed_need(
                        me, self._tile_state, private
                    )
                    sell_dp.replan(obs, self._tile_state, wheat_feed_reserve=wheat_feed)
                except Exception as exc:
                    _log(f"[sell_dp] replan failed d={day}: {exc}")

        if hour == 0:
            self._log_snap(obs, me, day, hour)
            self._log_hand_queues(obs, me, private, day)
            self._log_stuck_tiles(me, day)
        orders = market.build_orders(
            obs, me, private, day, hour, self._tile_state, self._empty_at_dawn
        )
        harvest_only = day >= script.SEASON_LAST_DAY

        if market.defer_farmer_hour0(hour, day):
            farmer, fnote = ["PASS"], "market-hour"
            hand_results = [(["PASS"], "market-hour") for _ in me["hands"]]
        else:
            farmer, fnote = self._farmer_action(
                me, private, day, hour, harvest_only
            )
            hand_results = [(["PASS"], "") for _ in me["hands"]]
        hands = [r[0] for r in hand_results]

        if orders:
            _log(f"[exec] d={day} h={hour} market {' '.join(_fmt(o) for o in orders)}")
        if day == 0:
            if any(o and o[0] == "BUY_SEED" for o in orders):
                self._day0_productive = True
            if farmer and farmer[0] == "PLANT":
                self._day0_productive = True
            for act in hands:
                if act and act[0] == "PLANT":
                    self._day0_productive = True
        _log(
            f"[exec] d={day} h={hour} farmer {_fmt(farmer)}"
            + (f" {fnote}" if fnote else "")
        )
        for i, (act, note) in enumerate(hand_results):
            w = workers.worker_for_hand_idx(i)
            pos = tuple(me["hands"][i]) if i < len(me["hands"]) else None
            adj = int(pos in workers.SHED_ADJACENT) if pos else 0
            owned = (
                int(pos in _owned_shed_tiles(me))
                if pos is not None
                else 0
            )
            _log(
                f"[exec] d={day} h={hour} hand{i}={w} {_fmt(act)} "
                f"pos={pos} adj={adj} owned={owned}"
                + (f" {note}" if note else "")
            )

        return {"farmer": farmer, "hands": hands, "market": orders}

    def _on_new_day(self, me: dict, day: int) -> None:
        self._cursor = 0
        for w in workers.WORKERS:
            self._tile_ops_today[w] = 0
            self._endgame_exhausted[w] = set()
            self._endgame_harvested[w] = set()

        for idx in range(workers.NUM_TILES):
            st = self._tile_state[idx]
            st["dig_plant_ok"] = False
            st["fert_today"] = False
            if day > 0:
                if st["lag"] > 0:
                    st["lag"] -= 1
                if st["gap"] > 0:
                    st["gap"] -= 1

            tile = _tile_at(me, idx)
            empty = tile is None
            if st["active"] and empty:
                item = tile_ops.current_queue_item(idx, st["queue_idx"])
                qi, lag, gap, dig = tile_ops.on_lifecycle_end(
                    idx, st["queue_idx"], item, st["pending_dig"]
                )
                st["queue_idx"] = qi
                st["lag"] = max(st["lag"], lag)
                st["gap"] = max(st["gap"], gap)
                st["pending_dig"] = dig
                st["active"] = False
            elif not empty:
                st["active"] = True

        self._empty_at_dawn = {
            idx for idx in range(workers.NUM_TILES) if _dawn_empty(me, idx, day)
        }
        ne_locked = sum(
            1
            for idx in range(workers.NUM_TILES)
            if planner.is_buy_morning_locked(_tile_at(me, idx), idx, day, me)
        )
        _log(
            f"[exec] d={day} dawn_empty={len(self._empty_at_dawn)} "
            f"dawn_ne_locked={ne_locked}"
        )
        if day >= script.SEASON_LAST_DAY:
            self._endgame_done = {w: set() for w in workers.WORKERS}

    def _classify_forecast_bucket(self, action: list) -> str:
        if not action or action[0] == "PASS":
            return "pass"
        if action[0] in _MOVE_VERBS:
            return "move"
        return "tile_ops"

    def forecast_day_counts(
        self, obs: dict, me: dict, private: dict, day: int
    ) -> dict:
        """Dry-run farmer hours 0..23 after h0 market on copied state."""
        saved_cursor = self._cursor
        saved_tile_state = copy.deepcopy(self._tile_state)
        saved_ops = dict(self._tile_ops_today)
        saved_endgame_done = {w: set(s) for w, s in self._endgame_done.items()}
        saved_endgame_exhausted = {
            w: set(s) for w, s in self._endgame_exhausted.items()
        }
        saved_endgame_harvested = {
            w: set(s) for w, s in self._endgame_harvested.items()
        }

        me_c = copy.deepcopy(me)
        priv_c = copy.deepcopy(private)
        self._cursor = 0
        self._tile_ops_today = {w: 0 for w in workers.WORKERS}
        self._tile_state = copy.deepcopy(saved_tile_state)

        prices = obs["market"]["prices"]
        orders = market.build_orders(
            obs,
            me_c,
            priv_c,
            day,
            0,
            self._tile_state,
            self._empty_at_dawn,
        )
        sim_apply.apply_market_orders(me_c, priv_c, orders, prices)

        counts = {"tile_ops": 0, "move": 0, "pass": 0}
        by_tile: dict[int, list[str]] = {}
        extra_verbs: list[str] = []
        harvest_only = day >= script.SEASON_LAST_DAY
        tile_note_re = re.compile(r"(?<!>)t(\d+)$")

        for hour in range(24):
            note = ""
            if market.defer_farmer_hour0(hour, day):
                action = ["PASS"]
            else:
                action, note = self._farmer_action(
                    me_c, priv_c, day, hour, harvest_only
                )
                sim_apply.apply_farmer_action(
                    me_c,
                    priv_c,
                    day,
                    action,
                    self._tile_state,
                    inv_idx=self._inv_idx("farmer"),
                )
            verb = action[0] if action else "PASS"
            bucket = self._classify_forecast_bucket(action)
            counts[bucket] += 1
            if bucket == "tile_ops":
                m = tile_note_re.search(note or "")
                if m:
                    tnum = int(m.group(1))
                    by_tile.setdefault(tnum, []).append(verb)
                else:
                    extra_verbs.append(verb)

        self._cursor = saved_cursor
        self._tile_state = saved_tile_state
        self._tile_ops_today = saved_ops
        self._endgame_done = saved_endgame_done
        self._endgame_exhausted = saved_endgame_exhausted
        self._endgame_harvested = saved_endgame_harvested
        counts["by_tile"] = by_tile
        counts["extra_verbs"] = extra_verbs
        return counts

    def _log_hand_queues(self, obs: dict, me: dict, private: dict, day: int) -> None:
        forecast = self.forecast_day_counts(obs, me, private, day)
        for w in workers.WORKERS:
            tiles = workers.WORKER_TILES.get(w, ())
            if not tiles:
                continue
            q = sum(
                1 for idx in tiles if script.TILE_QUEUES.get(idx)
            )
            empty = sum(1 for idx in tiles if _tile_at(me, idx) is None)
            locked = sum(
                1
                for idx in tiles
                if planner.is_buy_morning_locked(_tile_at(me, idx), idx, day, me)
            )
            live = sum(
                1
                for idx in tiles
                if isinstance(_tile_at(me, idx), dict)
                and _tile_at(me, idx).get("kind") in ("PLANT", "COOP", "PASTURE")
            )
            animal, crop = _zone_animal_crop_ops(me, w)
            if w == "farmer":
                fc = forecast
            else:
                fc = {"tile_ops": 0, "move": 0, "pass": 0, "by_tile": {}}
            _log(
                f"[hands] d={day} h0 {w} NUM_ACTIVE_HIRES={planner.NUM_ACTIVE_HIRES} "
                f"qtiles={q} empty={empty} locked={locked} live={live} "
                f"animal={animal} crop={crop} est_ops={fc['tile_ops']:g}"
            )
            if w == "farmer":
                parts = []
                for tnum in sorted(fc.get("by_tile") or {}):
                    verbs = ",".join(fc["by_tile"][tnum])
                    parts.append(f"t{tnum}={verbs}")
                _log(f"[theo] d={day} {w} " + (" ".join(parts) if parts else "-"))
                extra = fc.get("extra_verbs") or []
                _log(
                    f"[theo_extra] d={day} {w} "
                    + (",".join(extra) if extra else "-")
                )

    def _mark_endgame_tile_exhausted(
        self, worker: str, idx: int, me: dict, action: list
    ) -> None:
        """Do not repeat HARVEST on same tile after DROP clears _endgame_done."""
        if not action:
            return
        verb = action[0]
        if verb == "HARVEST":
            self._endgame_harvested[worker].add(idx)
            return
        tile = _tile_at(me, idx)
        if not isinstance(tile, dict):
            return
        if verb == "COLLECT_FERTILIZER" and tile.get("fertilizer_available"):
            self._endgame_exhausted[worker].add(idx)

    def _log_stuck_tiles(self, me: dict, day: int) -> None:
        if not _DEBUG:
            return
        for idx in range(workers.NUM_TILES):
            tile = _tile_at(me, idx)
            st = self._tile_state[idx]
            q = script.TILE_QUEUES.get(idx, [])
            qi = st["queue_idx"]
            item = q[qi] if qi < len(q) else None
            worker = zoning.worker_for_tile(idx)

            empty = tile is None
            pasture_empty = (
                isinstance(tile, dict)
                and tile.get("kind") in ("COOP", "PASTURE")
                and not tile.get("animal")
            )
            harvestable = tile_ops.tile_has_harvestable(idx, me, day)

            if (
                (empty or pasture_empty)
                and item is not None
                and st["lag"] == 0
                and st["gap"] == 0
            ):
                kind = tile if not isinstance(tile, dict) else tile.get("kind")
                _log(
                    f"[stuck] d={day} t{idx + 1} {worker} kind={kind} qi={qi} "
                    f"item={item.kind}:{item.label} lag={st['lag']} gap={st['gap']} "
                    f"qlen={len(q)}"
                )
            if harvestable and isinstance(tile, dict):
                _log(
                    f"[stuck] d={day} t{idx + 1} {worker} HARVESTABLE "
                    f"kind={tile.get('kind')} yield={tile.get('yield_units')} "
                    f"fert_avail={tile.get('fertilizer_available')}"
                )

    def _log_snap(self, obs: dict, me: dict, day: int, hour: int) -> None:
        shops = obs.get("town", {}).get("unlocked_shops", [])
        demand = rollouts.shop_demand_by_product(shops)
        prices = obs["market"]["prices"]
        parts = " ".join(
            f"{w}_empty={_zone_empty(me, w)}" for w in workers.WORKERS
        )
        demand_s = " ".join(f"demand_{p}={demand.get(p, 0)}" for p in sorted(demand))
        price_s = " ".join(f"{k}={int(prices.get(k, 0) or 0)}" for k in sorted(prices))
        _log(
            f"[snap] d={day} h={hour} money={int(me['money'])} {parts} "
            f"shops={len(shops)} {demand_s} {price_s}"
        )

    def _worker_pos(self, worker: str, me: dict) -> tuple[int, int]:
        if worker == "farmer":
            return tuple(me["farmer"])
        idx = workers.hand_index(worker)
        if idx >= len(me["hands"]):
            return (-1, -1)
        return tuple(me["hands"][idx])

    def _inv_idx(self, worker: str) -> int:
        return workers.inventory_index(worker)

    def _zone_ops_remaining(self, worker: str) -> int:
        cap = NET_TILE_OPS.get(worker, 0)
        return max(0, cap - self._tile_ops_today.get(worker, 0))

    def _bump_tile_op(self, worker: str, action: list) -> None:
        if action and action[0] in _TILE_OP_VERBS:
            self._tile_ops_today[worker] = self._tile_ops_today.get(worker, 0) + 1

    def _emit_action(
        self,
        worker: str,
        action: list,
        note: str,
        *,
        tile_idx: int | None = None,
    ) -> tuple[list, str]:
        if tile_idx is not None and action and action[0] == "FERTILIZE":
            self._tile_state[tile_idx]["fert_today"] = True
        self._bump_tile_op(worker, action)
        return action, note

    def _farmer_action(
        self,
        me: dict,
        private: dict,
        day: int,
        hour: int,
        harvest_only: bool,
    ) -> tuple[list, str]:
        worker = "farmer"
        fx, fy = tuple(me["farmer"])
        inv_idx = self._inv_idx(worker)

        if harvest_only:
            return self._endgame_action(worker, me, private, day, fx, fy, inv_idx)

        inv = (
            private["inventories"][inv_idx]
            if inv_idx < len(private["inventories"])
            else {}
        )
        if (fx, fy) in workers.SHED_ADJACENT and inv.get("WHEAT", 0) <= 0:
            if (fx, fy) not in _owned_shed_tiles(me):
                step = _step_to_owned_shed(me, fx, fy)
                if step:
                    return self._emit_action(worker, [step], f"{worker} ->shed")
            else:
                need = script.wheat_pickup_needed(
                    me, worker, self._tile_state, inv
                )
                if need > 0 and int(private["shed"].get("WHEAT", 0)) > 0:
                    n = min(need, int(private["shed"].get("WHEAT", 0)))
                    return self._emit_action(
                        worker, ["PICKUP", "WHEAT", n], f"{worker} wheat"
                    )

        tiles = workers.WORKER_TILES["farmer"]
        while self._cursor < len(tiles):
            idx = tiles[self._cursor]
            tx, ty = workers.TILE_COORDS[idx]
            if (fx, fy) != (tx, ty):
                return [_step_toward(fx, fy, tx, ty)], f"farmer ->t{idx + 1}"

            st = self._tile_state[idx]
            pickup = self._shed_pickup(worker, fx, fy, private, inv_idx, me)
            if pickup:
                act, note = pickup
                return self._emit_action(worker, act, note)

            action = tile_ops.next_tile_action(
                idx,
                me,
                private,
                day,
                inv_idx,
                st["queue_idx"],
                st["lag"],
                st["gap"],
                st["pending_dig"],
                harvest_only=False,
                empty_at_dawn=self._empty_at_dawn,
                dig_plant_ok=st["dig_plant_ok"],
                fert_today=st.get("fert_today", False),
                zone_ops_remaining=self._zone_ops_remaining(worker),
            )
            if action:
                if action[0] in ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE"):
                    st["active"] = True
                    st["dig_plant_ok"] = False
                if action[0] == "DIG" and st["pending_dig"]:
                    st["pending_dig"] = False
                    st["dig_plant_ok"] = True
                    item = tile_ops.current_queue_item(idx, st["queue_idx"])
                    if item and item.label == "STRAWBERRY":
                        st["queue_idx"] += 1
                if (
                    action[0] == "HARVEST"
                    and isinstance(_tile_at(me, idx), dict)
                    and _tile_at(me, idx).get("crop") == "STRAWBERRY"
                    and day - _tile_at(me, idx)["planted_day"]
                    == tile_ops.STRAWBERRY_LAST_AGE
                ):
                    st["pending_dig"] = True
                if action[0] == "HARVEST":
                    t = _tile_at(me, idx)
                    y = t.get("yield_units") if isinstance(t, dict) else "?"
                    _dbg(
                        f"[harv] d={self._day} h={self._hour} {worker} t{idx + 1} "
                        f"kind={t.get('kind') if isinstance(t, dict) else t} yield={y}"
                    )
                if action[0] in ("HARVEST", "COLLECT_FERTILIZER"):
                    self._mark_endgame_tile_exhausted(worker, idx, me, action)
                return self._emit_action(
                    worker, action, f"{worker} t{idx + 1}", tile_idx=idx
                )

            self._cursor += 1

        drop = self._drop_if_adjacent(fx, fy, private, inv_idx, me)
        if drop:
            return drop
        return ["PASS"], "farmer done-for-day"

    def _endgame_tile_needs_work(
        self,
        worker: str,
        idx: int,
        me: dict,
        private: dict,
        day: int,
        inv_idx: int,
    ) -> bool:
        if idx in self._endgame_exhausted.get(worker, ()):
            return False
        if idx in self._endgame_harvested.get(worker, ()):
            tile = _tile_at(me, idx)
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                return False
        if tile_ops.tile_has_harvestable(idx, me, day):
            return True
        st = self._tile_state[idx]
        return (
            tile_ops.next_tile_action(
                idx,
                me,
                private,
                day,
                inv_idx,
                st["queue_idx"],
                st["lag"],
                st["gap"],
                st["pending_dig"],
                harvest_only=True,
                empty_at_dawn=self._empty_at_dawn,
                dig_plant_ok=st["dig_plant_ok"],
            )
            is not None
        )

    def _endgame_nearest_target(
        self,
        worker: str,
        fx: int,
        fy: int,
        me: dict,
        private: dict,
        day: int,
        inv_idx: int,
    ) -> int | None:
        best_idx: int | None = None
        best_dist = 10**9
        for idx in workers.WORKER_TILES[worker]:
            if idx in self._endgame_done[worker]:
                continue
            if idx in self._endgame_exhausted.get(worker, ()):
                continue
            if idx in self._endgame_harvested.get(worker, ()):
                tile = _tile_at(me, idx)
                if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    continue
            if not self._endgame_tile_needs_work(
                worker, idx, me, private, day, inv_idx
            ):
                continue
            tx, ty = workers.TILE_COORDS[idx]
            dist = _manhattan(fx, fy, tx, ty)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx

    def _endgame_action(
        self,
        worker: str,
        me: dict,
        private: dict,
        day: int,
        fx: int,
        fy: int,
        inv_idx: int,
    ) -> tuple[list, str]:
        drop = self._drop_if_adjacent(fx, fy, private, inv_idx, me)
        if drop:
            self._endgame_done[worker].clear()
            return drop

        target = self._endgame_nearest_target(
            worker, fx, fy, me, private, day, inv_idx
        )
        if target is None:
            if _inv_nonempty(private, inv_idx):
                if (fx, fy) in _owned_shed_tiles(me):
                    return ["DROP"], f"{worker} drop"
                if (fx, fy) in workers.SHED_ADJACENT:
                    step = _step_to_owned_shed(me, fx, fy)
                    if step:
                        return [step], f"{worker} ->shed"
                return [_step_toward(fx, fy, *workers.SHED_DOOR)], f"{worker} ->shed"
            return ["PASS"], f"{worker} done"

        tx, ty = workers.TILE_COORDS[target]
        if (fx, fy) != (tx, ty):
            return [_step_toward(fx, fy, tx, ty)], f"{worker} ->t{target + 1}"

        st = self._tile_state[target]
        action = tile_ops.next_tile_action(
            target,
            me,
            private,
            day,
            inv_idx,
            st["queue_idx"],
            st["lag"],
            st["gap"],
            st["pending_dig"],
            harvest_only=True,
            empty_at_dawn=self._empty_at_dawn,
            dig_plant_ok=st["dig_plant_ok"],
        )
        if action:
            if action[0] in ("HARVEST", "COLLECT_FERTILIZER"):
                self._endgame_done[worker].add(target)
                self._mark_endgame_tile_exhausted(worker, target, me, action)
            return action, f"{worker} t{target + 1}"

        self._endgame_done[worker].add(target)
        return ["PASS"], f"{worker} t{target + 1}-skip"

    def _shed_pickup(
        self, worker: str, fx: int, fy: int, private: dict, inv_idx: int, me: dict
    ) -> tuple[list, str] | None:
        if (fx, fy) not in workers.SHED_ADJACENT:
            return None
        if (fx, fy) not in _owned_shed_tiles(me):
            step = _step_to_owned_shed(me, fx, fy)
            if step:
                return [step], "->shed"
            return None
        inv = private["inventories"][inv_idx] if inv_idx < len(private["inventories"]) else {}

        need = script.wheat_pickup_needed(me, worker, self._tile_state, inv)
        if need > 0:
            n = min(need, private["shed"].get("WHEAT", 0))
            if n > 0:
                return ["PICKUP", "WHEAT", n], "wheat"

        label = script.next_animal_pickup(
            me, worker, self._tile_state, private, inv_idx
        )
        if label:
            return ["PICKUP", label, 1], "animal"
        return None

    def _drop_if_adjacent(
        self, fx: int, fy: int, private: dict, inv_idx: int, me: dict
    ) -> tuple[list, str] | None:
        if (fx, fy) not in workers.SHED_ADJACENT:
            return None
        if (fx, fy) not in _owned_shed_tiles(me):
            step = _step_to_owned_shed(me, fx, fy)
            if step:
                return [step], "->shed"
            return None
        inv = private["inventories"][inv_idx] if inv_idx < len(private["inventories"]) else {}
        if any(v > 0 for v in inv.values()):
            return ["DROP"], "drop"
        return None


def step(obs: dict) -> dict:
    global _EXECUTOR
    if _EXECUTOR is None:
        from milos import planner

        print(
            f"[planner] CURRENT_SOLVER={planner.CURRENT_SOLVER} "
            f"NUM_ACTIVE_HIRES={planner.NUM_ACTIVE_HIRES}",
            flush=True,
        )
        _EXECUTOR = Executor()
    return _EXECUTOR.step(obs)
