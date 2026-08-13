"""
DP-filter + Master-assignment scheduler for Kaggriculture zones.

Pipeline:
  1. generate_tile_candidates() - enumerate (crop/mode, plant_day) placements per tile
  2. weighted_interval_dp()     - per-tile DP over those placements, run at a few
                                   min_gap levels to produce several "variants"
                                   (tight vs. loose) per tile
  3. solve_master()             - CP-SAT picks exactly one variant per tile,
                                   subject to per-zone daily ops caps and one
                                   global running-cash-balance constraint

Re-run this whole pipeline on a rolling cadence (every few days), excluding
tiles that are already locked by an animal placement or a still-growing crop.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
import bisect
from ortools.sat.python import cp_model


# ---------------------------------------------------------------------------
# 1. Templates & candidate generation
# ---------------------------------------------------------------------------

@dataclass
class CropTemplate:
    """One (crop, mode) rollout, e.g. WHEAT_no_fert or MELON_fert."""
    name: str                       # e.g. "WHEAT_no_fert"
    lifespan: int                   # days occupied on the tile, plant -> decay
    seed_cost: int
    ops_by_age: Dict[int, int]      # age -> ops that day
    revenue_by_age: Dict[int, int]  # age -> $ realized that day (harvest days)

    @property
    def gross_value(self) -> int:
        return sum(self.revenue_by_age.values()) - self.seed_cost


def load_templates_from_rollouts(rollout_json: dict, price_snapshot: Dict[str, int]) -> List[CropTemplate]:
    """
    Build CropTemplate objects from your existing crop_rollouts.json plus a
    current market-price snapshot (re-price every replan -- weights aren't
    static across the season, per the MPC discussion).

    Expected rollout_json shape (matches your notebook's rollout_ops()):
        rollout_json["crops"][crop][profile]["days"] = [
            {"age": int, "actions": [...]}, ...
        ]
    This is a STUB for the yield arithmetic -- plug in your real harvest-yield
    formulas (fertilized vs not, one-time vs ongoing) where marked TODO.
    """
    templates = []
    for crop, profiles in rollout_json.get("crops", {}).items():
        for profile, payload in profiles.items():
            days = sorted(payload["days"], key=lambda d: d["age"])
            ops_by_age: Dict[int, int] = {}
            revenue_by_age: Dict[int, int] = {}
            for d in days:
                ops = 0
                revenue = 0
                for action in d["actions"]:
                    if action in ("WATER", "FERTILIZE", "FEED", "CARE"):
                        ops += 1
                    elif action == "HARVEST":
                        ops += 1
                        # TODO: replace flat price with real yield formula
                        # (age, fert window, one-time vs ongoing) x price_snapshot[crop]
                        revenue += price_snapshot.get(crop, 0)
                    elif action == "PLANT":
                        ops += 1
                ops_by_age[d["age"]] = ops
                revenue_by_age[d["age"]] = revenue
            lifespan = max(ops_by_age) + 1 if ops_by_age else 1
            seed_cost = 0  # TODO: pull from Object Types table per crop
            templates.append(CropTemplate(
                name=f"{crop}_{profile}", lifespan=lifespan,
                seed_cost=seed_cost, ops_by_age=ops_by_age,
                revenue_by_age=revenue_by_age,
            ))
    return templates


def generate_tile_candidates(templates: List[CropTemplate], horizon: int) -> List[dict]:
    """All (template, plant_day) placements that fit inside [0, horizon)."""
    candidates = []
    for t in templates:
        for plant_day in range(0, horizon - t.lifespan + 1):
            ops_profile = {plant_day + age: n for age, n in t.ops_by_age.items()}
            cash_profile = {plant_day: -t.seed_cost}
            for age, rev in t.revenue_by_age.items():
                day = plant_day + age
                cash_profile[day] = cash_profile.get(day, 0) + rev
            candidates.append({
                "crop": t.name,
                "start": plant_day,
                "end": plant_day + t.lifespan - 1,
                "value": t.gross_value,
                "ops_by_day": ops_profile,
                "cash_by_day": cash_profile,
            })
    return candidates


# ---------------------------------------------------------------------------
# 2. Per-tile DP (weighted interval scheduling, with a min-gap knob)
# ---------------------------------------------------------------------------

def weighted_interval_dp(candidates: List[dict], min_gap: int = 0):
    """
    O(n log n) weighted interval scheduling, generalized with a min_gap knob:
    two selected placements must satisfy  next.start > prev.end + min_gap.

    min_gap=0     -> tightest packing (max value, ignores capacity smoothing)
    min_gap=1,3,. -> deliberately looser schedules -- same idea as your
                     handmade plan's "3 day break between harvest and plant".

    Returns (total_value, selected_candidates).
    """
    cands = sorted(candidates, key=lambda c: c["end"])
    ends = [c["end"] for c in cands]
    n = len(cands)

    pred = []
    for c in cands:
        threshold = c["start"] - min_gap - 1
        j = bisect.bisect_right(ends, threshold) - 1
        pred.append(j)

    dp = [0] * (n + 1)
    take = [False] * n
    for i in range(1, n + 1):
        idx = i - 1
        incl = cands[idx]["value"] + dp[pred[idx] + 1]
        excl = dp[i - 1]
        if incl >= excl:
            dp[i] = incl
            take[idx] = True
        else:
            dp[i] = excl

    selected, i = [], n
    while i > 0:
        idx = i - 1
        if take[idx]:
            selected.append(cands[idx])
            i = pred[idx] + 1
        else:
            i -= 1
    selected.reverse()
    return dp[n], selected


def build_tile_variants(templates: List[CropTemplate], horizon: int,
                         min_gaps: List[int] = (0, 1, 3)) -> List[dict]:
    """
    Run the DP at a few min_gap levels to get a small family of variants for
    one tile. Always includes an explicit "idle" variant (value 0, no ops, no
    cash) so the master can legally leave a tile empty.
    """
    raw = generate_tile_candidates(templates, horizon)
    variants, seen_signatures = [], set()

    for gap in min_gaps:
        value, selected = weighted_interval_dp(raw, min_gap=gap)
        ops_by_day: Dict[int, int] = {}
        cash_by_day: Dict[int, int] = {}
        for c in selected:
            for day, ops in c["ops_by_day"].items():
                ops_by_day[day] = ops_by_day.get(day, 0) + ops
            for day, cash in c["cash_by_day"].items():
                cash_by_day[day] = cash_by_day.get(day, 0) + cash
        signature = tuple(sorted((c["crop"], c["start"]) for c in selected))
        if signature in seen_signatures:
            continue  # this gap didn't change the outcome vs. one already kept
        seen_signatures.add(signature)
        variants.append({
            "min_gap": gap, "value": value,
            "ops_by_day": ops_by_day, "cash_by_day": cash_by_day,
            "placements": [(c["crop"], c["start"], c["end"]) for c in selected],
        })

    variants.append({"min_gap": None, "value": 0, "ops_by_day": {},
                      "cash_by_day": {}, "placements": []})
    return variants


# ---------------------------------------------------------------------------
# 3. Master: pick one variant per tile (small CP-SAT assignment)
# ---------------------------------------------------------------------------

def solve_master(tile_variants: Dict[str, List[dict]], horizon: int,
                  tile_zone: Dict[str, str], zone_caps: Dict[str, int],
                  starting_money: int, time_limit_s: float = 10.0):
    """
    tile_variants   : tile_id -> list of variant dicts from build_tile_variants()
    tile_zone       : tile_id -> zone name (e.g. "farmer", "top_left", "corner")
    zone_caps       : zone name -> daily ops cap for that zone
    starting_money  : bank balance at the start of this horizon
    """
    model = cp_model.CpModel()
    x = {t: [model.NewBoolVar(f"x_{t}_{i}") for i in range(len(vs))]
         for t, vs in tile_variants.items()}
    for t, vs in tile_variants.items():
        model.Add(sum(x[t]) == 1)

    zones = set(tile_zone.values())
    for zone in zones:
        zone_tiles = [t for t in tile_variants if tile_zone[t] == zone]
        for day in range(horizon):
            terms = []
            for t in zone_tiles:
                for i, v in enumerate(tile_variants[t]):
                    ops = v["ops_by_day"].get(day, 0)
                    if ops:
                        terms.append(ops * x[t][i])
            if terms:
                model.Add(sum(terms) <= zone_caps[zone])

    balance_vars = []
    for day in range(horizon):
        day_terms = []
        for t, vs in tile_variants.items():
            for i, v in enumerate(vs):
                delta = v["cash_by_day"].get(day, 0)
                if delta:
                    day_terms.append(delta * x[t][i])
        bal = model.NewIntVar(-1_000_000, 1_000_000, f"balance_{day}")
        prev = starting_money if day == 0 else balance_vars[-1]
        model.Add(bal == prev + sum(day_terms))
        model.Add(bal >= 0)
        balance_vars.append(bal)

    model.Maximize(sum(v["value"] * x[t][i]
                        for t, vs in tile_variants.items()
                        for i, v in enumerate(vs)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    status = solver.Solve(model)

    chosen = {}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for t, vs in tile_variants.items():
            for i, v in enumerate(vs):
                if solver.Value(x[t][i]):
                    chosen[t] = v
    return status, chosen


# ---------------------------------------------------------------------------
# Demo with tiny synthetic data -- proves the pipeline wires together.
# Swap load_templates_from_rollouts() in for your real crop_rollouts.json.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    wheat = CropTemplate("WHEAT", lifespan=4, seed_cost=10,
                          ops_by_age={0: 1, 1: 1, 2: 1, 3: 1},
                          revenue_by_age={3: 30})
    carrot = CropTemplate("CARROT", lifespan=3, seed_cost=20,
                           ops_by_age={0: 1, 1: 1, 2: 1},
                           revenue_by_age={2: 45})
    horizon = 15

    print("== single tile, variants at different min_gap ==")
    variants = build_tile_variants([wheat, carrot], horizon, min_gaps=[0, 1, 3])
    for v in variants:
        print(f"gap={v['min_gap']}  value={v['value']}  placements={v['placements']}")

    print("\n== 3-tile zone, master assignment ==")
    tile_variants = {f"T{i}": build_tile_variants([wheat, carrot], horizon)
                      for i in range(3)}
    tile_zone = {t: "demo_zone" for t in tile_variants}
    status, chosen = solve_master(
        tile_variants, horizon, tile_zone,
        zone_caps={"demo_zone": 5}, starting_money=200,
    )
    status_names = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
                     cp_model.INFEASIBLE: "INFEASIBLE", cp_model.UNKNOWN: "UNKNOWN"}
    print("status:", status_names.get(status, status))
    for t, v in chosen.items():
        print(t, "->", v["placements"], "value:", v["value"])
