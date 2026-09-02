"""Scripted turn-by-turn executor: snake routes + rollout-driven tile ops."""

from __future__ import annotations

from agent import market, planner, rollouts, script, sell_dp, tile_ops, workers
from agent.zoning import NET_TILE_OPS

_EXECUTOR: Executor | None = None

_TILE_OP_VERBS = frozenset({
    "PLANT", "WATER", "FERTILIZE", "HARVEST", "FEED", "CARE", "DIG", "PLACE",
    "BUILD_COOP", "BUILD_PASTURE", "COLLECT_FERTILIZER", "PICKUP", "DROP",
})
_ON_TILE_OP_VERBS = _TILE_OP_VERBS - frozenset({"PICKUP", "DROP"})


_PASS_NOTE_KEYS = frozenset({
    "pre-wait-shed", "done", "feed-wait", "wait", "tile-done", "no-hand",
    "market-hour", "pre->shed",
})
_STUCK_NOTE_KEYS = frozenset({"pre-wait-shed", "feed-wait", "pre->shed", "wait"})


def _log(msg: str) -> None:
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


def _tile_at(me: dict, idx: int):
    x, y = workers.TILE_COORDS[idx]
    return me["tiles"][y][x]


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
        self._route_idx = {w: 0 for w in workers.WORKERS}
        self._preamble_idx = {w: 0 for w in workers.WORKERS}
        self._endgame_done = {w: set() for w in workers.WORKERS}
        self._tile_state: dict[int, dict] = {}
        self._empty_at_dawn: set[int] = set()
        self._day0_productive = False
        self._tile_ops_today = {w: 0 for w in workers.WORKERS}
        self._tile_ops_peak = {w: 0 for w in workers.WORKERS}
        self._tile_ops_on_tile_today = {w: 0 for w in workers.WORKERS}
        self._tile_ops_on_tile_peak = {w: 0 for w in workers.WORKERS}
        self._note_counts: dict[str, dict[str, int]] = {
            w: {} for w in workers.WORKERS
        }
        self._pass_streak = {w: 0 for w in workers.WORKERS}
        self._route_order: dict[str, list[int]] = {}
        self._current_day = 0
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
        self._current_day = day

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

        orders = market.build_orders(
            obs, me, private, day, hour, self._tile_state, self._empty_at_dawn
        )
        harvest_only = day >= script.SEASON_LAST_DAY

        if market.defer_farmer_hour0(hour, orders, me, day):
            farmer = ["PASS"]
            hands = [["PASS"] for _ in me["hands"]]
            note = "market-hour"
            self._record_worker_note("farmer", farmer, note)
            for i in range(len(me["hands"])):
                self._record_worker_note(
                    workers.worker_for_hand_idx(i), ["PASS"], "market-hour"
                )
            hand_results: list[tuple[list, str]] = []
        else:
            farmer, note = self._worker_action(
                "farmer", me, private, day, hour, harvest_only
            )
            self._record_worker_note("farmer", farmer, note)
            hand_results = []
            for i in range(len(me["hands"])):
                worker = workers.worker_for_hand_idx(i)
                act, hnote = self._worker_action(
                    worker, me, private, day, hour, harvest_only
                )
                hand_results.append((act, hnote))
                self._record_worker_note(worker, act, hnote)
            hands = [act for act, _ in hand_results]

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
        _log(f"[exec] d={day} h={hour} farmer {_fmt(farmer)}" + (f" {note}" if note else ""))
        if market.defer_farmer_hour0(hour, orders, me, day):
            for i, act in enumerate(hands):
                _log(f"[exec] d={day} h={hour} hand{i} {_fmt(act)} market-hour")
        else:
            for i, (act, hnote) in enumerate(hand_results):
                _log(
                    f"[exec] d={day} h={hour} hand{i} {_fmt(act)}"
                    + (f" {hnote}" if hnote else "")
                )

        return {"farmer": farmer, "hands": hands, "market": orders}

    def _on_new_day(self, me: dict, day: int) -> None:
        if day > 0:
            parts = " ".join(
                f"{w}={self._tile_ops_today.get(w, 0)}" for w in workers.WORKERS
            )
            _log(f"[exec] tile_ops d={day - 1} {parts}")
            for w in workers.WORKERS:
                self._tile_ops_peak[w] = max(
                    self._tile_ops_peak.get(w, 0),
                    self._tile_ops_today.get(w, 0),
                )
                self._tile_ops_on_tile_peak[w] = max(
                    self._tile_ops_on_tile_peak.get(w, 0),
                    self._tile_ops_on_tile_today.get(w, 0),
                )
        for w in workers.WORKERS:
            self._route_idx[w] = 0
            self._preamble_idx[w] = 0
            self._tile_ops_today[w] = 0
            self._tile_ops_on_tile_today[w] = 0

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
            idx for idx in range(workers.NUM_TILES) if _tile_at(me, idx) is None
        }
        self._refresh_animal_first_routes(me)
        if day >= script.SEASON_LAST_DAY:
            self._endgame_done = {w: set() for w in workers.WORKERS}
        if day == script.SEASON_LAST_DAY:
            self._dump_note_counts()
            peak = " ".join(
                f"{w}={self._tile_ops_peak.get(w, 0)}" for w in workers.WORKERS
            )
            on_peak = " ".join(
                f"{w}={self._tile_ops_on_tile_peak.get(w, 0)}" for w in workers.WORKERS
            )
            _log(f"[exec] tile_ops_peak {peak}")
            _log(f"[exec] tile_ops_on_tile_peak {on_peak}")

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
        if action and action[0] in _ON_TILE_OP_VERBS:
            self._tile_ops_on_tile_today[worker] = (
                self._tile_ops_on_tile_today.get(worker, 0) + 1
            )

    def _pass_note_key(self, note: str) -> str:
        if not note:
            return "pass"
        token = note.rsplit(" ", 1)[-1]
        return token if token in _PASS_NOTE_KEYS else token

    def _record_worker_note(self, worker: str, action: list, note: str) -> None:
        if action and action[0] == "PASS":
            key = self._pass_note_key(note)
            counts = self._note_counts.setdefault(worker, {})
            counts[key] = counts.get(key, 0) + 1
            self._pass_streak[worker] = self._pass_streak.get(worker, 0) + 1
            if key in _STUCK_NOTE_KEYS and self._pass_streak[worker] > 8:
                _log(f"[exec] WARN {worker} stuck: {note}")
        else:
            self._pass_streak[worker] = 0

    def _dump_note_counts(self) -> None:
        parts = []
        for worker in workers.WORKERS:
            counts = self._note_counts.get(worker, {})
            if not counts:
                continue
            inner = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            parts.append(f"{worker}[{inner}]")
        if parts:
            _log(f"[exec] pass_notes {' '.join(parts)}")

    def _tile_animal_priority(self, idx: int, me: dict) -> bool:
        tile = _tile_at(me, idx)
        if isinstance(tile, dict) and tile.get("animal"):
            return True
        st = self._tile_state.get(idx, {})
        qi = st.get("queue_idx", 0)
        queue = script.TILE_QUEUES.get(idx, [])
        if qi < len(queue) and queue[qi].kind == "animal":
            return True
        for item in queue[qi:]:
            if item.kind == "animal":
                return True
        return False

    def _refresh_animal_first_routes(self, me: dict) -> None:
        for worker in workers.WORKERS:
            tiles = workers.WORKER_TILES[worker]
            animal_first = [t for t in tiles if self._tile_animal_priority(t, me)]
            crop_rest = [t for t in tiles if t not in animal_first]
            self._route_order[worker] = animal_first + crop_rest

    def _worker_route(self, worker: str) -> list[int]:
        return self._route_order.get(worker) or workers.WORKER_ROUTES[worker]

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

    def _worker_action(
        self,
        worker: str,
        me: dict,
        private: dict,
        day: int,
        hour: int,
        harvest_only: bool,
    ) -> tuple[list, str]:
        fx, fy = self._worker_pos(worker, me)
        if fx < 0:
            return ["PASS"], "no-hand"

        inv_idx = self._inv_idx(worker)

        if worker != "farmer":
            start_hour = 0 if harvest_only else workers.HAND_START_HOUR.get(worker, 1)
            if hour < start_hour:
                return ["PASS"], f"{worker} wait"

        if harvest_only:
            return self._endgame_action(worker, me, private, day, fx, fy, inv_idx)

        if worker != "farmer":
            pre = self._preamble_action(worker, me, private, fx, fy)
            if pre:
                act, note = pre
                return self._emit_action(worker, act, note)

        if not harvest_only:
            inv = (
                private["inventories"][inv_idx]
                if inv_idx < len(private["inventories"])
                else {}
            )
            if (fx, fy) in workers.SHED_ADJACENT and inv.get("WHEAT", 0) <= 0:
                need = script.wheat_pickup_needed(
                    me, worker, self._tile_state, inv
                )
                if need > 0 and int(private["shed"].get("WHEAT", 0)) > 0:
                    n = min(need, int(private["shed"].get("WHEAT", 0)))
                    return self._emit_action(
                        worker, ["PICKUP", "WHEAT", n], f"{worker} wheat"
                    )

        route = self._worker_route(worker)
        if self._route_idx[worker] >= len(route):
            if self._zone_pending(worker, me, private, day, inv_idx, harvest_only):
                self._route_idx[worker] = 0
            else:
                drop = self._drop_if_adjacent(fx, fy, private, inv_idx)
                return drop or (["PASS"], f"{worker} done")

        idx = route[self._route_idx[worker]]
        tx, ty = workers.TILE_COORDS[idx]
        st = self._tile_state[idx]

        if (fx, fy) == (tx, ty):
            if not harvest_only:
                pickup = self._shed_pickup(worker, fx, fy, private, inv_idx, me)
                if pickup:
                    return pickup

            action = tile_ops.next_tile_action(
                idx, me, private, day, inv_idx,
                st["queue_idx"], st["lag"], st["gap"], st["pending_dig"],
                harvest_only=harvest_only,
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
                    and day - _tile_at(me, idx)["planted_day"] == tile_ops.STRAWBERRY_LAST_AGE
                ):
                    st["pending_dig"] = True
                return self._emit_action(
                    worker, action, f"{worker} t{idx + 1}", tile_idx=idx
                )

            tile = _tile_at(me, idx)
            if tile_ops.tile_needs_feed(tile, day):
                inv = (
                    private["inventories"][inv_idx]
                    if inv_idx < len(private["inventories"])
                    else {}
                )
                if inv.get("WHEAT", 0) <= 0:
                    if (fx, fy) in workers.SHED_ADJACENT:
                        n = min(
                            script.wheat_pickup_needed(
                                me, worker, self._tile_state, inv
                            ),
                            private["shed"].get("WHEAT", 0),
                        )
                        if n > 0:
                            return self._emit_action(
                                worker, ["PICKUP", "WHEAT", n], f"{worker} feed-wait"
                            )
                    return ["PASS"], f"{worker} feed-wait"
                return ["PASS"], f"{worker} feed-wait"

            self._route_idx[worker] += 1
            if self._route_idx[worker] < len(route):
                ntx, nty = workers.TILE_COORDS[route[self._route_idx[worker]]]
                return [_step_toward(fx, fy, ntx, nty)], f"{worker} next"
            return ["PASS"], f"{worker} tile-done"

        return [_step_toward(fx, fy, tx, ty)], f"{worker} ->t{idx + 1}"

    def _endgame_tile_needs_work(
        self,
        idx: int,
        me: dict,
        private: dict,
        day: int,
        inv_idx: int,
    ) -> bool:
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
            if not self._endgame_tile_needs_work(idx, me, private, day, inv_idx):
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
        drop = self._drop_if_adjacent(fx, fy, private, inv_idx)
        if drop:
            self._endgame_done[worker].clear()
            return drop

        target = self._endgame_nearest_target(
            worker, fx, fy, me, private, day, inv_idx
        )
        if target is None:
            if _inv_nonempty(private, inv_idx):
                if (fx, fy) in workers.SHED_ADJACENT:
                    return ["DROP"], f"{worker} drop"
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
            return action, f"{worker} t{target + 1}"

        self._endgame_done[worker].add(target)
        return ["PASS"], f"{worker} t{target + 1}-skip"

    def _preamble_action(
        self, worker: str, me: dict, private: dict, fx: int, fy: int
    ) -> tuple[list, str] | None:
        steps = workers.PREAMBLE.get(worker, [])
        pi = self._preamble_idx[worker]
        if pi >= len(steps):
            return None

        step = steps[pi]
        inv_idx = self._inv_idx(worker)
        inv = private["inventories"][inv_idx] if inv_idx < len(private["inventories"]) else {}

        if step == "PICKUP_WHEAT":
            need = script.wheat_pickup_needed(me, worker, self._tile_state, inv)
            if need <= 0:
                self._preamble_idx[worker] += 1
                return self._preamble_action(worker, me, private, fx, fy)
            if (fx, fy) not in workers.SHED_ADJACENT:
                return (
                    [_step_toward(fx, fy, *workers.SHED_DOOR)],
                    f"{worker} pre->shed",
                )
            n = min(need, private["shed"].get("WHEAT", 0))
            if n > 0:
                self._preamble_idx[worker] += 1
                return ["PICKUP", "WHEAT", n], f"{worker} pre-wheat"
            self._preamble_idx[worker] += 1
            return self._preamble_action(worker, me, private, fx, fy)

        if step == "PICKUP_ANIMALS":
            label = script.next_animal_pickup(
                me, worker, self._tile_state, private, inv_idx
            )
            if label is None:
                self._preamble_idx[worker] += 1
                return self._preamble_action(worker, me, private, fx, fy)
            if (fx, fy) not in workers.SHED_ADJACENT:
                return (
                    [_step_toward(fx, fy, *workers.SHED_DOOR)],
                    f"{worker} pre->shed",
                )
            if int(private["shed"].get(label, 0)) <= 0:
                self._preamble_idx[worker] += 1
                return self._preamble_action(worker, me, private, fx, fy)
            self._preamble_idx[worker] += 1
            return ["PICKUP", label, 1], f"{worker} pre-animal"

        if step == "PICKUP_FERTILIZER":
            need = script.fert_pickup_needed(
                me, worker, self._tile_state, private, day=self._current_day
            )
            if need <= 0:
                self._preamble_idx[worker] += 1
                return self._preamble_action(worker, me, private, fx, fy)
            if (fx, fy) not in workers.SHED_ADJACENT:
                return (
                    [_step_toward(fx, fy, *workers.SHED_DOOR)],
                    f"{worker} pre->shed",
                )
            n = min(need, int(private["shed"].get("FERTILIZER", 0)))
            if n > 0:
                self._preamble_idx[worker] += 1
                return ["PICKUP", "FERTILIZER", n], f"{worker} pre-fert"
            self._preamble_idx[worker] += 1
            return self._preamble_action(worker, me, private, fx, fy)

        self._preamble_idx[worker] += 1
        return [step], f"{worker} pre"

    def _zone_pending(
        self, worker: str, me: dict, private: dict, day: int, inv_idx: int, harvest_only: bool
    ) -> bool:
        for idx in workers.WORKER_TILES[worker]:
            st = self._tile_state[idx]
            if tile_ops.tile_needs_work(
                idx, me, private, day, inv_idx,
                st["queue_idx"], st["lag"], st["gap"], st["pending_dig"],
                harvest_only=harvest_only,
                empty_at_dawn=self._empty_at_dawn,
                dig_plant_ok=st["dig_plant_ok"],
            ):
                return True
            if harvest_only and tile_ops.tile_has_harvestable(idx, me, day):
                return True
        return False

    def _shed_pickup(
        self, worker: str, fx: int, fy: int, private: dict, inv_idx: int, me: dict
    ) -> tuple[list, str] | None:
        if (fx, fy) not in workers.SHED_ADJACENT:
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

        fert_need = script.fert_pickup_needed(
            me, worker, self._tile_state, private, day=self._current_day
        )
        if fert_need > 0:
            n = min(fert_need, int(private["shed"].get("FERTILIZER", 0)))
            if n > 0:
                return ["PICKUP", "FERTILIZER", n], "fert"
        return None

    def _drop_if_adjacent(
        self, fx: int, fy: int, private: dict, inv_idx: int
    ) -> tuple[list, str] | None:
        if (fx, fy) not in workers.SHED_ADJACENT:
            return None
        inv = private["inventories"][inv_idx] if inv_idx < len(private["inventories"]) else {}
        if any(v > 0 for v in inv.values()):
            return ["DROP"], "drop"
        return None


def step(obs: dict) -> dict:
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = Executor()
    return _EXECUTOR.step(obs)
