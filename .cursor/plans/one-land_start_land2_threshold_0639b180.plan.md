---
name: One-Land Start Land2 Threshold
overview: Implement a one-land start strategy with dynamic Land 2 purchase at $6000 threshold (h=22/23), expand to 50 tiles at next dawn, and ensure animal_with_pickups.json is used throughout.
todos:
  - id: fix-animal-data
    content: Change animal_rollouts.py and planner.py to load animal_with_pickups.json
    status: completed
  - id: implement-two-layout
    content: Add TWO layout to zoning.py based on two_lands.md specification
    status: completed
  - id: add-buy-land
    content: Add BUY_LAND logic to market.py with $6000 threshold at h=22/23
    status: completed
  - id: layout-switching
    content: Add dynamic layout switching in executor._on_new_day when lands==2
    status: completed
  - id: update-build-script
    content: Update smoke_test.sh to copy both animal JSON files
    status: completed
  - id: replan-fallback
    content: Implement fallback ladder in planner.replan() - exclude broken zones, then preserve locked on total failure
    status: completed
  - id: smoke-test
    content: Run smoke test and verify one-land start with Land 2 expansion
    status: completed
isProject: false
---

# One-Land Start with $6000 Land 2 Threshold

## Overview

Start with one land (FIVE layout, 25 tiles) and buy Land 2 when cash reaches $6000 during the last 2 hours of the day (h=22 or h=23). At the next dawn (h=0), expand operations to all 50 tiles using spawn-driven routing.

## Current State

- `agent/zoning.py`: CURRENT = FIVE (25 tiles, 4 hires)
- `agent/animal_rollouts.py`: Still loading `animal_rollouts.json` (needs to use `animal_with_pickups.json`)
- `agent/planner.py`: Still loading `animal_rollouts.json` (needs to use `animal_with_pickups.json`)
- No Land 2 purchase logic exists
- No 50-tile layout implemented

## Key Changes

### 1. Fix Animal Rollout Data Source

**Files**: [`agent/animal_rollouts.py`](agent/animal_rollouts.py), [`agent/planner.py`](agent/planner.py)

Change the data source from `animal_rollouts.json` to `animal_with_pickups.json`:

```python
# agent/animal_rollouts.py line 15
_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "animal_with_pickups.json"
```

```python
# agent/planner.py lines 808, 911
animals_data = _load_json("animal_with_pickups.json")
```

**Why**: `animal_with_pickups.json` includes `PICKUP`, `BUILD_*`, and `PLACE` actions explicitly in the action lists, avoiding the double-counting issue that caused INFEASIBLE replans.

### 2. Add 50-Tile Layout to Zoning

**File**: [`agent/zoning.py`](agent/zoning.py)

Implement the TWO layout based on [`data/two_lands.md`](data/two_lands.md) specification:

- 50 tiles (25 per land)
- 10 zones total
- Farmer: tiles 0-4 (positions 1-5 in spec)
- 9 hires with spawn-driven routing
- Ops limits as specified in the document (adjusted for symmetry)

### 3. Market Logic for Land 2 Purchase

**File**: [`agent/market.py`](agent/market.py)

Add conditional Land 2 purchase in `build_orders()`:

```python
# Check for Land 2 purchase opportunity
if hour in (22, 23) and len(me.get("lands", [])) == 1:
    if money >= 6000:
        orders.append(["BUY_LAND", "NE"])
```

**Constraints**:
- Only trigger at h=22 or h=23 (last 2 hours)
- Only when we have exactly 1 land
- Only when cash >= $6000
- Buy NE quadrant

### 4. Dynamic Layout Switching in Executor

**File**: [`agent/executor.py`](agent/executor.py)

Detect land expansion and switch layouts at dawn:

```python
def _on_new_day(self, me: dict, day: int) -> None:
    # Detect if we now have 2 lands
    num_lands = len(me.get("lands", []))
    if num_lands == 2 and zoning.CURRENT == zoning.FIVE:
        _log(f"[executor] d={day} expanding to TWO layout (50 tiles)")
        zoning.bind(zoning.TWO)
        workers.sync_from_zoning()  # refresh worker tables
```

**Why h=22/23 purchase + dawn expansion**: Buying land late in the day gives time for the market order to execute, then at h=0 next day we can plan for the full 50 tiles.

### 5. Spawn-Driven Routing

**File**: [`agent/executor.py`](agent/executor.py)

When using TWO layout, detect spawn quadrants and assign zones dynamically:

- Use existing helpers from [`agent/workers.py`](agent/workers.py): `detect_spawn_quadrant`, `map_hands_to_zones_two`
- Build `self._hand_to_zone` mapping at first h=1 after expansion
- Use this mapping in `_resolve_worker_for_hand`

### 6. Replan Fallback Ladder (Plan B from docs/two_land_approach.md)

**File**: [`agent/planner.py`](agent/planner.py)

Implement a three-level fallback in `replan()` to avoid abandoning tiles when the full solve fails:

**Level 1**: Try full solve (current behavior)

**Level 2**: On INFEASIBLE, identify which zones caused the failure (ops-cap violations), exclude those zones' tiles from the solve, and retry with remaining zones only.

**Level 3**: On still INFEASIBLE, preserve current locked assignments (don't wipe queues). This prevents stale/empty queues from persisting the rest of the season.

**Current problem**: When replan hits `INFEASIBLE`, it returns early and leaves 10-20 tiles with stale or empty queues for the rest of the season. With TWO layout, this happens ~17-24 times per season, killing performance.

**Implementation approach**:
- Catch `RuntimeError` from `_solve_assignment`
- On failure, check `locked_ops > cap` per zone to identify broken zones
- Build a filtered `replan_tiles` list excluding broken zones
- Retry solve
- If still fails, log and return (preserving locked state) rather than wiping

### 7. Planner Data Source

**File**: [`agent/planner.py`](agent/planner.py)

Load animal data from `animal_with_pickups.json` (already covered in section 1).

**Note**: Remove any two-land specific code like mirror constraints or dual cash ledgers if they exist.

### 8. Build Script Update

**File**: [`scripts/smoke_test.sh`](scripts/smoke_test.sh)

Ensure both JSON files are bundled:

```bash
cp data/crop_rollouts.json data/animal_rollouts.json data/animal_with_pickups.json data/handmade_dp_candidates.json "$BUILD/data/"
```

## Implementation Order

1. Fix animal rollout data loading (simple path changes)
2. Implement TWO layout in zoning.py based on two_lands.md spec
3. Add BUY_LAND logic to market.py with $6000 threshold + h=22/23 constraint
4. Add layout switching in executor._on_new_day
5. Implement replan fallback ladder in planner.py (Plan B)
6. Update smoke_test.sh to bundle both JSON files
7. Run smoke test to verify

## Testing Strategy

- Smoke test should start with FIVE layout (25 tiles)
- Monitor logs for Land 2 purchase trigger
- Verify layout switch happens at next dawn
- Check that 50 tiles are being planned and worked after expansion

## Risk Areas

- **Spawn detection**: Workers need to be correctly mapped to zones based on spawn quadrant
- **Planner horizon**: With 50 tiles, the CP-SAT solver may need more time
- **INFEASIBLE replans**: Even with fallback ladder, some zones may overflow ops caps (animal-heavy zones with 5 ops/tile/day can exceed caps 14-15). The fallback will preserve locked state rather than wiping queues.
- **Hand inventory**: Need to handle 9 inventories instead of 4 after expansion
- **Ops cap violations**: The caps from two_lands.md are the MAX ops available per zone. The planner should properly assign animals based on animal_with_pickups.json action counts.
