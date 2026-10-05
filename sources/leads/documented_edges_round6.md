# Documented edges, round 6: high-turnover ideas that can reach 50 forward trades in 1–3 days

_Compiled 2026-10-05 by a research agent using web search, web fetch and read-only checks of public endpoints.
Everything taken from the web is a **lead** (`document` modality). It is not a trader's statement and not a validated
finding. Numbers are copied from the cited source unless marked **OWN-PRECHECK**. No backtest was run for this file._

Labels follow rounds 1–5:
- **DATA**: peer-reviewed, or a preprint with stated data and method;
- **DATA-weak**: single author, practitioner, frictionless, or abstract-only;
- **ANECDOTAL**;
- **MARKETING**.

**The OWN-PRECHECKs are feature-only.** They count how often an entry condition could fire, from one public snapshot.
They compute no price path, P&L or exit outcome. Raw pre-check files sit in the session scratchpad only, not in the repo.

---

## 0. Why this round looks where it does

The bar is at least 50 **forward** paper trades on data recorded after freezing, net profit after all costs, PF > 1.2,
and still profitable without the top 3 trades. Rounds 1–5 and the iteration log (`reports/failures/paper_loop_20261003.md`,
`reports/failures/agent_*.md`, `reports/candidates/hlanchor.md`) rule out a lot:

| Already tested or dropped | Families |
|---|---|
| pump.fun curve and PumpSwap (all of it) | heat, dev, sniper, KOL/copy, ML snapshots, BOOST, CTO, DEX-paid, fee claims, sympathy, crash bounce, LP, round USD levels, clock, Mayhem, viewers, narratives |
| HL vs Binance at seconds | HLANCHOR (fails on adverse selection), HLLAG (fragile near-pass, now in forward test) |
| Perp carry and basis | FUNDCARRY, FFDIFF(-WIDE), DATEDBASIS, SPOTCARRY-WIDE, PREMCONV, LSTCARRY, CARRYBOOK |
| Perp directional | FLUSH(-MW) (OI and price flushes), XLEAD (minute lead-lag from BTC/SOL/meme index), LISTSHORT, MOMENTUM (weekly), SOLLEAD, FUNDCLOCK (dropped) |

What has been learned:
1. Costs must be perp-level (HL 1.5/4.5 bp, Binance 2/5 bp), never curve or DEX.
2. Carry ideas fail on n: they trade a few times a month, so 50 forward trades take months.
3. Seconds-scale maker quoting is adverse-selected (HLANCHOR markout −2.5 to −4.4 bp at 30 s).
4. Minute-scale lead-lag is real but a few bp, below taker cost (XLEAD).

So this round looks for signals that fire **tens to hundreds of times a day** and have a **gross edge per trade that is
plausibly a multiple of 10–30 bp**. Two of the ideas use a data stream no earlier round used: **Hyperliquid's public,
protocol-native TWAP orders**, whose terms are visible from the moment they are placed.

### Costs used throughout (official schedules, as cited in rounds 4–5)

