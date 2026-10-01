# H3 failed its first test

**Tested:** H3 was registered at 14:52 UTC (`hyp_e0b12067e4a043a7`) to test the visible, mechanical part of Decu's entry pattern. It buys a token at most 30 s old within 20 s of the creator's first sell, when the creator put in at least 2.9 SOL and has already taken out more. It holds for 20 s with a 20% stop. Each trade is 1 SOL, with 1 s latency, a 125 bps fee, 0.01 SOL priority plus tip, 20% slippage tolerance and 2% failure. The window was 14:45–17:15 UTC, after the stream segment the rule came from. Run: `run_c28f0e2c1f5c4a31`.

**Result: FAIL.**

| | trades | PnL | expectancy/trade | win rate | PF |
|---|---|---|---|---|---|
| primary (1 s) | 487 | −77.07 SOL | −0.158 | 13% | 0.20 |
| with Decu's measured costs (225 bps, 0.015 SOL/tx) | 487 | −90.36 SOL | −0.185 | 12% | 0.16 |

It is negative at every latency from 0.1 to 10 s.

**What it implies:** The same rule had already lost in-sample (213 trades, −30.7 SOL). Run over all of the stream's candidates up to 15:03 (in-sample, 328 candidates), it also caught 6 of Decu's picks, which made +0.27 SOL per trade with 4 wins in 6 (p≈0.006 against the 15% base win rate). It lost on the other ~270 candidates it traded. The timing pattern is real, but Decu's edge is in which of these tokens they buy, through narrative and wallet screening the tape cannot see. It is also in *how long they hold*: their session profit came mostly from a few tokens held through migration (`evidence_decu_session_2026-10-01.json`). The second point motivated H5 (`reports/hypotheses/h5_preregistration.json`), which keeps H3's entry and changes only the exits. Its first test is on data recorded after it was frozen.
