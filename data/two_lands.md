# FIVE MAN: SIMPLE

## Tile numbering:

10 15 20 25  5 50 45 40 35 30
 9 14 19 24  4 49 44 39 34 29
 8 13 18 23  3 48 43 38 33 28
 7 12 17 22  2 47 42 37 32 27
 6 11 16 21  1 46 41 36 31 26

## Spawning...

### 3-man spawn in respect to shed:
- Hire 1 @ NE or NW if Farmer is not @NW (aka - 4,4 cell or cell 1)
- Hire 2 @ SW or NE if . . .
- Hire 3 @ SE or SW

### 4-man spawn in respect to shed:
- Hire 1 @ NE or NW
- Hire 2 @ SW or NE
- Hire 3 @ SE or SW
- Hire 4 @ NW or SE

### 5-man spawn in respect to shed:
- Hire 1 @ NE or NW
- Hire 2 @ SW or NE
- Hire 3 @ SE or SW
- Hire 4 @ NW or SE
- Hire 5 @ NE or NW

## Zone-split:
 
- Farmer: 1-5 (aka zone I)
- Turn 1 (h=0) Hire 1-4 (aka Hand 0-3 in code):
    - Hire spawned at NW: zone II = 6->10
    - Hire spawned at SW: zone III = 11->15
    - Hire spawned at NE: zone VI = 26->30
    - Hire spawned at SE: zone VII = 31->35
- Turn 2 (h=1) Hire 5-9 (aka Hand 4-8 in code):
    - Hire spawned at NW: zone IV = 16->20
    - Hire spawned at SW: zone V = 21->25
    - Hire spawned at NE: zone VIII = 36->40
    - Hire spawned at SE: zone IX = 41->45
    - Hire spawned at NW or NE: zone X = 46->50 (this one is overlap)

## Ops-limits:
 
LandOne:
- Farmer @ zone I: 18 -> 15 due to mirroring TwoLand plan
- Hire @ zone II: 14
- Hire @ zone III: 14
- Hire @ zone IV: 15
- Hire @ zone V: 15
LandTwo:
- Hire @ zone VI: 14
- Hire @ zone VII: 14
- Hire @ zone VIII: 15
- Hire @ zone IX: 15
- Hire @ zone X: 15

## Pre-defined movement snakes:
Note that hiring, selling & buying is same as for four-man...

LandOne:
- Farmer: just 4xN
- Hire @ zone II: pickup (if needed), 4xW to zone -> then 4xN
- Hire @ zone III: 1xN, pickup (if needed), 3xW to zone -> then 4xN
- Hire @ zone IV: pickup (if needed), 2xW to zone -> then 4xN
- Hire @ zone V: 1xN, pickup (if needed), 1xW to zone -> then 4xN

LandTwo:
- Hire @ zone VI: pickup (if needed), 4xE to zone -> then 4xN
- Hire @ zone VII: 1xN, pickup (if needed), 3xE to zone -> then 4xN
- Hire @ zone VIII: pickup (if needed), 2xE to zone -> then 4xN
- Hire @ zone IX: 1xN, pickup (if needed), 1xE to zone -> then 4xN
- Hire @ zone X: 1xE (if needed), pickup (if needed), then 4xN