# Active Context

## Current focus (Sep 15, 2026)

**Live agent = TwoLand WSP.** `CURRENT_SOLVER = "twoland_wsp"`, `zoning.CURRENT = TWO`. Re-added from [`docs/twolands/twoland_readd.md`](../../docs/twolands/twoland_readd.md).

### Critical engine rule — shed-adjacent **ONLY IF OWNED**

The four center tiles `(4,4)`, `(5,4)`, `(4,5)`, `(5,5)` are “shed-adjacent” in the rules, but **PICKUP / DROP no-op on a `LOCKED` tile** (tile actions no-op; logs confirmed shed never drains).

| Tile | Quadrant | OneLand | TwoLand (NW+NE) |
| --- | --- | --- | --- |
| `(4,4)` | NW | owned | owned |
| `(5,4)` | NE | **LOCKED** | owned after `BUY_LAND` |
| `(4,5)` | SW | **LOCKED** | **LOCKED all game** |
| `(5,5)` | SE | **LOCKED** | **LOCKED all game** |

**Never** treat `pos in SHED_ADJACENT` alone as permission to PICKUP/DROP. Gate on **owned** shed tiles: `me["tiles"][y][x] != "LOCKED"` (`executor._owned_shed_tiles`). Hands spawn on all four centers; with 9 hands they park on SW/SE and freeze if you PICKUP there.

**Natural path (live):** owned-shed first → PICKUP → compass into zone. Executor `_step_to_owned_shed` walks 0–2 steps to nearest owned center; FIVE hire1–4 preambles are pickup-first (no leading WEST/NORTH off `(4,4)`). This is **not** Sept02 mid-zone walk-to-shed.

### Status

| Item | State |
| --- | --- |
| Live agent | **`twoland_wsp` + `CURRENT = TWO`** |
| TwoLand glue | Probe → `BUY_LAND_DAY`; NE cascade; LOCKED carve-out on buy-morning |
| Smoke (post owned-shed) | ~**119k** (`scripts/smoke.txt`) |
| Prior freeze | ~74k — hire3+ stuck PICKUP on `(4,5)` with `adj=1 shed>0 inv=0` |
| Sept02 overhaul | Still **FAILED** — do not resume mid-zone walk-to-shed |

### What was done this session (Sep 15)

1. TwoLand re-add (zoning TWO, `twoland_wsp`, planner/market/executor buy-morning glue).
2. Executor debug logs + preamble give-up on empty/off-shed animal pickup.
3. Smoke analysis parsers for `handN=hireN` and `[harv]` earnings attribution.
4. **Owned-shed pickup:** `_owned_shed_tiles` / `_step_to_owned_shed`; gate all PICKUP/DROP; zoning hire1–4 pickup-first.

### Anti-patterns (still)

- Treating any of the four center tiles as a valid shed door without checking `LOCKED`
- Blind compass before `PICKUP_*` that walks off the only owned door
- Mid-zone pathfind-to-shed (Sept02 regression)
- Floor `conservative` at 0 / `cons >= min_balance`
- `track_shed=True` on WSP replan with W/F in conservative spend

### Immediate next steps

1. Ladder / diagnose post-NE ops gap as user asks (`docs/twoland/diagnosis_0911.md`)
2. Agents never submit without explicit ask
