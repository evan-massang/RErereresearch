# H5 — first test run

Window 2026-10-01T17:45:00+00:00 → 2026-10-01T19:15:00+00:00; run `run_f35dff95adbb45d1`; hypothesis `hyp_59643d536aba4ba3`.

Strategy: `{"name": "h5_dev_dump_runner", "size_sol": 1.0, "max_age_s": 30, "min_dev_buy_sol": 2.9, "max_since_dump_s": 20, "stop_pct": 25, "follow_through_s": 45, "min_gain_pct": 30, "trail_pct": 40, "tp_mcap_sol": 300, "max_hold_s": 1800}`

Execution: fee 125 bps, priority+tip 0.01 SOL/tx, latency 1.0 s, slippage tolerance 2000 bps, tx failure 2%.

**Verdict:** FAIL (pre-registered pass criteria: {'min_trades': 30, 'min_expectancy_sol': 0.0, 'min_profit_factor': 1.2}).

| run | trades | PnL SOL | expectancy | median | win rate | PF | max DD | fees+network | slippage | failed tx |
|---|---|---|---|---|---|---|---|---|---|---|
| primary | 250 | -40.643 | -0.1619 | -0.2045 | 0.08 | 0.28 | 43.225 | 11.023 | 6.042 | 32 |
| latency 0.1 s | 274 | -46.462 | -0.1692 | -0.2151 | 0.09 | 0.27 | 47.736 | 11.969 | 1.072 | 17 |
| latency 0.5 s | 263 | -43.558 | -0.1651 | -0.2075 | 0.09 | 0.29 | 45.892 | 11.526 | 5.131 | 22 |
| latency 1.0 s | 250 | -40.643 | -0.1619 | -0.2045 | 0.08 | 0.28 | 43.225 | 11.023 | 6.042 | 32 |
| latency 2.0 s | 227 | -43.721 | -0.1915 | -0.1806 | 0.06 | 0.14 | 44.615 | 10.021 | 6.817 | 41 |
| latency 5.0 s | 185 | -31.993 | -0.1713 | -0.1197 | 0.08 | 0.13 | 31.693 | 8.302 | 7.052 | 47 |
| latency 10.0 s | 142 | -20.239 | -0.1410 | -0.1051 | 0.05 | 0.10 | 20.263 | 6.417 | 5.392 | 40 |
