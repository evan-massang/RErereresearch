# H-LOTTOSHORT: FAIL (train and validation). Beta-hedged meme-basket short vs BTC/SOL, funding-gated, weekly

_Agent: lottoshort, 2026-10-05._

- **Pre-registration:** `reports/hypotheses/lottoshort_preregistration.json`. It was frozen at 12:44 UTC, before any return,
  beta, funding value or P&L was computed. The only data looked at beforehand were weekly counts of eligible memes
  (volume and bar presence only).
- **One amendment, made before any output was seen.** SOLUSDT has archive gaps (2022-02-26..28 and 2022-04-01..02), and
  the first train run crashed on them before printing anything. The fix forward-fills prices across those gaps. It is
  recorded in the pre-registration with the script's sha256.
- **Script:** `scripts/research/lottoshort_sim.py`.
- **Evidence:** `research/observations/evidence_lottoshort_{train,validation,diag_train,diag_validation}_20261005.json`.
- **Legs and weekly parquet:** `data/raw/web/lottoshort/`.
- **Holdout:** nothing from 2026-04-01 onward was read. The price archive used ends 2026-03-31. The 2026-04..09 meme data
  had already been used by the MEMEXS holdout, so it was never a clean test for this idea anyway.

## Verdict

1. **Train fails: none of the 12 configs passes the pre-declared bar.**
   - The bar had to hold on both units: basket-weeks and hedged coin-leg-weeks.
   - The best config, `G1_BTCSOL_EW_b30`, passes on basket-weeks (n 149, net +0.57, PF 1.222, ex-top-3 +0.08).
   - It fails on legs: PF is 1.166, below the 1.2 bar.
   - It also fails the round-13 kill test: max drawdown is −0.69 against a −0.35 limit.
2. **Validation (run once, as the pre-declared labelled diagnostic) fails too.**
   - It traded only 18 of 38 weeks, because the funding gate was off for 20 weeks.
   - Results: net +0.06, legs PF 1.18, and basket-week net ex top-3 −0.045.
3. **There is no meme-specific premium.**
   - **Train:** the same hedged rule applied to the 820 *non-meme* alt perps earned more than the meme version. Meme
     minus alt is **−31 bp a week (t −0.74)**.
   - **Validation:** meme minus alt is **+1 bp a week (t 0.03)**.
   - What train shows is "alts (memes included) lagged BTC/SOL in 2023–25". The SOL leg's 2023 rally is a large part of
     it. This is not a lottery premium.
4. **Most of a naive meme short's profit is the bear market.**
   - On validation, an *unhedged* equal-weight meme short (every week) made **+0.59**, with a BTC beta of −1.51 and
     R² 0.54.
   - Beta-hedged, the same weeks made **−0.04**, with alpha −6 bp a week (t −0.13). Gated, they made **+0.06**.
   - So essentially **all** of the validation profit of shorting memes in 2025-H2..2026-Q1 was market beta.

## Literature leads

Both papers were downloaded, archived and quoted verbatim. All quotes are `quote_verified = true` against the
`pdftotext` snapshots. They are leads in the `document` modality.

| paper | finding | sample | page | observation |
|---|---|---|---|---|
| Grobys & Junttila 2021, *JIFMIM* 71:101289 (JYX copy, src_368c936208b905fb) | "Our results show that average raw and risk-adjusted return differences between cryptocurrencies in the lowest and highest MAX quintiles exceed 1.50% per week. These results are robust after controlling for Bitcoin risk or potential microstructure effects." | "this study employs a set of 20 cryptocurrencies to implement the analysis of the MAX-effect over the January 2016–December 2019 period" (p.2) | p.1 (abstract) | obs_86d3f6acbd074968, obs_5e1c370445e145a1, obs_0e95bbd017324cdf (p.6: "the average predicted return linearly decreases as we move from lowest to highest maximum daily return portfolio"; H−L −1.54%/wk, t −2.68) |
| Ozdamar, Akdeniz & Sensoy 2021, *Financial Innovation* 7:74 (Bilkent copy, src_883de6f0622bb63b) | highest-minus-lowest MAX decile, weekly raw and risk-adjusted: "lowest MAX deciles are 3.03% and 1.99%, respectively"; p.8: "these findings show that portfolios of cryptocurrencies with the highest extreme returns continue to exhibit superior" [performance] | CoinMarketCap coins above $5M market cap; "our sample spans the period from the beginning of January 2014 to the end of September 2020" (p.5); 17 to 523 coins | p.1, p.5, p.8 | obs_b8b06e570c4c4b55, obs_872932a0ac544021, obs_0b438e1856e34339 |
| Ozdamar et al. on the conflict | "Our results contradict with the findings of Grobys and Sapkota (2019), Jia et al. (2020), and Grobys and Junttila (2021)." They attribute the gap to sample size. | | p.3 | obs_ff3bbc36027d4ec0 |

