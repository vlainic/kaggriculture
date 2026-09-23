# MILOS FINAL

All 4 hires bought at h=0!
- market h=0:
    - wheat priority
    - then animal
    - finally plant seed

## Tile numbering:

zone:    V IV III II  I
        25 20  15 10  5
        24 19  14  9  4
        23 18  13  8  3
        22 17  12  7  2
        21 16  11  6  1

## Zone assignement

- Farmer @ zone I
- Hire 1 = spawned at NW @ zone V
- Hire 2 = spawned at NE @ zone IV
- Hire 3 = spawned at SW @ zone III
- Hire 4 = spawned at SE @ zone II


## Pre-defined movement snakes:
- Farmer: buying & pickup (if needed), just 4xN [buying in parallel, ofc]
- Hire 1: pickup (if needed), 4xW to zone -> then 4xN
- Hire 2: 1xW, pickup (if needed), 3xW to zone -> then 4xN
- Hire 3: 1xN, pickup (if needed), 2xW to zone -> then 4xN
- Hire 4: 1xW, 1xN, pickup (if needed), 1xW to zone -> then 4xN


## Ops-limits:
 
- Farmer = 18
- Hire 1 = 14
- Hire 2 = 14
- Hire 3 = 15
- Hire 4 = 15