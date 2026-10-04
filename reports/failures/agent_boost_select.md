# Pre-migration pool selection on the BOOST base rule: FAIL on validation (agent boost_select, 2026-10-04)

**Verdict: FAIL.** On train, 4 of 28 pre-stated filters passed the bar at the 0.001 SOL tip. All 4 lose money on
validation (Oct 3), as does the unfiltered base rule. Validation was run once, for those 4 configs plus the base rule
as a reference. Holdout and forward rows were never loaded; the SQL filters exclude them and the scripts assert this.

- **Scripts:** `scripts/research/boost_select_lib.py` (features) and `scripts/research/boost_select_grid.py` (grid).
  Fills reuse `boost_lib.sliced_trip` and `amm_flow_lib`: exact constant product, reserve = logged + 17.585, fee_bps
  per side, conservative fill states.
- **Evidence:** `research/observations/evidence_boost_select_train_20261004.json` and
  `research/observations/evidence_boost_select_valid_20261004.json`.

## Base rule and universe

- **Base rule:** buy 0.5 SOL at pool creation + 1.0 s, only if the true reserve at entry is ≤ 150 SOL. Sell everything
  at +300 s. Tips are 0.001 or 0.01 SOL per transaction, 2 transactions per trade.
- **Train universe:** 291 base trades, of which 256 pools are eligible. The other 35 pools were dropped for one of two
  reasons:
  - the token's create event is not in our data, so its curve history is incomplete;
  - the token's curve history would overlap the holdout window. Rows from the holdout window are never read.
- **Base result on the 256 eligible pools:** +6.77 SOL, PF 1.18, −3.24 SOL without the best 3 trades. The full 291
  trades reproduce the boost agent's +6.16 SOL.

## Features

All features are known at pool creation. They come from `curve_creates` and from `curve_trades` up to pool creation.

| feature | definition |
|---|---|
| fill_s | Time from token create to pool creation. |
| top5_share | Share of curve buy SOL from the 5 largest buyers. |
| creator_hold | 1 if the creator wallet's net curve tokens are more than 1% of its gross buys. Transfers to other wallets are not visible. |
| snipe_share | Share of non-creator buy SOL in the create slot through create slot + 2. |
| n_buyers | Number of distinct buying wallets on the curve. |
| social | 1 if the metadata has a twitter, telegram or website field. |
| mayhem | The flag from `data/processed/mayhem_flags.parquet`. |

**Coverage on train:**
- **Metadata:** 165 of 256 pools (64%); 158 of them have socials.
- **Mayhem flag:** known for 208 of 256 pools, and **none** of them is Mayhem. So that filter does nothing here.
- **snipe_share:** missing for 6 pools.

**Coverage on validation:** metadata 146 of 470 pools (31%); Mayhem flag known for 330, none of them Mayhem.

## Grid: 28 configs, stated before any results were seen

- **Thresholds:** train medians and terciles of each feature, computed from the features only, without outcomes.
- **Configs:**
  - the base rule;
  - 12 single filters: median splits, both sides, plus SOCIAL and NOMAYHEM;
  - 5 tercile filters;
  - 10 two-feature pairs, built from the sides hypothesized to be "safe": slow fill, low top-5 share, creator sold
    out, low snipe share, many buyers.

## Train results

**The safe-side hypothesis was wrong.** Every safe-side single filter and every pair loses money on train, at −5.6 to
+0.5 SOL.

**The 4 train passers are the opposite sides.** They overlap heavily (83–106 of about 125 pools in common): one cluster
of concentrated, fast-filling launches with few buyers.

| config (0.001 tip) | n | net | PF | net without best 3 | Oct 1 net / PF | Oct 2 net / PF | net at 0.01 tip (without best 3) |
|---|---|---|---|---|---|---|---|
| CRE_HOLD | 119 | +12.00 | 1.74 | +1.99 | +2.47 / 1.30 | +9.53 / 2.21 | +9.86 (−0.10) |
| BUY_LO (fewer than 319 buyers) | 128 | +11.99 | 1.61 | +1.98 | +3.64 / 1.33 | +8.35 / 1.93 | +9.68 (−0.27) |
| TOP5_HI (top-5 share > 0.143) | 127 | +11.50 | 1.61 | +1.49 | +3.19 / 1.33 | +8.32 / 1.91 | +9.22 (−0.74) |
| SNIPE_HI (snipe share > 0.047) | 125 | +11.05 | 1.67 | +1.20 | +1.40 / 1.15 | +9.64 / 2.29 | +8.80 (−1.00) |

**Warning signs, visible before validation:**
- At the 0.01 SOL tip, none of the 4 is positive without its best 3 trades.
- On each day taken alone, each of the 4 is negative without its best 3 trades.
- Oct 2 supplies 70–87% of the profit.
- The cluster is the opposite of the stated hypothesis, and it was picked from 28 configs.

## Validation (Oct 3, run once)

Validation used 470 eligible thin pools, almost twice train's 256 over two days.

| config (0.001 tip) | n | net | PF | net without best 3 | net at 0.01 tip |
|---|---|---|---|---|---|
| TOP5_HI | 221 | −1.41 | 0.96 | −9.05 | −5.39 |
| BUY_LO | 241 | −3.87 | 0.91 | −11.52 | −8.21 |
| SNIPE_HI | 244 | −6.78 | 0.82 | −14.43 | −11.18 |
| CRE_HOLD | 271 | −9.24 | 0.78 | −14.58 | −14.11 |
| BASE (reference) | 470 | −12.09 | 0.84 | −19.79 | −20.55 |

## Reading

On validation, the filters lose less than the base rule. That is consistent with a small selection effect, but no
filter comes close to profit. The train pass is best explained by a right tail on Oct 2 together with selection from 28
configs.

The base rule itself turns from +6.8 SOL on train to −12.1 SOL on validation. The BOOST thin-pool trade does not carry
over to Oct 3 in any form we tested.

This pool-selection family is closed for these features. No thresholds or features were changed after validation.
