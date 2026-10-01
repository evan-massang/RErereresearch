# Holdout plan — split set `overnight-2026-10-01`

_Written 2026-10-01 ~17:35 UTC, before any validation-period result exists and before the holdout (19:15–21:15 UTC) begins._

## Status of the hypotheses

| hypothesis | first test | verdict | eligible for holdout |
|---|---|---|---|
| H1 hot token + dev sold + few snipers | train 12:15–17:15 | FAIL (−52.46 SOL, PF 0.40) | no |
| H2 later, calmer entries | train 14:00–17:15 | FAIL (−4.92 SOL, PF 0.42) | no |
| H3 Decu's post-dev-dump timing, 20-s hold | train 14:45–17:15 | FAIL (−77.07 SOL, PF 0.20) | no |
| H4 copy unknown consistent winners | train 15:20–17:15 | FAIL (−37.50 SOL, PF 0.39) | no |
| H5 H3 entry + Decu-like exits | validation 17:45–19:15 (frozen 17:26:23) | pending | only if it passes |
| H6 copy Decu's verified wallet (1 s) | validation 17:45–19:15 (frozen 17:33) | pending | only if it passes and H5 does not |

## Rule

Only one hypothesis can reach the holdout: H5, and only if its pre-registered first test passes. That means expectancy > 0, profit factor > 1.2 and at least 30 trades, with its registered execution at 1 s latency.

**If H5 passes,** the holdout is evaluated once with `pipeline.sim.splits.evaluate_holdout`:
- same strategy parameters and execution as registered (`reports/hypotheses/h5_preregistration.json`);
- window 19:15–21:15 UTC;
- pass criteria, fixed here:
  ```json
  [{"metric": "n_trades", "op": ">=", "value": 30},
   {"metric": "expectancy_sol", "op": ">", "value": 0},
   {"metric": "profit_factor", "op": ">", "value": 1.2}]
  ```
- the latency sweep (0.1–10 s) is reported alongside but does not change the verdict;
- a failure is written up in `reports/failures/`, and the holdout is then burned.

**If H5 fails,** nothing reaches the holdout. The 19:15–21:15 data stays unexamined by any strategy, so it remains a clean test period for hypotheses pre-registered later. No hypothesis may be created or changed after looking at it.

## Amendment 17:35 UTC (before any validation or holdout data was examined)

H6 was registered at 17:33 (`reports/hypotheses/h6_preregistration.json`). The holdout supports exactly one evaluation:
- If H5 passes, H5 takes it, because it was registered first.
- If H5 fails and H6 passes, H6 takes it.

H6's holdout criteria are the same as H5's except for sample size: at least 8 trades, expectancy > 0, profit factor > 1.2. Decu trades too rarely for 30 trades in 2 hours, so this would be a weak, small-sample confirmation and will be reported as such.

## Outcome (19:25 UTC)

Both H5 and H6 failed their first tests:
- **H5:** 250 trades, −40.64 SOL, PF 0.28.
- **H6:** 7 trades, −0.98 SOL, PF 0.35.

See `reports/failures/`. **No hypothesis reaches the holdout.** No strategy was run on the 19:15–21:15 data, and the split stays `open` (not burned). It remains a clean test period for any hypothesis registered later, provided it is registered before anyone looks at that data.
