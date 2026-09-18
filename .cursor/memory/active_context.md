# Active Context

## Current focus (Sep 18, 2026)

**Live agent = TwoLand WSP.** `CURRENT_SOLVER = "twoland_wsp"`, `zoning.CURRENT = TWO`. Opt-in: `KAGGRI_LANDS=3` → ThreeLand / `threeland_wsp`.

### Critical engine rule — shed-adjacent **ONLY IF OWNED**

The four center tiles `(4,4)`, `(5,4)`, `(4,5)`, `(5,5)` are “shed-adjacent” in the rules, but **PICKUP / DROP no-op on a `LOCKED` tile** (tile actions no-op; logs confirmed shed never drains).

| Tile | Quadrant | OneLand | TwoLand (NW+NE) | ThreeLand (+SW) |
| --- | --- | --- | --- | --- |
| `(4,4)` | NW | owned | owned | owned |
| `(5,4)` | NE | **LOCKED** | owned after 1st `BUY_LAND` | same |
| `(4,5)` | SW | **LOCKED** | **LOCKED all game** | owned after 2nd `BUY_LAND` ($2k) |
| `(5,5)` | SE | **LOCKED** | **LOCKED all game** | **LOCKED all game** |

**Never** treat `pos in SHED_ADJACENT` alone as permission to PICKUP/DROP. Gate on **owned** shed tiles: `me["tiles"][y][x] != "LOCKED"` (`executor._owned_shed_tiles`).

**Natural path (live):** owned-shed first → PICKUP → compass into zone. Executor `_step_to_owned_shed` walks 0–2 steps to nearest owned center; FIVE hire1–4 preambles are pickup-first. This is **not** Sept02 mid-zone walk-to-shed.

### Status

| Item | State |
| --- | --- |
| Live agent | **`twoland_wsp` + `CURRENT = TWO`** |
| Land buys | NE $1k; `BUY_LAND_DAY` kept through buy day, cleared next dawn (`day > BUY_LAND_DAY`) |
| ThreeLand | Opt-in `KAGGRI_LANDS=3` — NE then SW $2k |
| Sept02 overhaul | Still **FAILED** — do not resume mid-zone walk-to-shed |

### Anti-patterns (still)

- Treating any of the four center tiles as a valid shed door without checking `LOCKED`
- Blind compass before `PICKUP_*` that walks off the only owned door
- Mid-zone pathfind-to-shed (Sept02 regression)
- Floor `conservative` at 0 / `cons >= min_balance`
- `track_shed=True` on WSP replan with W/F in conservative spend

### Immediate next steps

1. Ladder / diagnose post-NE ops gap as user asks (`docs/twoland/diagnosis_0911.md`)
2. Agents never submit without explicit ask
