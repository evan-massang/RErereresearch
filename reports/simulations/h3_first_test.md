# H3 — first test run

Window 2026-10-01T14:45:00+00:00 → 2026-10-01T17:15:00+00:00; run `run_c28f0e2c1f5c4a31`; hypothesis `hyp_e0b12067e4a043a7`.

Strategy: `{"name": "h3_dev_dump_entry", "size_sol": 1.0, "max_age_s": 30, "min_dev_buy_sol": 2.9, "max_since_dump_s": 20, "hold_s": 20, "stop_pct": 20}`

Execution: fee 125 bps, priority+tip 0.01 SOL/tx, latency 1.0 s, slippage tolerance 2000 bps, tx failure 2%.

**Verdict:** FAIL (pass needs ≥30 trades, expectancy > 0, PF > 1.2).

| run | trades | PnL SOL | expectancy | median | win rate | PF | max DD | fees+network | slippage | failed tx |
|---|---|---|---|---|---|---|---|---|---|---|
| primary | 487 | -77.069 | -0.1575 | -0.1558 | 0.13 | 0.20 | 76.719 | 21.499 | 12.595 | 57 |
| latency 0.1 s | 526 | -77.655 | -0.1474 | -0.1708 | 0.14 | 0.27 | 77.555 | 23.010 | 1.898 | 31 |
| latency 0.5 s | 510 | -75.238 | -0.1470 | -0.1561 | 0.13 | 0.25 | 74.978 | 22.476 | 7.777 | 41 |
| latency 1.0 s | 487 | -77.069 | -0.1575 | -0.1558 | 0.13 | 0.20 | 76.719 | 21.499 | 12.595 | 57 |
| latency 2.0 s | 463 | -70.495 | -0.1513 | -0.1345 | 0.13 | 0.21 | 70.055 | 20.584 | 15.147 | 65 |
| latency 5.0 s | 363 | -49.687 | -0.1353 | -0.1071 | 0.10 | 0.19 | 49.107 | 16.447 | 13.612 | 99 |
| latency 10.0 s | 285 | -34.194 | -0.1176 | -0.1051 | 0.11 | 0.16 | 33.513 | 13.201 | 9.990 | 100 |
| decu_costs | 487 | -90.364 | -0.1845 | -0.1827 | 0.12 | 0.16 | 89.838 | 35.576 | 12.412 | 57 |
| size_3_sol | 489 | -326.587 | -0.6672 | -0.6778 | 0.10 | 0.11 | 326.277 | 42.996 | 37.164 | 55 |
