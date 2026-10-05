# Candidate (conditional, fragile): XS_L7_LO, cross-sectional momentum, long only, on Binance USDT-M perps

_Agent: momentum, 2026-10-05. Pre-registration (frozen before any download or P&L):
`reports/hypotheses/momentum_preregistration.json`. Scripts: `scripts/research/momentum_fetch.py`,
`momentum_sim.py`, `momentum_diag.py`. Evidence: `research/observations/evidence_momentum_{literature,train,train_slipx2,validation,diagnostics}.json`.
Holdout (>= 2026-04-01) was never downloaded or examined._

**Verdict.** Out of 12 pre-registered configs, 7 passed the bar on train. Two of those 7 passed on validation: XS_L7_LO and XS_L28_LO. Both are **long-only** cross-sectional configs.

The validation pass depends on three things:
- a handful of squeeze events;
- one delisting-settlement spike (ALPACA, April 2025);
- large **negative-funding receipts** on squeezed coins.

The bar fails on validation if either of these is removed:
- the contract-settlement episodes;
- the funding receipts.

So the candidate passes the letter of the bar, but it is not a robust momentum premium. All time-series configs and all long-short XS configs failed. See `reports/failures/agent_momentum.md`.

## Frozen rule (XS_L7_LO). The holdout must use exactly this
- **Universe:** every `*USDT` perpetual in data.binance.vision `futures/um`, delisted symbols included. Excluded: BTCDOM, DEFI, FOOTBALL, BLUEBIRD, USDC and stablecoin bases.
- **Rebalance time:** each Monday 00:00 UTC, time t.
- **Eligibility:** at least 60 daily bars, a bar for day t-1, and at least 25 of the last 30 days present.
- **Top 40:** rank the eligible coins by quote volume over the 30 daily bars ending t-1, and keep the top 40.
- **Signal:** R7 = close(t-1) / close(t-8) - 1, using daily closes.
- **Position:** long the top quintile by R7 (8 coins), at 1/8 of capital each (gross 1x, no leverage, no shorts). Fill at close(t-1), which is the open at t, and hold to t+7 at constant notional.
- **Costs:**
  - taker fee 5 bp per side;
  - slippage per side by 30-day average daily quote volume: 2 / 5 / 10 / 20 bp for at least $1B / $200M–1B / $50M–200M / below $50M;
  - cost = |Δw| × (fee + slippage);
  - funding is paid or received on every print in (t, t+7d];
  - a coin whose data ends while held exits at its last close, with a 2% penalty.

## Results (per-episode bar; one episode is the consecutive weeks one coin is held)
| | train (2020-10-19..2024-06-30) | validation (2024-07-01..2026-03-31) |
|---|---|---|
| episodes | 1189 | 560 |
| net (capital units, additive) | +2.93 | +2.04 |
| profit factor | 1.29 | 1.38 |
| net without the 3 best episodes | +2.05 | +0.33 |
| Sharpe (weekly, ×√52) | 0.79 | 0.96 |
| max DD, additive / compounded | −1.90 / −90% | −0.94 / −67% |
| average weekly turnover (Σ\|Δw\|) | 1.53 | 1.51 |
| top-3-coin share of net | 50% | 79% (ALPACA, MYX, PIPPIN) |
| funding (− = received) | +0.01 | **−1.05** |
| costs | 0.36 | 0.16 |
| per year | 2020 +1.04, 2021 +2.64, 2022 −1.50, 2023 +0.97, 2024H1 −0.21 | 2024H2 +1.05, 2025 +0.30, 2026Q1 +0.70 |
| per quarter (validation) | – | +0.08, +0.96, −0.81, +0.76, +0.40, −0.06, +0.70 |

XS_L28_LO results:
- Train: 635 episodes, net +2.88, PF 1.40, net without the top 3 episodes +1.78.
- Validation: 295 episodes, net +1.70, PF 1.39, net without the top 3 episodes **+0.057**. This is fragile. It fails at 4× slippage, and is only +0.005 at 2× slippage.

## Robustness (diagnostics, not used for selection; `evidence_momentum_diagnostics.json`)
- **Slippage:** validation still passes at 2× slippage (net without the top 3 episodes +0.24) and at 4× (+0.05).
- **One-day execution delay:** fill at close(t) instead of close(t-1). It still passes: validation net +3.41, PF 1.64.
- **Funding excluded:** validation net +0.99, PF 1.17, net without the top 3 episodes −0.59. **This fails.** The funding was real cash flow, but capacity during −2%/h funding squeezes is unknown.
- **Settlement episodes excluded:** these are episodes held into a contract's zero-volume settlement tail. They are ALPACA (+0.74), BNX and HIFI. Excluding them gives validation net +1.25, PF 1.23, net without the top 3 episodes −0.10. **This fails.**
- **Benchmark:** an equal-weight long position in the same universe, under the same cost model. On train it made net +1.87. On validation it made −0.36, PF 0.79. The momentum tilt did beat plain beta on validation.
- **Multiple testing:** 12 configs were tested, 7 passed train and 2 passed validation. Both survivors are long-only, so they carry full market beta. Their train profit comes mostly from the 2020–21 bull market.

## Risks
- **Tail and liquidity:** the profit comes from micro-cap squeezes and a delisting pump that reached the top-40 volume list. Fill sizes, reduce-only restrictions around delisting, and the tier slippage on squeezed coins are all unverified.
- **Drawdown:** compounded drawdown was −90% on train and −67% on validation, which is not deployable at 1× as is.
- **Universe drift:** in 2025–26 the top 40 by volume includes newly listed and tokenized-stock perps.
- **Data:** daily closes only. There is no intraday stop and no check for liquidation (none occurs at 1× long).

**Next step:** run the holdout once with this exact rule, and report it in `reports/failures/` if it fails. Do not tune.
