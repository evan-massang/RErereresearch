# H1 failed its first test

**Tested:** H1 was registered at 13:00 UTC (`hyp_7d238f22635e4581`), based on the BUY-vs-SKIP selection study. It enters hot new tokens when all of these hold:
- the token is under 60 s old;
- at least 8 unique buyers in 10 s;
- net inflow over 1.5 SOL in 30 s;
- the developer has already sold;
- snipers hold under 10%.

It exits after 60 s or at −25%. Each trade is 0.5 SOL, with 1 s latency, a 125 bps fee and 0.001 SOL priority fee. The window was the whole train period, 12:15–17:15 UTC. Run: `run_25fc821ce3334751`.

**Result: FAIL.**

| | trades | PnL | expectancy/trade | win rate | PF |
|---|---|---|---|---|---|
| primary (1 s) | 1,036 | −52.46 SOL | −0.051 | 12% | 0.40 |

It is negative at every latency from 0.1 to 10 s. Fees and network costs account for 14.5 SOL and slippage for 8.4 SOL. Even with zero costs it would still lose about 29.5 SOL.

**What it implies:** Tracked wallets' picks look like this profile: hot, the developer already sold, few snipers. The profile alone is shared by roughly a thousand tokens over five hours, and buying all of them loses. The selection study showed that profile tokens no tracked wallet buys next fall sharply. The wallets' real filter is something else, which the Decu footage points to: narrative checks and labelled-wallet tracking. H1 is retired.
