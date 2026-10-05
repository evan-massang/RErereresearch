# H-LISTSHORT: short newly listed memecoin perps (FAIL)

_Agent: listshort, 2026-10-05. Source idea: `sources/leads/documented_edges_round3.md`, idea 6._
_Evidence: `research/observations/evidence_listshort_{universe,train,validation}.json`._
_Scripts: `scripts/research/listshort_{universe,classify,fetch,analyze}.py`._

## Verdict

**FAIL.** Validation cannot meet the bar: it holds only **9** clean meme perp listings, and the bar needs at least 50 trades. All four configs that passed on train also **lose money** on those 9 validation listings, both raw and BTC-hedged (PF 0.37–0.81).

The train pass itself is fragile:
- it holds only with the BTC hedge;
- it needs 1× leverage (at 2× every config fails the top-3-removed test);
- it depends on the Oct 2024 – Jan 2025 listing wave. Without that wave the train PF is 0.86–1.02.

Nothing goes to `reports/candidates/`. The holdout (listings from 2026-04-01) was not examined.

## Universe (pre-declared before any price data)

**Venues:**
- Hyperliquid main-dex perps: `meta`, 234 coins including 56 delisted.
- Binance USDⓈ-M USDT perps: the S3 listing of `data.binance.vision/data/futures/um/monthly/klines/`, 1,056 symbols. `fapi.binance.com` returns HTTP 451 here.

**Memecoin definition:**
- The source is CoinGecko's `meme-token` category (https://www.coingecko.com/en/categories/meme-token; API `/coins/markets?category=meme-token`, 6,403 coins, fetched 2026-10-05).
- Matching is case-insensitive on the base symbol, after removing venue prefixes: HL `k`; BN `1000`, `1000000` and `1M`.
- When several CoinGecko coins share a symbol, the meme coin must be the largest by market cap.
- **Identity overrides** were made from asset identity only, before any prices were loaded. They are listed in `listshort_classify.py`.
  - Removed: AI (Sleepless AI), OMNI (Omni Network), the stock perps AMC/GME/HOOD, the commodity perps COPPER/XAU/XPD, MILK (MilkyWay), RONIN, RATS, X (X Empire), and FOOTBALL/KORU (unverifiable, with matched caps of about $3k–11k).
  - Added: HPOS, NEIROETH, BROCCOLI714 and BROCCOLIF3B, whose venue suffixes broke the symbol match.
  - BN `PUMPUSDT` was dropped because its files start in 2025-04, before pump.fun's PUMP existed. HL PUMP is used instead.
- Known limitations:
  - CoinGecko's membership is as of today, and coins that died may be missing from it (survivorship).
  - A coin missing from the category is classified as non-meme. JELLYJELLY is one example.

**Event unit:** one trade per coin, at its **earliest** listing on either venue. Coins whose earliest listing was before 2023-01-01 are excluded: DOGE, 1000SHIB, PEOPLE.

| split | clean | contaminated (round-3 set, reported separately) |
|---|---|---|
| train (≤ 2025-06-30) | **51** | 7 (AI16Z, ZEREBRO, GRIFFAIN, TRUMP, MELANIA, VINE, JELLY) |
| validation (2025-07-01 – 2026-03-31) | **9** | 3 (PUMP, USELESS, YZY) |
| holdout (≥ 2026-04-01) | not fetched; 8 symbols seen only as names | — |

The 11th round-3 coin, LAUNCHCOIN, is not in CoinGecko's meme category, so it is outside the universe. USELESS's HL listing falls in the holdout; its earlier Binance listing is the one used.

## Method

