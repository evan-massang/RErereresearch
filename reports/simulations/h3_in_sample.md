# H3 — in sample run

Window 2026-10-01T13:38:00+00:00 → 2026-10-01T14:45:00+00:00; run `run_0eb57e733e89450c`; hypothesis `hyp_e0b12067e4a043a7`.

Strategy: `{"name": "h3_dev_dump_entry", "size_sol": 1.0, "max_age_s": 30, "min_dev_buy_sol": 2.9, "max_since_dump_s": 20, "hold_s": 20, "stop_pct": 20}`

Execution: fee 125 bps, priority+tip 0.01 SOL/tx, latency 1.0 s, slippage tolerance 2000 bps, tx failure 2%.

**Verdict:** in-sample, not a test (pass needs ≥30 trades, expectancy > 0, PF > 1.2).

| run | trades | PnL SOL | expectancy | median | win rate | PF | max DD | fees+network | slippage | failed tx |
|---|---|---|---|---|---|---|---|---|---|---|
| primary | 213 | -30.740 | -0.1436 | -0.1408 | 0.14 | 0.20 | 30.580 | 9.448 | 4.457 | 25 |
| latency 0.1 s | 232 | -35.920 | -0.1545 | -0.1624 | 0.12 | 0.20 | 35.840 | 10.164 | 1.592 | 14 |
| latency 0.5 s | 223 | -36.160 | -0.1617 | -0.1653 | 0.12 | 0.17 | 36.060 | 9.773 | 3.791 | 18 |
| latency 1.0 s | 213 | -30.740 | -0.1436 | -0.1408 | 0.14 | 0.20 | 30.580 | 9.448 | 4.457 | 25 |
| latency 2.0 s | 200 | -29.692 | -0.1475 | -0.1266 | 0.10 | 0.18 | 29.564 | 8.901 | 6.626 | 28 |
| latency 5.0 s | 153 | -20.365 | -0.1313 | -0.1077 | 0.13 | 0.18 | 20.452 | 6.975 | 6.114 | 40 |
| latency 10.0 s | 125 | -17.159 | -0.1353 | -0.1051 | 0.08 | 0.09 | 16.970 | 5.714 | 5.437 | 42 |
| decu_costs | 213 | -36.618 | -0.1708 | -0.1680 | 0.12 | 0.16 | 36.378 | 15.637 | 4.398 | 25 |
| size_3_sol | 213 | -134.571 | -0.6310 | -0.6334 | 0.10 | 0.10 | 134.411 | 18.851 | 12.729 | 25 |
