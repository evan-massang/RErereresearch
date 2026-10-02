# H8 failed its first test

**Tested:** H8, the final-stretch rule, was frozen at 01:08 UTC (`reports/hypotheses/h8_preregistration.json`). It:
- buys a curve token once its market cap first reaches 250 SOL;
- holds it through migration;
- sells 5 minutes into PumpSwap;
- uses a 30% stop that fills at the actual price;
- assumes harsh costs and 1-SOL positions.

The test window was entries 17:15–18:15 UTC, using only data before 19:15.

**Result: FAIL.** 47 trades, **−6.83 SOL**, expectancy −0.145 SOL per 1-SOL trade, win rate 21%, profit factor 0.52. Without the top 3 trades the expectancy is −0.262.

Exits: 31 stopped out, 9 migrated, 7 timed out.

**What it implies:**
- In the test window only 19% of entries completed their curve, against 33% on train. The train profit came from a stretch of the day when far-along tokens kept finishing. That was not a stable property.
- The post-migration pop is real, but whether a 250-SOL token finishes is close to a coin flip that changes with the market's mood. Over this day it does not pay for the stops.
- H8 is retired. The holdout was not used.
