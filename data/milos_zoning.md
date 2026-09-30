# MILOS FINAL

## ThreeLand 4-man (live default)

Geometry matches [`handmade_pseudoplan.md`](handmade_pseudoplan.md) and legacy `agent/zoning.py` `FOUR` (9 + 6 + 6 + 4 tiles per land). Implemented as **`MILOS_THREELAND12`** in `milos/zoning.py` (`KAGGRI_LAYOUT=threeland12`, default). Legacy **5-man** remains `KAGGRI_LAYOUT=threeland15`.

---

## NW-land: 4-man

All **3** hires bought at h=0 (HIRE orders first in the h=0 market list).

- market h=0 only (no mid-day BUY wheat / animal / seed):
    - wheat (feed reserve)
    - then animal (shed pickup before PLACE)
    - finally plant seed

### Tile numbering (1-based)

Shed door = tile **1** at `(4, 4)`.

```text
24 23 13 14 15
25 22 12 11 10
19 18  9  8  7
20 17  4  5  6
21 16  3  2  1
```

**0-based indices** (env visit order): farmer `0..8`, Top `9..14`, Left `15..20`, Corner `21..24`.

### Zone assignment

| Zone | Worker | Tiles (1-based) | Count |
|------|--------|-----------------|------:|
| Farmer | farmer | 1–9 | 9 |
| Top | hire1 | 10–15 | 6 |
| Left | hire2 | 16–21 | 6 |
| Corner | hire3 | 22–25 | 4 |

- Hire1 spawned **NE** of shed (top-right adjacent); handles **Top**.
- Hire2 spawned **SW** of shed (bottom-left adjacent); handles **Left**.
- Hire3 handles **Corner** (also hired at h=0 with hire1/hire2).

### Pre-defined movement snakes

- Farmer: buying & pickup (if needed); in-zone **2×W, N, 2×E, N, 2×W**
- Hire1 (Top): **W**, then pickup if animal else **3×N** to zone; in-zone **2×W, N, 2×E**
- Hire2 (Left): **N**, then pickup if animal else **3×W** to zone; in-zone **2×N, W, 2×S**
- Hire3 (Corner): **W**, then pickup if animal else **3×W + 3×N** to zone; in-zone **N, W, S**

### Ops-limits

- Farmer = 14
- Hire1 = 12
- Hire2 = 12
- Hire3 = 10

---

## NE-land: 4-man

Mirror NW across the land boundary: coord `(x, y) → (9 − x, y)`. Tiles **26–50**. Hired at **h=1** (−1 net tile op vs NW). Market h=0–1 (extend to h=2 on NE buy day); no mid-day BUY after buy window closes.

### Tile numbering (1-based)

LR mirror of NW (`x' = 9 − x`, same `y`; north = top, matching NW diagram):

```text
40 39 38 48 49
35 36 37 47 50
32 33 34 43 44
31 30 29 42 45
26 27 28 41 46
```

### Zone assignment

| Zone | Worker | Tiles (1-based) | Count |
|------|--------|-----------------|------:|
| Farmer mirror | hire4 | 26–34 | 9 |
| Top mirror | hire5 | 35–40 | 6 |
| East mirror (was Left) | hire6 | 41–46 | 6 |
| Corner mirror | hire7 | 47–50 | 4 |

Preamble: walk to **owned NE shed-adjacent**, `PICKUP` wheat/animals as needed, then mirrored travel (**E** instead of **W**).

### Pre-defined movement snakes (mirror of NW)

- Hire4 (9-tile patch): in-zone **2×E, N, 2×W, N, 2×E** (mirror of farmer snake); approach via owned NE shed-adjacent **PICKUP** then column entry as implemented
- Hire5 (Top mirror): **E**, pickup if animal else **3×N**; in-zone **2×E, N, 2×W**
- Hire6 (East mirror): **N**, pickup if animal else **3×E**; in-zone **2×N, E, 2×S**
- Hire7 (Corner mirror): **E**, pickup if animal else **3×E + 3×N**; in-zone **N, E, S**

### Ops-limits

- Hire4 = 13
- Hire5 = 11
- Hire6 = 11
- Hire7 = 9

---

## SW-land: 4-man

Mirror NW south: `(x, y) → (x, 9 − y)`. Tiles **51–75**. Hired at **h=1** (−1 net tile op vs NW, same as NE). Market h=0–1 (extend on SW buy day); no mid-day BUY after buy window closes.

### Tile numbering (1-based)

UD mirror of NW (`y' = 9 − y`, same `x`; north/toward shed = top):

```text
71 66 53 52 51
70 67 54 55 56
69 68 59 58 57
75 72 62 61 60
74 73 63 64 65
```

### Zone assignment

| Zone | Worker | Tiles (1-based) | Count |
|------|--------|-----------------|------:|
| Farmer mirror | hire8 | 51–59 | 9 |
| Top mirror | hire9 | 60–65 | 6 |
| West mirror (was Left) | hire10 | 66–71 | 6 |
| Corner mirror | hire11 | 72–75 | 4 |

