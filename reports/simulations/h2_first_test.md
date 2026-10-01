# H2 — first test run

Window 2026-10-01T14:00:00+00:00 → 2026-10-01T17:15:00+00:00; run `run_52d098ba57f8459c`; hypothesis `hyp_e89f79649dd44f3b`.

Strategy: `{"name": "h2", "size_sol": 0.5, "min_age_s": 45, "max_age_s": 120, "min_buyers_10s": 6, "max_buyers_10s": 14, "min_inflow_30s": 1.0, "max_inflow_30s": 4.0, "require_dev_sold": true, "snipers_max_pct": 5, "hold_s": 25, "stop_pct": 15}`

Execution: fee 125 bps, priority+tip 0.001 SOL/tx, latency 1.0 s, slippage tolerance 2000 bps, tx failure 2%.

**Verdict:** FAIL (pass needs ≥30 trades, expectancy > 0, PF > 1.2).

| run | trades | PnL SOL | expectancy | median | win rate | PF | max DD | fees+network | slippage | failed tx |
|---|---|---|---|---|---|---|---|---|---|---|
| primary | 124 | -4.923 | -0.0397 | -0.0470 | 0.31 | 0.42 | 4.959 | 1.756 | 0.951 | 10 |
| latency 0.1 s | 135 | -5.963 | -0.0442 | -0.0526 | 0.27 | 0.37 | 5.962 | 1.899 | 0.146 | 5 |
| latency 0.5 s | 130 | -5.039 | -0.0387 | -0.0464 | 0.29 | 0.43 | 5.106 | 1.838 | 0.760 | 7 |
| latency 1.0 s | 124 | -4.923 | -0.0397 | -0.0470 | 0.31 | 0.42 | 4.959 | 1.756 | 0.951 | 10 |
| latency 2.0 s | 120 | -3.747 | -0.0312 | -0.0416 | 0.31 | 0.50 | 3.768 | 1.712 | 1.523 | 12 |
| latency 5.0 s | 107 | -3.440 | -0.0321 | -0.0376 | 0.30 | 0.49 | 3.454 | 1.529 | 2.960 | 15 |
| latency 10.0 s | 91 | -3.108 | -0.0340 | -0.0307 | 0.27 | 0.38 | 3.108 | 1.305 | 2.948 | 22 |
