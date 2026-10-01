# H2 failed its first test

**Tested:** H2 was registered at 14:13 UTC (`hyp_e89f79649dd44f3b`). It enters tokens 45–120 s old when:
- activity is moderate: 6–14 buyers in 10 s and 1–4 SOL inflow in 30 s;
- the developer has already sold;
- snipers hold under 5%.

It exits on a 15% stop or after 25 s. Each trade is 0.5 SOL, with 1 s latency, a 125 bps fee and 0.001 SOL priority fee. The window was train data from 14:00 to 17:15 UTC, which was not used to set the thresholds. Run: `run_52d098ba57f8459c`.

**Result: FAIL.**

| | trades | PnL | expectancy/trade | win rate | PF |
|---|---|---|---|---|---|
| primary (1 s) | 124 | −4.92 SOL | −0.040 | 31% | 0.42 |

It is negative at every latency from 0.1 to 10 s, between −3.1 and −6.0 SOL. Fees and network costs account for 1.76 SOL and slippage for 0.95 SOL. Even with zero costs it would still lose about 2.2 SOL.

**What it implies:** The traits that set profitable human-paced wallets apart (later, calmer entries with little sniper overhang) describe *who* wins. Applied as an entry rule to every token that fits, they do not select winners. Whatever the winning wallets add on top is not in these tape features. Their profit also depends on sizing and exit choices that this rule does not copy. H2 is retired; no threshold variants will be tried on this data.
