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