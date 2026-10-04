# Snapshot model + early-detector precision + aged-wallet demand (agent ml_wallet, 2026-10-04): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## Idea

Two near-misses, each a wallet-quality signal, added as features to the iteration-6 snapshot model (`ml_snapshots.py` / `ml_exits.py`):
- early-detector precision (`agent_early_detectors.md`: precision persists, 42% vs a 23% base, but triggers lose);
- aged-wallet demand with a wash filter (`agent_aged_demand.md`: cut losses 3–6× vs raw buyers, best train PF 0.93).

## Method

Scripts: `scripts/research/ml_wallet_build.py` (snapshots + features + labels), `scripts/research/ml_wallet_eval.py` (model and grid). Evidence: `research/observations/evidence_ml_wallet_20261004.json`.

**Data.** `data/market.duckdb` opened read-only. Only fold A (recv < 1790882100), fold B (1790899200–1790985600) and validation V (1790985600–1791072000) were ever queried.
- Trades with |vsol − rsol − 30| ≥ 0.01 are dropped before anything else.
- Mayhem Mode tokens are skipped, and so are tokens without a PumpPortal flag (14–19% of creates).
- The snapshots were **rebuilt** rather than reusing `ml_snapshots.parquet`, because that file ends at Oct 3 03:37 UTC and its Oct 1 labels could run into the holdout. Every snapshot's label window (t + 1 s + 300 s) lies inside its own split and inside one gap-free recording segment (no gap over 60 s).
- `creator_prior` counts only creates from the allowed data.
- Result: 99,847 train snapshots (A 49,682; B 50,165) and 164,344 validation snapshots, at ages 5, 10, 20, 30, 60, 120 and 300 s.

**The 24 tape features and the labels** are exactly as in `ml_snapshots.py`:
- `g_tp*_sl*_{120,300}`: 0.5 SOL, 1.25% fee per side, 1 s latency, exact curve fills, stored before tips.

**13 wallet features.** All are point in time, and dev buys are excluded.

*Detector features:*
- `det_n_since`, `det_sol_since`, `det_n_30`, `det_sol_30`: the count and SOL of buys since launch and in the last 30 s by detector wallets. A detector has precision ≥ 0.5 over at least 8 label-complete qualifying first buys, defined as in `early_detectors_build.py`.
- `prec_max`, `prec_mean`, `prec_known_n`: computed over the token's distinct buyers that have a known precision.
- The detector lists are cross-fitted: fold-A snapshots use the list built on fold B, and fold-B snapshots use the list built on fold A. Validation would use the list built on A+B.
- Lists: 821 / 990 / 1,699 wallets with a known precision; 11 / 23 / 28 detectors.

*Aged-demand features:*
- `aged_n_30`, `aged_share_30`, `aged_n_since`, `aged_share_since`: distinct non-wash buyers whose first seen time is at least 3 h before the buy, as a count and as a share of distinct buyers.
- `wash_share_30`, `wash_share_since`: the share of buys from wallets that bought and sold the token within 10 s of each other, both at or before t.

**Model and selection.** Unchanged from `ml_exits.py`:
- HistGradientBoostingClassifier with GroupKFold(5) by mint on train;
- target: g − 2 × 0.001 > 0;
- thresholds at the 0.99, 0.995 and 0.998 quantiles of out-of-fold train probabilities;
- one trade per token;
- tips of 0.001 SOL (main case) and 0.01 SOL per transaction.

**Grid.** 8 exits × 3 quantiles = **24 selectable configs** (base + wallet features), fixed before any result was seen. The same grid with the base features only, and with the wallet features plus age and mcap only, is reported as a reference and was not selectable.

## Result: FAIL on train. No config passes, so validation was not read.

**All 24 configs lose on train out-of-fold**, at −0.010 to −0.053 SOL per trade (tip 0.001), with PF 0.50–0.91.

**Best config:** `g_tp100_sl30_120`, q0.998. At tip 0.001:

| sample | trades | net SOL | profit factor | win rate | net without best 3 |
|---|---|---|---|---|---|
| train out-of-fold | 130 | −1.25 | 0.91 | 36% | −3.23 |
| fold A | 59 | −2.47 | 0.64 | — | — |
| fold B | 71 | +1.22 | 1.17 | — | −0.59 |

At a 0.01 tip the same config makes −3.59 SOL (PF 0.77).

**The wallet features help, but only relative to the base model.**
- They beat the base-only model in 18 of the 24 cells, at a mean of −0.029 vs −0.037 SOL per trade.
- Out-of-fold AUC is unchanged (0.83–0.84).
- The wallet-only model is worse than base + wallet.

**Univariate pattern (train, TP50/SL20 300 s).** Higher `prec_max`, aged count and aged share raise the win rate: for `prec_max`, from 5% in the bottom quintile to 16% in the top. The mean is *lower*, though: −0.043 vs −0.036 SOL per trade. These features flag active tokens that sometimes run, but they also dip and stop out more often. This is the same failure mode as the detector triggers.

## Verdict

**FAIL.** Combining early-detector precision and aged-wallet demand with the tape features makes the snapshot model lose less, but nothing reaches break-even on train after fees and a 0.001 SOL tip. The family total is 24 selectable configs (48 reference fits on top). Validation was never looked at.
