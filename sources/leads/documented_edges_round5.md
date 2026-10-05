# Documented edges, round 5: making real structural income robust (carry, basis, convergence)

_Compiled 2026-10-05 by a research agent using web search, web fetch and read-only checks of public endpoints.
Everything from the web is a **lead** (`document` modality). It is not a trader's statement and not a validated
finding. Numbers are copied from the cited source unless marked **OWN-PRECHECK**._

**The pre-checks are FEATURE-ONLY.** They cover:
- universe counts;
- data availability;
- how often an entry condition fires in **one train month (2025-03)**, counted on funding or premium prints alone.

No price path, P&L, or exit outcome was computed. The pre-check files sit only in the scratchpad (some were deleted
for disk space), not in the repo. 2025-03 lies in train for every perp split used so far:
- ffdiff, listshort and xlead: train ≤ 2025-06-30;
- fundcarry: train ≤ 2025-12-31.

Labels follow rounds 1–4:
- **DATA**: peer-reviewed, or a preprint with stated data and method;
- **DATA-weak**: single author, practitioner, or frictionless;
- **ANECDOTAL**;
- **MARKETING**.

---

## 0. What the near-misses say, and what this round changes

| Near-miss | Real income | Why it failed | Lever used below |
|---|---|---|---|
| H-FUNDCARRY, 1x (`agent_fundcarry.md`) | HL meme funding, +2.6 per 150 episodes in train | n = 6–13 in validation (19 coins). The DEX spot leg costs about 1.2% per round trip, and the result fails at 1% DEX cost. Decayed after 2024. | Swap to a **CEX spot leg** (about 0.3%), **widen to 471 coins**, and hold on a single venue (idea 2). |
| H-FFDIFF (`agent_ffdiff.md`) | HL−Binance differential, 54 bp per trade held to the flip | PF 1.07 at 5 bp slippage. One MOODENG liquidation decides the result, and the 35 meme coins are too few. | **Widen to all 169 HL∩Binance coins**, cut leverage, and use a measured slippage model (idea 4). |
| H-LISTSHORT (`agent_listshort.md`) | Short-sale-constraint drift | 9 validation listings; the squeeze tail is +200% to +10,000%. | **Not carry, so dropped.** It is a directional bet, and the round-5 ideas avoid squeeze-exposed shorts without a hedge. |
| BOOST (`agent_boost*.md`) | A forced 17.6 SOL buyer, predictable to the second | 2–2.5% fees against a 15% lift; rugs; train +6 SOL then validation −12 SOL. | **Not combinable.** pump.fun tape covers only Oct 1–5 2026, so it shares no history with the perp streams. Excluded from the portfolio idea. |
| aged_demand | none (a filter that loses less, not income) | PF 0.93 | Excluded. |

**The common lesson.** The income is real, but each stream was tested on about 20–35 coins and paid 40–120 bp per
round trip, so its thin per-episode yield (15–80 bp) was eaten by costs or by one squeeze. Round 5 does four things:
1. **Make the income contractual** where possible: dated futures converge by construction.
2. **Cut the cost** of the hedge leg: a CEX spot or perp, never a Solana DEX.
3. **Widen the universe 5–15×** to get n.
4. **Pre-register sizing** so that one squeeze cannot decide the result.

### Costs used throughout (official schedules)

