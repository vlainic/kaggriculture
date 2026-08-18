# Market price thresholds

Inventory levels where quoted sell price hits key fractions of **base**, plus the **$1 floor**. Source of truth for parameters: [README.md](README.md) § Market Mechanics. **I0 = 10,000** for every product.

**Notation:** **`d+ = inv − I0`** (glut). **`d− = I0 − inv`** (scarcity). Quoted price = `max(1, round(raw))`.

## Formula

**Glut** (`inv > I0`):

```
price(inv) = base − amp · f(d+)
amp       = above_target · base / f(T)
```

**Scarcity** (`inv < I0`):

```
price(inv) = base + amp · f(d−)
amp       = below_target · base / f(T)
```

`f ∈ { linear, sq, sqrt, log }` where **log = ln(1+x)**.

---

## Glut — price **falls** (`inv > I0`)

At **100% of base** price equals base at **`inv = I0`** (+0). Tables give the **first** `d+` where quoted price ≤ target.

| Resource | Base | 100% d+ | 100% inv | 50% d+ | 50% inv | 20% d+ | 20% inv | $1 d+ | $1 inv |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Wheat | 25 | 0 | 10,000 | — | — | — | — | — | — |
| Carrot | 35 | 0 | 10,000 | 205 | 10,205 | 567 | 10,567 | 842 | 10,842 |
| Tomato | 60 | 0 | 10,000 | 135 | 10,135 | 349 | 10,349 | 529 | 10,529 |
| Strawberry | 120 | 0 | 10,000 | 31 | 10,031 | 50 | 10,050 | 62 | 10,062 |
| Melon | 250 | 0 | 10,000 | 112 | 10,112 | 142 | 10,142 | 158 | 10,158 |
| Egg | 50 | 0 | 10,000 | — | — | — | — | — | — |
| Milk | 160 | 0 | 10,000 | 38 | 10,038 | 61 | 10,061 | 76 | 10,076 |
| Wool | 200 | 0 | 10,000 | 42 | 10,042 | 53 | 10,053 | 59 | 10,059 |
| Fertilizer | 100 | 0 | 10,000 | 248 | 10,248 | 398 | 10,398 | 493 | 10,493 |

### Glut target prices (rounded)

| Resource | 100% | 50% | 20% | Floor |
| --- | ---: | ---: | ---: | ---: |
| Wheat | $25 | $12 | $5 | — |
| Carrot | $35 | $18 | $7 | $1 |
| Tomato | $60 | $30 | $12 | $1 |
| Strawberry | $120 | $60 | $24 | $1 |
| Melon | $250 | $125 | $50 | $1 |
| Egg | $50 | $25 | $10 | — |
| Milk | $160 | $80 | $32 | $1 |
| Wool | $200 | $100 | $40 | $1 |
| Fertilizer | $100 | $50 | $20 | $1 |

### Calibration anchors (not the $1 crossing)

| Resource | T | Above | P(I0+T) | P(I0+2T) |
| --- | ---: | --- | ---: | ---: |
| Wheat | 400 | log / 0.20 | $20 | $19 |
| Carrot | 450 | sqrt / 0.70 | $10 | $1 |
| Tomato | 200 | sqrt / 0.60 | $24 | $9 |
| Strawberry | 100 | linear / 1.60 | $1 | $1 |
| Melon | 300 | sq / 3.60 | $1 | $1 |
| Egg | 332 | log / 0.20 | $40 | $39 |
| Milk | 122 | linear / 1.60 | $1 | $1 |
| Wool | 105 | sq / 3.20 | $1 | $1 |
| Fertilizer | 200 | linear / 0.40 | $60 | $20 |

**P(I0+T)** = “moving **T** past I0 shifts price by **target × base**” — premium goods often hit $1 **well before** I0+T (melon: floor at +158, not +300).

**Glut notes**

- **Wheat & egg** — `log` above curve; 50%, 20%, and $1 need ~10⁶–10¹² excess (never in a season). ~$17 at +10k glut for wheat.
- **Premium** — 50% within **+31…+112**; 20% / $1 within **+50…+158**.
- **Melon @ 20%** — first ≤ $50 at +142 (quote $48); floor at +158.
- **Wool @ 50%** — first ≤ $100 at +42 (quote $98).

---

## Scarcity — price **rises** (`inv < I0`)

**100%** at **`inv = I0`**. Smallest **d−** where quoted price ≥ target:

| Resource | Base | 100% d− | 100% inv | 120% d− | 120% inv | 150% d− | 150% inv | 200% d− | 200% inv |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Wheat | 25 | 0 | 10,000 | 21 | 9,979 | 157 | 9,843 | 601 | 9,399 |
| Carrot | 35 | 0 | 10,000 | 291 | 9,709 | — | — | — | — |
| Tomato | 60 | 0 | 10,000 | 96 | 9,904 | 246 | 9,754 | 496 | 9,504 |
| Strawberry | 120 | 0 | 10,000 | 8 | 9,992 | 51 | 9,949 | 203 | 9,797 |
| Melon | 250 | 0 | 10,000 | 284 | 9,716 | — | — | — | — |
| Egg | 50 | 0 | 10,000 | 158 | 9,842 | 407 | 9,593 | 822 | 9,178 |
| Milk | 160 | 0 | 10,000 | 14 | 9,986 | 84 | 9,916 | 337 | 9,663 |
| Wool | 200 | 0 | 10,000 | 99 | 9,901 | — | — | — | — |
| Fertilizer | 100 | 0 | 10,000 | 98 | 9,902 | 248 | 9,752 | 498 | 9,502 |

### Scarcity target prices (rounded)

| Resource | 120% | 150% | 200% |
| --- | ---: | ---: | ---: |
| Wheat | $30 | $38 | $50 |
| Carrot | $42 | — | — |
| Tomato | $72 | $90 | $120 |
| Strawberry | $144 | $180 | $240 |
| Melon | $300 | — | — |
| Egg | $60 | $75 | $100 |
| Milk | $193 | $240 | $320 |
| Wool | $240 | — | — |
| Fertilizer | $120 | $150 | $200 |

**Scarcity notes**

- **Carrot, melon, wool** — `log` below curve caps near P(I0−T); no 150%/200% within inv ≥ 0.
- **Strawberry** — 120% at only **−8** (inv 9,992).
- **Melon** — scarce side barely moves (−284 for 120%); glut crashes fast.

---

## By strategic tier

| Tier | Products | Glut sensitivity | Scarcity upside |
| --- | --- | --- | --- |
| **Premium** | strawberry, melon, milk, wool | $1 at +59…+158 | low (melon/wool capped) |
| **Mid** | tomato, carrot, fertilizer | $1 at +493…+842 | moderate |
| **Glut-resistant** | wheat, egg | no $1 in practice | wheat spikes at −601 for 200% |

~**60–160** net sells above I0 can wipe premium pricing. Two players dumping melons cross 50% after ~112 units.

---

## Closed-form (glut, raw price = target)

Solve `amp · f(d+) = base − target` when above func is not log:

| Above `f` | **d+ at raw = target** |
| --- | --- |
| linear | `(base − target) · f(T) / (above_target · base)` |
| sqrt | `((base − target) · f(T) / (above_target · base))²` |
| sq | `√((base − target) · f(T) / (above_target · base))` |
| log | `exp((base − target) · f(T) / (above_target · base)) − 1` → huge for wheat/egg |

Integer columns use **`max(1, round(raw))`**, so crossings can differ by 1 from continuous math (carrot $1: continuous ≈ +867, table +842).

---

## Gameplay caveats

1. **Shared pool** — both players’ sells, minus town drain and `BUY_PRODUCT` (wheat/fertilizer).
2. **$1 floor absorption** — at $1, sells pay $1 but **do not increase** inventory; price can recover on buys/drain.
3. **Pre-sell quoting** — each unit priced at inventory before that unit is added; orders interleave one unit at a time.
4. **Town drain** — shops + town center remove stock every 4–12 turns. See README § Town Buildings.

---

## Reproduce

```python
import math

I0 = 10_000

def f(name, x):
    return {"linear": x, "sq": x*x, "sqrt": math.sqrt(x), "log": math.log(1+x)}[name]

def quoted(base, d, func, target, T, glut=True):
    amp = target * base / f(func, T)
    raw = base - amp * f(func, d) if glut else base + amp * f(func, d)
    return max(1, round(raw))

def glut_cross(base, T, af, at, want):
    for d in range(200_000):
        if quoted(base, d, af, at, T, True) <= want:
            return d, I0 + d
    return None, None

def scarcity_cross(base, T, bf, bt, want):
    for d in range(1, I0):
        if quoted(base, d, bf, bt, T, False) >= want:
            return d, I0 - d
    return None, None
```

Parameters match `MARKET_PARAMS` in `kaggriculture.py` (kaggle-environments).