- **Entry:** short at the close of the first bar at or after listing + N. Bars are BN 1h, HL 1h/4h/1d, whichever reaches the listing; HL candleSnapshot serves only the last 5,000 bars.
- **Exit:** after H days. **Stop:** none or +40%.
- **Liquidation:** at +(1/L − 10%) adverse move, losing 100% of margin.
- **Grid:** N ∈ {4, 24, 72 h} × H ∈ {7, 14, 30 d} × stop ∈ {none, +40%} = 18 configs.
- **Leverage:** 1× is primary; 2× is a sensitivity.
- **Costs:**
  - Taker fees: HL 0.045% (tier 0, https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees, fetched) and BN 0.05% (USDⓈ-M VIP0, https://www.binance.com/en/fee/futureFee; not fetchable here, documented rate).
  - Slippage: 0.10% per side.
  - Hedge leg: 0.07% per side.
- **Funding:** each venue's actual funding history, received or paid, scaled by price/entry. Some HL coins have gaps in their funding history; missing funding is counted as zero.
- **Hedge:** long β × BTC perp. β = 1.24 is a pooled OLS of daily coin returns on BTC over **train** windows (1,525 observations); a SOL/ETH 50/50 mix gives β = 1.06. **The bar is applied to the BTC-hedged 1× returns.** Returns are per unit of equity, summed over trades.

## Train (selection), 51 clean listings

| N | hold | stop | raw net | raw PF | raw ex-top3 | BTC-hedged net | hedged PF | hedged ex-top3 | SOL/ETH-hedged net | full-window MAE median / max | trades with full-window MAE >= +40% | liquidated at 1x | stopped | mean funding | bar on train |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 h | 7 d | none | -2.82 | 0.75 | -4.88 | -1.32 | 0.87 | -3.38 | -1.32 | +29% / +5087% | 17/51 | 9 | 0 | +1.0% | fail |
| 4 h | 7 d | +40% | +0.43 | 1.05 | -1.63 | +1.61 | 1.23 | -0.46 | +1.65 | +29% / +5087% | 17/51 | 0 | 17 | +0.8% | fail |
| 4 h | 14 d | none | -6.13 | 0.60 | -8.38 | -4.40 | 0.69 | -6.50 | -4.91 | +37% / +5087% | 24/51 | 12 | 0 | +1.5% | fail |
| 4 h | 14 d | +40% | -2.10 | 0.80 | -4.34 | -0.76 | 0.92 | -2.86 | -1.24 | +37% / +5087% | 24/51 | 0 | 24 | +1.0% | fail |
| 4 h | 30 d | none | -10.71 | 0.51 | -13.25 | -7.43 | 0.60 | -10.06 | -8.87 | +69% / +10988% | 31/51 | 19 | 0 | +2.7% | fail |
| 4 h | 30 d | +40% | -2.81 | 0.77 | -5.33 | -0.84 | 0.92 | -3.38 | -1.82 | +69% / +10988% | 31/51 | 0 | 31 | +1.5% | fail |
| 24 h | 7 d | none | -0.10 | 0.99 | -1.96 | +1.31 | 1.18 | -0.48 | +1.11 | +23% / +1019% | 15/51 | 6 | 0 | +0.8% | fail |
| 24 h | 7 d | +40% | +0.55 | 1.08 | -1.31 | +1.92 | 1.31 | +0.13 | +1.63 | +23% / +1019% | 15/51 | 0 | 15 | +0.7% | PASS |
| 24 h | 14 d | none | -2.52 | 0.79 | -4.72 | -1.00 | 0.91 | -3.11 | -1.61 | +38% / +1019% | 24/51 | 9 | 0 | +1.4% | fail |
| 24 h | 14 d | +40% | -1.43 | 0.85 | -3.64 | -0.13 | 0.99 | -2.23 | -0.70 | +38% / +1019% | 24/51 | 0 | 24 | +1.1% | fail |
| 24 h | 30 d | none | -6.91 | 0.63 | -9.37 | -3.22 | 0.80 | -5.78 | -5.31 | +63% / +2292% | 30/51 | 17 | 0 | +2.7% | fail |
| 24 h | 30 d | +40% | -1.72 | 0.85 | -4.19 | +0.62 | 1.07 | -1.94 | -0.99 | +63% / +2292% | 30/51 | 0 | 30 | +1.6% | fail |
| 72 h | 7 d | none | +1.28 | 1.18 | -0.54 | +2.38 | 1.36 | +0.61 | +1.48 | +19% / +259% | 15/51 | 3 | 0 | +1.0% | PASS |
| 72 h | 7 d | +40% | +1.73 | 1.26 | -0.10 | +2.77 | 1.46 | +1.00 | +2.05 | +19% / +259% | 15/51 | 0 | 15 | +0.8% | PASS |
| 72 h | 14 d | none | -1.04 | 0.91 | -3.29 | +0.41 | 1.04 | -1.78 | -0.92 | +27% / +259% | 20/51 | 8 | 0 | +1.5% | fail |
| 72 h | 14 d | +40% | +1.09 | 1.13 | -1.16 | +2.32 | 1.31 | +0.13 | +1.55 | +27% / +259% | 20/51 | 0 | 20 | +1.2% | PASS |
| 72 h | 30 d | none | -5.36 | 0.69 | -7.80 | -1.95 | 0.88 | -4.44 | -4.00 | +50% / +673% | 28/51 | 16 | 0 | +2.8% | fail |
| 72 h | 30 d | +40% | -0.45 | 0.96 | -2.88 | +1.92 | 1.21 | -0.57 | +0.05 | +50% / +673% | 28/51 | 0 | 28 | +1.7% | fail |

The "net" columns are the sum of per-trade equity returns; +2.77 means 277% of one trade's margin over 51 trades. The full-window MAE is the highest high over the whole intended hold, ignoring the stop.

### Reading the train results

- **Raw vs hedged.** No config passes on raw returns: raw ex-top3 is negative everywhere. The BTC hedge adds about +1 to +3.7 per 51 trades because BTC rose over the train windows. On raw returns the short is mostly crypto beta working *against* it.
- **Best train config:** N = 72 h, H = 7 d, stop +40%. BTC-hedged: n = 51, net +2.77, mean +5.4%/trade, PF 1.46, ex-top3 +1.00, win rate 59%. The SOL/ETH-hedged version nets +2.05.
- **Squeeze risk.** The short squeeze is the dominant risk.
  - In the median trade, price rose 19–69% above entry at some point during the hold. Between 15 and 31 of 51 trades see +40% or more.
  - The worst cases are +259% (HPOS, entering at 72 h), +1,019% (TUT at 24 h) and +5,087% to +10,988% (HPOS at 4 h).
  - Without a stop, 3–19 of 51 trades are liquidated even at 1×.
  - At 2× the +40% stop is the liquidation level. All four train passers then fail ex-top3 (−0.9 to −3.8), and 15–20 trades are liquidated.
- **Funding** is small: +0.7% to +2.8% per trade received on average.
- **Fragility.**
  - Doubling slippage keeps the passers marginal: ex-top3 drops to +0.03 for the 24h/7d and 72h/14d configs.
  - 25 of 51 train trades come from 2024 H2. Removing Oct 2024 – Jan 2025 leaves 29 trades with PF 0.86–1.02 and a negative ex-top3 for every passer.
  - Excluding all 23 coins the round-3 precheck saw, rather than only the 11, leaves 39 trades: hedged PF 1.43–1.56, but n < 50.
- **Contaminated train listings (7)**, for the 72h/7d/+40% config: raw net +1.58, PF 4.9. This confirms the precheck's numbers came from an unusually good set.

## Validation (looked at once, only for the 4 train passers; betas frozen from train)

| config | n | raw net | raw PF | BTC-hedged net | hedged PF | hedged ex-top3 |
|---|---|---|---|---|---|---|
| 24 h / 7 d / +40% | 9 | −0.19 | 0.85 | −0.26 | 0.81 | −1.17 |
| 72 h / 7 d / none | 9 | −1.65 | 0.38 | −1.77 | 0.37 | −2.72 |
| 72 h / 7 d / +40% | 9 | −0.66 | 0.60 | −0.66 | 0.61 | −1.61 |
| 72 h / 14 d / +40% | 9 | −1.11 | 0.46 | −1.12 | 0.46 | −2.04 |

- Validation squeezes:
  - 4USDT went +224% over the full window.
  - MUSDT went +157% and gapped through the stop, losing 48%.
  - BIRB went +87%.
- The 3 contaminated validation listings (PUMP, USELESS, YZY) were all profitable: hedged +0.70 for the 72h/7d configs. The coins the idea came from keep looking good; the others do not.

## Why it failed, and what would be needed

- There are too few meme perp listings. About 51 per 2.5 years train-side and 9 per 9 months validation-side, across two major venues.
- The train edge is one regime: the Q4-2024 meme listing wave that topped out in January 2025. It is not a persistent short-sale-constraint drift.
- The squeeze tail (+200% to +10,000%) makes any leverage above 1× fatal, and an unhedged short is a bet on crypto beta.
- A real test needs pooling of all altcoin listings, or Bybit/OKX meme listings. That would be a different family and would need a fresh train/validation design.
