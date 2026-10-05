# Documented edges, round 4: cost-advantaged, high-frequency ideas (perps and cross-venue)

_Compiled 2026-10-05 by a research agent using web search, web fetch and a few read-only descriptive
pre-checks. Everything from the web is a **lead** (`document` modality). It is not a trader's
statement and not a validated finding. Numbers are copied from the cited source and not re-computed by us unless
marked **OWN-PRECHECK**._

**The pre-checks are FEATURE-ONLY.** They measure:
- spreads;
- the distribution of the premium and the gap to the reference price;
- event counts.

**No forward return or outcome was computed for any idea.** The data that was looked at:
- Tardis free sample day 2026-09-01: Hyperliquid `quotes` and `derivative_ticker`, and Binance-futures `book_ticker`, for WIF, FARTCOIN, PUMP and kBONK/1000BONK;
- Binance archive for 2026-08: `metrics`, 5-min klines and `fundingRate` for WIFUSDT, FARTCOINUSDT, 1000BONKUSDT and POPCATUSDT.

These files sit only in the scratchpad, not in the repo. To be strict, keep those two periods out of any validation or holdout window.

Labels follow rounds 1–3: **DATA** (peer-reviewed, or a preprint with stated data and method), **DATA-weak**
(single author, or an industry report with a partial method), **ANECDOTAL**, **MARKETING**. **Preprints** and
**single-author** work are flagged in each case.

---

## 0. Why this round looks where it does

About 57 families failed, for two dominant reasons:
- **(a) costs:** 1.25%+ per side on the curve, 0.3–2.5% on PumpSwap, plus tips;
- **(b) too few trades,** or a result that rests on the top 3.

`agent_fundcarry.md` came closest. It failed on (b): n = 6–13 in validation. It also lost at 1% DEX cost, because its spot leg was a Solana DEX.

**The structural fix is to trade where round-trip costs are 10–40× lower** and to use signals that fire many times a day. All
ideas below trade **Hyperliquid (HL) perps on Solana memecoins**. Binance or OKX data is used as the **signal or
reference only** (see the jurisdiction note in §3).

### Costs, from the official schedules

