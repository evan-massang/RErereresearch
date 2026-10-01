# H4 failed its first test

**Tested:** H4 was registered at 15:12 UTC (`hyp_3e8d7c0324ce4aec`). It copies a frozen basket of 49 unknown wallets that were profitable at human pace in both halves of 12:17–15:15 (`reports/hypotheses/h4_basket.json`). It buys 0.5 SOL once per token when any of them opens a position, and mirrors that wallet's sells. Execution: 1 s latency, 125 bps fee, 0.005 SOL priority plus tip, 20% slippage tolerance, 2% failure. The window was 15:20–17:15 UTC. Run: `run_99d6da2781874d3b`.

**Result: FAIL.**

| | trades | PnL | expectancy/trade | win rate | PF |
|---|---|---|---|---|---|
| primary (1 s) | 680 | −37.50 SOL | −0.055 | 19% | 0.39 |

It is negative at every latency from 0.1 to 10 s. Fees and network costs account for 15.4 SOL and slippage for 5.4 SOL.

Over the same window, the basket wallets' *own* closed positions netted **+117.0 SOL** (1,658 positions; 22 of 48 active wallets profitable).

**What it implies:** The wallets kept making money; copying them did not. The gap comes from three costs a copier pays and they do not:
- a copier buys after the leader's own price impact and sells after the leader's exit has moved the price;
- a copier pays two transaction fees per trade on small positions;
- a copier uses fixed sizing and cannot know which entries the leader sizes up.

The same happened with the famous KOLs, where a follower spike made it worse. On the bonding curve, a profitable wallet's edge is not available to anyone copying it from the chain. H4 is retired.