| Venue / action | Per side | Source |
|---|---|---|
| HL perps, tier 0 | taker 4.5 bp, maker 1.5 bp | [HL fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees) |
| Binance USDⓈ-M, VIP0 | taker 5 bp, maker 2 bp | [Binance FAQ 360033544231](https://www.binance.com/en/support/articles/360033544231) |
| Slippage | Pre-registered by liquidity tier: 2 bp (BTC, ETH, SOL, HYPE), 3 bp (top 11–50 by volume), 5 bp (rank 51–150). Plus a full spread when size exceeds the displayed top. | round-4 OWN-PRECHECK spreads 2–6 bp |
| Latency | ≥ 300 ms from our receipt of the triggering print to our order resting or arriving | brief |
| Funding | Actual prints for every hold that crosses a settlement | HL hourly, Binance 8 h archives |

### Public no-key data checked from this container (2026-10-05)

- **Hypurrscan TWAP feed: `GET https://api.hypurrscan.io/twap/*` returns 200.** It is a third-party explorer, so treat it as a lead source.
  - One call returned 513 `twapOrder` actions covering 2026-10-04 06:11 to 2026-10-05 05:39 UTC (23.5 h).
  - Each record has user, asset index `a`, side `b`, size `s`, minutes `m`, reduce-only `r`, randomize `t`, block and tx hash.
  - 338 were on perps (asset index < 10,000); 36 of those were reduce-only.
- **HL `info` (POST, no key):**
  - `twapHistory` for any user returns each TWAP's state: coin, side, size, `executedSz`, `executedNtl`, minutes, `twapId`, and status (`activated`, and later finished or terminated).
  - `userTwapSliceFills` returns the slice fills (`crossed: true`, so slices are taker). Both checked on the address `0x8ca58d…e310`.
  - `twapId` rose from 2,281,685 to 2,283,152 in about 19 h, roughly 1,850 a day *if* ids count only TWAPs. So the Hypurrscan feed may cover only about 25–30% of TWAPs. **Measuring the feed's coverage is pre-check 0 for ideas 1–2.**
- **HL explorer websocket** (`wss://rpc.hyperliquid.xyz/ws`, `explorerTxs`): it connects, but in 25 s it delivered only about 340 transactions, none of them TWAPs. That looks like a sample, not a full stream, so it was not used.
- **data.binance.vision:**
  - `futures/um/daily/metrics` (5-min OI, `count_toptrader_long_short_ratio`, `sum_toptrader_long_short_ratio`, `count_long_short_ratio`, `sum_taker_long_short_vol_ratio`), checked on WIFUSDT 2025-03-01;
  - `bookDepth` (200);
  - 1m klines (already used by xlead and premconv).
- **Binance `fapi` REST returns 451**, including `futures/data/globalLongShortAccountRatio`. A plain-Python websocket to `fstream.binance.com` timed out from this shell. `scripts/research/hllag_forward.py` connects with the proxy CA bundle (`_ssl()`), so use that pattern for forward recording.

**Forward protocol for every idea.** Freeze `reports/hypotheses/<id>_preregistration.json`, holding the rule, grid, costs
and fill model, **before** the first forward record is written. Score the frozen grid on forward data only. Where history
exists, run train and validation first under the perp calendar (train ≤ 2025-06-30, validation 2025-07-01 to 2026-03-31,
holdout ≥ 2026-04-01 untouched; keep 2026-08 and 2026-09-01 out). **Report by day and by coin** as well as by trade,
because correlated trades on one day can pass the top-3 rule while being one bet.

---

## 1. Ideas (ranked in §2)

### Idea 1. Ride visible HL TWAP flow while it executes (H-TWAPRIDE)

**Mechanism.** HL TWAPs are executed by validators. Slices go out at a fixed interval (minimum 30 s), each with up to 3%
slippage, and missed size "catches up" in later slices of up to 3× normal size
([HL order types](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/order-types), lead). Direction, total size and
horizon are public from the placement transaction. So a known taker is going to keep buying (or selling) at a known rate
for a known time, and its price impact builds during execution. Entering in the TWAP's direction right after it appears,
and exiting before or at completion, captures part of that impact.

This is not MEV or sandwiching: we place no transaction around anyone's transaction, and we trade on public order
terms over minutes to hours. But it is "trading ahead of a disclosed order", which Brunnermeier and Pedersen (2005) call
predatory trading in a stress context. **Flag it for the owner's ethics and legal review before any live use.**

**Evidence.**
- **Barone and Lillo, "Trading in the Sunshine or in the Shade: Market Impact and Adverse Selection on Hyperliquid"** (arXiv
  2606.15715, June 2026). DATA, preprint. [arXiv](https://arxiv.org/abs/2606.15715), [HTML](https://arxiv.org/html/2606.15715).
  - Their data are HL perps, 2025-07-28 to 2026-03-23: about 641M fills, 465,000 visible TWAP executions and 4.3M reconstructed hidden metaorders.
  - TWAPs "trade nearly uniformly".
  - The native-TWAP price trajectory follows a "smooth, concave square-root-like profile" that rises during execution and then gradually decays (fetched-page summary, not a verbatim quote).
  - **Against the idea:** visible TWAPs have lower impact than hidden metaorders (about 8.9 bp lower temporary impact in order-level regressions; about 55 bp less post-execution displacement on common support). Also, "displayed depth rises and the book tilts toward the absorbing side" while they run. **Sunshine invites liquidity, and that is exactly what can kill this idea.**
- Square-root impact during metaorder execution is a robust stylised fact (the general literature; not re-cited here). The HL-specific magnitude for TWAPs is the open question.
- Whale-TWAP news items (e.g. [altfins](https://altfins.com/crypto-news/crypto-news-summary/350715), [cryptorank](https://cryptorank.io/news/feed/d882c-whale-sells-hype-hyperliquid)) are ANECDOTAL.

**Data.** Forward only.
- **Signal:** poll Hypurrscan `/twap/*` every 5 s, and log first-seen time, block time and the full record.
- **Status:** confirm with HL `twapHistory` (user) every 60 s. Capture `executedSz` progress, termination and cancellation.
- **Prices:** HL websocket `l2Book` and `trades` for every coin with an active qualifying TWAP. The repo's `hllag_forward.py` already records HL `bbo` and `trades`.
- Historical backfill is not available without the requester-pays HL S3 archive (excluded), so this is **forward-test-only**. Train on the first recorded days if needed, freeze, then score the frozen rule on later days.

**Pre-registerable rule.**
- **Qualifying TWAP:** a perp, not reduce-only, with no trigger price, at least 30 min to run, and first seen within 60 s of its block time.
- **Participation** p = (size × mark at first sight / minutes) ÷ (coin's trailing 24-h HL notional / 1,440), all from data
  before first sight.
- **Entry:** taker in the TWAP direction at first sight + 300 ms, filled at the HL book walked for our size.
- **Size:** $1k, at most one position per coin; if same-direction TWAPs overlap, the first one counts.
- **Exit:** taker at the earlier of: H after entry; the TWAP's terminated or cancelled status seen; or a stop at −S.
- **Grid (12):** p ≥ {0.25%, 1%} × H ∈ {15 min, 60 min, TWAP end capped at 6 h} × S ∈ {none, 1.5%}.
- **Trade unit:** one round trip.

**Expected trades/day.** OWN-PRECHECK on the one 23.5 h snapshot, using *current* mark and 24 h volume, not point in time:
- 54 perp TWAPs had p ≥ 0.25% (14–26 at p ≥ 1%, depending on duration filter);
- 45 of the 54 ran ≤ 24 h.

If the Hypurrscan feed is complete for large TWAPs, **about 30–55 a day at 0.25%** and 15–25 at 1%. That is **50 trades in 1–3 days.** If the feed undercounts (see §0), more.

**Costs.** HL taker in and out is 9 bp + about 2–4 bp spread + slippage, so **about 12–16 bp per round trip** on liquid coins (HYPE, BTC, ETH, PUMP, SOL), more on thin ones. Funding is charged on holds that cross the hour.

**Main kill risk.**
- **The sunshine effect itself.** Barone and Lillo find visible TWAPs draw liquidity onto the absorbing side and have low impact, so the drift over our hold may be below 15 bp.
- **Feed lag.** If Hypurrscan shows a TWAP minutes after placement, the early, steepest part of the concave impact is gone. Log `first_seen − block_time` and pre-register a 60 s cutoff.
- **Overlapping TWAPs** on the same coin (e.g. HYPE had 59 in one day) make trades correlated, so report by coin-day.

---

### Idea 2. Fade the post-completion decay of large TWAPs (H-TWAPFADE)

**Mechanism.** Barone and Lillo describe TWAP impact as rising during execution and then *gradually decaying* after
completion: the transient part of the impact reverts. A TWAP's completion time is known at placement (start + minutes),
unless it is cancelled. So a reversal trade can be entered at a pre-known time, which allows a **maker** entry posted
shortly before completion. That halves the fee disadvantage that hurt HLLAG.

This is the same data stream as idea 1, but the opposite and independent side of the impact curve. Idea 1 bets on the
build-up, idea 2 on the decay. Their joint result tells us whether the stream has any tradeable shape.

**Evidence.**
- Barone and Lillo, as above (DATA, preprint). Their reported pattern is that native-TWAP trajectories rise during execution and then "gradually decay" (fetched-page summary).
- Transient versus permanent impact decomposition is standard in metaorder studies; the general literature is not re-cited.
- **Against it:** their finding that TWAPs leave about 55 bp *less* post-execution displacement than hidden metaorders means there may be little left to revert.

**Data.** Same recorder as idea 1. Completion is confirmed by `twapHistory` status, with `executedSz` ≥ 90% of size.

**Pre-registerable rule.**
- **Qualifying TWAP:** idea 1's filters, a duration of 30 min to 24 h, and `executedSz/size` ≥ 0.9 at completion.
- **Signal:** the impact proxy is the coin's return from first sight to completion − 1 min, measured on HL mid. Trade only if it is ≥ m in the TWAP direction.
- **Entry:**
  - **Maker:** post-only at the touch, against the TWAP direction, from completion − 1 min. It fills only on a print strictly through our price (trade-through, as in HLANCHOR).
  - **Taker:** cross at completion + 300 ms.
- **Exit:** taker after H; no stop beyond a 3% disaster stop.
- **Grid (12):** m ∈ {0, 0.5%} × entry ∈ {maker, taker} × H ∈ {30 min, 2 h, 6 h}.

**Expected trades/day.** Completions should match starts in a steady state. With 21–45 TWAPs/day lasting ≤ 6–24 h at p ≥ 0.25%, there are **about 20–45 a day before the m filter**, and the m = 0.5% arm perhaps a third of that. Maker non-fills reduce n further. Expect 50 trades in 2–3 days for m = 0, longer for m = 0.5%.

**Costs.**
- Maker in and taker out is 6 bp + half-spread + adverse selection on the maker fill, so about 8–12 bp.
- Taker/taker is 12–16 bp.

**Main kill risk.**
- The decay may be slow or small next to normal coin volatility, so the reversal is noise.
- Maker fills on the trade-through rule happen exactly when price keeps going in the TWAP direction (the HLANCHOR lesson).
- Cancelled TWAPs are excluded by rule, but a cancellation seen late would leak into the sample. Log status latency.

---

### Idea 3. High-frequency cointegrated pairs on liquid perps (H-PAIRS)

**Mechanism.** Crypto coins share large common factors (BTC, sector). Over minutes, idiosyncratic order flow pushes a
pair's spread away from its short-run equilibrium, and liquidity provision pulls it back. A pair is market-neutral, so
it avoids XLEAD's need to predict direction and FLUSH's knife risk. It fires many times a day across a universe of pairs.

**Evidence.**
- **Fil and Kristoufek (2020), "Pairs trading in cryptocurrency markets"**, IEEE Access 8, 172644–172651. DATA.
  - Distance and cointegration methods on 26 Binance coins at 5-min, 1-h and daily frequency.
  - Abstract (via [STARFOS](https://starfos.tacr.cz/vysledky-vyzkumu/RIV%2F00216208%3A11230%2F20%3A10416379)): "11.61% monthly at 5-minute intervals versus -0.07% for daily", which the tool paraphrased rather than quoted.
  - A search snippet adds that results are "quite sensitive to … transaction costs or execution windows".
- **Tadi and Kortchemski (2021)**, Studies in Economics and Finance (Emerald, [IDEAS](https://ideas.repec.org/a/eme/sefpps/sef-12-2020-0497.html), [arXiv 2109.10662](https://arxiv.org/abs/2109.10662v1)). DATA.
  - BitMEX minute data, 2018-09-27 to 2019-10-02. Entry at |z| = 2, exit at |z| = 1. The OU half-life sets the look-back window.
  - Fill rule: "best bid/ask quotes and market trades … with one or more period gaps after signal generation".
  - Scenario 2: monthly 13.9–17.3%, Sharpe 7.94, about 2,000 trades in 39 weeks.
  - **Caveat:** BitMEX paid a −2.5 bp maker *rebate*, and "commission profits comprised 26%–35%" of gains. We pay +1.5 to +2 bp maker, so their numbers overstate ours.
- **Tadi and Witzany (2023)**, copula pairs ([arXiv 2305.06961](https://arxiv.org/abs/2305.06961)). DATA, preprint.
  - Binance hourly, 20 coins, 2021-01 to 2023-01, taker fees of 4 bp.
  - 176 transactions in 2 years, 37.1% a year, with costs 11.7% of gross.
  - Shows the hourly version is too slow for our n.
- Avellaneda and Lee (2010) PCA-residual stat-arb on US equities (Sharpe 1.44 after costs, 1997–2007; [PDF](https://www.math.nyu.edu/faculty/avellane/AvellanedaLeeStatArb20090616.pdf)) is the template for a residual variant. It is not crypto evidence.

**Data.**
- **History:** data.binance.vision USDⓈ-M 1m klines. They are already cached for 22 memes by xlead, and the archive covers every symbol.
- **Forward:** Binance futures websocket `kline_1m` and `bookTicker`, via the `hllag_forward.py` pattern.
- **Execution venue for the paper test:** Binance USDⓈ-M, or HL for coins listed on both. Pre-register one: **HL**, because Binance trading is jurisdiction-blocked from here.

**Pre-registerable rule.**
- **Universe:** each Monday 00:00 UTC, the top 40 Binance USDⓈ-M perps by the prior 30-day quote volume, also listed on HL, with stablecoins excluded.
- **Pair selection:** on the prior 21 days of log prices at frequency f:
  - Engle–Granger p < 0.05 in both orderings (take the smaller p);
  - OU half-life between 10 bars and 1 day;
  - at most 3 pairs per coin;
  - keep the 30 pairs with the lowest p.

  The hedge ratio is frozen for the week.
- **Signal:** z = (spread − rolling mean) / rolling sd, with the window = 2 × half-life (Tadi–Kortchemski heuristic).
- **Entry:** |z| ≥ z_in.
- **Exit:**
  - |z| ≤ 0.5;
  - stop at |z| ≥ z_in + 2;
  - time stop at 4 × half-life;
  - Monday re-selection closes everything.
- **Execution:**
  - (a) taker both legs at the next bar's open + 300 ms; or
  - (b) maker entry: post-only at the touch on both legs for one bar, filled only by a strict trade-through (else cancel and do not trade), with taker exit.
- **Grid (12):** f ∈ {1m, 5m} × z_in ∈ {2.0, 2.5, 3.0} × execution ∈ {taker, maker-entry}.
- **Trade unit:** one pair round trip, counted as 1 trade (both legs costed).

**Expected trades/day.** Tadi–Kortchemski got about 7/day on BitMEX's few contracts. With 30 pairs at 5-min, a guess is **20–80 a day** (more at 1m and z = 2). A pre-check should count |z| crossings on one train month before any P&L.

**Costs.**
- Taker: 4 leg-sides × 4.5 bp (HL) + slippage 2–3 bp × 4 ≈ **26–30 bp per pair round trip.**
- Maker entry, taker exit: 2 × 1.5 + 2 × 4.5 = 12 bp + exit slippage, so about **16–18 bp.**

**Main kill risk.**
- **Costs versus spread amplitude.** A 5-min z = 2 spread move between two liquid perps may be only 20–40 bp, and the published results relied on rebates or ignored latency.
- **Cointegration breaks** (listings, unlocks, delistings) produce the top-3 losers.
- **Overlap with XLEAD's finding** that minute-scale structure is a few bp: the difference is that pairs bet on mean reversion of a spread, not on a cross-asset lead.

---

### Idea 4. Intraday cross-sectional residual reversal, split by liquidity (H-XSREV)

**Mechanism.** In crypto, the last period's losers beat its winners, and the reversal is compensation for providing
liquidity in thinner coins. The most liquid coins show momentum instead. Going long the coins that dropped most
*relative to their BTC beta* over the last 1–4 h, and short those that rose most, is liquidity provision across many
coins at once. At hourly rebalancing it generates hundreds of position round trips a day.

**Evidence.**
- **Zaremba, Bilgin, Long, Mercik and Szczygielski (2021)**, "Up or down? Short-term reversal, momentum, and liquidity
  effects in cryptocurrency markets", IRFA 78, 101908 ([IDEAS](https://ideas.repec.org/a/eee/finana/v78y2021ics1057521921002349.html)). DATA.
  - Over 3,600 coins, daily: coins with low last-day return outperform.
  - "The handful of largest and most tradeable coins exhibit daily momentum rather than a reversal" (search snippet of the abstract).
- **Kozlowski, Puleo and Zhou (2020)**, "Cryptocurrency return reversals", Applied Economics Letters ([Fairfield](https://fairfield.elsevierpure.com/en/publications/cryptocurrency-return-reversals/)). DATA.
  - 200 coins, 2015–19: reversal at daily, weekly and monthly frequency, "most pronounced among smaller capitalization and less liquid cryptocurrencies".
- **Wen, Bouri, Xu and Zhao (2022)**, "Intraday return predictability in the cryptocurrency markets: Momentum, reversal, or both", NAJEF 62 ([IDEAS](https://ideas.repec.org/a/eee/ecofin/v62y2022ics1062940822000833.html)). DATA.
  - It finds intraday momentum *and* reversal, and attributes the reversal to "investors' overreaction to non-fundamental information".
- A search snippet claims "a long-short portfolio formed on past returns … 2.16% daily out-of-sample after transaction costs". **The source was not identified, so ignore the number.**
- **Distinct from H-MOMENTUM** (weekly, top 40, momentum) and **XLEAD** (minute, time-series lead from leaders). This is cross-sectional, 1–4 h, residual, and bets on the reversal in the less liquid tier.

**Data.**
- **History:** data.binance.vision USDⓈ-M 1m klines aggregated to 1h, plus `fundingRate`, for every symbol (delisted included) from 2023-01.
- **Forward:** Binance futures websocket `kline_1m` for the universe.
- **Execution venue:** HL for coins listed there (174/178 overlap per round 5); otherwise skip the coin.

**Pre-registerable rule.**
- **Universe:** each day, rank Binance USDⓈ-M perps by the prior 30-day volume.
  - U_A = ranks 11–50, U_B = ranks 51–150.
  - Coins must also be HL-listed and have ≥ 60 days of history.
- **Beta:** each coin's beta to BTC from the trailing 30 days of hourly returns.
- **Signal:** residual return over the last L hours, e = r_i − β_i × r_BTC, from bars closed before t.
- **Portfolio:** at each rebalance (every H hours, on the hour), long the 5 lowest e and short the 5 highest e.
  - Equal $ per leg.
  - Taker at the next minute's open + 300 ms.
  - Hold H, then close or roll. A leg kept in the same bucket is not re-traded.
  - 15% per-leg disaster stop.
- **Grid (8):** L ∈ {1 h, 4 h} × H ∈ {1 h, 4 h} × universe ∈ {U_A, U_B}.
- **Trade unit:** one coin-leg round trip. Also report per rebalance basket.

**Expected trades/day.** At H = 1h with 10 legs and about 50–70% turnover, **about 120–170 leg trades a day**; at H = 4h, about 30–40. 50 trades take under a day, though the effective n is the number of baskets (6–24 a day).

**Costs.**
- HL taker 9 bp + slippage 2 × 3 bp (U_A) or 2 × 5 bp (U_B) = **15–19 bp per leg round trip,** plus funding.
- A maker-entry variant is deliberately left out of the grid to keep it ≤ 12. Add it only as a stated follow-up after a train result.

**Main kill risk.**
- **The documented reversal is daily, and in illiquid coins.** At 1–4 h in the HL-listed set, the effect may be smaller than 15–19 bp, or it may be momentum (Zaremba's liquid-coin finding).
- **Short squeezes** in U_B, the listshort tail, are the top-3 losers. The 15% stop is the pre-registered guard.

---

### Idea 5. Queue-imbalance-gated passive quoting on HL's own book (H-QIMAKER)

**Mechanism.** HLANCHOR quoted both sides around a Binance-implied fair value and was picked off: fills arrived just
before Binance moved through the quote. Microstructure evidence says the *own-book* queue imbalance at the touch predicts
the next mid move, especially on large-tick books where the spread is usually one tick. Resting **only** on the side that
the imbalance favours (bid when the bid queue is much larger than the ask queue) means our fills come mostly from
uninformed flow hitting a queue that is unlikely to be depleted. Exiting passively on the other side captures the
spread at maker fees.

**Evidence.**
- **Gould and Bonart (2016)**, "Queue imbalance as a one-tick-ahead price predictor in a limit order book" ([arXiv 1512.03492](https://arxiv.org/abs/1512.03492)). DATA.
  - Nasdaq, 10 stocks: "strongly statistically significant relationship" between queue imbalance and the next mid move.
  - "Considerable improvement … for large-tick stocks, and a moderate improvement for small-tick stocks".
- **Cartea, Donnelly and Jaimungal (2018)**, "Enhancing trading strategies with order book signals", Applied Mathematical Finance 25(1) ([IDEAS](https://ideas.repec.org/a/taf/apmtfi/v25y2018i1p1-35.html)). DATA.
  - The volume imbalance predicts the sign of the next market order.
  - Out of sample (Jul–Dec 2014), using it "considerably boosts strategy profits … because employing the imbalance measure reduces adverse selection costs".
- **Zhai et al., arXiv 2608.04373** (round 4 H-TOXFILTER, not re-tested): HL wallet toxicity persists (rank correlation 0.52 across 10-day windows). This is the complementary overlay. Not part of this grid.
- **Against:**
  - [Jeon, arXiv 2607.09230](https://arxiv.org/abs/2607.09230) finds order flow adds little beyond liquidity state for Binance BTC/ETH, though for a different target.
  - Our own HLANCHOR markouts.

**Data.**
- **History:** Tardis free first-of-month HL `incremental_book_L2` + `trades` (≈ 24 days since 2024-10-29). Same train/validation day split as HLANCHOR.
- **Forward:** HL websocket `l2Book` (20 levels) + `trades` for the chosen coins.
- **Coins:** pre-registered as the HL perps whose median spread is exactly 1 tick on ≥ 70% of 1-s samples on the first train day. That is a large-tick criterion, decided from spreads only.

**Pre-registerable rule.**
- **Imbalance:** I = (Q_bid1 − Q_ask1)/(Q_bid1 + Q_ask1) from the latest book snapshot received.
- **Quote:** when I ≥ θ (or ≤ −θ), post-only bid (ask) at the touch for $1k after 300 ms. Cancel when |I| < θ/2 or on the opposite sign, with a 300 ms cancel latency during which we can still be hit.
- **Fill:** only on a print strictly through our price (conservative; queue position unknown).
- **Exit:** post-only at the opposite touch; if not filled within T, exit taker.
- **Inventory:** one unit per coin; flatten at day end.
- **Grid (8):** θ ∈ {0.5, 0.8} × T ∈ {5 s, 30 s} × coin set ∈ {top-2 large-tick by volume, all large-tick}.

**Expected trades/day.** On HL's liquid large-tick books, θ = 0.5 should trigger thousands of quote events, and the trade-through fill rule cuts that to perhaps **tens to hundreds of round trips a day.** The first train day gives the count.

**Costs.**
- Maker/maker: 3 bp minus the spread captured (1 tick).
- Maker in, taker out: 6 bp + half-spread.

**Main kill risk.**
- **The fill model.** With trade-through-only fills we are always last in queue, so filled orders are by construction the ones the market ran through. That is the adverse selection the signal is meant to avoid. A paper test cannot know queue position, so a pass under this conservative model is meaningful, but a fail does not refute the equity-market evidence.
- **The edge may need sub-100 ms reaction** that we do not have.

---

### Idea 6. Retail-positioning contrarian, cross-sectional, from Binance account ratios (H-LSRATIO)

**Mechanism.** Binance publishes, every 5 min per perp, the long/short ratio by *account count* (crowd) and by *top-trader
position* (large accounts), plus the taker buy/sell volume ratio. When the crowd piles into one side faster than large
accounts, retail is crowding, and the crowded side tends to unwind (funding pressure, liquidations). Sorting the
cross-section by crowd-versus-top-trader divergence gives a market-neutral book that rebalances often.

**Evidence. Weaker than ideas 1–5, so it is ranked lower.**
- **Dunbar and Owusu-Amoako (2023)**, "Predictability of crypto returns: The impact of trading behavior" ([repository page](https://digitalcommons.uncfsu.edu/college_business_economics/314)). DATA-weak: abstract only, and the data source is not stated.
  - "Cryptocurrency returns are driven and predicted by the trading behavior of speculative retail traders".
  - "Net-short trading behavior of speculative retail traders is an economically strong and statistically significant determinant".
- Practitioner pages claim crowd ratios above about 3 precede corrections, and that top-trader ratios are more predictive ([sharpe.ai](https://www.sharpe.ai/futures/long-short-ratio), [Amberdata docs](https://docs.amberdata.io/data-dictionary/market/longshort-ratio)). MARKETING/ANECDOTAL. **No peer-reviewed backtest on these Binance ratios was found.**

**Data.**
- **History:** data.binance.vision `futures/um/daily/metrics/<SYM>` (5-min, columns listed in §0), every USDⓈ-M symbol.
- **Forward:** the live REST endpoint is 451 from here, so forward scoring uses the **daily archive published after the freeze date**. Decisions at t use only rows with `create_time` ≤ t − 5 min.
  - That is a legitimate forward out-of-sample test, but it is scored a day late and cannot measure live latency.
  - Execution prices come from 1m klines, with fills at the next minute open + slippage.

**Pre-registerable rule.**
- **Universe:** Binance USDⓈ-M ranks 11–100 by 30-day volume that are also HL-listed.
- **Divergence:** D = z(Δ24h log `count_long_short_ratio`) − z(Δ24h log `sum_toptrader_long_short_ratio`). The z-scores are cross-sectional at t.
- **Portfolio:** every H hours, short the top-k D (crowd getting long while big accounts are not) and long the bottom-k.
  - Taker on HL.
  - Hold H, with a 15% per-leg disaster stop.
- **Grid (8):** H ∈ {4 h, 24 h} × k ∈ {5, 10} × signal ∈ {D, crowd-only z(Δ24h log `count_long_short_ratio`)}.
- **Trade unit:** one coin-leg round trip.

**Expected trades/day.** At H = 4h and k = 5, up to 60 legs a day (less after keeping unchanged legs). At 24 h, 10–20.
**50 forward trades take 1–4 days**, but the archive lag adds one day.

**Costs.** Same as idea 4: about 15–19 bp per leg round trip + funding. Crowded legs pay more funding when short-crowded.

**Main kill risk.**
- **The weak evidence base.** The ratio may simply proxy past returns, in which case idea 4 already subsumes it. Pre-register a check that D adds to residual return in a train regression before any P&L.
- **Crowd-short squeezes.**
- **Archive gaps:** some symbols' metrics have missing days.

---

### Idea 7. Intraday time-series momentum: first session predicts the last (H-ITSM)

**Mechanism.** Gao et al. (2018) found that the S&P 500 ETF's first half-hour return predicts its last half-hour. For
Bitcoin, using volume to define active sessions, the same holds, driven by liquidity provision rather than late-informed
trading. Applied per coin across a liquid perp universe, it trades once per coin per day.

**Evidence.**
- **Shen, Urquhart and Wang (2022)**, "Bitcoin Intraday Time Series Momentum", Financial Review 57(2) 319–344, DOI 10.1111/fire.12290 ([Birmingham](https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/)). DATA.
  - "The first half-hour positively predicts the last half-hour return."
  - Predictability is strongest for the highest-volume or highest-volatility first sessions, and the strategy works best in downturns.
- **Wen, Bouri, Xu and Zhao (2022)**, as in idea 4. DATA. Intraday momentum and reversal on BTC, ETH, LTC and XRP. The pattern shifts with jumps, FOMC days and liquidity.
- **Gao, Han, Li and Zhou (2018)**, the template ([alphaarchitect summary](https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/)). DATA (equities).

**Data.**
- **History:** data.binance.vision 1m klines from 2021 (per symbol).
- **Forward:** Binance futures websocket klines.
- **Execution:** HL.

**Pre-registerable rule.**
- **Universe:** the top N Binance USDⓈ-M perps by 30-day volume that are also HL-listed.
- **Session anchor A:**
  - (i) UTC day: first half-hour 00:00–00:30, last half-hour 23:30–24:00; or
  - (ii) US equity session: first half-hour 13:30–14:00 UTC, last half-hour 19:30–20:00 UTC (shift with DST).
- **Signal:** r1 = the coin's first-half-hour return.
- **Trade:** if |r1| ≥ k × σ (the coin's 30-day sd of that half-hour's return), enter in the sign of r1 at the last half-hour's open + 300 ms, taker, and exit taker at its close.
- **Grid (8):** A ∈ {UTC day, US session} × k ∈ {0, 1} × N ∈ {20, 50}.

**Expected trades/day.** Up to N a day (20 or 50) at k = 0, and roughly 30% of that at k = 1. **Volume is enough for 50 trades in 1–3 days, but these trades are one market-wide bet per day.** The effective n is days, so passing the top-3 rule on 2–3 days says almost nothing. This idea only becomes meaningful over weeks of forward data, so it is ranked last despite good evidence.

**Costs.** HL taker 9 bp + slippage 4–6 bp, so about 13–15 bp per round trip, against a half-hour return sd of roughly 30–80 bp for alts.

**Main kill risk.**
- **Correlation:** effectively 1 bet a day.
- **The published effect is on BTC** with a volume-defined session, and may be weaker on alts and on fixed clock sessions.

---

## 2. Ranking (time to 50 forward trades × evidence × cost advantage)

| Rank | Idea | Round-trip cost | History | Forward trades/day (est.) | Days to 50 | Evidence | Main kill risk |
|---|---|---|---|---|---|---|---|
| 1 | **H-TWAPRIDE**: ride visible HL TWAPs | 12–16 bp | Forward only | 15–55 (OWN-PRECHECK, one 23.5 h snapshot) | 1–3 | DATA (preprint 2026, HL-specific) | Sunshine liquidity flattens impact; feed lag |
| 2 | **H-PAIRS**: 1m/5m cointegrated pairs on HL-listed perps | 16–30 bp per pair | Full (Binance 1m) | 20–80 | ≤ 1–3 | DATA (two papers, one with rebates) | Spread amplitude vs cost; cointegration breaks |
| 3 | **H-TWAPFADE**: fade post-completion decay | 8–16 bp | Forward only | 7–45 | 2–5 | DATA (same preprint) | Little transient impact left; maker fills adverse |
| 4 | **H-XSREV**: 1–4 h residual reversal by liquidity tier | 15–19 bp per leg | Full (Binance 1m/1h) | 30–170 legs (6–24 baskets) | < 1 (legs) | DATA (daily-horizon papers) | Hourly effect below cost or momentum in liquid tier; squeezes |
| 5 | **H-QIMAKER**: queue-imbalance-gated HL quoting | 3–6 bp | ~24 Tardis days + forward | tens to hundreds | < 1 | DATA (equities) | Trade-through fill model is adverse by construction; latency |
| 6 | **H-LSRATIO**: crowd vs top-trader divergence | 15–19 bp per leg | Full (Binance metrics) | 10–60 legs (archive +1 day) | 2–5 | DATA-weak / MARKETING | Proxy for past returns; weak literature |
| 7 | **H-ITSM**: first half-hour predicts last | 13–15 bp | Full | 6–50, but 1 effective bet per day | 1–3 nominal, weeks real | DATA (BTC) | One correlated bet per day |

**Suggested order.**
1. **Start the TWAP recorder now** (ideas 1–2 share it). Every day not recorded is a day lost, and there is no backfill.
   - Pre-check 0: compare the Hypurrscan feed with `twapId` increments and with `twapHistory` of a sample of active users, to measure coverage and `first_seen − block_time` lag.
   - Freeze both pre-registrations before the first scored day.
2. **Run H-PAIRS and H-XSREV on train today.** They share the Binance 1m archive fetcher (`pipeline/sources/binance_archive.py`, round 5). Count signal frequency first, then P&L, then validation for anything passing. Start their forward recording as soon as a config passes validation.
3. Run H-QIMAKER on the Tardis HL L2 free days already partly cached for HLANCHOR (`data/raw/web/tardis/parquet/` holds quotes and trades; L2 needs fetching).
4. H-LSRATIO and H-ITSM come last. LSRATIO needs a pre-registered "adds to residual return" check first.

---

## 3. Considered and dropped (do not re-research)

| Lead | Why dropped |
|---|---|
| **Absorbing TWAP slices as a maker** (post on the side TWAP slices hit) | Slices are taker (`crossed: true`), and price drifts in the TWAP direction during execution (Barone and Lillo), so the absorber is short the drift. Idea 2 takes the reverting side only after completion. |
| HL explorer websocket `explorerTxs` as the TWAP source | It delivered about 340 transactions in 25 s, none TWAPs. It looks sampled, not complete. Use Hypurrscan + `twapHistory`. |
| Round-number stop clustering on perps (Osler-style) | Only practitioner and marketing sources were found ([bit.com](https://www.bit.com/insights/knowledge-hub/support-resistance), TradingView scripts). The analogous pump.fun test failed (`agent_round_levels.md`). |
| Binance `forceOrder` liquidation-burst fade | The same mechanism as FLUSH / FLUSH-MW (29 configs, all negative on train). The live stream also throttles to 1 liquidation per symbol per second (round 4). |
| Following "smart" HL wallets as a taker | Zhai: the top-ventile markout is 3.11 bp, below the 4.5 bp taker fee (round 4). |
| Weekly cross-sectional momentum | Already tested as H-MOMENTUM (`reports/hypotheses/momentum_preregistration.json`). |
| Hourly copula pairs (Tadi and Witzany) | 176 trades in 2 years: fails the forward-n requirement by construction. Idea 3 uses 1–5 min instead. |
| Binance spot as a leader for perps | The spot REST API is 451. Perps usually lead spot. A HLLAG variant at best. |
| Upbit or Binance listing announcements | About 1 event a day or fewer, so no 50 trades in 1–3 days. Directionally covered by LISTSHORT. |

## 4. Gaps

- **Barone and Lillo** was read from the arXiv abstract and an HTML summary produced by the fetch tool. The bp figures (8.9 bp, 55 bp) and the "square-root-like … gradually decay" description are the tool's extraction, not verified verbatim. Read the PDF before freezing ideas 1–2. In particular, find the post-completion decay half-life and the TWAP impact in bp versus participation rate. These set H and p.
- **Hypurrscan** is a third-party explorer: its coverage, rate limits and lag are unknown. The 23.5 h OWN-PRECHECK used *current* marks and 24 h volumes, not point-in-time values.
- The `twapId` rate (about 1,850 a day) may count spot TWAPs or other objects. The paper's 465,000 TWAP executions over about 8 months is about 1,900 a day, but "executions" may mean slices.
- **Fil and Kristoufek**' cost assumptions and the "11.61% monthly" figure come from an abstract paraphrase. The full paper was not read.
- **Zaremba et al.**' abstract came from a search snippet (the repository page returned 503). The "2.16% daily after costs" claim could not be attributed and is ignored.
- The **Dunbar and Owusu-Amoako** full text is "not available" on the repository, so the positioning data source is unknown.
- A plain websocket to `fstream.binance.com` timed out from this shell. Forward recording should reuse `hllag_forward.py`'s connection code, and its working state should be confirmed before relying on it.
- **Jurisdiction:** all ideas execute on HL perps (Binance is data only). Confirm the team may trade HL before anything goes beyond paper (round 4 §3). Ideas 1–2 additionally need an ethics and legal read on trading ahead of disclosed orders.
