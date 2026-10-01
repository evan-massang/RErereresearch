# H6 — first test run

Window 2026-10-01T17:45:00+00:00 → 2026-10-01T19:15:00+00:00; run `run_387ed44d0b9e4dbe`; hypothesis `hyp_c65bc43fde404899`.

Strategy: `{"wallet": "4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9", "size_sol": 0.5, "max_hold_s": 900}`

Execution: fee 125 bps, priority+tip 0.005 SOL/tx, latency 1.0 s, slippage tolerance 2000 bps, tx failure 2%.

**Verdict:** FAIL (pre-registered pass criteria: {'min_trades': 8, 'min_expectancy_sol': 0.0, 'min_profit_factor': 1.2}).

| run | trades | PnL SOL | expectancy | median | win rate | PF | max DD | fees+network | slippage | failed tx |
|---|---|---|---|---|---|---|---|---|---|---|
| primary | 7 | -0.975 | -0.1386 | -0.2484 | 0.29 | 0.35 | 1.261 | 0.152 | 0.292 | 1 |
| latency 0.1 s | 8 | -0.732 | -0.0915 | -0.2402 | 0.38 | 0.49 | 1.226 | 0.172 | 0.118 | 0 |
| latency 0.5 s | 7 | -0.792 | -0.1124 | -0.2561 | 0.29 | 0.46 | 1.251 | 0.154 | 0.176 | 1 |
| latency 1.0 s | 7 | -0.975 | -0.1386 | -0.2484 | 0.29 | 0.35 | 1.261 | 0.152 | 0.292 | 1 |
| latency 2.0 s | 6 | -1.118 | -0.1846 | -0.2785 | 0.17 | 0.24 | 1.458 | 0.132 | 0.156 | 2 |
| latency 5.0 s | 5 | -0.774 | -0.1529 | -0.2237 | 0.20 | 0.27 | 1.050 | 0.114 | 0.116 | 3 |
| latency 10.0 s | 5 | -0.939 | -0.1868 | -0.2749 | 0.20 | 0.19 | 1.152 | 0.107 | 0.232 | 3 |
