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

    def fits(self, start: int, horizon: int) -> bool:
        if self.is_animal:
            return start < horizon
        return start + self.tile_free_age < horizon


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


def _mono_greedy(template: Template, lag: int, horizon: int) -> list[list]:
    chain, start = [], 0
    while template.fits(start, horizon):
        chain.append([template.name, start])
        start = start + template.tile_free_age + lag
    return chain


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


def build_catalog(horizon: int, price_of: Callable[[str], int]) -> list[list]:
    """Handmade-format chains for days 0..horizon-1 relative to replan day."""
    if horizon <= 0:
        return [[]]

    templates = _templates(price_of, horizon)
    chains: list[list] = []

    def mono(crop: str, lag: int) -> list[list]:
        return _mono_greedy(templates[f"{crop}_{CROP_PROFILE}"], lag, horizon)

    def mix(lag: int) -> list[list]:
        base_tmps = _base_templates(templates, "mix")
        _, selected = weighted_interval_dp(generate_placements(base_tmps, horizon), lag)
        return placements_to_chain(selected)

    def insert_crop(base: str, extra_crop: str, lag: int) -> list[list]:
        extra = templates[f"{extra_crop}_{CROP_PROFILE}"]
        base_tmps = _base_templates(templates, base)
        best_chain, best_val = [], -10**18
        for t_extra in range(horizon):
            if not extra.fits(t_extra, horizon):
                continue
            prefix = _pack_window(templates, base_tmps, lag, horizon, 0, t_extra)
            suffix_start = t_extra + extra.tile_free_age + lag
            suffix = (
                _pack_window(templates, base_tmps, lag, horizon, suffix_start, horizon)
                if suffix_start < horizon
                else []
            )
            chain = prefix + [[extra.name, t_extra]] + suffix
            val = chain_value(chain, templates, horizon)
            if val > best_val:
                best_val, best_chain = val, chain
        return best_chain

    def insert_animal(base: str, animal: str, lag: int) -> list[list]:
        animal_tmpl = templates[f"{animal}_{ANIMAL_PROFILE}"]
        base_tmps = _base_templates(templates, base)
        best_chain, best_val = [], -10**18
        for t in range(horizon):
            if not animal_tmpl.fits(t, horizon):
                continue
            prefix = _pack_window(templates, base_tmps, lag, horizon, 0, t)
            chain = prefix + [[animal_tmpl.name, t]]
            val = chain_value(chain, templates, horizon)
            if val > best_val:
                best_val, best_chain = val, chain
        return best_chain

    for lag in LAGS:
        chains.append(mono("WHEAT", lag))
        chains.append(mono("CARROT", lag))
        chains.append(mix(lag))

    for base in ("WHEAT", "CARROT", "mix"):
        for lag in LAGS:
            for extra in EXTRA_CROPS:
                chains.append(insert_crop(base, extra, lag))
            for animal in ANIMALS:
                chains.append(insert_animal(base, animal, lag))

    for animal in ANIMALS:
        for start in LAGS:
            chains.append([[f"{animal}_{ANIMAL_PROFILE}", start]])

    chains.append([])
    return chains
