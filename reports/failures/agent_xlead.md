# H-XLEAD (minute cross-asset lead-lag into meme perps): FAIL on train, validation not opened

Agent "xlead", 2026-10-05. Source: `sources/leads/documented_edges_round4.md`, idea 5 (H-XLEAD; Guo, Sang, Tu & Wang,
JEDC 163, 2024, peer-reviewed). Scripts: `scripts/research/xlead_fetch.py`, `scripts/research/xlead_sim.py`.
Evidence: `research/observations/evidence_xlead_train.json`. Splits: train ≤ 2025-06-30, validation 2025-07-01 to
2026-03-31 (not scored, because nothing passed train), holdout ≥ 2026-04-01 (never downloaded).

## Data
- Source: data.binance.vision USDⓈ-M futures monthly 1m klines, 2024-01 to 2026-03. Holdout months were not fetched.
  The cache is `data/raw/web/binance_fut/xlead/`: per-month parquet (OHLC, quote volume, trades). The zips were
  deleted to save disk; each one's URL, size and sha256 are in `manifest.json`. 573 files; 102 symbol-months are
  missing because the coin was not yet listed.
- Leaders: BTC, SOL (ETH was fetched but not used, per the pre-registered model).
- The meme universe was fixed before any return was looked at. The rule: Binance USDⓈ-M perps in the CoinGecko meme
  category that are also Hyperliquid perps (HL `meta`, delisted coins included) and were listed on Binance by
  2024-12-31. That gives 22 coins: DOGE, 1000PEPE, 1000SHIB, 1000BONK, 1000FLOKI, WIF, BOME, MEME, PEOPLE, MYRO,
  POPCAT, TURBO, BRETT, MEW, NEIRO, GOAT, MOODENG, PNUT, CHILLGUY, PENGU, FARTCOIN, DOGS. All 22 have data from
  listing to 2026-03.

## Method (pre-registered in the script docstring)
- **Target:** log return of meme i from close_t to close_{t+h}.
- **Regressors:** returns of minutes t, t-1 and t-2 for BTC, SOL and the equal-weight meme index excluding i. That is
  9 regressors, with no intercept. The "own" variant adds i's own 3 lags.
- **Fitting:** per-coin OLS (with a negligible ridge), refit weekly on the trailing 30 days. Only targets realised
  before the refit time are used.
- **Taker execution:** HL fee 4.5 bp per side, base tier (https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees),
  plus slippage of 2, 3 or 5 bp. The 3 bp case is the one judged.
  - Entry is at the Binance close_t (delay 0), which is optimistic. A delay-1 variant enters at close_{t+1}.
- **Maker entry:** 1.5 bp fee. A fill needs a trade-through of at least 1 bp in minute t+1; the exit is taker.
- **Trade rule:** trade when |pred| ≥ c × round-trip cost. One position per coin at a time.
- **Configs:** 15 in total. Taker: h {1, 3, 5} × c {1.5, 2, 3}. Maker: h {3, 5} × c {1, 1.5}. Own-lags: h 5 × c {1.5, 2}.

## Gross edge vs costs (train, out-of-sample walk-forward)
- **Model fit:** pooled out-of-sample R² is negative for the base model (h1 −0.0003, h5 −0.0002); corr(pred, realised)
  is about 0.02.
- **Realised edge by bucket (signed realised return given |pred|):**
  - 2–5 bp predicted: +1.4 bp realised.
  - 10–15 bp predicted: about +6 bp realised.
  - Above 30 bp predicted: negative. The biggest predictions come on shock minutes and reverse.
- **Costs:** the taker round trip is 15 bp (11–19 bp across the slippage cases); the maker round trip is 9 bp.
- **Base model trades:** average gross edge is between −208 and +7 bp per trade, against a 15 bp cost.
- **Own-lag variant:** about +14 bp gross at delay 0, but only +1.4 bp at delay 1.
  - So the visible edge is continuation inside the kline-close minute, which cannot be captured.
  - Half of its trades are one coin, CHILLGUY in 2025-Q2.

## Best train stats (3 bp slippage, delay 0)
| config | n | net bp | PF | ex-top-3 | gross/trade |
|---|---|---|---|---|---|
| T_own_h5_c2.0 | 4438 | −4,315 | 0.985 | −8,759 | +14.0 |
| T_base_h5_c1.5 | 2209 | −17,426 | 0.905 | −21,715 | +7.1 |
| M_base_h5_c1.5 | 11204 | −78,792 | 0.87 | −83,275 | +2.0 |
| others | 32–35,620 | all negative | 0.26–0.84 | negative | — |

- **2 bp slippage:** T_own_h5_c2.0 nets +13,104 bp but with PF 1.03 and a negative ex-top-3. It still fails.
- **Delay 1:** every config loses heavily.
- **Turnover:** 0.06 to 65 trades per day across the 22 coins.
- **Stability (T_own_h5_c2.0):**
  - Quarterly PF is 0.70–1.16, and no quarter is positive once its top 3 trades are removed.
  - By coin, 8 of 22 are positive (BONK, PEPE, FARTCOIN, CHILLGUY…) and 14 are negative (WIF, GOAT, MEME…).

## Verdict
**FAIL.** None of the 15 configs passes the bar on train, even with the optimistic delay-0 fill. Validation was
therefore not scored, and the holdout was never loaded.
- Minute-scale lead-lag from BTC, SOL and the meme sector exists, at a few bp, but it is far below Hyperliquid taker
  cost.
- Maker entry is adverse-selected: gross edge is about 0 bp on filled orders.
- This matches the counter-evidence of about 0.5 bp per boundary cited in the brief.
- **Caveats:**
  - Binance klines were used as the HL execution price, with no basis risk.
  - Sub-minute timing was not modelled. Either would lower the results further.
  - Adaptive LASSO on a wider leader set (HYPE, PUMP) was not tried. Given a gross edge of ≤ 14 bp at delay 0 that
    vanishes at delay 1, a re-test is not recommended without tick data and sub-second execution.
