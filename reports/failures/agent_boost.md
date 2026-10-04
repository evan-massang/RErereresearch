# Trading alongside pump.fun BOOST: FAIL on train (agent boost, 2026-10-04)

**Verdict: FAIL.** BOOST is real and fully visible in our data, but none of the 30 pre-declared configs passed the
bar on train (at least 50 trades, net > 0, PF > 1.2, net > 0 without the 3 best trades). As the rules require,
validation (Oct 3) was **not examined**. Holdout and forward rows were never loaded (the loader filters them in SQL
and asserts it).

- **Evidence:** `research/observations/evidence_boost_verify_train_20261004.json` (BOOST pattern) and
  `research/observations/evidence_boost_train_20261004.json` (grid results, both tip levels).
- **Scripts:** `scripts/research/boost_verify.py`, `boost_lib.py`, `boost_explore.py`, `boost_sim.py`
  (fills reuse `amm_flow_lib.py`).

## 1. BOOST in our data (train only, observed on-chain)

- **Which pools.** 546 of 688 train pools have `amm_pools.quote_in` = 84.99 SOL (pump.fun migrations). Their first
  logged quote reserve is `quote_in − 17.585`. This is the same 17.585 SOL offset that agent amm_flow found in the swap
  math: the BOOST budget sits in the pool's quote vault. The flag is known at the pool-creation event.
- **Who buys.** Each BOOST pool has its own buy-only wallet. It looks like a per-pool PDA: none of these wallets
  appears in a second pool.
  - In 342 pools the wallet's buys total exactly **17.5845 SOL**.
  - In 199 more pools the captured buys total 14.2–17.2 SOL (5th–95th percentile). These are probably slices the
    recorder missed. This was not verified.
  - None of the 142 non-84.99 pools has such a wallet.
- **Schedule** (medians, with the 5th–95th percentile range):
  - 29 slices per pool (27–30);
  - 0.60 SOL per slice (0.37–0.84);
  - one slice every 11.7 s (10.6–14.1 s);
  - first slice 1.9 s after the pool-creation event (1.2–15.4 s); last slice at 341 s (329–358 s).
  - In short: a regular TWAP of about 340 s.
- **Starting state.** About half the pools take a large bundled buy in the creation slot: the reserve is already above
  150 SOL at entry, with a median price of 7.6× the initial price.

## 2. Grid: 30 configs, chosen on train only

The grid crosses three things: entry latency, exit and a liquidity filter.

- **Entry latency** (after the pool-creation event): 0.25 s or 1 s.
- **Exit:**
  - single sells at +120 s, +300 s or +340 s (+340 s is the end of the BOOST window);
  - or equal slices, either five at 60/120/180/240/300 s or four at 90/180/270/330 s.
- **Liquidity filter** on the reserve at entry: all pools; thin (≤ 150 SOL); bundled (> 150 SOL).

**Fills and costs.**
- Size is 0.5 SOL, with exact constant-product fills. The reserve is the logged value + 17.585.
- Fees are charged per side at `fee_bps/1e4`, which is 1.0–1.25% early in a pool's life.
- Fills use the conservative entry and exit states from amm_flow.
- Our own earlier exit slices stay in the pool, with no reversion assumed.
- The tip is 0.001 or 0.01 SOL per transaction, charged on 1 + the number of exit slices.

## 3. Results (train)

**Best configs at a 0.001 SOL tip:**

| config | trades | net SOL | PF | net without best 3 | net at 0.01 tip |
|---|---|---|---|---|---|
| L1.0_X300_THIN | 291 | +6.16 | 1.15 | −3.85 | +0.92 (PF 1.02) |
| L1.0_X300_ALL | 545 | +4.53 | 1.08 | −5.48 | −5.28 |
| L0.25_X300_THIN | 213 | +2.68 | 1.09 | −5.26 | −1.15 |

- 7 of the 30 configs are net positive at the 0.001 SOL tip.
- **None reaches PF 1.2, and none is positive without its best 3 trades.**
- All the bundled-pool configs lose money. They win 66–82% of trades, but rugs give them a heavy left tail.
- Sliced exits are worse than single exits: they pay more fees and tips.

## Reading

The forced 17.6 SOL buyer is predictable to the second. It lifts the median bundled pool by about 15% by +340 s.
But costs and other flow swamp it:

- About 2–2.5% in fees per round trip, plus tips.
- In the first second, snipers have already bought ahead of the schedule.
- Holders sell into the TWAP. In thin pools the median gross return to +340 s is −13%, and the mean is positive only
  because of a right tail.
- The 10th percentile of gross returns is −70% to −84%: rugs and dev dumps during the window.

There is no robust out-of-sample-ready edge, so this family is closed at these latencies.
