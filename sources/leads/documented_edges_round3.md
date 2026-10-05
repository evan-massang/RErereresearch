# Documented edges, round 3: transferable evidence from outside pump.fun

_Compiled 2026-10-05 by a research agent using web search, web fetch and a few read-only descriptive
pre-checks. Everything from the web is a **lead** (`document` modality). It is not a trader's
statement and not a validated finding. Numbers are copied from the cited source and not
re-computed by us unless marked **OWN-PRECHECK**.

The pre-checks are descriptive counts:
- they are not hypothesis tests, and no rule was tuned on them;
- the pump.fun-tape pre-check read only train hours (recv < 1790882100, or 1790899200–1790985600), never the holdout, the Oct 3 validation day or forward data;
- the Hyperliquid pre-check (§1, idea 5) **looked at outcomes** for 23 coins, so those coins' past listings cannot serve as an out-of-sample test. See the note there._

Labels are the same as in rounds 1–2: **DATA** (peer-reviewed, or a preprint with stated data and
method), **DATA-weak** (single author, or an industry report with a partial method),
**ANECDOTAL**, **MARKETING**. Preprints and single-author work are marked in each case.

**Starting point.** Rounds 1–2 and about 50 failed families (`reports/failures/`) point to one
pattern: anything in public on-chain or social data is priced in within about 1 s, and positive
train results fall apart on validation. So this round looked for mechanisms of three kinds:
- **(a)** the signal comes from a market the pump.fun crowd does not watch at sub-second speed (SOL/USD, perps);
- **(b)** we are paid to *supply* convexity rather than buy it (the skewness-seller side);
- **(c)** the effect is structural or calendar-driven, not a race.

---

## 0. Short answers by topic

