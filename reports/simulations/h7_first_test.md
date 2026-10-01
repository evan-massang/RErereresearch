# H7 — first test run

Window 2026-10-01T17:15:00+00:00 → 2026-10-01T19:15:00+00:00; run `run_6d4d0dd05fa24e40`; hypothesis `hyp_ef5fd3143ca5432a`.

Strategy: `{"name": "h7_good_dev_launch", "size_sol": 0.5, "min_prior_migrations": 1, "min_migration_rate": 0.2, "max_prior_launches": null, "trade_from": 1790874900.0, "stop_pct": 30, "follow_through_s": 60, "min_gain_pct": 20, "trail_pct": 40, "tp_mcap_sol": 300, "max_hold_s": 1800}`

Execution: fee 125 bps, priority+tip 0.01 SOL/tx, latency 1.0 s, slippage tolerance 3000 bps, tx failure 2%.

**Verdict:** FAIL (pre-registered pass criteria: {'min_trades': 15, 'min_expectancy_sol': 0.0, 'min_profit_factor': 1.2}).

| run | trades | PnL SOL | expectancy | median | win rate | PF | max DD | fees+network | slippage | failed tx |
|---|---|---|---|---|---|---|---|---|---|---|
| primary | 11 | 2.358 | 0.2180 | -0.0476 | 0.27 | 3.78 | 0.512 | 0.432 | 0.311 | 5 |
| latency 0.1 s | 14 | 1.983 | 0.1438 | -0.1130 | 0.07 | 2.25 | 0.870 | 0.515 | 0.005 | 3 |
| latency 0.5 s | 13 | 1.219 | 0.0961 | -0.0509 | 0.15 | 2.01 | 0.628 | 0.473 | 0.420 | 4 |
| latency 1.0 s | 11 | 2.358 | 0.2180 | -0.0476 | 0.27 | 3.78 | 0.512 | 0.432 | 0.311 | 5 |
| latency 2.0 s | 11 | 1.881 | 0.1746 | -0.0475 | 0.27 | 3.58 | 0.355 | 0.426 | 0.575 | 4 |
| latency 5.0 s | 7 | 1.930 | 0.2815 | -0.0475 | 0.14 | 5.48 | 0.300 | 0.295 | 0.564 | 4 |
| latency 10.0 s | 5 | -0.344 | -0.0567 | -0.0480 | 0.00 | 0.00 | 0.284 | 0.221 | 0.100 | 6 |
