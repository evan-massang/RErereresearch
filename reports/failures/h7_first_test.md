# H7 failed its first test, on sample size, but was profitable

**Tested:** H7 was frozen at 23:32 UTC (`reports/hypotheses/h7_preregistration.json`). It is the user's "track good devs" idea:
- **Entry:** buy the launch, about 1 s after it appears, when its creator already had a migration that day and a migration rate of at least 20%.
- **Exits:**
  - −30% stop;
  - at 60 s, sell unless up at least 20%;
  - 40% trailing stop;
  - take profit at 300 SOL market cap;
  - 30-minute time stop.
- **Size:** 0.5 SOL.
- **Execution:** 1 s latency, 125 bps fee, 0.01 SOL priority plus tip, 30% slippage tolerance, 2% tx failure.
- **Dev record:** built from all data since 12:17.
- **Window:** trades 17:15–19:15 UTC.
- **Pass required:** at least 15 trades, expectancy > 0, PF > 1.2.

**Result: FAIL, because only 11 trades occurred.**

| delay | trades | PnL SOL | PF |
|---|---|---|---|
| 0.1 s | 14 | +1.98 | 2.25 |
| 0.5 s | 13 | +1.22 | 2.01 |
| **1 s (primary)** | **11** | **+2.36** | **3.78** |
| 2 s | 11 | +1.88 | 3.58 |
| 5 s | 7 | +1.93 | 5.48 |
| 10 s | 5 | −0.34 | 0 |

**What it implies:**
- **One trade carries the result.** AFD returned +3.17 SOL (6.3×). The other ten trades lost a total of about 0.8 SOL. Five positions were still open at the end, marked at about +0.1 SOL net.
- **Payoffs are lottery-shaped.** Many small cuts and the occasional runner. Judging the rule needs on the order of 100 trades, i.e. several recorded days.
- **In-sample it was about breakeven** (train: 40 trades, PF 1.02).
- **The next honest test** is the same frozen rule on new recordings. The holdout was not used for it.

H7 stays registered; its status is set to rejected below.
