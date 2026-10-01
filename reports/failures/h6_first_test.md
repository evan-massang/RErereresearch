# H6 failed its first test

**Tested:** H6 was frozen at 17:33 UTC (`reports/hypotheses/h6_preregistration.json`, `hyp_c65bc43fde404899`). It copies Decu's verified wallet on the bonding curve:
- buy 0.5 SOL when the wallet opens a position;
- mirror its sells;
- 900-s time stop.

Execution: 1 s latency, 125 bps fee, 0.005 SOL priority plus tip, 20% slippage tolerance, 2% failure. The window was 17:45–19:15 UTC. Pass required at least 8 trades, expectancy > 0 and PF > 1.2. Run: `run_387ed44d0b9e4dbe`.

**Result: FAIL.**

| | trades | PnL | expectancy/trade | win rate | PF |
|---|---|---|---|---|---|
| primary (1 s) | 7 | −0.98 SOL | −0.139 | 29% | 0.35 |

It falls short of the 8-trade minimum, and is negative at every latency from 0.1 to 10 s.

**What it implies:** In-sample over the train period, copying Decu at 1 s made +0.92 SOL on 16 trades. Out of sample it lost on 7. Decu's wallet made 80 curve trades on 11 tokens in this window. The copier opens one position per token on the wallet's first buy, so it did not mirror Decu's adds or their exits after migration on Pump AMM. Those, together with what Decu does on Raydium Launchpad, are where most of their profit comes from (`evidence_decu_session_2026-10-01.json`).

The sample is too small to call copying Decu worthless. What it does show is that the in-sample gain did not repeat, so the in-sample result is not reliable evidence of an edge. H6 is retired.

**Data note:** kolscan relayed none of Decu's trades from 18:00 to 19:00, while the tape recorded 41 curve trades. kolscan's per-wallet coverage has gaps. This test used only the tape.