Preamble: **owned SW shed-adjacent**, `PICKUP`, then mirrored travel (**S** instead of **N** where applicable).

### Pre-defined movement snakes (mirror of NW)

- Hire8 (9-tile patch): in-zone **2×W, S, 2×E, S, 2×W** (mirror of farmer snake); **PICKUP** at owned SW shed-adjacent first
- Hire9 (Top mirror): **W**, pickup if animal else **3×S**; in-zone **2×W, S, 2×E**
- Hire10 (West mirror): **S**, pickup if animal else **3×W**; in-zone **2×S, W, 2×N**
- Hire11 (Corner mirror): **W**, pickup if animal else **3×W + 3×S**; in-zone **S, W, N**

### Ops-limits

- Hire8 = 13
- Hire9 = 11
- Hire10 = 11
- Hire11 = 9

---

## NW-land: 5-man
All 4 hires bought at h=0 (when implemented: HIRE orders first in the h=0 market list).
- market h=0 only (no mid-day BUY wheat / animal / seed):
    - wheat (feed reserve)
    - then animal (shed pickup before PLACE)
    - finally plant seed

### Tile numbering:

zone:    V IV III II  I
        25 20  15 10  5
        24 19  14  9  4
        23 18  13  8  3
        22 17  12  7  2
        21 16  11  6  1

### Zone assignement

- Farmer @ zone I
- Hire 1 = spawned at NW @ zone V
- Hire 2 = spawned at NE @ zone IV
- Hire 3 = spawned at SW @ zone III
- Hire 4 = spawned at SE @ zone II


### Pre-defined movement snakes:
- Farmer: buying & pickup (if needed), just 4xN [buying in parallel, ofc]
- Hire 1: pickup (if needed), 4xW to zone -> then 4xN
- Hire 2: 1xW, pickup (if needed), 3xW to zone -> then 4xN
- Hire 3: 1xN, pickup (if needed), 2xW to zone -> then 4xN
- Hire 4: 1xW, 1xN, pickup (if needed), 1xW to zone -> then 4xN


### Ops-limits:
 
- Farmer = 18
- Hire 1 = 14
- Hire 2 = 14
- Hire 3 = 15
- Hire 4 = 15

## NW-land: 6-man
All 5 hires bought at h=0 (when implemented: HIRE orders first in the h=0 market list).
- market h=0 only (no mid-day BUY wheat / animal / seed):
    - wheat (feed reserve)
    - then animal (shed pickup before PLACE)
    - finally plant seed

### Tile numbering:

zone:    V  IV  III II   I
  VI   [25  24  23  22]  5
        21  17  13   9   4
        20  16  12   8   3
        19  15  11   7   2
        18  14  10   6   1

### Zone assignement

- Farmer @ zone I
- Hire 1 = spawned at NW @ zone V
- Hire 2 = spawned at NE @ zone IV
- Hire 3 = spawned at SW @ zone III
- Hire 4 = spawned at SE @ zone II
- Hire 5 = twofold spawn, could be NW or NE @ zone VI


### Pre-defined movement snakes:
- Farmer: buying & pickup (if needed), just 4xN [buying in parallel, ofc]
- Hire 1: pickup (if needed), 4xW to zone -> then 3xN
- Hire 2: 1xW, pickup (if needed), 3xW to zone -> then 3xN
- Hire 3: 1xN, pickup (if needed), 2xW to zone -> then 3xN
- Hire 4: 1xW, 1xN, pickup (if needed), 1xW to zone -> then 3xN
- Hire 5: 1xW (if not spawned at NW, but rather NE), pickup (if needed), 4xN+1xW to zone -> then 3xW


### Ops-limits:
 
- Farmer = 18
- Hire 1 = 15
- Hire 2 = 15
- Hire 3 = 16
- Hire 4 = 16
- Hire 5 = 13

**Live code** keeps the 5-man column tile index order (`milos/zoning.py`); zone VI is tiles **10, 15, 20, 25** (indices 9, 14, 19, 24), not the diagram row 22–25 above.

## NE-land: 6-man

Basically mirroring NW! Note that there will be 1 ops less, because they are hired at h=1!

All 6 hires bought at h=1 (when implemented: HIRE orders first in the h=1 market list).
- market h=0-1 only (no mid-day BUY wheat / animal / seed):
    - wheat (feed reserve)
    - then animal (shed pickup before PLACE)
    - finally plant seed
    - leftover can be bought in h=2+, but after buying is over -> NO MID-DAY!

## Tile numbering:
* is done as mirrong 5-man if we decide to revert ;)

zone:  VII VIII IX   X XI
        30 [35  40  45 50] -> XII
        29  34  39  44 49
        28  33  38  43 48
        27  32  37  42 47
        26  31  36  41 46

### Zone assignement

