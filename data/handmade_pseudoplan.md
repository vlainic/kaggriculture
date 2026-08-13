https://docs.google.com/spreadsheets/d/1H1mb1uw7uObnRZ80nzWn6JVygtBHWfsCDZ4B99s8ohg/edit?usp=sharing

# PLAN

## Farmer: tiles 1-9

Tiles 1,2,3:
- 6 wheets with 2-3xWater-2 ops
Tiles 4,5,6:
- 2 carrots with 2-2xWater-2 ops
- then 4 wheets with 2-2xWater-2 ops
Tiles 7,8,9 (1 day lag):
- 2 melons with 2-9xWater-2 ops
- then 1 wheet with 2-2xWater-2 ops

## Top & Left: tiles 10-15 + 16-21

All 6 tiles start with 1 wheet each 2-2xWater-2 ops, then...

Tile 10,11 & 16,17:
- Sheeps with doing it all: feed, care, collect fert, harvest every 3 when possible
Tile 12,13 & 18,19:
- 2 melons with 2-9xWater-2 ops
    - note: 1 day break between harvest and plant
Tiles 14,15 & 20,21:
- 2 melons with 2-9xWater-2 ops
    - note: 1 tile break between harvest and plant
    - note 2: also lag of 1 day with first melon tiles

## Corner: tiles 22-25

All 6 tiles start with 1 wheat each 2-2xWater-2 ops, then...

Tile 22:
- Cow with doint it all: feed, care, collect fert, harvest every 3 when possible
Tile 23:
- Cow with doint it all: feed, care, collect fert, harvest every 3 when possible
    - note: 1 day lag in respect to tile 22
Tile 24:
- Strawbery with non-fert patern: 2-8xWater-4x(Water->Harvest) ops
- then 2 carrots with 2-2xWater-2 ops
    - note that for first carrot you need to DIG after strawbery -> DIG on PLANT carrot day, not on strawberry HARVEST :)
Tile 25:
- 1 lag day then melon with 2-9xWater-2 ops
- 1 lag day then melon with 2-9xWater-2 ops

# NOTES

Tile numbering:

24 23 13 14 15
25 22 12 11 10
19 18  9  8  7
20 17  4  5  6
21 16  3  2  1

## Farmer

Move 1:
- Hire 2 hands
- Buy crops and animals for this day
- SELL if there is anything
- no move!

Move 2:
- Hire last hand
- Finalize market if needed
- Work on the plan

Snake movement handling the plan:
- 2xW, N, 2xE, N, 2xW

## Hand 1

Appears top-right of Shed on hour 2 -> will handle Top zone...

Move 1 is West, then:
- IF it has animal: PICKUP enough wheat (probably 2) -> then move towards zone as bellow
- ELSE: move towards zone with 3xN
- inzone movement: 2xW, N, 2xE

## Hand 2

Appears bottom-left of Shed on hour 2 -> will handle Left zone...

Move 1 is North, then:
- IF it has animal: PICKUP enough wheat (probably 2) -> then move towards zone as bellow
- ELSE: move towards zone with 3xW
- inzone movement: 2xN, W, 2xS

## Hand 3

Appears top-right of Shed on hour 3 -> will handle Corner zone...

Move 1 is West, then:
- IF it has animal: PICKUP enough wheat (probably 2) -> then move towards zone as bellow
- ELSE: move towards zone with 3xW+3xN
- inzone movement: N, W, S

## Trading

Keep wheet and fertilizer caped at 10 -> so sell everything above that for wheet and fertilizer!
Rest of products -> just sell as they come in.

Day 30: try to make just harvest-only route, so they return to tile 1 - (4,4) coords - so workers drop thing to SHED!!!
- and then just SELL all in shed what is sellable -> like ALL!!!

# CHANGES

I have to make them due to low money and animals die!!!

## Farmer

Tiles 1,2,3 -> have first CARROTS, then 5xWHEAT

## Top/Left zone

Tiles 11 and 17 respectively: delay second sheep by insertin carrot!

Tile 12,13 & 18,19: break between harvest and plant is 3 days instead of 1

## Corner

Tiles 23: instead of 1 day lag insert wheat for productive 5 day lag of second cow