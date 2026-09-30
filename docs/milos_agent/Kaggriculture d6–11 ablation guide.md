# Kaggriculture d6–11 ablation guide

Sep 30, 2026 · @Miloš Vlainić

## Purpose and hypothesis

Find which planner gate causes our d6–11 under-commitment, one change at a time. The d0–5 opener is ruled out: with the V55 opener tape we match the opponent's buys and actions exactly, hold identical cash on d6 ($688), and still lose by 65–100k.

What diverges on d6–11 in the last smoke:

| d6–11 | opp | us |
| --- | --- | --- |
| NE land | d6 | d8 |
| Hires on d6 | 7 | 3 |
| Strawberries | 16 on d6–8, +13 on d11 | 4 by d9, 20 on d12–13 |
| Sheep / cows | 4 / 2 | 1 / 2 |
| Animals alive on d15 | \~17 | 9 |

Hypothesis: three gates in our own code block commitment. The land trigger demands a cash buffer, new zones activate on a staples-only catalog, and the cash rows keep reserves and under-credit the d10–11 melon payday. The ablation measures how much each one costs.

## Fixed baseline

Every run, including the control, uses the same stack. Only the arm under test changes.

- **Opener:** V55 opener tape on for steps 0–143 (`KAGGRI_V55_OPENER=1`), handoff at d6 h0 with occupied tiles locked.
- **Layout:** `threeland12` (4-man per land), NE/SW bound by hire slot.
- **Seller:** greedy premium seller, dawn/base THETA, fert reserve capped at 10, fert exempt from the 0.5 × base floor.
- **Planner prices:** quote baseline for concave products and for `cash_by_day`.
- **Opponent:** `scripts/v55_logged_opponent.py`.
- **Seeds:** unseeded, as on Kaggle.

Freeze the code at a commit before the first run and record its hash. Each arm is a flag on top of that commit, so turning the flag off restores the control exactly.

## The three arms

Each arm is one flag, default off, so the control is all three off.

### Arm A: land trigger (`KAGGRI_ABL_LAND`)

- **Change:** buy NE when `money ≥ 1000 + 300` and day ≥ 6; buy SW when `money ≥ 2000 + 300` and NE is bought. Drop the `ne_not_full` condition and the dusk cash buffer.
- **Where:** NE/SW dusk trigger in `milos/planner.py`.
- **Expected log:** `[ne] dusk_trigger` on d5 or d6 with `buy_day` = 6, instead of d7/d8. SW buy by d11–12.
- **What it isolates:** whether a two-day land delay alone explains the d6–11 gap.

### Arm B: full-catalog activation (`KAGGRI_ABL_CATALOG`)

- **Change:** walk 2, walk 3 and the SW buy-replan use the full catalog (animals, strawberry, melon) instead of WHEAT + CARROT only.
- **Where:** the label allowlist passed into `build_patterns` from `twoland.solve`, in `milos/wsp/mip.py` and `milos/planner.py`.
- **Expected log:** `wsp_plan` on the NE buy day shows STRAWBERRY and SHEEP/COW picks, not only WHEAT/CARROT. `[ne] accept` lines lose `staple=1`.
- **What it isolates:** whether new land starts on low-value crops and stays there.

### Arm C: cash rows (`KAGGRI_ABL_CASH`)

- **Change:** credit locked harvests at the quote on harvest day + 1, and drop early-game reserves (`MONEY_BUFFER`, overage reserve) through d11.
- **Where:** `cash_by_day` stamping in `milos/replan_lock.py` and the zone cash row in `milos/wsp/mip.py`.
- **Expected log:** on d6–9, dawn cash after planned spend runs near $0–200 instead of holding $1–3k. More BUY\_ANIMAL and strawberry BUY\_SEED orders on d6–9.
- **What it isolates:** whether the solver can see the d10–11 melon payday and pre-commit against it.

If an arm has no visible effect on its expected log line, the flag is not wired. Fix that before counting the run.

## Run protocol

Five configurations, three unseeded V55 smokes each: 15 smokes in total.

1. **Control:** all three flags off. Run this first; it sets the noise band.
2. **A only:** `KAGGRI_ABL_LAND=1`.
3. **B only:** `KAGGRI_ABL_CATALOG=1`.
4. **C only:** `KAGGRI_ABL_CASH=1`.
5. **All on:** A + B + C. This checks whether the arms add up or interact.

Rules:

- One configuration at a time, three smokes back to back, no code edits in between.
- Save each log as `smoke_<config>_<n>.txt` so the parser can group them.
- If an arm crashes or its expected log line never appears, stop, fix the wiring, and rerun that arm from zero.
- Leave-one-out (all on minus one arm) only if the all-on run beats every single arm by more than the noise band. That signals an interaction worth splitting.