| Topic | What exists | Consequence |
|---|---|---|
| Other launchpads (four.meme, SunPump, Zora, Clanker) | **No academic return study was found for any of them.** MemeChain covers Ethereum, BSC, Solana and Base, 34,988 coins: 5.15% stop trading within 24 h ([arXiv 2601.22185](https://arxiv.org/abs/2601.22185), DATA, 2 authors, dataset paper with no return analysis). Zora creator/content coins: −80% within two days for a viral creator coin, engagement −98% after the airdrop ([BeInCrypto](https://beincrypto.com/zora-sentiment-indicators-decline/), [The Defiant](https://thedefiant.io/news/markets/zora-drops-as-creator-coins-disappoint); ANECDOTAL). SunPump: only adoption metrics, no outcome data ([TechFlow](https://techflowpost.substack.com/p/sun-meme-tron)). | Same base-rate picture as pump.fun. Nothing transferable as an entry edge. |
| Ethereum new pairs (Uniswap V2) | Naviglio, Tarantelli & Lillo, 17,194 new tokens, Oct–Dec 2024: **88% are honeypots**. A buy at the 60th swap "returns" +1,557% overall, but only +46.7% on *sellable* tokens. The honeypot "profit" is not realisable. Expected profit rises monotonically with later entry (60th swap rather than the first blocks), because early-block gas is prohibitive ([arXiv 2502.10512](https://arxiv.org/abs/2502.10512), EPJ Data Science 2026, DATA). Cernera et al.: ~60% of ETH/BSC tokens are active for less than 1 day, and 1-day rug pulls made ~$240M ([arXiv 2206.08202](https://arxiv.org/abs/2206.08202), USENIX Sec 2023, DATA). | "Late entry beats first-block entry" is already covered by our age-sliced ML (ages 5 s to 3,600 s, all failed). Honeypots barely exist on pump.fun (a standard SPL token with no transfer hooks). **Not transferable.** |
| Microstructure: order-flow toxicity | VPIN and the Roll measure predict price dynamics in BTC/ETH ([Easley, O'Hara, Yang & Zhang 2024, SSRN 4814346](https://stoye.economics.cornell.edu/docs/Easley_ssrn-4814346.pdf), DATA working paper). LVR: AMM LPs lose to better-informed arbitrageurs in proportion to σ² ([Milionis, Moallemi, Roughgarden & Zhang, arXiv 2208.06046](https://arxiv.org/abs/2208.06046), DATA). About half of Uniswap V3 LPs lose money ([Heimbach, Schertenleib & Wattenhofer, arXiv 2205.08904](https://arxiv.org/abs/2205.08904), DATA). | Toxicity *features* as predictors are covered by the 24-feature ML and curve/AMM flow failures. Toxicity as a *cost to a liquidity supplier* is new: idea 2. |
| Cross-asset lead-lag | Minute-level Binance data: other coins' lagged returns predict a coin's return **up to 10 min ahead**, through slow diffusion under limited attention. A long-short portfolio earns **2.16% a day out of sample after costs** ([Guo, Sang, Tu & Wang, J. Econ. Dynamics & Control 2024](https://ideas.repec.org/a/eee/dyncon/v163y2024ics0165188924000551.html), DATA, peer-reviewed). "Price formation mainly takes place on the centralized exchanges while price adjustments on the decentralized exchanges can be sluggish" ([Hansen, Kim & Kimbrough, arXiv 2109.12142](https://arxiv.org/abs/2109.12142), DATA, 3 authors). Small caps respond to BTC with a delay (Tokyo Tech paper, **403, not fetched**). | Idea 1: SOL/USD leading SOL-denominated memecoin prices. **None of our ~50 families used SOL/USD returns as a signal.** Iteration 10's regime features were launch counts and trades per minute. |
| Clock-time periodicity | Kim & Hansen: volume and volatility bursts at 1-, 5- and **quarter-hour** marks on Binance perps, tied to algorithmic trading. The opening order imbalance predicts returns over 4–12 h ([arXiv 2607.09426](https://arxiv.org/abs/2607.09426), DATA, 2 authors, preprint Jul 2026). | Idea 4: a descriptive check on our tape. |
| Retail attention shocks | Robinhood "Top Movers" herding: the top stocks bought each day show **−4.7% abnormal return over 20 days** (−3% over 5 days; −6% at extreme herding) ([Barber, Huang, Odean & Schwarz, J. Finance 2022; SSRN 3715077](https://www.smallake.kr/wp-content/uploads/2020/12/SSRN-id3715077.pdf), DATA, peer-reviewed). | **This agrees with our own failures**: King of the Hill (PF 0.59–0.73), coins reaching 5 live viewers (−19% over 15 min), KOL follower spikes. The "seller" use is idea 3: an exit overlay. |
| Lottery / skewness (MAX) | In crypto the MAX effect is **positive at weekly horizons**: high-MAX coins earn +1.5% to +3.03% a week more ([Özdamar, Akdeniz & Şensoy 2021, Bilkent repository](https://repository.bilkent.edu.tr/items/78167f5c-d3e2-4f07-b4bc-5e8a3ed0b2c0), DATA; [Li, Urquhart, Wang & Zhang, "MAX momentum"](https://pure.bit.edu.cn/en/publications/max-momentum-in-cryptocurrency-markets/), DATA). Intraday it is **negative**: +1 sd of MAX gives −0.043% next period ([Yadav, "Intraday lottery demands"](https://pure.jgu.edu.in/id/eprint/9270/), DATA-weak, **single author**). Supply-limited, positively skewed assets have negative expected returns, consistent with prospect theory (theory and experiments, e.g. [CFS WP 566](https://gfk-cfs.de/media/CFS_WP_566.pdf)). | The overpricing side cannot be shorted on the curve or PumpSwap. The only ways to be "the seller" are: supplying convexity as an LP (idea 2); shorting where a perp exists (ideas 5–6); and selling held inventory into attention (idea 3). |
| Short-sale constraint | Bitcoin peaked on the day CME futures opened, and the fall after is consistent with pessimists finally being able to short ([Hale, Krishnamurthy, Kudlyak & Shultz, FRBSF Economic Letter 2018-12](https://www.frbsf.org/research-and-insights/publications/economic-letter/2018/05/how-futures-trading-changed-bitcoin-prices), DATA-weak: a single-event study). Newly listed Binance perps "almost all fall" over 150 days, with 86 contracts in 2023 and a decline persisting after index adjustment ([FMZ Quant on StockSharp](https://stocksharp.com/posts/m/79763), DATA-weak: blog, no stats). | Idea 6. |
| Perp funding / carry | Crypto carry averages >10% a year and reaches 40–60% a year. It is driven by small trend-chasing investors seeking leverage and by scarce arbitrage capital, and **high carry predicts crashes** ([Schmeling, Schrimpf & Todorov, BIS WP 1087, Management Science](https://www.bis.org/publ/work1087.htm), DATA, peer-reviewed). Perp–spot deviations are larger than in FX, and a no-arbitrage strategy has "high Sharpe ratios" ([He, Manela, Ross & von Wachter, arXiv 2212.06888](https://arxiv.org/abs/2212.06888), DATA). Anecdotes: WIF funding at +0.25% per 8 h for 4 days after its Binance listing ([sharpe.ai](https://www.sharpe.ai/funding-rate/dogwifhat), ANECDOTAL). | Idea 5. Our own pre-check finds very high early funding on Solana meme perps on Hyperliquid. |
| Time-of-day / weekday retail flow on Solana | pump.fun launches cluster at 15:00–22:00 UTC (peak 20:00), with a second peak at 11:00 ([Bitquery](https://docs.bitquery.io/docs/mcp/trading/examples/pumpfun-launch-pulse/), MARKETING/data snapshot). Pine: deployer-funded snipes cluster at 14:00–23:00 UTC (round 1, A1). Kamat's 15-day bot deployment: the 3 worst entry hours average −11.6% against +1.8% for the rest, **but p = 0.56, "non-confirmatory"** ([arXiv 2606.08232](https://arxiv.org/abs/2606.08232), DATA-weak, **single author**, n=190). | Idea 7, with OWN-PRECHECKs below. |
| Scheduled retail DCA flow (Jupiter Recurring) | DCA parameters (amount, interval, output mint) are held **off-chain** by Jupiter's keeper. Per-user vaults are Privy-managed, and execution is randomised by ±30 s ([Jupiter docs](https://developers.jup.ag/docs/trigger/dca.md)). | **Dropped.** The schedule is not public, and trading ahead of it would be borderline harmful anyway. |

---

## 1. Ideas, ranked by how testable they are with data we already hold

### Idea 1. SOL/USD leads SOL-denominated memecoin prices (H-SOLLEAD)

**Mechanism.**
- Curve and PumpSwap prices are quoted in SOL, but pump.fun's UI, Axiom and most bots show **USD** market cap, and traders anchor on USD.
- A SOL/USD move therefore changes every memecoin's USD value at once. No market maker connects SOL/USD to a bonding-curve token, so any SOL-denominated reaction comes only from humans and bots noticing.
- Two outcomes are possible:
  - a SOL drop triggers risk-off selling and USD-cap stop-losses, a lagged negative SOL-denominated response (memecoin beta to SOL above 1);
  - USD anchoring pulls SOL prices the other way (mean reversion to a USD level).
- Either way the signal is set on Binance, where price formation happens. The DEX side adjusts sluggishly (Hansen et al.) and slow diffusion lasts up to ~10 min (Guo et al.).
- That makes this a minutes-scale, cross-market edge, not a race against pump.fun snipers. **No failed family used it.**

**Evidence.**
- DATA, peer-reviewed: [Guo et al., JEDC 2024](https://ideas.repec.org/a/eee/dyncon/v163y2024ics0165188924000551.html), cross-crypto predictability up to 10 min.
- DATA, preprint: [Hansen, Kim & Kimbrough, arXiv 2109.12142](https://arxiv.org/abs/2109.12142), DEX adjustment lags CEX.
- **Nothing on memecoins specifically.**
- Round 2's round-USD-level pre-check found no clustering of sells at round USD caps. That weakens the "USD trigger" route but not the risk-off route.

**Rule.**
- **Signal:** r_k = log return of SOL/USDT over the last k completed 1-min Binance bars (k ∈ {1, 3, 5}). The `data-api.binance.vision` 1-s klines allow a finer version. Point in time means the last *completed* bar only.
- **Step 0 (descriptive, train only):** regress the equal-weighted next-h SOL-denominated return (h ∈ {1, 5, 15} min) on r_k for:
  - (i) trusted active curve tokens with real SOL ≥ 20 and no Mayhem;
  - (ii) PumpSwap pools older than 1 h with ≥ 50 SOL quote reserve (true reserve = logged + 17.585).

  Do the same with next-h net buy SOL as the dependent variable. Stop if the slope's t-stat is below 3 on train.
- **H-SOLLEAD-a (overlay, no new tuning of the base):** block entries of the frozen near-miss rules (aged demand PF 0.93, early detectors PF 0.90, ML exits without Mayhem PF 0.82) when r_5 is on the train-identified bad side by more than θ, with θ ∈ {0.3%, 0.5%}.
- **H-SOLLEAD-b (standalone, long only):** when r_5 crosses θ in the direction that train says predicts a positive SOL-denominated follow-through:
  - buy 0.2 SOL in each of the top 5 PumpSwap pools by trailing-1-h volume, aged at least 1 h;
  - exit at +h, with exact x·y=k fills, `fee_bps` and a tip.

**Data.** **Fully covered:** the curve tape, PumpSwap swaps and SOL/USD 1-min (`data/raw/web/solusd/`, Oct 1–3). Extend SOL klines to Oct 4–5 from the same public source. Caveat: SOL traded only $116.8–123.6 over Oct 1–3, so few |r_5| > 0.5% events. Power will be low until more volatile days are recorded.

**Expected trades/day.** Overlay: the base rule's count. Standalone: about 2–10 SOL events a day at θ = 0.5% (to be measured), × 5 pools, so **~10–50**.

---

### Idea 2. Be the seller of convexity: passive PumpSwap LP in surviving pools (H-LPSELL)

**Mechanism.**
- Lottery-seeking buyers overpay for right-skew (MAX/skewness literature).
- A constant-product LP is short a convex payoff, short gamma, and is paid in fees: 0.20% of volume goes to LPs on PumpSwap, which is permissionless to deposit into ([round 1 C3](https://defillama.com/protocol/pumpswap); [Solana Tracker guide](https://docs.solanatracker.io/guides/pumpfun-amm)).
- It is the only way to be "the seller of lottery tickets" on pump.fun without a short.
- LVR theory says LPs lose to informed flow in proportion to variance. On memecoin pools there is no CEX arbitrage, and the toxic flow is insiders and the trend.
- So the test is whether fee turnover (volume/TVL) in *surviving, high-turnover* pools beats drift plus variance.

**Evidence.**
- DATA: [Milionis et al., LVR](https://arxiv.org/abs/2208.06046); [Heimbach et al.](https://arxiv.org/abs/2205.08904) (about half of V3 LPs lose; profitable only in low-volatility pools); Uniswap V3 fees $199M against IL $260M ([The Defiant on Bancor/IntoTheBlock](https://thedefiant.io/news/research-and-opinion/uniswap-v3-impermanent-loss), DATA-weak, industry).
- **No study of memecoin LP returns exists** (rounds 1–2 found none either).
- **Prior is low.** From iteration 14's numbers:
  - creator fees over 4 h were 0.1–0.55% of market cap;
  - pool TVL at migration is about 0.41 × market cap (≈207M of 1B tokens in the pool, ×2 for both legs);
  - so at a 0.05% creator tier, LP fees ≈ 1–5% of TVL over 4 h;
  - a −25% price move costs an LP 1 − √0.75 ≈ 13% against cash.

  The arithmetic is rough: the creator-fee tier was not verified per pool.

**Rule.**
- **Eligibility:** pool age A ∈ {1 h, 6 h, 24 h}; true quote reserve ≥ 50 SOL; trailing-1-h volume/TVL ≥ V (V set on train from {2, 5, 10}).
- **Entry:** deposit 0.5 SOL of value balanced. Half is swapped into the token through the pool at the exact fill and fee.
- **Exit:** withdraw at A + h (h ∈ {1, 4} h) or when price ≤ 0.6 × entry.
- **PnL:** exact share-of-k accounting using `amm_trades` reserves. The LP fee stays in the reserves; protocol and creator fees leave. Charge 2 transactions each way plus tips.
- **Benchmarks:** cash, and holding the same token amount.

**Data.** **Covered:** `amm_pools`, `amm_trades` (reserves, `fee_bps`) and the 15-min OHLCV for 1,124 pools. Check whether `pumpswap_raw` holds third-party deposit and withdraw events. They change our pool share but not per-unit-of-k accounting.

**Expected trades/day.** About 20–100 positions, depending on V.

---

### Idea 3. Sell into retail attention: an attention-event exit overlay (H-ATTNEXIT)

**Mechanism.**
- Barber et al.: attention-driven herding forecasts negative returns, because the app points everyone at the same short list.
- pump.fun's equivalents are King of the Hill, the front-page and live lists, and DexScreener trending.
- Our own data already shows the buying side of this is negative:
  - KOTH buys: PF 0.59–0.73;
  - first reaching 5 live viewers: −19% over 15 min;
  - KOL follower spikes reverse by 10–20 s.
- The transferable use is the **seller's**: a holder who sells *into* the predictable attention flow captures it instead of donating to it. "Holdings timed to known demand" is exactly this.

**Evidence.** DATA, peer-reviewed: [Barber, Huang, Odean & Schwarz](https://www.smallake.kr/wp-content/uploads/2020/12/SSRN-id3715077.pdf). Our own validated-negative KOTH and viewer results serve as in-domain evidence.

**Rule.**
- Take the frozen entries of the three least-bad failed families, unchanged.
- Replace the exit with: sell at the **first** attention event + 1 s, or the base exit, whichever comes first. Attention events:
  - (a) the token becomes King of the Hill (as defined in `event_studies.py`);
  - (b) the token first reaches ≥ 5 live viewers, which is only recorded from Oct 4 08:54;
  - (c) the first trade by a top-20 kolscan KOL.
- Report the change in PnL against the base exit. Do not re-tune the entries.

**Data.** **Covered:** curve tape, kolscan trades and live viewers. Viewers are forward-only, so variant (b) must wait for new train days.

**Expected trades/day.** The base rules' count (hundreds). It cannot rescue an entry that never reaches attention. **Expect a loss reduction, not a sign flip.**

---

### Idea 4. Clock-time periodicity in curve flow (H-CLOCK)

**Mechanism.**
- Kim & Hansen find algorithmic bursts at minute, 5-minute and quarter-hour marks on Binance perps.
- On pump.fun, scheduled actors include:
  - cron-driven volume and bump bots;
  - Telegram call channels and KOL posts at :00 or :30;
  - the Mayhem agent, which runs every 3 slots;
  - BOOST, which buys every ~11.7 s.
- If buy flow arriving at clock marks is *mechanical*, it is predictable demand that a holder can sell into, and a price impact that reverts.

**Evidence.** DATA, preprint, 2 authors: [arXiv 2607.09426](https://arxiv.org/abs/2607.09426); [arXiv 2109.12142](https://arxiv.org/abs/2109.12142). **No pump.fun evidence.**

**Rule.**
- **Step 0 (train, descriptive):** buy SOL, creates and number of distinct buyers by second-of-minute and minute-of-hour, net of the hourly level. Continue only if a mark carries more than 1.3× its neighbours.
- **Then:** for trusted tokens, compare the 30-s and 120-s SOL-denominated return after buy-flow bursts that fall within ±3 s of the flagged marks with the same size of burst off-mark.
- **Trade (if reversal):** hold existing positions until just after the mark, then sell. A long-only entry is possible only if off-mark bursts continue and on-mark bursts revert, which is a filter for the curve-flow family.

**Data.** **Fully covered** (`curve_trades.ts`/`recv`, `curve_creates`).

**Expected trades/day.** Hundreds if it exists. **Low prior. Run the descriptive check (~30 min) first.**

---

### Idea 5. Funding carry on Solana-meme perps: short perp + long spot on a Solana DEX (H-FUNDCARRY)

**Mechanism.**
- Retail leverage demand for meme perps keeps funding persistently positive.
- Arbitrage capital is scarce because of margin and liquidation risk (BIS crypto carry).
- A delta-neutral short perp / long spot position is paid that funding, so it sells the leveraged lottery demand.
- It is not a speed race: funding is paid hourly on Hyperliquid.
- It is the one "seller of overpriced lottery tickets" structure with a direct, documented payment stream.

**Evidence.**
- DATA, peer-reviewed: [Schmeling, Schrimpf & Todorov](https://www.bis.org/publ/work1087.htm), carry above 10% a year and up to 40–60% a year, and carry predicts crashes.
- DATA: [He et al.](https://arxiv.org/abs/2212.06888), high Sharpe ratios for a perp–spot arbitrage, with deviations shrinking over time.
- **OWN-PRECHECK** with the public, unauthenticated Hyperliquid `info` API on 2026-10-05:
  - the Hyperliquid universe holds ~23 Solana memecoin perps, live or delisted;
  - over the **first ~21 days after listing** (the first 500 hourly prints), the mean funding of 22 coins was a **median 74% a year** (mean 72%), and only 2 were negative (VINE, JELLY);
  - pump.fun-origin examples: FARTCOIN 91%, GOAT 100%, MOODENG 72%, PNUT 55%, CHILLGUY 134%, PUMP 83%.
- **Crash risk is real.** JELLY: a −85% move in 7 days and a delisting during the squeeze ([Decrypt](https://decrypt.co/311713/hyperliquid-delists-solana-meme-coin-liquidation-crisis)).

**Rule.**
- **Universe:** Hyperliquid perps whose underlying SPL token has a Solana pool (a hand-made map; verify CASHCAT and PONS, which our script assumed).
- **Open** when the trailing 24-h mean hourly funding is ≥ F a year (F set on train from {30%, 50%, 80%}):
  - short notional N on Hyperliquid;
  - buy N of spot through the deepest Solana pool, paying its exact fee and impact.
- **Close** on any of:
  - trailing 24-h funding < 10% a year;
  - the basis moves more than 5% against the position;
  - 14 days pass;
  - margin use exceeds 50%.
- **Costs:** Hyperliquid taker fee (check the current tier), DEX fee and impact both ways, priority fees.
- **Splits by calendar time:** train up to 2025-12-31, validation 2026-01-01 to 2026-06-30, and an untouched holdout from 2026-07-01.

**Data.** **Not in our recordings.** It can be backfilled publicly:
- Hyperliquid `fundingHistory` (500 rows per call, paginate) and `candleSnapshot`;
- spot from GeckoTerminal OHLCV (our `fetch_pool_ohlcv.py`) or our own PumpSwap tape for recent months.

This would be a new adapter in `pipeline/sources/` (public endpoints). Trading needs a Hyperliquid account; **check jurisdictional eligibility**.

**Expected trades/day.** About 0.1–1 opens a day across ~12 live coins. Over 2023–2026 that gives several hundred coin-episodes, so the 50-trade bar can be met on history. **It is not a pump.fun-curve strategy.**

---

### Idea 6. Short newly listed Solana-meme perps: short-sale constraint relief (H-LISTSHORT)

**Mechanism.**
- Before a perp exists, only optimists can trade a memecoin, so it is overpriced (Miller; Hale et al. on BTC/CME).
- A perp listing lets pessimists in, and the price drifts down over days to weeks.
- This is the "patient seller of lottery tickets" in its plainest form.

**Evidence.**
- DATA-weak: [FRBSF 2018-12](https://www.frbsf.org/research-and-insights/publications/economic-letter/2018/05/how-futures-trading-changed-bitcoin-prices), one event.
- DATA-weak: [FMZ/StockSharp](https://stocksharp.com/posts/m/79763), 86 Binance listings in 2023, no statistics.
- Round 2: general CEX listing returns mean-revert within about 2 weeks ([The TIE](https://www.thetie.io/insights/what-does-an-exchange-listing-actually-deliver-in-2026)).
- **OWN-PRECHECK**, Hyperliquid daily closes from the first listing-day close, **raw, not market-adjusted**:

  | sample | n | median r7 | median r30 | median r90 | negative at 30 d |
  |---|---|---|---|---|---|
  | all 23 Solana meme perps | 22–23 | −11% | −23% | −60% | 13/22 |
  | listed 2025 or later | 8–12 | −24% | −63% | −85% | 10/11 |

  The right tail is fat: kBONK +328% at 30 d, PNUT +310% at 7 d. 2025 was a falling meme market, so most of this may be beta.
- **These 23 listings are now "seen".** A proper test must use a disjoint set: Binance/Bybit/OKX meme perp listings, or forward Hyperliquid listings.

**Rule.**
- On the first hourly bar ≥ 1 h after a new perp opens on an SPL memecoin, short N.
- Hold 7 or 30 days, with a stop at +50%. Include funding received or paid.
- **Benchmark:** the same window's return on an equal-weight basket of older Solana meme perps (to remove beta).

**Data.** Not in our recordings. Public backfill: Hyperliquid `meta` + `candleSnapshot`, and the public kline archives of other exchanges.

**Expected trades/day.** About 1–3 Solana-meme listings a month on Hyperliquid. Pooling all venues and all altcoins for power gives ~10–30 a month. **It cannot hit 50 Solana-meme trades quickly; use it as a pooled-venue study.**

---

### Idea 7. Demand-per-launch and calendar regime (H-DEMANDCAL). Partly covered

**Mechanism.**
- Retail SOL demand and the supply of new launches follow different clocks:
  - launches and snipers peak in US/EU hours (Bitquery, Pine);
  - human demand may not.
- When buy SOL per new token is high, each launch faces more uninformed flow.
- Weekend and payday effects on retail gambling are documented in equities, and a general crypto day-of-week effect exists ([review](https://journal.stie-mce.ac.id/index.php/jabminternational/article/view/1472), DATA-weak).

**OWN-PRECHECKs (descriptive only).**
- **Our tape, train hours only.** Buy SOL per create was **~21–22 at 03:00–06:00 UTC** against **~13–15 at 13:00–17:00 UTC**: launch supply grows faster than demand in US hours. Each hour bucket has only 1–2 observations, and 08–11 and 20–00 UTC are missing from train.
- **DefiLlama public daily pump.fun volume** (891 days, `api.llama.fi/summary/dexs/pump.fun`). Log volume against a centred 15-day median:

  | day | deviation | ± s.e. |
  |---|---|---|
  | Sat | −7.5% | 1.5% |
  | Sun | −10.6% | 1.6% |
  | Mon–Thu | +1% to +4% | — |
  | Fri | −0.7% | — |
  | 1st/2nd/15th/16th of month | no effect: −1.5% vs −1.1% | — |

  This is a volume pattern, not a return pattern.

**Rule.**
- Gate the frozen near-miss rules on trailing-60-min buy SOL per create ≥ its train 67th percentile, or on 02:00–07:00 UTC.
- Run a separate weekend vs weekday comparison of the same frozen rules.
- Iteration 10 already put launch counts and trades per minute into an ML model and failed. The ratio as a hard gate is the only untested part.

**Data.** Covered in form but **thin in time**: train lacks several hours, and the tape spans only Thu Oct 1 to Mon Oct 5. Weekday tests need weeks of recording.

**Expected trades/day.** A fraction (~30–50%) of the base rule's count.

---

### Idea 8 (lowest). Cross-chain narrative lead: four.meme / Base → pump.fun

**Mechanism.** A ticker that runs on BNB (four.meme) or Base (Zora, Clanker) gets copied on pump.fun. Being *first* pays: "Meme Coin Factories" ([arXiv 2609.10246](https://arxiv.org/html/2609.10246v1); copycats graduate at 0.86% vs 9.2% for originals).

**Evidence.** ANECDOTAL for the cross-chain lead. Our same-chain sympathy test failed (PF 0.39), and so did narrative-cluster heat.

**Rule.** When a four.meme or Base token first passes $1M FDV (GeckoTerminal new-pools and trending, public), buy the earliest pump.fun curve token with the same ticker created in the previous 24 h. Exits on the standard grid.

**Data.** Not covered; it needs a GeckoTerminal BSC/Base poller.

**Expected trades/day.** About 1–10. **The prior is low by analogy with sympathy plays. Listed for completeness only.**

---

## 2. Ranking summary

| Rank | Idea | Data coverage | Trades/day | Prior |
|---|---|---|---|---|
| 1 | H-SOLLEAD: SOL/USD leads memecoin SOL prices | Full (extend SOL klines) | 10–50, or overlay | Medium-low. New signal class; low SOL volatility in sample. |
| 2 | H-LPSELL: PumpSwap LP as convexity seller | Full | 20–100 | Low (iteration-14 arithmetic). Cleanest "seller" test. |
| 3 | H-ATTNEXIT: sell into attention events | Full (viewers forward only) | Base rule's count | Reduces losses; unlikely to flip the sign. |
| 4 | H-CLOCK: clock-mark periodicity | Full | 100s if it exists | Low. 30-min descriptive check first. |
| 5 | H-FUNDCARRY: meme-perp funding carry | Public backfill, new adapter | 0.1–1 | **Medium. The strongest documented payment stream.** |
| 6 | H-LISTSHORT: short new meme perps | Public backfill | under 0.1 (Solana memes) | Medium-low. Beta and fat tails; precheck sample is spent. |
| 7 | H-DEMANDCAL: demand-per-launch and weekend gate | Covered but thin in time | Part of base | Low. Partly covered by iteration 10. |
| 8 | Cross-chain ticker lead | Not covered | 1–10 | Low. Sympathy analogue. |

## 3. Considered and dropped (do not re-research)

| Lead | Why dropped |
|---|---|
| Jupiter Recurring/DCA schedule front-running | The schedule is off-chain and private ([docs](https://developers.jup.ag/docs/trigger/dca.md)). It would also be borderline harmful. |
| Uniswap "buy at 60th swap" returns | The headline return is honeypot-driven and unrealisable. Late-entry ML is covered. |
| Kamat time-of-day bot paper | Single author, n=190, p=0.56, profit gone without the top 3 trades. Not evidence. |
| VPIN / Kyle-lambda entry signals | Covered by the 24-feature snapshot ML and flow families. |
| Zora, Clanker, SunPump specifics | No outcome studies; mechanisms differ (Clanker uses Uniswap v4 single-sided pools, Zora coins are content). |
| MAX momentum (weekly, large caps) | Horizon and universe do not match; our hour-scale momentum after migration failed (iteration 8). |

## 4. Gaps
- No academic study of returns on four.meme, SunPump, Zora or Clanker, or of memecoin LP returns, was found.
- The Tokyo Tech small-cap BTC-lag paper returned 403, and the SMU Guo et al. page returned 503. The figures come from the IDEAS/Bristol abstract only.
- The Hyperliquid pre-check is raw (not beta-adjusted). Funding covers the first 500 hourly prints only, about 21 days. CASHCAT and PONS were assumed to be SPL memecoins without verification.
- The DefiLlama weekday pattern is in volume, not in strategy returns.