| Venue / action | Per side | Source |
|---|---|---|
| Binance spot, regular user | 0.100% maker and taker; 0.075% when paid in BNB | [Binance fee schedule](https://www.binance.com/en/fee/schedule) (fetched 2026-10-05) |
| Binance USDⓈ-M and COIN-M futures, regular user | maker 0.02%, taker 0.05% (USDⓈ-M: 10% off with BNB) | [Binance FAQ 360033544231](https://www.binance.com/en/support/articles/360033544231) (fetched) |
| Binance quarterly delivery | Settlement "is charged as a taker fee" per secondary sources. **Model it as 0.05% (assumption).** | [Binance FAQ](https://www.binance.com/fr/support/articles/360033544231), search snippet; no explicit rate found |
| Hyperliquid perps, tier 0 | taker 0.045%, maker 0.015% | [HL fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees) (as cited in round 4) |
| dYdX v4, tier 1 | taker 0.05%, maker 0.01% | [dYdX docs](https://docs.dydx.exchange/introduction-trading_fees) (search snippet) |
| Slippage | **Pre-register by liquidity tier, not by outcome** (see each idea). Base: 5 bp per leg. | round-4 OWN-PRECHECK spreads 2–6 bp on HL/Binance memes |

### Funding mechanics that make part of the income structural (DATA, official docs)

- **Binance:** `Funding Rate = Average Premium Index + clamp(interest − premium, ±0.05%)`, with "interest rate fixed at
  0.03% daily … 0.01% per funding interval". The premium index is computed from **impact bid/ask prices**, i.e.
  executable prices, not last trades ([Binance funding FAQ](https://www.binance.com/en/support/faq/introduction-to-binance-futures-funding-rates-360033525031)).
- **Hyperliquid** uses the same clamp, with "0.01% every 8 hours … or 11.6% APR paid to short", paid hourly and
  capped at 4%/hour ([HL funding docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding)).
- **So when the premium is near zero, a short perp is paid about 11%/yr.** That is the structural floor of cash-and-carry. The
  clamp makes funding sticky at 0.01%/8h across a ±0.05% premium band.

### Literature on the carry (leads)

- **Christin, Routledge, Soska and Zetlin-Jones, "The Crypto Carry Trade"** (CMU, 1 Aug 2022). DATA, working paper.
  - Short futures and long spot on Binance is "unusually profitable producing in-sample annual Sharpe ratios in the range of 7 to 10".
  - The paper attributes this to long-side leverage demand.
  - [PDF](https://www.andrew.cmu.edu/user/azj/files/CarryTrade.v1.0.pdf). The quote is from the abstract, which we extracted from the PDF ourselves.
- **Schmeling, Schrimpf and Todorov, "Crypto carry"** (BIS WP 1087, 2023, revised 2025). DATA.
  - Carry "can become very large (up to 60% p.a.)".
  - It is driven by small-investor leverage demand and scarce arbitrage capital.
  - **High carry predicts crashes**, and arbitrage faces "spikes in margins and liquidations amid drawdowns".
  - Search snippet of the revision: the average carry is about 7% p.a. from Apr 2019 to Jul 2024.
  - [BIS page](https://www.bis.org/publ/work1087.htm).
- **He, Manela, Ross and von Wachter, "Fundamentals of Perpetual Futures"** (arXiv 2212.06888 v6, Aug 2024). DATA.
  - Deviations from no-arbitrage "diminish over time" (about 11%/yr).
  - A threshold strategy (open when the spread exceeds the cost bound, close when it returns to the frictionless value) gives
    "a Sharpe ratio of 1.8 under high trading costs typical of retail investors" for BTC, and is "even better for Ether and other cryptocurrencies".
  - [arXiv](https://arxiv.org/abs/2212.06888).
- **Robot Wealth, "Hyperliquid Carry Looks Trendy"** (practitioner, frictionless). DATA-weak.
  - A cross-sectional *directional* carry (rank perps by 24h funding) made about 50% frictionless on Binance since early 2024.
  - On HL it was flat: "price changes consistently work against you (post 2024), wiping out funding gains".
  - **This is a warning against unhedged funding-sorted portfolios on HL.** None of the ideas below holds unhedged price exposure.
  - [link](https://edgealchemy.robotwealth.com/p/hyperliquid-carry-looks-trendy).
- **Lei Lu et al., "The Risk and Return of Cryptocurrency Carry Trade"** (seminar abstract, no paper URL found).
  DATA-weak.
  - A cross-sectional carry earns 43.4%/yr, with Sharpe 0.74.
  - The authors attribute it to an equity-volatility risk premium.
  - [ZUEL seminar page](https://dtf.zuel.edu.cn/szjsyxdjr-szjs_tzyg/szjsyxdjr_cont_news/details-40034.html).
- **Ethena (USDe)** is a live, multi-billion-dollar implementation of ETH/BTC spot plus short perp. Its yield is public:
  - DeFiLlama sUSDe pool `66985a81-…`, 4.96% APY on 2026-10-05;
  - a secondary source gives aggregate BTC/ETH funding of about 11% in 2024 and about 5% in 2025, negative in stress episodes such as Oct 2025 ([Coin Metrics SOTN 335](https://coinmetrics.substack.com/p/state-of-the-network-issue-335); search snippet).

  This confirms both that the carry exists at scale and that it decays.

### Public no-key data checked from this container (2026-10-05)

- **data.binance.vision (200).** All of these are in the archive:
  - `futures/um/monthly/fundingRate`: 989 symbols, BTCUSDT from 2020-01;
  - `spot/monthly/klines`: 3,711 symbols. **471 USDT symbols have both a spot pair and a USDⓈ-M perp.**
  - `futures/um/monthly/premiumIndexKlines/1m`: BTCUSDT from 2020-01, WIFUSDT from 2024-01;
  - **dated futures klines:**
    - USDⓈ-M quarterlies: BTCUSDT_210326 … BTCUSDT_261225, plus ETHUSDT quarterlies;
    - COIN-M quarterlies for BTC, ETH, SOL, XRP and BNB through 261225;
    - COIN-M quarterlies for ADA, BCH, DOT, LINK and LTC through 250926 (273 COIN-M kline prefixes);
  - **LST spot:** WBETHUSDT 1h from 2023-07, BNSOLUSDT 1h from 2024-10.
- **Hyperliquid `info`** (POST, no key):
  - `fundingHistory` goes back to 2023-05 (ETH's first print is 2023-05-12);
  - `meta` lists 234 coins, 56 of them delisted;
  - **174 of the 178 live HL coins have a Binance USDⓈ-M perp.**
- **dYdX v4 indexer** (`indexer.dydx.trade/v4/historicalFunding/<MKT>`): hourly funding plus oracle price, BTC-USD back to at least 2023-12. 296 markets. A third perp venue.
- **BitMEX** `api/v1/funding` (public): XBTUSD from 2016-05, SOLUSDT from 2021-06. The `instrument/active` listing returns
  only 12 rows from here, so build the universe per symbol.
- **public.bybit.com/trading/** (200): Bybit **trade-level** archives, e.g. WIFUSDT from 2024-01-11. These give prices,
  not funding. The Bybit API itself returns 403.
- **Limited or no history:**
  - OKX `funding-rate-history` returns only recent data (empty for 2023), and the OKX CDN archive path returns 404;
  - Gate has a 180-day limit;
  - Kraken Futures funding starts 2025-10-01 for PF_XBTUSD. Forward recording only.
- **DeFiLlama yields** `yields.llama.fi/chart/<pool>`: staking APY history, e.g. Lido stETH from 2022-05, plus JitoSOL, mSOL and wBETH pools.
- **FRED** `fredgraph.csv?id=DTB3`: the 3-month T-bill rate, no key (last row 2026-10-01, 4.00%).

---

## 1. Ideas (ranked in §2)

Common rules for every idea:
- **Splits:** reuse the perp-family calendar, with train ≤ 2025-06-30, validation 2025-07-01 to 2026-03-31 and
  holdout ≥ 2026-04-01. Keep 2026-08 and 2026-09-01 out (round-4 pre-check periods).
- **Pass test:** the bar is applied to **per-episode returns on capital employed**.
- **Report:**
  - by calendar quarter and by coin;
  - with and without the 2024Q4 regime;
  - by event-day, as well as per trade, because the top-3 rule bites on clustered squeeze days.
- **Point in time:** decisions use only prints and bars closed before the decision time, through `PointInTimeView`.
- **Concurrency:** one position per coin per idea.

### Idea 1. Dated-futures cash-and-carry held to delivery on Binance (H-DATEDBASIS)

**Mechanism.** A quarterly future must converge to the index at delivery. Buy spot and short the future, and the
annualised basis at entry is locked in, apart from fees, settlement-index error and margin events. The basis exists for
the same reason as positive funding: leveraged long demand plus scarce arbitrage capital (Christin et al.; BIS WP 1087).

Unlike every perp carry we tested, the income does **not** depend on funding persisting after entry. That decay was the
fundcarry failure.

**Evidence.**
- Christin et al. 2022: Sharpe 7–10 in sample for short futures plus long spot on Binance ([PDF](https://www.andrew.cmu.edu/user/azj/files/CarryTrade.v1.0.pdf)).
- BIS WP 1087: average carry about 7% p.a. for 2019–24, up to 60% p.a. ([BIS](https://www.bis.org/publ/work1087.htm)).
- Both are DATA.

**Pre-registerable rule.**
- **Instruments:** every Binance quarterly with 21–120 days to expiry at the decision time:
  - USDⓈ-M: BTCUSDT_YYMMDD, ETHUSDT_YYMMDD;
  - COIN-M: BTC/ETH/SOL/XRP/BNB/ADA/BCH/DOT/LINK/LTC USD_YYMMDD, while listed.

  The spot leg is `<COIN>USDT` on Binance spot.
- **Decision:** every Monday 00:00 UTC, on the 1h close of each leg.
- **Signal:** annualised basis b = (F/S − 1) × 365/days_to_expiry.
- **Entry:** b − c_rt × 365/days ≥ h_t + 2%. Here:
  - c_rt is the round-trip cost below;
  - h_t is the latest 3-month T-bill from FRED, known before t, so the test is against cash, not against zero;
  - +2% is a fixed risk margin.
- **Hold:** to delivery. No early exit, except a margin event: if the future's 1h high rises ≥ 60% above entry, close both legs at the next 1h close plus 50 bp.
- **P&L:**
  - USDⓈ-M: linear.
  - COIN-M: inverse. Hold spot coin equal to the contract's USD face / S, which leaves a second-order convexity term; compute it exactly.
  - Report gross and net of h_t × holding time.
- **Trade unit:** each weekly entry per instrument.

**Costs.** Spot 0.10% in and 0.10% out, futures taker 0.05% in, settlement modelled as 0.05%, plus slippage 2 bp per leg on BTC/ETH and 5 bp elsewhere. That gives **c_rt ≈ 0.34–0.40%.**

**Data and history.** All of it is on data.binance.vision, with no keys:
- dated klines (USDⓈ-M BTC since 210326, COIN-M since about 2020);
- spot 1h klines;
- FRED DTB3.

Train is 2021-01 to 2025-06, which covers 18 delivery cycles.

**Expected trades.** Roughly 5–12 live instruments × 4.3 Mondays, so about 20–50 entries a month whenever the hurdle is met. A rough
guess: zero entries in bear quarters. **Entries overlap heavily**, so also report the effective n by delivery cycle × coin.

**Main risk.**
- **Small edge, regime-dependent.** In bear or quiet regimes the basis is below cash and the rule does not trade, so
  validation may fail on n, not on PF.
- **Settlement-index mismatch.** Binance settles on its index average, and the spot leg is sold at one venue's price.
- Other risks: COIN-M convexity, and exchange counterparty risk.
- **The real question is "beats T-bills after costs"**, which the hurdle builds in. Without it, PF will look trivially high.

---

### Idea 2. Wide-universe single-venue cash-and-carry: Binance spot long plus USDⓈ-M perp short (H-SPOTCARRY-WIDE)

**Mechanism.** This is the fundcarry trade with its two failure causes removed:
- the Solana DEX spot leg (about 1.2% per round trip) becomes **Binance spot (0.2% per round trip)**;
- the 19-coin universe becomes **every USDT pair with a Binance spot market and a perp (471 symbols, delisted ones included).**

Exiting when funding decays protects the episode against the post-2024 decay. The single venue removes the cross-venue basis
that hurt ffdiff.

**Evidence.**
- Christin et al. and BIS, as above.
- He et al. 2024: deviations are larger "for Ether and other cryptocurrencies" than for BTC.
- Robot Wealth: Binance funding carry still positive frictionless since 2024. DATA-weak.

**Pre-registerable rule.**
- **Universe:** symbols in both `spot/monthly/klines` and `futures/um/monthly/fundingRate`, listed for ≥ 30 days on both.
- **Liquidity tiers:** trailing-7d spot quote volume from the kline column. This is point in time.
  - **≥ $20M/day:** slippage 5 bp per leg.
  - **$2M–20M:** 15 bp per leg.
  - **< $2M:** excluded.
- **Signal:** S72 = the sum of funding prints in the trailing 72h, annualised by actual elapsed time. Binance intervals are 8h, 4h or 1h.
- **Entry:** S72 ≥ 30%/yr **and** the latest single print ≥ 0.01%/8h-equivalent. The trade fills at the next 1h close on both legs.
- **Exit:** any of:
  - S72 < 10%/yr;
  - 14 days pass;
  - the perp 1h high ≥ entry × 1.5;
  - the symbol is delisted. In that case close at the last bar, minus 2%.
- **Margin and P&L.** The perp is 1x isolated (margin = notional), so capital = 2N. Funding is received on prints strictly
  after entry. Price P&L uses both legs' 1h closes, so the spot−perp basis is included.
- **The rule is frozen now.** Its single grid point copies fundcarry's L72 cell. The F30 and Z14 values were in fundcarry's grid.

**Costs.**
- Spot 0.10% × 2 and perp 0.05% × 2, so **0.30%**, plus 4 legs × tier slippage.
- **Total about 0.50% (tier 1) or 0.90% (tier 2).**
- Sensitivity: BNB discount, 0.075% spot.

**Data and history.** data.binance.vision only:
- spot 1h klines;
- USDⓈ-M 1h klines;
- `fundingRate`.

History runs from 2020 (BTC) or the listing date. Train ≤ 2025-06-30.

**Expected trades.**
- **OWN-PRECHECK (feature-only, 2025-03, 357 symbols):** 14 onsets at the 30%/yr threshold (17 at 20%). Median
  symbol funding that month was 1.9%/yr, and 12% of symbols averaged above 10%/yr.
- March 2025 was a quiet month, so **expect 15–60 episodes a month**, more in bull months. Over the 9-month validation
  that is likely 100+.

**Main risk.**
- **Squeeze on the perp leg, but much smaller than in fundcarry.** At 1x the spot leg offsets the price move; only the
  margin is at risk, and the +50% stop caps it.
- **Basis blow-outs at entry.** High funding coincides with a high premium, so the spot−perp gap converges against the
  position, the same effect as ffdiff's negative "basis" line. The P&L includes it.
- **Jurisdiction.** Binance spot plus futures access must be legal for the team.
- Delistings.
- **Survivorship:** none, because the archive keeps delisted symbols.

---

### Idea 3. Premium-spike convergence: He et al.'s random-maturity arbitrage on the impact-price premium (H-PREMCONV)

**Mechanism.** This is a different clock from funding carry. Binance's premium index is built from **impact bid/ask**
prices for a fixed margin notional. When retail longs push the perp's executable bid above the index by more than the
round-trip cost, an arbitrageur can short the perp and buy spot. They earn the premium as it converges back
(typically within hours, inside the 8h funding window), plus any funding paid.

He et al. show this threshold rule, "open when the spread exceeds the trading-cost bound, close when it returns to the
frictionless value", has Sharpe 1.8 for BTC at retail costs, and is higher for other coins. It turns many small,
fast-reverting dislocations into many trades, which is what the bar's n needs.

**Evidence.**
- He, Manela, Ross and von Wachter, arXiv 2212.06888 v6. DATA, preprint with stated method ([arXiv](https://arxiv.org/abs/2212.06888)).
- Binance premium-index definition ([FAQ](https://www.binance.com/en/support/faq/introduction-to-binance-futures-funding-rates-360033525031)).

**Pre-registerable rule.**
- **Universe:** as idea 2 (471 spot∩perp symbols, liquidity tiers, ≥ 30 days listed).
- **Signal:** P = the close of the 1m `premiumIndexKlines` bar.
- **Entry:** P ≥ B, where B = round-trip cost + 10 bp:
  - **0.60%** for tier 1;
  - **1.00%** for tier 2.

  Short the perp and buy spot at the **open of the next 1m bar plus 60 s of latency**, i.e. the bar after next. Each leg's
  1m high/low is used adversely: perp at that bar's low, spot at its high. That is a conservative trade-through fill.
- **Exit:** first of:
  - P ≤ 0.05%, filled at the next-next 1m bar, adversely;
  - 72h pass;
  - perp 1m high ≥ entry × 1.3, with both legs closed.
- **Income:** funding prints during the hold are included.
- **Trade limits:** one position per symbol, and no re-entry for 1h after an exit.

**Costs.** As idea 2: 0.30% fees plus tier slippage. The adverse-extreme fill already prices in impact.

**Data and history.** data.binance.vision:
- `premiumIndexKlines/1m` (BTC since 2020-01; memes from listing, e.g. WIF 2024-01);
- spot `klines/1m`;
- USDⓈ-M `klines/1m`.

About 0.65 MB per symbol-month for the premium file alone, so fetch per symbol and month and drop the zips.

**Expected trades.**
- **OWN-PRECHECK (feature-only, 2025-03, 360 symbols):** 1m premium onsets, re-armed when P ≤ 0.05%:
  - **540** at ≥ 0.5% (84 symbols);
  - **52** at ≥ 1.0% (27 symbols);
  - 3,387 at ≥ 0.3%.
- **So expect about 100–400 a month** at the pre-registered bounds, more in active months.
- Many will be clustered on one symbol and day, so report by event-day as well.

**Main risk.**
- **The index is not the venue we buy.** Binance's index is a multi-venue spot average, and the spot leg trades on Binance only. A
  1m premium spike can be a **Binance-spot lag** rather than a perp rich to all spot. That case is self-hedged only if
  Binance spot also lags.
- **Execution latency.** 1m bars against professional arbitrageurs: the spike may be gone by our fill. The
  adverse-extreme fill is the guard.
- **Premiums that widen in a squeeze** before converging, so the mark-to-market hits the perp margin. The +30% stop caps this.
- **Decay.** He et al. find deviations shrink about 11%/yr.

---

### Idea 4. Funding differential widened to every HL coin, perp against perp (H-FFDIFF-WIDE)

**Mechanism.** HL's retail-skewed flow keeps its funding above other venues' for days ("HL funding is the one that runs
hot": `agent_ffdiff.md`, train). Holding to the sign flip collected 54 bp per trade on memes, but n and one liquidation
sank it.

The lever is n. **174 of 178 live HL coins have a Binance perp, against 35 memes before.** Most non-memes are far less
squeeze-prone, so per-leg liquidation is rarer. A third venue (dYdX v4, public hourly funding) adds pairs.

**Evidence.**
- `agent_ffdiff.md` (own train results: real, frequent, 54 bp per trade held to the flip).
- He et al.: deviations comove across coins and are larger off BTC.
- BitMEX's practitioner write-up on harvesting HL funding is in search results only (the article returned 404 when
  fetched; treat it as ANECDOTAL). The search snippet reported SOL funding of 0.00871% on BitMEX vs 0.00030% on HL in 2025H1, an example of
  persistent cross-venue gaps.

**Pre-registerable rule.** The **frozen iteration-2 rule**, with only the universe, leverage and cost model changed:
- **Universe:** every HL `meta` coin, delisted ones included, mapped to a Binance USDⓈ-M symbol by the `listshort_classify`
  prefix rules plus an identity check (median price ratio 0.995–1.005).
- **Signal:** D_W = HL funding − Binance funding, annualised over W hours, on a 4h clock:
  - HL prints up to T−1h;
  - Binance prints before T.
- **Entry:** s·D72 ≥ 40%/yr and s·D24 ≥ 40%/yr. Short the high venue and long the other at equal notional.
- **Exit:** any of:
  - the trailing-72h differential flips sign;
  - 14 days pass;
  - either leg's adverse close-to-entry move reaches 40%;
  - liquidation;
  - a data gap.
- **Leverage:** 0.5 effective per leg (margin = 2× notional on each venue). Pre-registered from ffdiff's stated revisit
  condition: "lev ≤ 0.5 effective".
- **Slippage:** measured before any P&L, from Binance `bookDepth` (±1% depth) at the trade notional. The HL side
  uses that same measurement. Floor 2 bp, cap 15 bp. **Freeze the model before the run.**
- **Variant D:** add dYdX v4 as a third venue (pairs HL–dYdX, Binance–dYdX), same rule, dYdX taker 0.05%. Report it separately and pre-declare it now.
- **Meme subset:** memes are already spent on ffdiff train, so **report the 134 non-meme coins as the primary test** and memes as secondary.

**Costs.** HL taker 4.5 bp plus Binance taker 5 bp per side, plus 4 × measured slippage. **About 27–39 bp per round trip**
(ffdiff's base and sensitivity).

**Data and history.**
- HL `fundingHistory` (from 2023-05) plus HL 4h candles. The latest 5,000 only, so prices start about 2024-06.
- Binance `fundingRate` plus 4h klines (archive).
- dYdX indexer funding plus `candles`.
- Effective train window: 2024-06 to 2025-06.

**Expected trades.**
- **OWN-PRECHECK (feature-only, 2025-03, 169 HL coins with ≥ 600 hourly prints and a Binance match):** 42 entry onsets
  under the frozen entry/flip rule. 8 were memes and **34 non-memes**.
- **So expect about 30–60 a month**, against 12–18 a month for memes alone.

**Main risk.**
- **Non-meme differentials may be smaller per episode.** The onsets clear the same 40%/yr bar, but the hold length is unknown.
- **0.5x leverage halves return on capital.** The bar is per trade, so it passes or fails on P&L, not on ROC.
- **Per-leg liquidation on separate venues.** Leverage 0.5 survives a +46% 4h bar such as MOODENG's.
- HL delistings and ADL.
- HL `candleSnapshot` limits price history to about 2024-06 onward.

---

### Idea 5. Pre-registered volatility-scaled sizing and squeeze guard, as an overlay on ideas 2–4 (H-VOLSIZE)

**Mechanism.**
- Each carry failure was decided by a handful of squeezes: JELLY, CHILLGUY, MOODENG.
- BIS WP 1087 finds high carry **predicts** crashes and margin spikes.
- Moreira and Muir show that scaling exposure by inverse recent variance raises Sharpe for factor portfolios, **including the
  currency carry trade**.

Under equal notional, the most volatile, highest-funding coins carry the most risk. Inverse-vol notional evens the
risk per episode and so reduces the "top/bottom 3 trades decide it" problem.

**Evidence.**
- Moreira and Muir, *J. Finance* 72(4) 2017, DOI 10.1111/jofi.12513 ([NBER w22208](https://www.nber.org/papers/22208)). DATA.
- BIS WP 1087. DATA.
- **Counter-evidence:** Cederburg, O'Doherty, Wang and Yan, *JFE* 138(1) 2020. Across 103 equity strategies, real-time
  volatility-managed versions "do not systematically outperform" ([RePEc](https://ideas.repec.org/a/eee/jfinec/v138y2020i1p95-117.html)). DATA.
- So **pre-register it as a side-by-side A/B, decided by a rule fixed now.**

**Pre-registerable rule** (applied identically to ideas 2, 3 and 4).
- **Notional:** N_i = N0 × min(1, σ* / σ_i):
  - σ_i is the trailing-30d realised volatility of the coin's 4h perp returns, annualised;
  - σ* = 80%/yr, fixed now. It is roughly the 2024–25 BTC/ETH-to-alt midpoint and chosen without returns.
- **Squeeze guard (skip the entry)** if any of:
  - the coin's trailing-30d max |4h return| > 25%;
  - the perp has been listed < 60 days;
  - the entry signal is above the 99th percentile of its own trailing-90d history. This reflects BIS "high carry predicts crashes".
- **Decision rule, fixed now:** adopt the overlay only if **both** of these hold on train:
  - the scaled variant's PF ≥ the unscaled variant's;
  - its ex-top-3 net ≥ the unscaled ex-top-3 net.

  Otherwise keep unscaled. **Validation then runs only on the chosen variant.**
- **The bar is computed on N-weighted returns per trade.**

**Costs.** None extra. Smaller notional gives proportionally the same bp cost.

**Data.** As ideas 2–4. Volatility is computed from 4h klines, point in time.

**Expected trades.** As the host idea, minus the guard's skips (likely 10–30%).

**Main risk.**
- **It does not create income.** It only reshapes the distribution, and Cederburg et al. find vol-timing gains often vanish out of sample.
- **The guard may skip the most profitable episodes.** In fundcarry, 2024 high funding was both the income and the squeeze source.

---

### Idea 6. Pre-registered equal-risk carry book: pool ideas 1, 2 and 4 (plus frozen near-miss configs) (H-CARRYBOOK)

**Mechanism.** The streams draw on different sources:
- dated basis, a term premium;
- spot–perp funding, single-venue leverage demand;
- the cross-venue funding gap, venue-clientele segmentation;
- in 2024–25, meme-perp funding.

Their bad days differ. Pooling raises n and averages out single-squeeze days. **No weights are fitted.**

**Evidence.**
- Diversification across carry sources is standard: Moreira and Muir include FX carry, and the BIS paper finds carry
  comoves across exchanges, which is a caution.
- Our own near-miss list shows uncorrelated failure dates:
  - fundcarry: JELLY Mar 2025;
  - ffdiff: MOODENG Nov 2024;
  - listshort: Q4-2024 wave.

**Pre-registerable rule.**
- **Members, fixed now:**
  - (a) idea 1;
  - (b) idea 2;
  - (c) idea 4, non-meme primary;
  - (d) fundcarry 1x L72 F100 Z14, frozen;
  - (e) ffdiff iteration 2, L72 X40 flip stop40, at the 5 bp base, frozen.
- **Excluded, with reasons:**
  - listshort: directional and negative in validation;
  - BOOST and aged_demand: no overlapping history, and not income.
- **Weights:** equal *risk* per member, with each member's per-trade capital scaled so its train per-trade return
  standard deviation is equal. Statistics only, no P&L ranking. Within a member, the member's own sizing.
- **The book's trade list** is the union of members' trades.
- **Pass:** the book passes the bar on the union, **and** on daily book P&L the worst calendar month is > −3 × the median monthly gain. That second condition is a stability check fixed now.
- **Order:**
  1. Each member is run on train.
  2. The book is formed **regardless of individual pass or fail.**
  3. Validation runs once on the book.

**Validation caveat.** Members (d) and (e) have spent windows:
- fundcarry's validation (2026H1) was opened;
- ffdiff's train was used to choose iteration 2.

So the book's validation for (d) must use 2025-07 to 2026-03, which fundcarry treated as train. **Treat (d)'s part as
in-sample.** The cleanest version drops (d) and (e) and pools only (a)–(c), the new streams.

**Costs.** Each member's own.

**Data.** As the members.

**Expected trades.** The sum of members, about 70–150 a month.

**Main risk.**
- **The carry streams are correlated in a crash.** BIS: carry is high before crashes, and margin spikes hit all of them together, for example the Oct 2025 deleveraging.
- **Pooling can let one strong member carry weak ones.** Report each member's contribution.
- If members (a)–(c) individually fail, the book is mostly averaging noise.

---

### Idea 7. Liquid-staking-token carry: long wBETH/BNSOL spot, short ETH/SOL perp, single venue (H-LSTCARRY)

**Mechanism.** The long leg is the staking token, which accrues about 2–5%/yr in staking yield in its price:
- Lido stETH 2.2% and JitoSOL 4.9% APY on DeFiLlama, 2026-10-05;
- Binance's wBETH and BNSOL are the CEX equivalents.

So the hedged position earns **staking yield + funding**. When funding is slightly negative, staking still covers it,
which raises the floor that sank funding-only carry in bear months. This is Ethena's structure on two assets, run on a single CEX venue.

**Evidence.**
- Ethena's public sUSDe yield, from funding plus staking (DeFiLlama pool `66985a81-…`; [Coin Metrics SOTN 335](https://coinmetrics.substack.com/p/state-of-the-network-issue-335)). DATA-weak.
- BIS and Christin for the funding part.

**Pre-registerable rule.**
- **Pairs:**
  - WBETHUSDT spot (from 2023-07) against ETHUSDT perp;
  - BNSOLUSDT spot (from 2024-10) against SOLUSDT perp.
- **Hedge ratio:** hold perp notional = spot notional × (WBETH/ETH price ratio), refreshed weekly. Staking accrual shows up
  as the ratio's drift.
- **Decision:** every Monday 00:00 UTC.
- **Entry or hold:** S168 + y ≥ 6%/yr, where:
  - S168 is trailing-7d funding, annualised;
  - y is the trailing-30d DeFiLlama APY of the matching pool (stETH proxy for wBETH, JitoSOL proxy for BNSOL), known before t.
- **Exit:** when S168 + y < 2%/yr, at the next Monday.
- **Trade unit:** each weekly holding period counts as a trade, a mark-to-market week.

**Costs.**
- Spot 0.10% and perp 0.05% per side on entry and exit.
- Weekly hedge rebalance at perp taker 0.05% on the adjusted notional.
- LST spot slippage 5 bp. Check BNSOL depth; it may be thin.

**Data and history.**
- Binance spot 1h klines for WBETHUSDT and BNSOLUSDT;
- perp `fundingRate` and klines;
- DeFiLlama yields chart (stETH from 2022-05).

Train is 2023-07 (ETH) or 2024-10 (SOL) to 2025-06.

**Expected trades.** At most 2 pairs × 4.3 weeks, so **≤ 9 a month.** Validation (9 months) gives ≤ 78 weekly trades, and fewer when gated off.

**Main risk.**
- **n is marginal**, and weekly "trades" are overlapping exposure, not independent episodes.
- LST depeg or discount events.
- wBETH/BNSOL spot liquidity.
- **Low absolute yield, about 5–15%/yr.** Best as a sleeve inside idea 6, not standalone.

---

## 2. Ranking (expected robustness × testability)

| Rank | Idea | Round-trip cost | History (public, no key) | Trades/month (OWN-PRECHECK basis) | Prior |
|---|---|---|---|---|---|
| 1 | H-SPOTCARRY-WIDE (idea 2) | ~0.5–0.9% | Full, 2020→ (Binance archive) | 15–60 (14 onsets in quiet 2025-03) | **Medium.** It directly fixes fundcarry's two failure causes. Basis convergence at entry is the unknown. |
| 2 | H-DATEDBASIS (idea 1) | ~0.35–0.4% | Full, 2021→ | 20–50 entries (overlapping), 0 in bear | **Medium-high robustness** (contractual), **low income.** The T-bill hurdle is the real test, and it may fail on n in bear validation. |
| 3 | H-FFDIFF-WIDE (idea 4) | ~0.27–0.39% | HL prices from 2024-06; funding full | 30–60 (42 onsets in 2025-03) | Medium. The rule is frozen, and n and leverage were the stated fixes. |
| 4 | H-PREMCONV (idea 3) | ~0.5–1.0% | Full 1m, 2020→ | 100–400 (540 at ≥0.5% in 2025-03) | Medium-low. The most trades and a peer-documented rule, but the index-vs-Binance-spot mismatch and latency are serious. |
| 5 | H-CARRYBOOK (idea 6) | members' | members' | 70–150 | Medium **if** ≥ 2 members are individually near-pass. Otherwise it is noise averaging. |
| 6 | H-VOLSIZE overlay (idea 5) | 0 | as host | as host, minus 10–30% | Low-medium. Reshapes risk only; Cederburg et al. counter-evidence. |
| 7 | H-LSTCARRY (idea 7) | ~0.4% + rebalances | 2023-07 / 2024-10 → | ≤ 9 | Low as standalone (n). Useful as a book sleeve. |

**Suggested order.**
1. Ideas 2 and 1 share one fetcher: Binance archive spot, perp and dated klines plus funding. Write it as `pipeline/sources/binance_archive.py`.
2. Run train on both.
3. Then idea 4 (mostly cached), with the slippage model frozen first.
4. Run idea 5 as the pre-declared A/B on whichever of 2 and 4 is closest.
5. Form idea 6 last, regardless of results.

---

## 3. Considered and dropped (do not re-research)

| Lead | Why dropped |
|---|---|
| Cross-sectional *unhedged* funding-sorted long/short on HL perps | It is a price-direction bet, not carry. The practitioner evidence says HL price moves wipe out the funding post-2024 ([Robot Wealth](https://edgealchemy.robotwealth.com/p/hyperliquid-carry-looks-trendy)). The listshort squeeze tail applies. |
| Combining BOOST, aged_demand or listshort into a portfolio | BOOST and aged_demand: pump.fun tape covers 2026-10-01 to 05 only, with no overlap with perp histories; aged_demand is a loss-reducing filter, not income. Listshort is directional and negative in validation. |
| Binance vs Bybit vs OKX funding histories | The Bybit API is 403. OKX `funding-rate-history` serves only recent months and its CDN archive is 404. Gate is limited to 180 days, and Kraken Futures funding starts 2025-10. **Use dYdX v4 (full, public) and BitMEX (`api/v1/funding`, from 2016) as the extra venues.** Bybit trade archives (public.bybit.com) give prices only. |
| HL spot + HL perp cash-and-carry | HL spot lists mostly HL-native tokens. Historical HL spot candles have the same 5,000-candle limit. Not enough history for the bar. |
| HLP vault deposit | Not a ≥ 50-trade strategy (round 4). |
| Solana-DEX spot leg in any form | 25–120 bp per side against professional searchers: the fundcarry cost trap. |
| Drift / Jupiter perps | Drift was exploited 2026-04 and its bucket is empty. Jupiter lists only SOL, ETH and BTC (round 4). |

## 4. Gaps

- Christin et al. was read from its PDF abstract. The BIS revised numbers (7% p.a. average, Apr 2019 to Jul 2024) come from a search snippet; the BIS PDF did not download as PDF.
- No official Binance quarterly settlement-fee rate was found, so 0.05% (taker) is an assumption.
- The Lei Lu cross-sectional carry paper was seen only as a seminar abstract.
- The BitMEX HL funding article returned 404.
- Trade-count pre-checks use one quiet train month (2025-03). Bull months will differ. They are **counts of entry conditions only**, not income.
- Jurisdiction: Binance spot and futures and HL perps must be legal for the team before anything goes beyond research (round 4 §3).
