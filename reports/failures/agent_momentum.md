# Momentum family: failures (10 of 12 pre-registered configs)

_Agent: momentum, 2026-10-05. Pre-registration: `reports/hypotheses/momentum_preregistration.json`.
The two long-only XS configs that passed both train and validation are written up, with heavy caveats, in
`reports/candidates/momentum.md`. Evidence: `research/observations/evidence_momentum_train.json`,
`evidence_momentum_train_slipx2.json`, `evidence_momentum_validation.json`._

**Data:**
- Source: data.binance.vision USDT-M daily klines (900 symbols listed, 683 with data, delisted symbols included) and fundingRate monthly files, up to 2026-03 (about 60 MB).
- Universe: point in time, top 40 by trailing 30-day quote volume.
- Rebalance: weekly, on Monday.
- Costs: 5 bp taker, plus 2–20 bp slippage per side by liquidity tier, plus funding on every print.

**Bar:** at least 50 episodes, net > 0, PF > 1.2, and net > 0 without the 3 best episodes.

## Train (2020-10-19..2024-06-30)
| config | n | net | PF | net without top 3 | Sharpe | maxDD (additive) | pass |
|---|---|---|---|---|---|---|---|
| TS_L7_LS | 4079 | +0.67 | 1.21 | +0.58 | 0.68 | −0.28 | yes (fails at 2× slippage: PF 1.18) |
| TS_L14_LS | 3017 | +0.34 | 1.12 | +0.25 | 0.35 | −0.54 | no |
| TS_L28_LS | 2094 | +0.87 | 1.40 | +0.77 | 0.99 | −0.19 | yes |
| TS_L28_skip1_LS | 2132 | +0.99 | 1.46 | +0.88 | 1.05 | −0.32 | yes |
| TS_L14_LO | 1525 | +0.63 | 1.42 | +0.54 | 0.67 | −0.44 | yes |
| TS_L28_LO | 1065 | +0.90 | 1.87 | +0.80 | 1.02 | −0.29 | yes |
| XS_L7_LS | 2428 | +0.99 | 1.10 | +0.55 | 0.70 | −0.47 | no |
| XS_L14_LS | 1847 | +0.13 | 1.01 | −0.35 | 0.09 | −0.56 | no |
| XS_L28_LS | 1363 | +0.78 | 1.10 | +0.23 | 0.53 | −0.33 | no |
| XS_L28_skip1_LS | 1367 | +0.46 | 1.06 | −0.09 | 0.32 | −0.43 | no |
| XS_L7_LO | 1189 | +2.93 | 1.29 | +2.05 | 0.79 | −1.90 | yes |
| XS_L28_LO | 635 | +2.88 | 1.40 | +1.78 | 0.82 | −1.37 | yes |

The TS long-short profit came almost entirely from the long leg. For TS_L28_LS the short leg made +0.01 against +0.94 for the long leg, and 2021 contributed 0.37 of 0.87. The XS long-short short leg lost money in every L tested (−0.28 to −0.76), even though it received funding.

## Validation (looked at once, only for the 7 configs that passed train)
| config | n | net | PF | net without top 3 | Sharpe | maxDD | per year (2024H2 / 2025 / 2026Q1) | pass |
|---|---|---|---|---|---|---|---|---|
| TS_L7_LS | 2003 | −0.05 | 0.97 | −0.11 | −0.11 | −0.25 | −0.05 / −0.06 / +0.06 | **no** |
| TS_L28_LS | 1079 | +0.14 | 1.13 | +0.07 | 0.33 | −0.28 | −0.14 / +0.26 / +0.02 | **no** (PF; top-3-coin share 69%) |
| TS_L28_skip1_LS | 1088 | +0.05 | 1.05 | −0.01 | 0.12 | −0.26 | −0.10 / +0.17 / −0.01 | **no** |
| TS_L14_LO | 717 | −0.04 | 0.95 | −0.10 | −0.09 | −0.23 | +0.01 / +0.00 / −0.05 | **no** |
| TS_L28_LO | 516 | +0.03 | 1.06 | −0.03 | 0.10 | −0.18 | +0.08 / +0.02 / −0.07 | **no** |
| XS_L7_LO | 560 | +2.04 | 1.38 | +0.33 | 0.96 | −0.94 | +1.05 / +0.30 / +0.70 | yes (see candidate) |
| XS_L28_LO | 295 | +1.70 | 1.39 | +0.06 | 0.83 | −0.94 | +0.73 / +0.36 / +0.61 | yes, fragile |

## Reading
- **Time-series momentum:** this is the effect Liu & Tsyvinski (2021) found strongest. Vol-scaled to 50% per coin, it looked good on train, with Sharpe about 1. On validation it decayed to roughly zero after costs. Its train edge was mostly being long during the 2020–21 and 2023 uptrends.
- **Cross-sectional long-short momentum:** this is the Liu, Tsyvinski & Wu (2022) factor. It never passed train, on PF or on concentration. Shorting losers in a perp universe full of squeezes is costly. This agrees with Grobys & Sapkota (2019) and with the Han, Kang & Ryu cost caveat.
- **Survivorship:** the archive contains delisted contracts (LUNA, ALPACA, BNX, HIFI, ...), so survivorship bias is limited. Some symbols' early history may be missing (for example, FTTUSDT klines start in 2022-04).
