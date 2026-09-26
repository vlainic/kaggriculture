"""Local mutations for executor day forecast (not full engine parity)."""

from __future__ import annotations

from milos import animal_rollouts, rollouts, tile_ops, workers
from milos.tile_ops import ONE_TIME_CROPS, on_lifecycle_end, plant_harvest_transfer

_MOVE = frozenset({"NORTH", "SOUTH", "EAST", "WEST"})

_SHED_ACCESS = ((4, 4), (5, 4), (4, 5), (5, 5))


def _spawn_hand_pos(me: dict) -> list[int]:
    """Match env _spawn_hand: min occupancy on shed-access tiles, NWSE tiebreak."""
    occupants = {tile: 0 for tile in _SHED_ACCESS}
    for pos in [tuple(me["farmer"])] + [tuple(p) for p in me.get("hands", [])]:
        if pos in occupants:
            occupants[pos] += 1
    best = sorted(
        occupants.items(),
        key=lambda kv: (kv[1], _SHED_ACCESS.index(kv[0])),
    )
    return list(best[0][0])


def _tile_at(me: dict, idx: int):
    x, y = workers.TILE_COORDS[idx]
    return me["tiles"][y][x]


def _set_tile(me: dict, idx: int, value) -> None:
    x, y = workers.TILE_COORDS[idx]
    me["tiles"][y][x] = value


def _inv_at(private: dict, inv_idx: int) -> dict:
    invs = private["inventories"]
    while len(invs) <= inv_idx:
        invs.append({})
    return invs[inv_idx]


def _tile_idx_at(me: dict, fx: int, fy: int) -> int | None:
    for idx, (x, y) in enumerate(workers.TILE_COORDS):
        if x == fx and y == fy:
            return idx
    return None


def apply_market_orders(
    me: dict,
    private: dict,
    orders: list[list],
    prices: dict,
) -> None:
    seeds = private.setdefault("seeds", {})
    shed = private.setdefault("shed", {})
    for order in orders:
        if not order:
            continue
        op = order[0]
        if op == "BUY_SEED" and len(order) >= 3:
            crop, n = order[1], int(order[2])
            cost = rollouts.seed_cost(crop) * n
            me["money"] = int(me["money"]) - cost
            seeds[crop] = seeds.get(crop, 0) + n
        elif op == "BUY_PRODUCT" and len(order) >= 3:
            item, n = order[1], int(order[2])
            unit = int(prices.get(item, 25) or 25)
            me["money"] = int(me["money"]) - unit * n
            shed[item] = shed.get(item, 0) + n
        elif op == "BUY_ANIMAL" and len(order) >= 3:
            animal, n = order[1], int(order[2])
            cost = animal_rollouts.animal_cost(animal) * n
            me["money"] = int(me["money"]) - cost
            shed[animal] = shed.get(animal, 0) + n
        elif op == "HIRE":
            hands = me.setdefault("hands", [])
            hands.append(_spawn_hand_pos(me))
            private.setdefault("inventories", [{}]).append({})
        elif op == "SELL" and len(order) >= 3:
            item, n = order[1], int(order[2])
            n = min(n, shed.get(item, 0))
            if n <= 0:
                continue
            unit = int(prices.get(item, 1) or 1)
            shed[item] = shed.get(item, 0) - n
            me["money"] = int(me["money"]) + unit * n


def apply_hand_action(
    me: dict,
    private: dict,
    day: int,
    hand_idx: int,
    action: list,
    tile_state: dict[int, dict],
    *,
    inv_idx: int,
) -> None:
    if hand_idx >= len(me.get("hands", [])):
        return
    saved = me["farmer"]
    me["farmer"] = list(me["hands"][hand_idx])
    try:
        apply_farmer_action(
            me, private, day, action, tile_state, inv_idx=inv_idx
        )
        me["hands"][hand_idx] = list(me["farmer"])
    finally:
        me["farmer"] = saved


