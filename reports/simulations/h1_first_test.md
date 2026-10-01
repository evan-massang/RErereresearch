# H1 — first test run

Window 2026-10-01T12:15:00+00:00 → 2026-10-01T17:15:00+00:00; run `run_25fc821ce3334751`; hypothesis `hyp_7d238f22635e4581`.

Strategy: `{"name": "h1_structure_entry", "size_sol": 0.5, "min_age_s": 0.0, "max_age_s": 60.0, "min_buyers_10s": 8, "max_buyers_10s": null, "min_inflow_30s": 1.5, "max_inflow_30s": null, "require_dev_sold": true, "snipers_max_pct": 10.0, "hold_s": 60.0, "stop_pct": 25.0}`

Execution: fee 125 bps, priority+tip 0.001 SOL/tx, latency 1.0 s, slippage tolerance 2000 bps, tx failure 2%.

**Verdict:** FAIL (pass needs ≥30 trades, expectancy > 0, PF > 1.2).

| run | trades | PnL SOL | expectancy | median | win rate | PF | max DD | fees+network | slippage | failed tx |
|---|---|---|---|---|---|---|---|---|---|---|
| primary | 1036 | -52.460 | -0.0506 | -0.0573 | 0.12 | 0.40 | 52.777 | 14.530 | 8.402 | 90 |
| latency 0.1 s | 1089 | -56.940 | -0.0523 | -0.0650 | 0.12 | 0.42 | 57.269 | 15.231 | 1.201 | 60 |
| latency 0.5 s | 1060 | -55.710 | -0.0525 | -0.0627 | 0.12 | 0.41 | 55.981 | 14.833 | 5.838 | 73 |
| latency 1.0 s | 1036 | -52.460 | -0.0506 | -0.0573 | 0.12 | 0.40 | 52.777 | 14.530 | 8.402 | 90 |
| latency 2.0 s | 993 | -48.424 | -0.0487 | -0.0481 | 0.12 | 0.40 | 48.998 | 13.975 | 11.575 | 109 |
| latency 5.0 s | 885 | -43.315 | -0.0488 | -0.0374 | 0.12 | 0.34 | 43.447 | 12.488 | 12.213 | 144 |
| latency 10.0 s | 793 | -32.555 | -0.0409 | -0.0322 | 0.12 | 0.37 | 32.832 | 11.290 | 11.289 | 166 |