**Notes on these leads:**
- **Page numbers.** Grobys & Junttila page numbers are the printed article pages; the self-archived PDF page is one
  higher. Ozdamar et al. page numbers are "Page x of 27".
- **Lost minus sign.** In the Grobys & Junttila text extraction the minus glyph comes out as U+0001. The sign is read
  from Table 1 (low quintile 1.33, high quintile 0.22).
- **Superseded observations.** Seven first-attempt observations were attached to the PDF snapshots, which have no
  extracted text, so their quote_verified was NULL. They are marked `rejected` and were re-recorded against the text
  snapshots.
- **Neither paper tests what H-LOTTOSHORT trades.** Both are cross-sectional MAX sorts within coins. Neither is a
  sector-versus-BTC short, and neither covers memes or the perp era.

## Rule (frozen)

**Universe.** The H-MEMEXS 74-symbol CoinGecko meme list, today's classification (look-ahead caveats as in memexs).
- Eligibility at each Monday 00:00 UTC: at least 35 bars, a bar for t−1, at least 25 of the last 30 days present, and
  30-day ADV of at least $5M.
- A week is tradable only with at least 3 eligible memes.

**Position.** Short the basket and go long BTC (or BTC/SOL 50/50).
- Hedge ratio β: daily returns over a trailing W days, clipped to [0.25, 3].
- Gross 1: S = 1/(1+β) short and H = β/(1+β) long.

**Gate.** Basket funding F is the mean over basket members of the 7-day funding sum ÷ 21 (a per-8h equivalent).
- G1: trade if F > 0.
- G2: trade if F > 0.01% per 8h.
- When the gate is off, the book is flat.

**Execution and costs.**
- Fill at close(t−1) and hold 7 days.
- Taker fee 5 bp plus an ADV slippage tier (2/5/10/20 bp), per leg per side, charged on weight changes.
- Funding is paid or received on both legs.

**Grid (12).** Gate {G1, G2} × hedge {BTC, BTC/SOL} × {EW β60, inverse-vol β60, EW β30}.

**n.** Validation can have at most 38 basket-weeks, so the 50-basket-week bar is impossible there. It was pre-declared,
before any return was computed, that validation n would count hedged coin-leg-weeks: one meme short leg carrying its
pro-rata share of the hedge. Net, PF and ex-top-3 had to pass on both units.

## Train: all 12 configs (rebalances 2022-02-14 .. 2025-06-23)