## Metrics per run

The primary metric is **our reward**. The margin moves with the opponent's bank, which swings 150–200k on its own.

| Metric | Source | Why |
| --- | --- | --- |
| Our reward | `Player 0 (us): reward=` | Primary outcome |
| Opp reward | `Player 1 (opp): reward=` | Separates our gain from their variance |
| NE / SW buy day | `[exec] … BUY_LAND` | Arm A signal |
| d6–11 animals bought | `BUY_ANIMAL` in `[exec]` lines d6–11 | Commitment |
| d6–11 strawberry seeds | `BUY_SEED STRAWBERRY` d6–11 | Commitment, Arm B signal |
| Animals alive on d15 | sum of `animal=` in `[hands] d=15` | Asset base entering the payout phase |
| Dawn cash d6–9 | `[snap] d=6..9 h=0 money=` | Arm C signal |
| Empty tiles on d11 and d15 | `*_empty=` in `[snap]` | Land actually used |
| Revenue by product | SELL units × dawn price | Where the money comes from |
| Ops per tile, d12–20 | the plot | Asset density |

Match-ups to compare line by line: our `[exec] d=6..11 market` against `[opp] d=6..11 market` in the same log. The shops are shared, so the opponent's lines show what full commitment looks like in that exact game.

## Decision rules

The arm with the largest mean reward gain over control, beyond the noise band, is the main gap.

- **Noise band:** the spread of our reward across the three control smokes. Recent runs ranged 73–100k, so expect a band of roughly ±10k. A gain smaller than the band is not a finding.
- **Real effect:** mean gain above the band, **and** the arm's own signal moved (land day, strawberry seeds, dawn cash). A reward change without its signal moving is noise or a side effect.
- **Main gap:** the single arm with the largest real effect. If two arms are within the band of each other, call them joint.
- **Additive or not:** if all-on ≈ the sum of the single-arm gains, the gates are independent. If all-on is much larger, they interact; for example, land on d6 may only pay off once the catalog lets NE start on strawberries.
- **Kill:** an arm that lowers mean reward on all three smokes stays off.

The convergence check: after the winning arms are on, our d6–11 buys should look like the `[opp]` lines in shape (land day, animal count, strawberry count). If they converge and reward is still far behind, the gap has moved past d11, into care, selling or the tail.

## Pitfalls

- **Shop draw varies by run.** The opponent's strategy depends on which shops unlock (one run it sold 1,341 wheat). Log the `[shops] d=6` line per run and compare arms only across similar shop draws where you can.
- **Unwired flags.** Past arms silently did nothing (the `busy_day0` gate survived a fix). Always confirm the arm's expected log line before reading its reward.
- **Bind failures.** A `[bind] hire_mismatch` or `hire_unbound` rollback in a run invalidates it: hands were paid but idle. Fix and rerun.
- **Smoke test false fail.** The `SELL WHEAT during hours 0–4` check trips on the V55 opener. Whitelist `step < 144` so it doesn't hide real failures.
- **Two changes at once.** Don't tune THETA, caps or zoning during the ablation. Any other edit resets the control.
- **One lucky smoke.** Never promote on a single run; three per arm is the minimum.

## Results

Fill one row per smoke; add the mean row per configuration once its three runs are in.

| Config | Run | Our reward | Opp reward | NE day | SW day | d6–11 animals | d6–11 strawberries | Animals d15 | Empty tiles d15 | Shops d6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Control | 1 |  |  |  |  |  |  |  |  |  |
| Control | 2 |  |  |  |  |  |  |  |  |  |
| Control | 3 |  |  |  |  |  |  |  |  |  |
| A land | 1 |  |  |  |  |  |  |  |  |  |
| A land | 2 |  |  |  |  |  |  |  |  |  |
| A land | 3 |  |  |  |  |  |  |  |  |  |
| B catalog | 1 |  |  |  |  |  |  |  |  |  |
| B catalog | 2 |  |  |  |  |  |  |  |  |  |
| B catalog | 3 |  |  |  |  |  |  |  |  |  |
| C cash | 1 |  |  |  |  |  |  |  |  |  |
| C cash | 2 |  |  |  |  |  |  |  |  |  |
| C cash | 3 |  |  |  |  |  |  |  |  |  |
| All on | 1 |  |  |  |  |  |  |  |  |  |
| All on | 2 |  |  |  |  |  |  |  |  |  |
| All on | 3 |  |  |  |  |  |  |  |  |  |
| Opp reference | – | – | – | 6 | 11 | \~13 | 29 | \~17 | 0 | – |
