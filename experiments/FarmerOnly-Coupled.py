# %% cell 0
import json

import collections
from ortools.sat.python import cp_model

# %% cell 1
import resource
import tracemalloc
from functools import wraps

def peak_mem(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        tracemalloc.start()
        try:
            return fn(*args, **kwargs)
        finally:
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            print(
                f"{fn.__name__}: "
                f"tracemalloc peak={peak / 1e6:.1f} MB, "
                f"RSS max={rss_after / 1024:.1f} MB "
                f"(was {rss_before / 1024:.1f} MB)"
            )
    return wrapper

# %% cell 2
with open("../data/crop_rollouts.json", "r") as f:
    crops_data = json.load(f)
with open("../data/animal_rollouts.json", "r") as f:
    animals_data = json.load(f)

# %% cell 3
NUM_DAYS = 30
NUM_TILES = 9
SETUP_OP_OVERHEAD = 1

CROP_PROFILES = ("no_fert", "with_fert")
ANIMAL_PROFILES = ("no_care", "with_care")

elements = [(tile, day) for tile in range(NUM_TILES) for day in range(NUM_DAYS)]


def parse_age_maps(profile, label, kind):
    harvest_map = dict(zip(profile["harvest_ages"], profile["yield_per_harvest"]))
    ops_by_age = {}
    feed_by_age = {}
    fert_use_by_age = {}
    collect_by_age = {}
    wheat_gain_by_age = {}
    for day in profile["days"]:
        age = day["age"]
        acts = day["actions"]
        ops_by_age[age] = len(acts)
        feed_by_age[age] = 1 if "FEED" in acts else 0
        fert_use_by_age[age] = 1 if "FERTILIZE" in acts else 0
        collect_by_age[age] = 1 if "COLLECT_FERTILIZER" in acts else 0
        if kind == "crop" and label == "WHEAT" and age in harvest_map:
            wheat_gain_by_age[age] = harvest_map[age]
        else:
            wheat_gain_by_age[age] = 0
    return ops_by_age, feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age


def fill_daily_arrays(subset, ops_by_age, feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age):
    d_ops = [0] * NUM_DAYS
    d_feed = [0] * NUM_DAYS
    d_fert = [0] * NUM_DAYS
    d_collect = [0] * NUM_DAYS
    d_wheat = [0] * NUM_DAYS
    tile = subset["tile"]
    start = subset["start_day"]
    kind = subset["kind"]
    for d in range(NUM_DAYS):
        if (tile, d) not in subset["subset"]:
            continue
        age = d - start
        if age not in ops_by_age:
            continue
        n_ops = ops_by_age[age]
        if kind == "animal" and age == 0:
            n_ops += SETUP_OP_OVERHEAD
        d_ops[d] = n_ops
        d_feed[d] = feed_by_age.get(age, 0)
        d_fert[d] = fert_use_by_age.get(age, 0)
        d_collect[d] = collect_by_age.get(age, 0)
        d_wheat[d] = wheat_gain_by_age.get(age, 0)
    subset["daily_ops"] = d_ops
    subset["daily_feed"] = d_feed
    subset["daily_fert"] = d_fert
    subset["daily_collect"] = d_collect
    subset["daily_wheat"] = d_wheat


subsets = []

for crop_name, crop_spec in crops_data["crops"].items():
    seed_cost = crop_spec["seed_cost"]
    base_price = crop_spec["base_price"]
    for profile_name in CROP_PROFILES:
        if profile_name not in crop_spec:
            continue
        profile = crop_spec[profile_name]
        age_maps = parse_age_maps(profile, crop_name, "crop")

        for tile, start_day in elements:
            subset = {
                "id": f"S{len(subsets)}",
                "kind": "crop",
                "label": crop_name,
                "profile": profile_name,
                "tile": tile,
                "start_day": start_day,
                "subset": set(),
                "weight": 0,
            }
            fits = True
            for day in profile["days"]:
                cal = start_day + day["age"]
                if cal < NUM_DAYS:
                    subset["subset"].add((tile, cal))
                else:
                    fits = False
                    break
            if not fits:
                continue
            rev = sum(
                yld * base_price
                for age, yld in zip(profile["harvest_ages"], profile["yield_per_harvest"])
                if start_day + age < NUM_DAYS
            )
            subset["weight"] = rev - seed_cost
            (
                subset["ops_by_age"],
                subset["feed_by_age"],
                subset["fert_use_by_age"],
                subset["collect_by_age"],
                subset["wheat_gain_by_age"],
            ) = age_maps
            fill_daily_arrays(subset, *age_maps)
            subsets.append(subset)

for animal_name, animal_spec in animals_data["animals"].items():
    animal_cost = animal_spec["animal_cost"]
    base_price = animal_spec["base_price"]
    for profile_name in ANIMAL_PROFILES:
        profile = animal_spec[profile_name]
        age_maps = parse_age_maps(profile, animal_name, "animal")

        for tile, start_day in elements:
            subset = {
                "id": f"S{len(subsets)}",
                "kind": "animal",
                "label": animal_name,
                "profile": profile_name,
                "tile": tile,
                "start_day": start_day,
                "subset": set(),
                "weight": 0,
            }
            for age_day in profile["days"]:
                cal = start_day + age_day["age"]
                if cal < NUM_DAYS:
                    subset["subset"].add((tile, cal))
                else:
                    break
            if not subset["subset"]:
                continue
            rev = sum(
                yld * base_price
                for age, yld in zip(profile["harvest_ages"], profile["yield_per_harvest"])
                if start_day + age < NUM_DAYS
            )
            subset["weight"] = rev - animal_cost
            (
                subset["ops_by_age"],
                subset["feed_by_age"],
                subset["fert_use_by_age"],
                subset["collect_by_age"],
                subset["wheat_gain_by_age"],
            ) = age_maps
            fill_daily_arrays(subset, *age_maps)
            subsets.append(subset)

print(f"{len(subsets)} candidates")

# %% cell 4
# Declare the model
model = cp_model.CpModel()

# %% cell 5
# Define the variables - one binary decision var per candidate subset
y = {s["id"]: model.NewBoolVar(s["id"]) for s in subsets}

# %% cell 6
# Packing constraint: each element covered by at most one selected subset
for e in elements:
    covering = [y[s["id"]] for s in subsets if e in s["subset"]]
    if covering:
        model.Add(sum(covering) <= 1)

# %% cell 7
# Daily limit on the operations: 16 is the max number of operations per day
for day in range(NUM_DAYS):
    operations = [
        y[s["id"]] * s["daily_ops"][day]
        for s in subsets
        if s["daily_ops"][day]
    ]
    if day == 0:
        model.Add(sum(operations) <= 15)  # first day also has BUY_* market turn
    else:
        model.Add(sum(operations) <= 16)

# %% cell 8
# Closed wheat / fertilizer inventory (no BUY_PRODUCT)
MAX_INV = 500
W = [model.NewIntVar(0, MAX_INV, f"W_{d}") for d in range(NUM_DAYS + 1)]
F = [model.NewIntVar(0, MAX_INV, f"F_{d}") for d in range(NUM_DAYS + 1)]
model.Add(W[0] == 0)
model.Add(F[0] == 0)

for d in range(NUM_DAYS):
    feed_d = sum(y[s["id"]] * s["daily_feed"][d] for s in subsets)
    fert_d = sum(y[s["id"]] * s["daily_fert"][d] for s in subsets)
    collect_d = sum(y[s["id"]] * s["daily_collect"][d] for s in subsets)
    wheat_d = sum(y[s["id"]] * s["daily_wheat"][d] for s in subsets)
    model.Add(W[d] >= feed_d)
    model.Add(F[d] >= fert_d)
    model.Add(W[d + 1] == W[d] - feed_d + wheat_d)
    model.Add(F[d + 1] == F[d] - fert_d + collect_d)

# %% cell 9
# Objective: maximize harvest revenue minus seed/animal setup costs
model.Maximize(sum(s["weight"] * y[s["id"]] for s in subsets))

# %% cell 10
@peak_mem
def run(_solver):
    return _solver.Solve(model)

solver = cp_model.CpSolver()
status = run(solver)

print(status, solver.StatusName(status))
print("objective:", solver.ObjectiveValue())

# %% cell 11
selected = [s for s in subsets if solver.Value(y[s["id"]]) == 1]
print("n selected:", len(selected))
for s in selected:
    tag = f"{s['kind'][0]}{s['profile'][0]}{s['start_day']}"
    print(
        f"  {tag} {s['label']:10} {s['profile']:9} "
        f"tile={s['tile']} start={s['start_day']} weight={s['weight']:.0f}"
    )

daily_ops = [0] * NUM_DAYS
for s in selected:
    for d in range(NUM_DAYS):
        daily_ops[d] += s["daily_ops"][d]
print("peak ops/day:", max(daily_ops), "  day 0:", daily_ops[0])

trace_days = min(16, NUM_DAYS + 1)
print(f"\nInventory trace (solver W/F, d=0..{trace_days - 1}):")
print("  d    W[d]  F[d]")
for d in range(trace_days):
    print(f"  {d:2d}  {solver.Value(W[d]):5d}  {solver.Value(F[d]):5d}")

# %% cell 12
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

CROP_STYLE = {
    "WHEAT": {"color": "#e8c84a", "hatch": "///"},
    "CARROT": {"color": "#e8913a", "hatch": "+++"},
    "TOMATO": {"color": "#8bc34a", "hatch": "xxx"},
    "MELON": {"color": "#2e7d32", "hatch": "ooo"},
    "STRAWBERRY": {"color": "#d94f4f", "hatch": "..."},
}
ANIMAL_STYLE = {
    "GOOSE": {"color": "#90caf9", "hatch": "///"},
    "COW": {"color": "#8d6e63", "hatch": "ooo"},
    "SHEEP": {"color": "#eceff1", "hatch": "..."},
}


def bar_style(s):
    if s["kind"] == "crop":
        st = dict(CROP_STYLE.get(s["label"], {"color": "#999999", "hatch": ""}))
    else:
        st = dict(ANIMAL_STYLE.get(s["label"], {"color": "#999999", "hatch": ""}))
    if s["profile"] in ("with_fert", "with_care"):
        st["edgecolor"] = "#1565c0" if s["kind"] == "crop" else "#c62828"
        st["linewidth"] = 1.5
    else:
        st.setdefault("edgecolor", "#333333")
        st.setdefault("linewidth", 0.8)
    return st


fig, ax = plt.subplots(figsize=(14, 5))
for s in selected:
    days = sorted(d for _, d in s["subset"])
    start, end = days[0], days[-1] + 1
    st = bar_style(s)
    ax.barh(
        y=s["tile"],
        width=end - start,
        left=start,
        height=0.8,
        color=st["color"],
        hatch=st["hatch"],
        edgecolor=st["edgecolor"],
        linewidth=st["linewidth"],
    )
    tag = f"{s['kind'][0]}{s['profile'][0]}{s['start_day']}"
    ax.text(start + 0.15, s["tile"], tag, va="center", fontsize=7, color="#111")

ax.set_xlabel("day")
ax.set_ylabel("tile")
ax.set_yticks(range(NUM_TILES))
ax.set_xlim(0, NUM_DAYS)
ax.set_ylim(-0.6, NUM_TILES - 0.4)
ax.set_title("Coupled plan (crop + animal, closed wheat/fert loop)")
ax.invert_yaxis()
legend_handles = [
    Patch(facecolor=st["color"], hatch=st["hatch"], edgecolor="#333333", label=name)
    for name, st in {**CROP_STYLE, **ANIMAL_STYLE}.items()
]
ax.legend(handles=legend_handles, loc="upper right", ncol=4, fontsize=8)
ax.grid(axis="x", alpha=0.3)
plt.tight_layout()
plt.show()

