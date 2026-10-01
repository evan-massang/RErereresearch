# H5 failed its first test

**Tested:** H5 was frozen at 17:26:23 UTC (`reports/hypotheses/h5_preregistration.json`, `hyp_59643d536aba4ba3`), as a child of H3. It keeps H3's entry and swaps the 20-s hold for Decu-like exits:
- a −25% stop;
- at 45 s, sell unless up at least 30%;
- a 40% trailing stop;
- take profit at 300 SOL market cap, near migration;
- a 30-min time stop.

Each trade is 1 SOL, with 1 s latency, a 125 bps fee, 0.01 SOL priority plus tip, 20% slippage tolerance and 2% failure. The window was 17:45–19:15 UTC, data recorded after H5 was frozen. Run: `run_f35dff95adbb45d1`.

**Result: FAIL.**

| | trades | PnL | expectancy/trade | win rate | PF |
|---|---|---|---|---|---|
| primary (1 s) | 250 | −40.64 SOL | −0.162 | 8% | 0.28 |

It is negative at every latency from 0.1 to 10 s. Fees and network costs account for 11.0 SOL and slippage for 6.0 SOL. 34 positions were still open at the end and are not counted.

**What it implies:** Letting runners run did not rescue the mechanical entry. Its win rate was lower than H3's: 8% here against 13%. Most entries never gained 30% within 45 s and were cut at a loss. The few runners were not enough to pay for that. So Decu's exit skill only pays because their *entries* are already selective: on their picks, the same entries made money. Mechanical timing plus Decu-like exits loses. H5 is retired.