def apply_farmer_action(
    me: dict,
    private: dict,
    day: int,
    action: list,
    tile_state: dict[int, dict],
    *,
    inv_idx: int = 0,
) -> None:
    if not action or action[0] == "PASS":
        return
    verb = action[0]
    fx, fy = tuple(me["farmer"])
    if verb in _MOVE:
        dx, dy = {"EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, 1), "NORTH": (0, -1)}[
            verb
        ]
        me["farmer"] = [fx + dx, fy + dy]
        return

    idx = _tile_idx_at(me, fx, fy)
    inv = _inv_at(private, inv_idx)
    shed = private.setdefault("shed", {})
    seeds = private.setdefault("seeds", {})

    if verb == "PICKUP" and len(action) >= 2:
        item = action[1]
        n = int(action[2]) if len(action) > 2 else shed.get(item, 0)
        n = min(n, shed.get(item, 0))
        if n > 0:
            shed[item] = shed.get(item, 0) - n
            inv[item] = inv.get(item, 0) + n
        return

    if verb == "DROP":
        for item, n in list(inv.items()):
            if n <= 0:
                continue
            shed[item] = shed.get(item, 0) + n
        inv.clear()
        return

    if idx is None:
        return

    tile = _tile_at(me, idx)
    st = tile_state.setdefault(
        idx,
        {
            "queue_idx": 0,
            "lag": 0,
            "gap": 0,
            "pending_dig": False,
            "dig_plant_ok": False,
            "active": False,
            "fert_today": False,
        },
    )

    if verb == "PLANT" and len(action) >= 2:
        crop = action[1]
        if seeds.get(crop, 0) <= 0:
            return
        seeds[crop] -= 1
        _set_tile(
            me,
            idx,
            {
                "kind": "PLANT",
                "crop": crop,
                "planted_day": day,
                "watered_today": False,
                "consecutive_unwatered": 0,
                "yield_units": 0,
                "fertilized_until_day": -1,
            },
        )
        return

    if verb in ("BUILD_COOP", "BUILD_PASTURE"):
        kind = "COOP" if verb == "BUILD_COOP" else "PASTURE"
        _set_tile(
            me,
            idx,
            {
                "kind": kind,
                "animal": None,
                "placed_day": day,
                "fed_today": False,
                "cared_today": False,
                "yield_units": 0,
                "fertilizer_available": False,
            },
        )
        return

    if not isinstance(tile, dict):
        if verb == "DIG":
            _set_tile(me, idx, None)
            st["dig_plant_ok"] = True
        return

    if verb == "WATER" and tile.get("kind") == "PLANT":
        tile["watered_today"] = True
        return

    if verb == "FERTILIZE" and tile.get("kind") == "PLANT":
        if inv.get("FERTILIZER", 0) > 0:
            inv["FERTILIZER"] -= 1
            tile["fertilized_until_day"] = day + 2
        return

    if verb == "HARVEST":
        if tile.get("kind") == "PLANT":
            crop = tile["crop"]
            y = int(tile.get("yield_units", 0))
            if y > 0:
                take, remaining = plant_harvest_transfer(crop, y)
                inv[crop] = inv.get(crop, 0) + take
                if crop in ONE_TIME_CROPS:
                    item = tile_ops.current_queue_item(idx, st["queue_idx"])
                    qi, lag, gap, dig = on_lifecycle_end(
                        idx, st["queue_idx"], item, st["pending_dig"]
                    )
                    st["queue_idx"] = qi
                    st["lag"] = max(st["lag"], lag)
                    st["gap"] = max(st["gap"], gap)
                    st["pending_dig"] = dig
                    st["active"] = False
                    _set_tile(me, idx, None)
                else:
                    tile["yield_units"] = remaining
        elif tile.get("kind") in ("COOP", "PASTURE"):
            animal = tile.get("animal")
            y = int(tile.get("yield_units", 0))
            if y > 0 and animal:
                product = animal_rollouts.product_for(animal)
                inv[product] = inv.get(product, 0) + y
                tile["yield_units"] = 0
        return

    if verb == "DIG":
        kind = tile.get("kind")
        if kind in ("WEED", "PLANT") or (
            kind in ("COOP", "PASTURE") and not tile.get("animal")
        ):
            _set_tile(me, idx, None)
            st["dig_plant_ok"] = True
        return

    if verb == "PLACE" and len(action) >= 2:
        animal = action[1]
        if tile.get("kind") in ("COOP", "PASTURE") and not tile.get("animal"):
            if inv.get(animal, 0) > 0 and inv.get("WHEAT", 0) > 0:
                inv[animal] -= 1
                tile["animal"] = animal
                tile["placed_day"] = day
        return

    if verb == "FEED" and tile.get("animal"):
        if not tile.get("fed_today") and inv.get("WHEAT", 0) > 0:
            inv["WHEAT"] -= 1
            tile["fed_today"] = True
        return

    if verb == "CARE" and tile.get("animal"):
        if tile.get("fed_today") and not tile.get("cared_today"):
            tile["cared_today"] = True
        return

    if verb == "COLLECT_FERTILIZER" and tile.get("fertilizer_available"):
        inv["FERTILIZER"] = inv.get("FERTILIZER", 0) + 1
        tile["fertilizer_available"] = False
        return