| config | basket-weeks | net | PF (weeks) | ex-top-3 (weeks) | legs | PF (legs) | ex-top-3 (legs) | Sharpe | max DD | half-years > 0 | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G1_BTC_EW_b60 | 149 | +0.04 | 1.02 | −0.27 | 1716 | 1.01 | −0.12 | 0.03 | −0.81 | 5/7 | no |
| G1_BTC_IV_b60 | 149 | −0.03 | 0.99 | −0.33 | 1716 | 0.99 | −0.15 | −0.02 | −0.76 | 5/7 | no |
| G1_BTC_EW_b30 | 149 | +0.26 | 1.12 | −0.04 | 1716 | 1.09 | +0.11 | 0.24 | −0.57 | 4/7 | no |
| G1_BTCSOL_EW_b60 | 149 | +0.31 | 1.12 | −0.14 | 1716 | 1.09 | +0.17 | 0.20 | −0.95 | 5/7 | no |
| G1_BTCSOL_IV_b60 | 149 | +0.20 | 1.08 | −0.25 | 1716 | 1.06 | +0.09 | 0.13 | −0.91 | 5/7 | no |
| **G1_BTCSOL_EW_b30** | 149 | **+0.57** | **1.22** | **+0.08** | 1716 | **1.17** | +0.45 | 0.42 | −0.69 | 5/7 | **no (legs PF)** |
| G2_BTC_EW_b60 | 50 | −0.23 | 0.80 | −0.48 | 753 | 0.86 | −0.29 | −0.33 | −0.80 | 3/7 | no |
| G2_BTC_IV_b60 | 50 | −0.29 | 0.75 | −0.54 | 753 | 0.82 | −0.35 | −0.43 | −0.79 | 3/7 | no |
| G2_BTC_EW_b30 | 50 | +0.02 | 1.03 | −0.24 | 753 | 1.02 | −0.04 | 0.05 | −0.56 | 3/7 | no |
| G2_BTCSOL_EW_b60 | 50 | −0.18 | 0.88 | −0.63 | 753 | 0.91 | −0.26 | −0.22 | −0.98 | 3/7 | no |
| G2_BTCSOL_IV_b60 | 50 | −0.26 | 0.82 | −0.71 | 753 | 0.86 | −0.36 | −0.33 | −0.95 | 3/7 | no |
| G2_BTCSOL_EW_b30 | 50 | +0.13 | 1.10 | −0.37 | 753 | 1.08 | +0.03 | 0.19 | −0.74 | 3/7 | no |

**How to read the table.**
- Net is the additive sum of fractions of gross capital 1.
- Of the 182 possible weeks, 5 had fewer than 3 eligible memes, and the G1 gate was off in 28 more.
- In 2022–23 the basket was 3–5 coins: DOGE, 1000SHIB and PEOPLE, then 1000PEPE, 1000FLOKI, MEME and ORDI.

**What the train results show.**
- **Every config loses heavily in 2024-H1,** the meme mania (−0.56 for the selected config).
- **The stricter gate (G2) is uniformly worse.** Crowded-funding weeks are when memes keep squeezing, the opposite of
  "we are paid to hold".
- **The selected config's P&L split:**
  - the meme short leg made −0.64 in price;
  - the BTC/SOL long leg made +1.13;
  - funding received was +0.13;
  - costs were 0.05.
- **The profit is the hedge outrunning a smaller β-scaled meme short.** Mean β was 1.14, so the short notional was
  about 0.49. With BTC-only hedges the best config makes +0.26 with PF 1.12.

## Selected config by split

| | train | validation (run once, diagnostic) |
|---|---|---|
| basket-weeks traded / possible | 149 / 182 | **18 / 38** (gate off for 20 weeks; funding negative after 2026-02-09) |
| hedged coin-leg-weeks | 1716 | 916 |
| net | +0.571 | +0.060 |
| PF weeks / legs | 1.222 / 1.166 | 1.413 / **1.180** |
| net ex top-3 weeks / legs | +0.079 / +0.448 | **−0.045** / +0.044 |
| mean per basket-week | +38 bp | +33 bp |
| weekly Sharpe (×√52) | 0.42 | 0.89 |
| max drawdown (additive) | **−0.69** | −0.12 |
| mean basket size / β / short notional | 11.5 / 1.14 / 0.49 | 50.9 / 1.64 / 0.38 |
| meme-leg price / hedge-leg price / funding received / costs | −0.64 / +1.13 / +0.13 / 0.05 | +0.19 / −0.12 / +0.003 / 0.01 |
| by half-year | 22H1 +0.06, 22H2 −0.25, 23H1 +0.35, 23H2 +0.45, 24H1 −0.56, 24H2 +0.25, 25H1 +0.26 | 25H2 +0.12, 26H1 −0.06 |
| best coins (pro-rata hedge included) | PEOPLE +0.16, 1000SHIB +0.16, MEME +0.11 | NEIROETH, FARTCOIN, GRIFFAIN (each ≤ +0.01) |
| worst coins | WIF −0.15, 1000PEPE −0.09, 1000FLOKI −0.05 | PIPPIN −0.02, VINE −0.01, USELESS −0.01 |

## Beta-neutrality and the bear market (diagnostics, not used for selection)

OLS of weekly P&L on the same week's BTC return, and on the hedge-basket return:

| series | split | n weeks | β to BTC (t) | β to hedge (t) | alpha, bp a week (t) | R² (BTC) |
|---|---|---|---|---|---|---|
| selected (G1) | train | 149 | −0.22 (−2.85) | −0.02 (−0.28) | +57 (1.08) | 0.05 |
| hedged, always on (G0) | train | 177 | −0.18 (−2.71) | −0.02 (−0.44) | +24 (0.52) | 0.04 |
| unhedged EW meme short (G0) | train | 177 | −1.71 (−11.3) | −1.11 | +22 (0.20) | 0.42 |
| selected (G1) | validation | 18 | +0.12 (1.04) | +0.11 (1.23) | +50 (0.76) | 0.06 |
| hedged, always on (G0) | validation | 38 | +0.04 (0.49) | +0.06 (0.80) | −6 (−0.13) | 0.01 |
| unhedged EW meme short (G0) | validation | 38 | −1.51 (−6.5) | −1.29 | −24 (−0.19) | 0.54 |

**The hedge works.** It is neutral to its own hedge basket, with a residual BTC β of about −0.2 on train coming from
the SOL half.

**The bear market's share.** Shorting memes unhedged in validation earned **+0.59** (PF 1.43), which looks good.
Hedging removes all of it: **−0.04** always-on and **+0.06** gated, with alpha t-statistics around zero. On train,
unhedged shorting lost −2.14, mostly to the 2024 meme mania (−2.41 in 2024).

**Placebo: the same hedged rule on all eligible non-meme USDT-M alts.** The 820-symbol alt universe excludes BTC, ETH,
SOL, BTCDOM, DEFI and stablecoins.

| | train meme / alt (G0) | validation meme / alt (G0) | meme − alt, bp a week (t) |
|---|---|---|---|
| net | +0.17 / **+0.68** | −0.04 / −0.05 | train −31 (−0.74); validation +1 (0.03) |

- With the same config and its own gate, the alt placebo made +0.44 on train (PF 1.34) and +0.05 in 5 validation weeks.
- Memes are not special. Any small-cap alt basket lagged BTC/SOL in 2023–25 by about as much.

## Other diagnostics, selected config

| variant | train net / PF weeks / ex-top-3 weeks | validation net / PF weeks / ex-top-3 weeks |
|---|---|---|
| G0 (gate removed) | +0.17 / 1.05 / −0.33 | −0.04 / 0.90 / −0.16 |
| slippage ×2 | +0.54 / 1.21 / +0.05 | +0.05 / 1.35 / −0.05 |
| funding excluded | +0.44 / 1.16 / −0.05 | +0.06 / 1.39 / −0.05 |
| identity-doubtful coins excluded | +0.32 / 1.17 / −0.17 (92 weeks; 2022 drops to < 3 memes) | +0.08 / 1.48 / −0.03 (20 weeks) |

The G1 gate adds about +0.40 on train, through funding and by skipping weeks of negative funding. On validation it
skips the 2026-Q1 weeks, when the hedged short would have done nothing. That is not robust evidence.

## Reading

- **The lottery-premium story is not supported at the meme-sector level against BTC.** Hedged, the sector short has
  about zero alpha.
- **Its train profit depends on two things:**
  - the hedge leg (SOL's 2023 run);
  - the 2023 period, when the basket held 3–5 coins dominated by DOGE, SHIB and PEOPLE.
- **The funding "paid to hold" component is modest:** +0.13 over 149 weeks, about 9 bp a week at gross 1.
- **The 2024 mania drawdown (−0.56 in one half-year) would be unbearable at 1× gross.**
- This matches the UNLOCK and MEMEXS lessons. Shorting memes in 2025-26 looks good only because the market fell. Within
  or across memes, after beta, there is no edge at weekly horizons.

## Not done / limits

- **No forward paper test was set up.** No config passed train, so there is nothing frozen to forward-test.
- **Weights drift within the week and are not modelled.** Costs are charged on target-weight changes, as in memexs.
- **The classification is today's CoinGecko list,** so the survivorship and look-ahead caveats from memexs apply.
- **Downloads:** 2.9 MB of papers only, in `data/raw/web/lottoshort/papers/`. Prices are read-only from the momentum
  cache.