| Venue / action | Cost per side | Source |
|---|---|---|
| HL perps, tier 0 (<$5M 14-day volume) | taker **0.045%**, maker **0.015%** | [HL fee docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees) |
| HL maker *rebate* | −0.001% to −0.003%, **only** with maker volume share >0.5% / >1.5% / >3% of the whole exchange | same. **Unreachable for us; plan on a +0.015% maker fee, not a rebate.** |
| HL staking discount | 5–40% off for staking 10–500k HYPE | same |
| Binance USDⓈ-M, VIP0 | maker 0.02%, taker 0.05% (10% off when paid in BNB) | [Binance fee FAQ](https://www.binance.com/en/support/articles/360033544231) |
| OKX swaps, Regular tier | maker 0.02%, taker 0.05% | [bitdegree summary](https://www.bitdegree.org/crypto/tutorials/okx-fees) (secondary source) |
| For comparison: pump.fun curve, PumpSwap, Raydium WIF/SOL AMM | 1.25%+; 0.3–2.5%; 0.25% + impact | our failures; DexScreener pool `EP2ib6…` |

**OWN-PRECHECK: quoted spreads (median, 1-s grid, 2026-09-01, Tardis free sample)**

| Coin | HL median | HL p90 | Binance-futures median |
|---|---|---|---|
| WIF | 2.0 bp | 3.5 bp | 5.0 bp (tick-bound) |
| FARTCOIN | 2.3 bp | 4.0 bp | 5.7 bp |
| PUMP | 2.3 bp | 4.5 bp | 2.3 bp |
| kBONK | 3.4 bp | 6.7 bp | 3.2 bp |

**All-in round trip on HL:**
- taker/taker ≈ 9 bp + spread ≈ **11–13 bp**;
- maker/taker ≈ 6 bp + adverse selection;
- maker/maker ≈ **3 bp**.

**Compare: ≥250 bp on the curve.**

**Liquidity caveat.** Current HL 24-h notional, from `metaAndAssetCtxs` on 2026-10-05:

| Coin | 24-h volume |
|---|---|
| PUMP | ~$150M |
| FARTCOIN | ~$7.4M |
| PENGU | ~$2.1M |
| TRUMP | ~$2.8M |
| kBONK | ~$1.35M |
| WIF | ~$0.83M |
| POPCAT, GOAT, PNUT, MOODENG, BOME | $0.08–0.17M |

Size must stay small (≈$500–5k per order) for the impact assumptions to hold. Most ideas therefore concentrate on PUMP,
FARTCOIN, kBONK, WIF, PENGU and TRUMP.

### Public data with no keys (checked from this container on 2026-10-05)

**data.binance.vision** (HTTP 200). Daily or monthly archives for every USDⓈ-M perp since listing:
- `aggTrades`/`trades` (ms timestamps);
- `klines` 1m;
- `premiumIndexKlines` 1m (perp-vs-index premium);
- `markPriceKlines`;
- `metrics`: 5-min open interest and long/short ratios;
- `bookDepth`: ±1–5% depth snapshots;
- `fundingRate` (monthly; e.g. WIFUSDT 2024-01 to 2026-09).

`bookTicker` (top of book) exists **only up to 2024-03-30** (WIFUSDT 2024-01-18 to 2024-03-30, 73 days).

**Tardis.dev free samples.** The first day of every month needs no key; other days return 401.
- **Hyperliquid** since 2024-10-29: `quotes`, `trades`, `incremental_book_L2` and `derivative_ticker` (mark, oracle/index, funding, OI). That is about 24 free days.
- **binance-futures:** `book_ticker`, `trades` and `liquidations`, about 33 free days since the meme perps listed.
- **HL `liquidations` is not offered** (HTTP 400).
- URL pattern: `https://datasets.tardis.dev/v1/<exchange>/<type>/<YYYY>/<MM>/01/<SYMBOL>.csv.gz`.

**HL `info` API** (POST, no key):
- `fundingHistory`: full history, already cached in `data/raw/web/hyperliquid/`;
- `metaAndAssetCtxs`: mark, oracle, premium, impact prices and OI for every coin in one call;
- `l2Book`: 20 levels;
- `recentTrades`: **includes both wallet addresses (`users`)**;
- `candleSnapshot`: only the last 5,000 candles;
- `vaultDetails`.

The public websocket gives the same data forward.
- **No public global HL liquidation feed exists.** It is per-wallet only. GoldRush/Hypedexer are keyed or paid ([GoldRush docs](https://goldrush.dev/docs/api-reference/hyperliquid-websocket/liquidation-fills.md)).
- The HL S3 archive (`hyperliquid-archive`) is requester-pays and needs AWS credentials, so it is **excluded**.

**Other liquidation sources.**
- OKX `/api/v5/public/liquidation-orders`: public, but only a rolling recent window (about 14 h of WIF fills seen). Use it for forward recording.
- Gate `futures/usdt/liq_orders`: public.
- Binance live `fapi`/`fstream` returns **451/403 from here**, so the Binance archive is the only Binance route.

---

## 1. Ideas, ranked by testability × cost advantage

### Idea 1. Anchored passive quoting on HL meme perps around Binance-implied fair value (H-HLANCHOR)

**Mechanism.**
- Price discovery happens on Binance. HL meme books are thin, so HL-local flow can push the HL mid away from where the leader says it should be. That flow includes local retail market orders, liquidation market orders sent to the HL book, and stop runs.
- A resting limit order placed at *fair ± k* on HL is filled only when such local flow overshoots.
- The order **pays the 1.5 bp maker fee instead of 4.5 bp**, and it is filled at a price already away from fair.
- Exit when HL re-converges to fair. Use a maker order, or a taker order after T seconds.
- This is cross-venue convergence done from the cheap side. We **supply** liquidity to price-insensitive local flow (Nagel-style liquidity provision) rather than racing for it.

**Evidence.**
- **Binance leads HL.** "Binance leads Hyperliquid in every price-discovery window"; even the most informed HL wallet cohort "also follows Binance on average". Source: [Lim, SSRN 6993378](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6993378). **Working paper, single author.** BTC only, May–Jun 2026. The abstract came via search snippet because the page returned 403. **DATA-weak.**
- **Cross-venue deviations exist and mean-revert.** Arbitrage capital is the bottleneck. Source: [Makarov & Schoar, JFE 2020, doi:10.1016/j.jfineco.2019.07.001](https://doi.org/10.1016/j.jfineco.2019.07.001). **DATA, peer-reviewed.** Covers spot only.
- **Short-term reversal pays for liquidity provision.** Its profits rise when liquidity is scarce. Source: [Nagel, "Evaporating Liquidity", RFS 2012, doi:10.1093/rfs/hhs066](https://doi.org/10.1093/rfs/hhs066). **DATA, peer-reviewed.** Covers equities.
- **Caution on maker margins.** HL's own market-making/liquidation vault, HLP, earned $138.5M all-time on about $181M equity. Its **current APR is only 3.6%**, with +$0.58M over the last month (OWN-PRECHECK, `vaultDetails`, 2026-10-05). Passive provision on HL is positive but thin for a professional.

**OWN-PRECHECK (features only, 2026-09-01).** Episodes in which the HL mid deviates from the Binance-perp mid by more than X:
- method: deviation after removing a trailing 10-min median basis; counts are rising edges on a 1-s grid;

| Coin | >10 bp | >20 bp |
|---|---|---|
| WIF | 177 | 11 |
| FARTCOIN | 304 | 14 |
| PUMP | 416 | 31 |
| kBONK | 428 | 47 |

**Rule (pre-register).**
- **Fair value:** F_t = Binance-perp mid_t × (1 + b_t), where b_t is the trailing 10-min median of (HL mid / Binance mid − 1). Point-in-time; Binance timestamps take a latency penalty of +300 ms.
- **Quoting:** keep a resting HL bid at F_t·(1 − k) and an ask at F_t·(1 + k), with k ∈ {10, 15, 20} bp and size $1k.
  - Cancel and replace when F moves by more than k/2. Charge a 300 ms cancel latency: a stale quote can still be hit.
  - Pause quoting while |Binance 2-s return| > k, to avoid being picked off on the leader's own moves.
- **Fill model:** conservative trade-through. A bid fills only if an HL trade prints **strictly below** the bid price, or prints at the bid with cumulative volume at that price exceeding the queue ahead (L2 size at the time of posting).
- **Exit:** a maker order at F_t; if not filled within T ∈ {10, 30} s, a taker order. Stop out at 3k against the position.
- **Costs:** 1.5 bp maker; 4.5 bp taker on fallback exits.
- **Variant:** use the HL oracle price from `derivative_ticker` / `metaAndAssetCtxs` as the anchor instead of Binance.

**Data.** History comes from about 24 free Tardis days, with HL L2 and trades plus Binance `book_ticker` on the same day. Forward: record HL `l2Book`/`trades` over WS, and download the Binance `aggTrades` archive the next day.

**Expected trades per week.** At k = 15–20 bp: about 20–100 fills per coin per day on the 4 coins in the pre-check, so **hundreds per week**. Even the 24 free history days should give more than 50 fills.

**Main risk.**
- **Adverse selection.** A fill at fair − k is most likely exactly when Binance is about to move down: the fair-value estimate is stale and we are the slow maker.
- Trade-through fill models still flatter queue position.

**Kill test.** The 30-s markout of fills, net of fees, must be > 0 by train-period markout alone before any PnL tuning.

---

### Idea 2. Taker catch-up on HL after a Binance move (H-HLLAG)

**Mechanism.**
- This is the same lead-lag as idea 1, taken from the other side.
- When the Binance perp mid moves by more than θ within 2 s and the HL mid has moved by less than θ/2, buy or sell HL in Binance's direction with a taker order. Exit after H seconds, or once the HL gap closes.
- It is the only cheap-venue convergence trade where crossing the spread costs about 6 bp (4.5 bp fee plus half a 2–3 bp spread) rather than 125+ bp.
- It is not harmful MEV:
  - it is ordinary cross-venue arbitrage on a central limit order book (CLOB);
  - it trades against stale *quotes* that professional market makers choose to leave;
  - it does not reorder anyone's transactions.

**Evidence.**
- [Lim, SSRN 6993378](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6993378): **DATA-weak, single-author working paper**, venue-level lead of Binance over HL.
- Price adjustment on less-dominant venues is sluggish ([Hansen, Kim & Kimbrough, arXiv 2109.12142](https://arxiv.org/abs/2109.12142)): **DATA, preprint.**
- Cross-crypto diffusion lasts up to 10 min ([Guo et al., JEDC 2024](https://ideas.repec.org/a/eee/dyncon/v163y2024ics0165188924000551.html)): **DATA, peer-reviewed.**
- **Note:** our H-SOLLEAD failure tested SOL/USD → pump.fun tokens, a different and illiquid target with 250 bp costs. That failure does not speak to perp-to-perp lag.

**OWN-PRECHECK (features only, 2026-09-01).** Binance 2-s mid moves:

| Coin | >10 bp | >20 bp |
|---|---|---|
| WIF | 763 | 42 |
| FARTCOIN | 1,005 | 47 |
| PUMP | 771 | 111 |
| kBONK | 988 | 178 |

**Rule (pre-register).**
- θ ∈ {15, 25} bp over 2 s on the Binance-perp mid.
- **Condition:** the HL mid has moved by less than θ/2 over the same 2 s.
- **Decision time:** the Binance event plus a **latency L ∈ {300, 800} ms**, using Tardis `local_timestamp` for both venues.
- **Fill:** an HL taker at the then-current HL best ask or bid, walking the L2 book for $1k size.
- **Exit:** H ∈ {5, 30} s taker, or when HL mid − fair ≤ 2 bp. Fees are 4.5 + 4.5 bp.
- **Cooldown:** 10 s per coin.

**Data.** The same as idea 1. Both venues' history is on the free Tardis days; forward recording needs only public WS and archives.

**Expected trades per week.** At θ = 15–25 bp, with the HL condition removing some: about 20–150 per coin per day, so **hundreds per week**.

**Main risk.**
- **We are slow.** HL market makers re-quote off Binance within milliseconds. The gaps that survive 300–800 ms of latency may be gaps that do not close, being HL-specific information.
- The test must use realistic latency and treat L as a robustness axis, not a tuning knob.
- Spikes in HL block time or API latency during volatility make it worse.

---

### Idea 3. Liquidity provision after forced deleveraging: buy flushes on meme perps (H-FLUSH)

**Mechanism.**
- Liquidation engines send price-insensitive market orders, and cascades overshoot as each forced sale triggers the next.
- The patient buyer is paid the liquidity premium:
  - in theory, Brunnermeier–Pedersen liquidity spirals;
  - empirically, Nagel 2012.
- On perps the flush is **observable**: open interest falls sharply in the same 5-min bar as a price drop, or liquidation prints cluster.
- Entry is a **maker bid ladder** below the market, so we earn the spread at the moment others pay it. Exit after the rebound window.

**Evidence.**
- [Nagel, RFS 2012](https://doi.org/10.1093/rfs/hhs066): **DATA, peer-reviewed.** Reversal returns are compensation for liquidity provision and are largest when liquidity evaporates.
- [Wen, Bouri, Xu & Zhao, NAJEF 2022](https://www.sciencedirect.com/science/article/abs/pii/S1062940822000833): **DATA, peer-reviewed.** Intraday crypto returns show both momentum and *reversal*, the reversal tied to jumps and overreaction.
- ["Intraday Bitcoin price shocks: when bad news is good news", J. Applied Economics 2022](https://www.tandfonline.com/doi/full/10.1080/15140326.2022.2151253): **DATA, peer-reviewed.** Overreaction after *negative* shocks, larger for bigger shocks.
- Cascade mechanics on Binance perps: seven cascades from 2022 to 2025 ([arXiv 2607.27070](https://arxiv.org/html/2607.27070v1); [arXiv 2608.03616](https://arxiv.org/pdf/2608.03616)): **preprints, single author for 2608.03616.** They are about early warning and branching, not post-cascade returns.
- **No paper measuring returns after meme-perp liquidations was found.**

**OWN-PRECHECK (features only, 2026-08, Binance archive).**
- With **absolute** thresholds (5-min OI drop >2% and price drop >1.5%), there were only **0–1 events per coin in the whole month** for WIF, FARTCOIN, 1000BONK and POPCAT. August 2026 was quiet.
- **Absolute thresholds will fail the 50-trade bar.** The rule must be relative and pooled.

**Rule (pre-register).**
- **Universe:** every Binance USDⓈ-M perp on a Solana memecoin that is also listed on HL (about 20; fundcarry's map).
- **Signal per coin, point in time:**
  - z_OI = 5-min ΔOI / trailing-30-day sd;
  - z_P = 5-min return / trailing-30-day sd.
  - A flush is z_OI < −q and z_P < −q, with q ∈ {2.5, 3}.
  - Optional confirmation: Binance `liquidations` prints (Tardis days / forward OKX + Gate) of more than $X in the bar.
- **Entry:** at the bar close plus 5 s, post HL bids at mid × (1 − j), j ∈ {0.3%, 0.6%}, for 60 s; unfilled orders are cancelled.
- **Exit:** after H ∈ {15, 60} min, by a maker order at mid, falling back to a taker order 60 s later. Stop at −3%.
- **Mirror (short-squeeze flush):** symmetric, reported separately.
- **Control:** the same ladder after equally large price drops **without** an OI fall. This is the plain "extreme-move reversal" variant, and it shows whether forced flow matters.
- **Fill model:** the HL fill must be confirmed on HL trades. Where HL history is missing, **use Binance `aggTrades` as the fill tape, and charge HL fees plus a 5 bp venue-mismatch haircut**.

**Data.**
- **Signal history is full:** Binance `metrics` (5-min OI) and 1m klines from 2024 to now, all public.
- **Fill tape:** Binance `aggTrades`, full history.
- **Liquidations:** only on Tardis free days, plus forward OKX/Gate.

**Expected trades per week.** At q = 2.5 (about the top 0.6% of bars per tail), roughly 10 per coin per week × 20 coins, so **~100–200 a week**. These are heavily clustered on market-wide days: use date-clustered statistics and count market-wide days, not just events.

**Main risk.**
- **Catching knives.** In a trending crash, flushes continue (the October 10, 2025 type), and the top-3/bottom-3 trades dominate.
- The relative threshold stays high-frequency only if volatility is not regime-shifting.

---

### Idea 4. HL–Binance funding *differential* carry, perp against perp (H-FFDIFF): the direct fix for H-FUNDCARRY

**Mechanism.**
- Fundcarry was killed by two things: the **Solana DEX spot leg** (0.5–1% per side) and **too few high-funding episodes after 2024**.
- Replace the spot leg with the *other venue's perp*:
  - when HL funding exceeds Binance funding by D, short HL and long Binance (or the reverse);
  - collect the difference while the legs stay delta-neutral.
- The four taker legs cost about **0.2% per round trip**, against about 1.2% for fundcarry. The trade fires on the **signed differential** (either direction), not only on a high level.
- HL pays funding hourly from an hourly average premium, capped at 4%/h. Binance meme perps settle every 4 h with tighter caps. The two venues' funding therefore diverges in meme squeezes, because different user bases push each side.

**Evidence.**
- Perp–spot and funding deviations are large in crypto and arbitrage is limited by capital ([Schmeling, Schrimpf & Todorov, BIS WP 1087](https://www.bis.org/publ/work1087.htm), **DATA, peer-reviewed**; [He, Manela, Ross & von Wachter, arXiv 2212.06888](https://arxiv.org/abs/2212.06888), **DATA**).
- DEX funding is "more volatile and can deviate significantly from CEX rates" (search snippet of [ScienceDirect S2096720925000818](https://www.sciencedirect.com/science/article/pii/S2096720925000818); the page returned 403, so this is **DATA-weak until read**).
- Practitioner write-up of the CEX–DEX funding gap ([pi2 network blog](https://blog.pi2.network/arbitrage-opportunities-in-perpetual-dexs-a-systematic-analysis/)): **MARKETING.**
- Cross-sectional funding sorts on Binance 2023–25 die above about 20 bp of cost ([dimaquant](https://dimaquant.substack.com/p/can-we-trade-funding-information)): **ANECDOTAL/DATA-weak.** It is a warning about turnover.

**OWN-PRECHECK (features only).** In August 2026, Binance funding |rate| ≥ 0.05% per 4 h occurred **once in 744 prints** across WIF, FARTCOIN, 1000BONK and POPCAT. The *level* regime is dead, so only *differential* episodes can supply the count. **Their frequency is unmeasured; measure it first.**

**Rule (pre-register).**
- **Signal:** D_t = trailing-24-h mean of HL hourly funding − the Binance 4-h funding, both annualised.
- **Open** when |D| ≥ d, with d ∈ {20%, 40%, 80%} per year:
  - short the venue with the higher funding and long the other;
  - equal notional, 1x on each venue (fundcarry's 2x liquidations lesson).
- **Close** on any of:
  - |D| < 5% per year;
  - 7 days pass;
  - the cross-venue price gap moves more than 1% against the position.
- **Costs:** 4 × taker (HL 4.5 bp, Binance 5 bp), plus spread and impact from `bookDepth`.
- **Splits:** the same calendar splits as fundcarry (train to 2025-12-31, validation 2026 H1, untouched holdout from 2026-07-01).
- **Power:** pool *all* coins listed on both HL and Binance (about 150) as a "related markets" sample, and report the meme subset separately.

**Data.**
- **Fully public and mostly cached already:** HL `fundingHistory` in `data/raw/web/hyperliquid/funding_*.json`, plus the Binance `fundingRate` monthly archive.
- Price-gap risk comes from Binance 1m klines and the HL premium proxy (validated in fundcarry: median abs error 0.07%).

**Expected trades per week.**
- Meme subset alone: unknown, likely 1–5 per week.
- Pooled 150 coins: **probably 20–100 per week.** That is the reason to pool.

**Main risk.**
- Two-venue capital and margin.
- **Auto-deleveraging (ADL) or delisting on one leg** (JELLY on HL, March 2025).
- Funding differential is a weak signal for meme-only power.
- Two exchange accounts are needed (jurisdiction, §3).

---

### Idea 5. Cross-meme lead-lag at minute frequency on perps (H-XLEAD)

**Mechanism.**
- Guo et al. show that other coins' lagged 1-min returns predict a coin's next returns, through limited attention and slow diffusion. Their long-short portfolio earns 2.16% a day out of sample after costs.
- Our H-SOLLEAD tested a *different* target, pump.fun tokens with ≥250 bp costs, in a dead-quiet SOL week.
- The paper's own setting is liquid perps with 5–10 bp costs, and **meme perps** (WIF, kBONK, FARTCOIN, PUMP and others) are the inattentive, slow-diffusion end of it.
- Leaders to try: BTC, SOL, HYPE, and the largest meme perp (PUMP or FARTCOIN).

**Evidence.**
- [Guo, Sang, Tu & Wang, "Cross-cryptocurrency return predictability", JEDC 163 (2024)](https://ideas.repec.org/a/eee/dyncon/v163y2024ics0165188924000551.html): **DATA, peer-reviewed**; adaptive LASSO and principal components; Binance.
- [Hansen, Kim & Kimbrough, arXiv 2109.12142](https://arxiv.org/abs/2109.12142): **DATA, preprint.**
- **Counter-evidence:** the quarter-hour paper puts predictable components at about 0.5 bp per boundary for majors ([arXiv 2607.09426](https://arxiv.org/html/2607.09426v2), **preprint, 2 authors**). Minute-scale predictability in *majors* is far below taker cost. Our edge must come from the meme tail.

**Rule (pre-register).**
- **Each minute t**, for each meme perp i, predict r_i(t+1..t+5) from the 1–5-min lagged returns of the leader set and of i itself.
  - Model: adaptive LASSO refit weekly on a trailing 30 days (train only).
  - All inputs are completed Binance 1m klines.
- **Trade** if |prediction| ≥ c × (round-trip cost), with c ∈ {1.5, 2}:
  - enter with an HL limit order at the touch (maker), which must fill within 20 s or is cancelled;
  - exit at t+5 by maker, falling back to a taker order.
- Report the **taker-only** version alongside, as the conservative bound.

**Data.**
- Full history: Binance 1m klines for all meme and leader perps (data.binance.vision).
- Maker-fill realism: `aggTrades` trade-through.

**Expected trades per week.** If |prediction| clears 1.5× cost in even 0.5% of coin-minutes: 20 coins × 10,080 min × 0.5% ≈ **1,000 a week**.

**Main risk.**
- **The edge is probably smaller than cost.** The paper's after-cost result may rely on its own cost assumption, which was not stated in the abstract.
- Maker fills are adversely selected exactly when the prediction is right.
- Lagged-return predictors decay as fast as idea 2's lag.

---

### Idea 6. Wallet-identity toxicity filter for HL quoting (H-TOXFILTER): an overlay on idea 1

**Mechanism.**
- HL's tape is public with **both wallet addresses on every trade** (`users` in `recentTrades` and the WS `trades` channel; verified 2026-10-05).
- Wallet toxicity, measured as the post-trade markout of a wallet's aggressive orders, is a persistent wallet attribute.
- A quoter that **withdraws or widens** after a known-toxic wallet trades, and quotes tighter when only benign wallets are active, cuts adverse selection, the main risk of idea 1.

**Evidence.**
- [Zhai, "Public Trader Identity: Adverse Selection and Return Predictability", arXiv 2608.04373](https://arxiv.org/html/2608.04373v3). **Preprint, single author. DATA.** Built from 17.1 billion L4 messages from a non-validating HL node; covers July 2026, replicated on December 2025; 147,113 wallets.
  - Toxicity ranks persist: Spearman 0.52 across adjacent 10-day windows.
  - Top-ventile markout is **3.11 bp**.
  - Identity features raise one-second R² from 10.88% to 12.31% (t = 9.2).
  - **Limits: BTC, ETH and SOL only, no memecoins, and no trading strategy.**
- **3.11 bp is below the 4.5 bp taker fee**, so *following* toxic wallets as a taker does not pay. Only the defensive maker use does.

**Rule (pre-register).**
- **Step 0 (forward, 2 weeks):** record HL trades with `users` for the idea-1 coins. Rank wallets by 10-s markout over the first 10 days. Check that the rank persists over the next 4 days (Spearman > 0.3), or stop.
- **Overlay:** run idea 1 unchanged, except that quoting is paused for S ∈ {5, 15} s after any trade by a top-decile-toxic wallet. Report the change in the 30-s markout and in net PnL against idea 1.

**Data.**
- **Forward only** (public WS). The Tardis normalised `trades` file has no wallet field.
- A non-validating node is the other route: public, but heavy to run.

**Expected trades per week.** The same order as idea 1 (hundreds), minus the paused periods.

**Main risk.**
- Meme-perp wallets may be too sparse for stable ranks.
- It is an overlay: it cannot rescue idea 1 if idea 1's markouts are deeply negative.

---

### Idea 7 (lowest). Funding-settlement avoidance flow (H-FUNDCLOCK)

**Mechanism.**
- Only positions held *at* the funding stamp pay.
- When funding is extreme, the paying side closes just before the stamp (on Binance: 00/04/08… UTC for 4-h meme perps; on HL: every hour) and reopens just after. That predicts a dip into the stamp and a rebound after it, when longs pay.
- **Long entries at T+5 s, exited within the interval, pay no funding.**

**Evidence.**
- Settlement-hour volume and volatility periodicity ([Hansen, Kim & Kimbrough, arXiv 2109.12142](https://arxiv.org/pdf/2109.12142)): **DATA, preprint.**
- Kim & Hansen found the quarter-hour effect "essentially unchanged" when funding quarter-hours are excluded, so **funding stamps are not a big driver for majors** ([arXiv 2607.09426](https://arxiv.org/html/2607.09426v2)).
- No paper documents a price pattern at the stamp. **DATA-weak.**
- On HL, funding is computed from the *hourly average* premium, which removes the snapshot incentive, but payment is still on positions held at the hour ([HL funding docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding)).

**OWN-PRECHECK (features only).** August 2026: |Binance funding| ≥ 0.1% per 4 h occurred **0 times in 744 prints** across 4 meme perps, and ≥ 0.05% only once. In quiet regimes this **cannot reach 50 trades**. Test it only on 2024–25 history (where fundcarry saw high funding), pooled across all perps.

**Rule.**
- **Events:** the latest *predicted* funding |f| ≥ f₀, with f₀ ∈ {0.05%, 0.1%} per interval.
- **Trade:** a long (if f > 0) by HL or Binance maker at T + 5 s; exit at T + {10, 30} min.
- **Control:** the same clock times when |f| is below f₀.

**Data.** Full public history: the Binance `fundingRate` archive and 1m klines, and HL `fundingHistory` (hourly). HL 1-min candles go back only 3.5 days, so the HL version is forward-only.

**Expected trades per week.** About 0 in 2026 regimes; tens in the 2024 meme mania.

**Main risk.** Regime dependence: the same decay that killed fundcarry.

---

## 2. Ranking

| Rank | Idea | Cost per round trip | History available | Trades per week | Prior |
|---|---|---|---|---|---|
| 1 | H-FLUSH: maker bids after OI/price flushes | ~3–6 bp | **Full** (Binance metrics, klines, aggTrades 2024–26) | 100–200 (pooled, relative threshold) | Medium. Peer-reviewed liquidity-provision basis; knife risk. |
| 2 | H-HLANCHOR: anchored HL quoting vs Binance fair value | ~3–6 bp | ~24 free Tardis days, then forward | hundreds | Medium-low. The direct cost advantage; adverse selection is the question. |
| 3 | H-FFDIFF: HL–Binance funding differential | ~20 bp | **Full, mostly cached** | 20–100 pooled; few for memes alone | Medium. A strict improvement on fundcarry's costs. |
| 4 | H-XLEAD: cross-meme minute lead-lag | 3–12 bp | **Full** (1m klines) | ~1,000 | Medium-low. Peer-reviewed, but majors show sub-cost effects. |
| 5 | H-HLLAG: HL taker catch-up after a Binance move | ~11–13 bp | ~24 free Tardis days, then forward | hundreds | Low-medium. Latency race against professional market makers. |
| 6 | H-TOXFILTER: wallet-toxicity overlay on idea 2 | n/a | forward only | as idea 2 | Low-medium. Preprint, majors only. |
| 7 | H-FUNDCLOCK: settlement avoidance flow | ~3–12 bp | full | ~0 now, tens in 2024 | Low. Fails n in the current regime. |

**Suggested order.**
1. Ideas 3, 4 and 5 can be backtested **today** on full public history with no forward recording.
2. Ideas 1 and 2 can be backtested today on the ~24 free Tardis days.
3. Start the HL WS recorder (L2, trades with `users`, and `metaAndAssetCtxs` every 5 s) now. Ideas 1, 2 and 6 then gain forward data.

---

## 3. Cross-cutting cautions

- **Jurisdiction.** From this container, Binance `fapi` returns 451 ("restricted location") and Bybit returns 403.
  - **Before any of this goes beyond research, confirm that the team may legally trade HL perps** (HL's terms restrict some jurisdictions) and, for idea 4, a second perp venue.
  - Data access is fine either way.
  - Solana-native meme perps are not a fallback: Drift lost about $285M in an exploit on 2026-04-01, and its public historical bucket now lists no objects ([Nexus Mutual incident report](https://nexusmutual.io/blog/drift-protocol-incident-report)). Jupiter Perps lists only SOL, ETH and BTC.
- **Simulation rules apply.**
  - Use a `PointInTimeView` that treats Binance and HL timestamps with an explicit latency.
  - Fees are sourced as above. Use conservative trade-through fills for every maker order.
  - Use calendar splits, and keep the 2026-08 and 2026-09-01 pre-check periods out of validation and holdout.
- **The 3-best-trades rule** bites hardest on idea 3 (crash days). Report results by event-day as well as by trade.
- **New adapters:** `pipeline/sources/binance_archive.py`, `tardis_free.py` and `hyperliquid_ws.py`. Stages must not import them directly.

## 4. Considered and dropped (do not re-research)

| Lead | Why dropped |
|---|---|
| Earning HL maker *rebates* | They need >0.5% of HL's total maker volume. At tier 0 we pay +1.5 bp ([fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)). |
| Jupiter limit orders as a public book | Trigger orders are kept off-chain and private (round 2 §drops; [Jupiter docs](https://developers.jup.ag/docs/trigger)). |
| Phoenix / OpenBook memecoin books | Phoenix volume is mostly SOL/USDC. OpenBook v2 shows about $0 in 30-day volume ([DefiLlama OpenBook](https://defillama.com/protocol/openbook)). Neither has a liquid meme book. |
| Drift meme perps (maker rebates, public S3 history) | Exploited April 2026; the `drift-historical-data-v2` bucket lists no keys. |
| Global HL liquidation feed | Not public. GoldRush/Hypedexer are keyed or paid, and the HL S3 archive is requester-pays. Idea 3 uses Binance OI/liquidations instead. |
| Following toxic HL wallets as a taker | The top-ventile markout of 3.11 bp is below the 4.5 bp taker fee (Zhai). |
| Solana-DEX leg CEX–DEX arbitrage (e.g. WIF Raydium 0.25%) | Pool fees of 25 bp plus impact, against professional searchers; the same cost trap as fundcarry. |
| Quarter-hour effect on perps | About 0.5 bp per boundary, one tenth of the taker fee ([arXiv 2607.09426](https://arxiv.org/html/2607.09426v2)). |
| Depositing into the HLP vault | Not a strategy with ≥50 trades. Current APR is 3.6%; useful only as a benchmark for idea 1. |
| Binance `liquidationSnapshot` archive | The dataset prefix is empty (404). The live `forceOrder` stream also sends at most one liquidation per symbol per second, so it undercounts. |

## 5. Gaps

- Lim (SSRN 6993378) and the ScienceDirect CEX/DEX funding paper were **not readable** (403); their claims come from search snippets.
- No study of meme-perp liquidations, meme-perp lead-lag or HL meme-perp market making was found. All of the meme-specific transfer is our inference.
- The pre-check counts come from one day (2026-09-01) and one month (2026-08). Both were quiet.