- Hire 6 = there is for sure duplicate spawn at NE @ zone VII
- Hire 7 = spawned at NE @ zone XI
- Hire 8 = spawned at NW @ zone X
- Hire 9 = spawned at SE @ zone IX
- Hire 10 = spawned at SW @ zone VIII
- Hire 11 = twofold spawn, could be NW, SW or even SE @ zone XII


### Pre-defined movement snakes:
- Hire 6: pickup (if needed), just 4xN
- Hire 7: pickup (if needed), 4xE to zone -> then 3xN
- Hire 8: 1xE, pickup (if needed), 3xE to zone -> then 3xN
- Hire 9: 1xN, pickup (if needed), 2xE to zone -> then 3xN
- Hire 10: 1xE, 1xN, pickup (if needed), 1xE to zone -> then 3xN
- Hire 11: move to NE-shed-adjacent = (5,4), pickup (if needed), 4xN+1xE to zone -> then 3xE


### Ops-limits:
 
- Hire 6 = 17
- Hire 7 = 14
- Hire 8 = 14
- Hire 9 = 15
- Hire 10 = 15
- Hire 11 = 12

## SW-land: 6-man

Basically mirroring NW! Note that there will be 2 ops less, because they are hired at h=2!

All 6 hires bought at h=2 (when implemented: HIRE orders first in the h=2 market list).
- market h=0-2 only (no mid-day BUY wheat / animal / seed):
    - wheat (feed reserve)
    - then animal (shed pickup before PLACE)
    - finally plant seed
    - leftover can be bought in h=3+, but after buying is over -> NO MID-DAY!

## Tile numbering:
* is done as mirrong 5-man if we decide to revert ;)

zone:    XVII XVI  XV XIV XIII
          71   66  61  56  51 
          72   67  62  57  52
          73   68  63  58  53
          74   69  64  59  54
XVIII -> [75   70  65  60] 55

### Zone assignement

- Hire 12 = spawned at SW @ zone XIII
- Hire 13 = spawned at SE @ zone XVII
- Hire 14 = spawned at NW @ zone XVI
- Hire 15 = spawned at NE @ zone XV
- Hire 16 = duplicate spawn at NW or NE @ zone XIV
- Hire 17 = second duplicate spawn, could be anywhere @ zone XVIII


### Pre-defined movement snakes:
- Hire 12: pickup (if needed), just 4xS
- Hire 13: 1xW, pickup (if needed), 4xW to zone -> then 3xS
- Hire 14: 1xS, pickup (if needed), 3xW to zone -> then 3xS
- Hire 15: 1xS, 1xW, pickup (if needed), 2xW to zone -> then 3xS
- Hire 16: 1xS + 1 more if needed to SW-shed = (4,5), pickup (if needed), 1xW to zone -> then 3xS
- Hire 17: move to SW-shed-adjacent = (4,5), pickup (if needed), 4xS+1xW to zone -> then 3xW


### Ops-limits:
 
- Hire 12 = 16
- Hire 13 = 12
- Hire 14 = 13
- Hire 15 = 13
- Hire 16 = 14
- Hire 17 = 11

## NE-land: 5-man (live default with MILOS_THREELAND15)

Mirrors NW 5-man columns. Hired at **h=1** (1 fewer market hour than NW).

All **5** hires at h=1; market buy window h=0–1 (extend to h=2 on NE buy day).

### Tile indices (env order, columns x=5..9)

| Zone | Hire | Tiles |
|------|------|-------|
| VII | hire5 | 25–29 |
| VIII | hire6 | 30–34 |
| IX | hire7 | 35–39 |
| X | hire8 | 40–44 |
| XI | hire9 | 45–49 |

Preamble: `PICKUP` only (walk to owned shed, then column snake).

### Ops-limits

- hire5 = 17, hire6 = 14, hire7 = 14, hire8 = 13, hire9 = 13

## SW-land: 5-man (live default with MILOS_THREELAND15)

Mirrors NW columns south of y=5. Hired at **h=2** (2 fewer market hours than NW).

All **5** hires at h=2; market buy window h=0–3 on SW buy day.

### Tile indices (columns x=4..0 south)

| Zone | Hire | Tiles |
|------|------|-------|
| XIII | hire10 | 50–54 |
| XIV | hire11 | 55–59 |
| XV | hire12 | 60–64 |
| XVI | hire13 | 65–69 |
| XVII | hire14 | 70–74 |

Preamble: `PICKUP` only.

### Ops-limits

- hire10 = 16, hire11 = 13, hire12 = 12, hire13 = 12, hire14 = 11

**Layout env (live):** `KAGGRI_LAYOUT=threeland12` (default), `threeland15`, `threeland18`, `twoland12`; `KAGGRI_SW=0` disables SW buy/activate only. Day-0 loads `milos/wsp/wsp4_prestart.json` and buys NE at h=0; day-1 fills NE zones (staple WHEAT/CARROT probe); SW dusk cash ≥ $3000, overage ≥ 20s.