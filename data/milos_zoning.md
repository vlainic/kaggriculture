# MILOS FINAL

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