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
