# FIVE MAN: SIMPLE

## Tile numbering:

zone:    V  IV III II  I VI VII VIII IX X
        25  20  15 10  5 30  35  40  45 50
        24  19  14  9  4 29  34  39  44 49
        23  18  13  8  3 28  33  38  43 48
        22  17  12  7  2 27  32  37  42 47
        21  16  11  6  1 26  31  36  41 46

## Market Hiring

If only 2 hires are required -> do them at h=0!
For 5+ hires split them to half so larger half is hired at h=1, due to more buying (seeds, animals) at h=0:
- 3 -> 2+1
- 5 -> 2+3
- 7 -> 3+4
- 9 -> 4+5

## Spawning...

Spawing is happening in 4 tiles around the shed with order being: [NW->]NE->SW->SE. Nothing that NW is skipped as start IF faremr is there!!! I will count always like its swawned in most further tile for OPS limit, so we are safe (no slack!)

## Zone-split:
 
- Farmer - the zeroth work: zone I
- Each Hand X takes zone X+1...

## Ops-limits (conservative):
 
LandOne:
- Farmer @ zone I: 18
- Hire 1: 17
- Hire 2: 16
- Hire 3: 14
- Hire 4: 13
LandTwo:
- Hire 5: 16
- Hire 6: 14
- Hire 7: 13
- Hire 8: 12
- Hire 9: 11

## Pre-defined movement snakes:
Note that selling & buying is same as for four-man...

LandOne:
- Farmer: just 4xN
- Hire 1: reach 4,4-tile (if not there), pickup (if needed), 1xW to zone -> then 4xN
- Hire 2: reach 4,4-tile (if not there), pickup (if needed), 2xW to zone -> then 4xN
- Hire 3: reach 4,4-tile (if not there), pickup (if needed), 3xW to zone -> then 4xN
- Hire 4: reach 4,4-tile (if not there), pickup (if needed), 4xW to zone -> then 4xN

LandTwo:
- Hire 5: reach 5,4-tile (if not there), pickup (if needed) -> then 4xN
- Hire 6: reach 5,4-tile (if not there), pickup (if needed), 1xE to zone -> then 4xN
- Hire 7: reach 5,4-tile (if not there), pickup (if needed), 2xE to zone -> then 4xN
- Hire 8: reach 5,4-tile (if not there), pickup (if needed), 3xE to zone -> then 4xN
- Hire 9: reach 5,4-tile (if not there), pickup (if needed), 4xE to zone -> then 4xN