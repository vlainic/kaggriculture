"""Runtime WIS catalog for replan: lag-aware chains over remaining horizon."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent import animal_rollouts, rollouts

LAGS = (0, 1, 2)
CROP_PROFILE = "no_fert"
ANIMAL_PROFILE = "with_care"
BASE_CROPS = ("WHEAT", "CARROT")
EXTRA_CROPS = ("MELON", "TOMATO", "STRAWBERRY")
ANIMALS = ("GOOSE", "COW", "SHEEP")
# Near-best insert diversity (see .cursor/logs.txt)
INSERT_TOLERANCE = 0.05
INSERT_MAX_VARIANTS = 4


@dataclass(frozen=True)
class Template:
    name: str
    label: str
    tile_free_age: int
    setup_cost: int
    harvest_map: dict[int, int]
    is_animal: bool
    price_of: Callable[[str], int]

    def unit_price(self) -> int:
        product = (
            animal_rollouts.product_for(self.label)
            if self.is_animal
            else self.label
        )
        return self.price_of(product)

    def placement_value(self, start: int, horizon: int) -> int:
        value = -self.setup_cost
        price = self.unit_price()
        for age, units in self.harvest_map.items():
            day = start + age
            if day < horizon:
                value += units * price
        return value

    def _first_yield_day(self, start: int) -> int:
        return start + min(self.harvest_map)

    def fits(self, start: int, horizon: int) -> bool:
        return self._first_yield_day(start) < horizon


def _crop_template(crop: str, price_of: Callable[[str], int]) -> Template:
    harvest_map = dict(
        zip(
            rollouts.harvest_ages(crop, CROP_PROFILE),
            rollouts.yield_per_harvest(crop, CROP_PROFILE),
        )
    )
    return Template(
        name=f"{crop}_{CROP_PROFILE}",
        label=crop,
        tile_free_age=rollouts.tile_free_age(crop, CROP_PROFILE),
        setup_cost=rollouts.seed_cost(crop),
        harvest_map=harvest_map,
        is_animal=False,
        price_of=price_of,
    )


def _animal_template(animal: str, price_of: Callable[[str], int], horizon: int) -> Template:
    harvest_map = dict(
        zip(
            animal_rollouts.harvest_ages(animal, ANIMAL_PROFILE),
            animal_rollouts.yield_per_harvest(animal, ANIMAL_PROFILE),
        )
    )
    return Template(
        name=f"{animal}_{ANIMAL_PROFILE}",
        label=animal,
        tile_free_age=horizon,
        setup_cost=animal_rollouts.animal_cost(animal),
        harvest_map=harvest_map,
        is_animal=True,
        price_of=price_of,
    )


def _templates(price_of: Callable[[str], int], horizon: int) -> dict[str, Template]:
    out = [_crop_template(c, price_of) for c in BASE_CROPS + EXTRA_CROPS]
    out.extend(_animal_template(a, price_of, horizon) for a in ANIMALS)
    return {t.name: t for t in out}


def _placement(template: Template, start: int, horizon: int) -> dict:
    free_day = horizon if template.is_animal else start + template.tile_free_age
    return {
        "name": template.name,
        "start": start,
        "free_day": free_day,
        "value": template.placement_value(start, horizon),
        "template": template,
    }


def generate_placements(templates: list[Template], horizon: int) -> list[dict]:
    out = []
    for tmpl in templates:
        for start in range(horizon):
            if tmpl.fits(start, horizon):
                out.append(_placement(tmpl, start, horizon))
    return out


def weighted_interval_dp(candidates: list[dict], lag: int) -> tuple[int, list[dict]]:
    """WIS by finish day; seam rule next.start >= prev.free_day + lag."""
    cands = sorted(candidates, key=lambda c: (c["free_day"], c["start"]))
    n = len(cands)
    pred = [-1] * n
    for i in range(n):
        lo, hi, best = 0, i - 1, -1
        while lo <= hi:
            mid = (lo + hi) // 2
            if cands[mid]["free_day"] + lag <= cands[i]["start"]:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        pred[i] = best

    dp = [0] * (n + 1)
    take = [False] * n
    for i in range(1, n + 1):
        idx = i - 1
        prev_val = dp[pred[idx] + 1] if pred[idx] >= 0 else 0
        incl = cands[idx]["value"] + prev_val
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
            i = pred[idx] + 1 if pred[idx] >= 0 else 0
        else:
            i -= 1
    selected.reverse()
    return dp[n], selected


def placements_to_chain(selected: list[dict]) -> list[list]:
    return [[p["name"], p["start"]] for p in selected]


def chain_value(chain: list[list], templates: dict[str, Template], horizon: int) -> int:
    return sum(templates[name].placement_value(start, horizon) for name, start in chain)


def _mono_greedy_from(
    template: Template, lag: int, horizon: int, start: int = 0
) -> list[list]:
    chain: list[list] = []
    while template.fits(start, horizon):
        chain.append([template.name, start])
        start = start + template.tile_free_age + lag
    return chain


def _mono_greedy(template: Template, lag: int, horizon: int) -> list[list]:
    return _mono_greedy_from(template, lag, horizon, 0)


def _base_templates(templates: dict[str, Template], base: str) -> list[Template]:
    if base == "mix":
        return [templates[f"{c}_{CROP_PROFILE}"] for c in BASE_CROPS]
    return [templates[f"{base}_{CROP_PROFILE}"]]


def _pack_window(
    templates: dict[str, Template],
    base_tmps: list[Template],
    lag: int,
    horizon: int,
    start_min: int,
    end_exclusive: int,
) -> list[list]:
    cands = [
        c
        for c in generate_placements(base_tmps, horizon)
        if c["start"] >= start_min and c["free_day"] + lag <= end_exclusive
    ]
    _, selected = weighted_interval_dp(cands, lag)
    return placements_to_chain(selected)


def _thin_near_best(
    scored: list[tuple[int, list[list]]],
    *,
    tolerance: float,
    max_variants: int,
    sort_start: Callable[[list[list]], int],
) -> list[list[list]]:
    if not scored:
        return []
    best_val = max(v for v, _ in scored)
    best_chain = next(c for v, c in scored if v == best_val)

    threshold = best_val - abs(best_val) * tolerance
    kept = [c for v, c in scored if v >= threshold]
    seen: set[tuple] = set()
    unique: list[list[list]] = []
    for c in kept:
        key = tuple((name, start) for name, start in c)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    unique.sort(key=sort_start)

    step = max(1, len(unique) // max_variants)
    thinned = unique[::step][:max_variants]

    best_key = tuple((name, start) for name, start in best_chain)
    if not any(tuple((n, s) for n, s in c) == best_key for c in thinned):
        thinned = [best_chain] + thinned[: max_variants - 1]
    return thinned


def _merge_variant_sets(*sets: list[list[list]]) -> list[list[list]]:
    seen: set[tuple] = set()
    out: list[list[list]] = []
    for group in sets:
        for c in group:
            key = tuple((name, start) for name, start in c)
            if key not in seen:
                seen.add(key)
                out.append(c)
    return out


def build_catalog(
    horizon: int,
    price_of: Callable[[str], int],
    lags: int | tuple[int, ...] | None = None,
    *,
    tolerance: float = INSERT_TOLERANCE,
    max_variants: int = INSERT_MAX_VARIANTS,
) -> list[list]:
    """Handmade-format chains for days 0..horizon-1 relative to replan day.

    ``lags`` selects WIS seam gaps (and animal-only start days). ``None`` uses
    module ``LAGS``; a single int is treated as a 1-tuple.

    Insert families keep near-best landing days (``tolerance`` / ``max_variants``)
    without forcing wheat/carrot prefixes before the insert.
    """
    if horizon <= 0:
        return [[]]

    if lags is None:
        lag_set: tuple[int, ...] = LAGS
    elif isinstance(lags, int):
        lag_set = (lags,)
    else:
        lag_set = tuple(lags)

    templates = _templates(price_of, horizon)
    mix_tmps = _base_templates(templates, "mix")
    chains: list[list] = []

    def mono(crop: str, lag: int) -> list[list]:
        return _mono_greedy(templates[f"{crop}_{CROP_PROFILE}"], lag, horizon)

    def mix(lag: int) -> list[list]:
        _, selected = weighted_interval_dp(generate_placements(mix_tmps, horizon), lag)
        return placements_to_chain(selected)

    def insert_crop(extra_crop: str, lag: int) -> list[list[list]]:
        extra = templates[f"{extra_crop}_{CROP_PROFILE}"]
        scored: list[tuple[int, list[list]]] = []
        for t_extra in range(horizon):
            prefix = _mono_greedy_from(extra, lag, horizon, t_extra)
            if not prefix:
                continue
            last_start = prefix[-1][1]
            suffix_start = last_start + extra.tile_free_age + lag
            suffix = (
                _pack_window(templates, mix_tmps, lag, horizon, suffix_start, horizon)
                if suffix_start < horizon
                else []
            )
            chain = prefix + suffix
            val = chain_value(chain, templates, horizon)
            scored.append((val, chain))
        return _thin_near_best(
            scored,
            tolerance=tolerance,
            max_variants=max_variants,
            sort_start=lambda c: next(
                start for name, start in c if name == extra.name
            ),
        )

    def insert_animal(animal: str, lag: int) -> list[list[list]]:
        animal_tmpl = templates[f"{animal}_{ANIMAL_PROFILE}"]
        scored: list[tuple[int, list[list]]] = []
        for t in range(horizon):
            if not animal_tmpl.fits(t, horizon):
                continue
            chain = [[animal_tmpl.name, t]]
            val = chain_value(chain, templates, horizon)
            scored.append((val, chain))
        return _thin_near_best(
            scored,
            tolerance=tolerance,
            max_variants=max_variants,
            sort_start=lambda c: c[-1][1],
        )

    for lag in lag_set:
        chains.append(mono("WHEAT", lag))
        chains.append(mono("CARROT", lag))
        chains.append(mix(lag))

    for lag in lag_set:
        for extra in EXTRA_CROPS:
            chains.extend(insert_crop(extra, lag))
        for animal in ANIMALS:
            chains.extend(insert_animal(animal, lag))

    for animal in ANIMALS:
        for start in lag_set:
            chains.append([[f"{animal}_{ANIMAL_PROFILE}", start]])

    chains.append([])
    return _merge_variant_sets(chains)
