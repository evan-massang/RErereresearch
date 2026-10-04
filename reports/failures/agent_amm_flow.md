# Post-migration PumpSwap order flow, minutes timescale: FAIL on train (agent amm_flow, 2026-10-04)

**Verdict: FAIL.** None of the 30 pre-declared configs passed the bar on train. As the rules require, validation (Oct 3) was **not examined**. The holdout and forward data were never loaded.

- **Evidence:** `research/observations/evidence_amm_flow_train_20261004.json`.
- **Scripts:** `scripts/research/amm_flow_lib.py`, `amm_flow_features.py`, `amm_flow_sim.py` and `amm_flow_gross.py`.

## Setup

**Data.** `amm_trades` from `data/market.duckdb`, opened read-only.
- **Train window:** recv before 1790882100, or from 1790899200 to before 1790985600.
- **Coverage:** 689 pools were active (at least 3 trades in the preceding 60 s).
- **Excluded:** pools created inside the holdout.

**Decisions.** One every 15 s per pool. Features use only trades received at or before t. The entry is at t+1 s, and exits never cross a window end.

**Fills.** Each trade is 0.5 SOL on exact constant-product math.
- **Entry:** the higher-priced of two states, the pool state at t+1 s or the state after the first trade within 5 s.
- **Exit:** the lower-priced of the same two states. It is also marked down to the next trade's pre-trade state when that state is more than 2% lower, which covers unobserved liquidity changes.
- **Fees:** `fee_bps/1e4` per side.
- **Tips:** 0.001 or 0.01 SOL per transaction.

**Two corrections to the brief, verified on the data:**
1. **The SOL reserve used by the swap math is the logged value *plus* 17.585 SOL, not minus 17.6.** On 94,624 train sells, `sol = R_s*tok/(R_t+tok)` holds exactly with this offset (the 90th and 99th percentiles agree to four decimals).
2. **`fee_bps` already includes the LP and protocol fees.** `load_amm` sums all three, and on sells `user_sol/sol = 1 - fee_bps/1e4`.

Both of the brief's readings are coded as sensitivities. They would only make the results worse, so they were not needed.

**Data quality.** About 0.4% of consecutive trades in the same pool show a jump of more than 5% between one trade's post-trade state and the next trade's logged pre-trade state. Ordering by slot does not remove these jumps, so they are probably missed events or liquidity moves. The conservative exit charges them against the strategy.

## Exploration (train)

Decile tables were built for 159k snapshots, and separately for the 66 deep pools (SOL reserve at least 600). The features were:
- order-flow imbalance (OFI) over 60, 180 and 300 s;
- returns over 60 and 300 s;
- drawdown from the post-migration high;
- the streak of buys from distinct wallets;
- the number of distinct buyers in the last 60 s;
- age, reserve and volume;
- the largest sell in the last 60 s and how far the price has recovered from it.

The outcome was the net PnL of a round trip held 60, 180 or 600 s.

**Every decile has a negative mean, even before tips.** In deep pools, high-OFI and many-buyer deciles have positive medians and win 70–84% of the time at 600 s. Their means are still negative, because of a left tail of drops of 50–100%: rug-like single sells or liquidity pulls.

## Grid: 30 configs, 15 rules × 2 exits

**Rules:**
- OFI momentum (5 min OFI of at least 0.5 or 0.7, at least 10 buyers in 60 s, reserve at least 100 or 600 SOL);
- contrarian heavy selling (60 s OFI at or below −0.5 and price down at least 5%);
- absorption of a large sell (at least 1% or 3% of the reserve, price recovered at least 70% of that drop, and net buying);
- streaks of buys from 8 or 15 distinct wallets;
- a dip of 30% or 50% below the post-migration high with buying returning, at an age of at least 30 min;
- young pools (under 30 min) near their high with net buying.

**Exits:** hold 600 s, or take profit / stop loss at ±5% on the mid with a 600 s maximum.

**Results at a 0.001 SOL tip (all 30 fail):**

| | trades | net SOL | PF | win rate | net without best 3 |
|---|---|---|---|---|---|
| Best mean per trade: `ofi_mom_th0.7_rs600_TPSL5` | 232 | −2.05 | 0.45 | 66% | −2.15 |
| Highest PF: `streak8_rs100_H600` | 1,222 | −22.99 | 0.77 | — | −43.9 |

- The best config's mean is −0.0088 SOL per trade.
- **At a 0.01 SOL tip, every config loses more.** The best config loses −6.23 SOL with PF 0.02.
- **Gross mid-to-mid returns are not enough to cover the cost.**
  - The best OFI and young-pool take-profit/stop-loss variants average +0.2–0.5% gross before conservative fills.
  - The round-trip cost is about 0.6% in deep pools and about 2.5% elsewhere, plus 0.4% in tips.
  - The contrarian, absorption and dip rules are negative even gross (−1% to −17%).

## Reading

Minute-scale flow on post-migration PumpSwap carries a weak, positive-median continuation. It sits on top of a fat left tail of rugs and dumps, which a ±5% stop cannot avoid because the drops are gaps. Under honest fills and fees there is no edge, so this family is closed for minute-scale holds.
