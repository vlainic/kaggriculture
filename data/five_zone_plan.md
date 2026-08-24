# FIVEMAN: SIMPLE

## Tile numbering:

10 15 20 25  5
 9 14 19 24  4
 8 13 18 23  3
 7 12 17 22  2
 6 11 16 21  1

## Zone-split:
 
- Farmer: 1-5
- Turn 1 (h=0) Hire 1 & 2 (aka Hand 0 & 1 in code) -> 6-10 & 11-15
- Turn 2 (h=1) Hire 3 & 4 (aka Hand 2 & 3 in code) -> 16-20 & 21-25

## Ops-limits:
 
- Farmer @ zone 1: 18
- Hire 1 @ zone 2: 13
- Hire 2 @ zone 3: 14
- Hire 3 @ zone 4: 14
- Hire 4 @ zone 5: 15

## Pre-defined movement snakes:
Note that hiring, selling & buying is same as for four-man...
- Farmer: just 4xN
- Hire 1: 1xW, pickup (if needed), 4xW to zone -> then 4xN
- Hire 2: 1xN, pickup (if needed), 3xW to zone -> then 4xN
- Hire 3: 1xW, pickup (if needed), 2xW to zone -> then 4xN
- Hire 4: 1xN, pickup (if needed), 1xW to zone -> then 4xN