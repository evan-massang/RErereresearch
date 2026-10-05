# Documented edges, round 10: memecoin-only ideas sized against the real cost of a round trip

_Agent: round 10, 2026-10-05 (09:15–10:00 UTC). Leads review only. No backtest was run, and no P&L, return or
win rate was computed from any price path. Web content is cited as a **lead** (`document` modality). **DOC** marks
official documentation. **OWN-PRECHECK** marks a check run from this container. Every OWN-PRECHECK is
descriptive: reachability, counts, fee fields, quoted costs and funding levels. None is a strategy test. The
counts below come from `data/market.duckdb` and use features only (balances, pool reserves, trades per hour).
No returns were computed. Raw pre-check files are in the session scratchpad only, not in the repo._

**Scope.** Memecoins only (`reports/scope_memecoins_20261005.md`): Solana/pump.fun tokens and memecoin perps.

## 0. Why this round looks where it does

There are 23 pump.fun/Solana failures (H1–H8, iterations 1–24, and the agent reports on curve_flow,
early_detectors, amm_flow, crash_bounce, sympathy, committed_dev, aged_demand, mayhem, ml_wallet, boost,
boost_select, pregrad, dev_funding, narrative_cluster, round_levels, dex_paid, cto, fee_claim, sollead,
lpsell_clock and xlead). Meme-perp failures include fundcarry, ffdiff, listshort, flush, wicknet and premconv.
They agree on two points:
- **Seconds-to-minutes signals on the curve or a fresh PumpSwap pool are priced in.** Their gross edge is a few
  percent at best, against a round trip of about 3–5%.
- **Hour-scale post-migration holds lose to decay** (iteration 8: 4 h means −13% to −16%).

So every idea here has to do one of two things:
- **(a)** target a gross edge of at least ~2× the full round trip computed below; or
- **(b)** trade memecoin perps at 0–4.5 bp, at a horizon where our 0.2–0.3 s latency does not matter.

### Costs, stated precisely (the yardstick for every idea)

**pump.fun bonding curve (OWN-PRECHECK on `curve_trades`).**
- 9.57M of 11.24M trades carry `fee_bps = 95` (protocol) plus `cfee_bps = 30` (creator), which is **1.25% per side**.
- 1.66M trades show 0/0. These are mostly Mayhem/special curves (`agent_mayhem.md`). Do not assume zero fees.

**PumpSwap (OWN-PRECHECK on a 2M-row sample of `amm_trades`; `fee_bps` already includes LP and protocol fees,
`agent_amm_flow.md`).** The total fee falls as the pool's market cap rises (the Project Ascend creator-fee tiers,
[Blockworks](https://blockworks.com/news/pumpdotfun-fee-model), lead). Market cap (SOL) = (logged pool SOL + 17.585)
÷ pool tokens × 1e9.

| pool market cap (SOL) | median total fee per side |
|---|---|
| < 420 (every new pool's first trade: median 125 bp, p10–p90 all 125) | **1.25%** |
| 420–1,470 | 1.20% |
| 1,470–2,460 | 1.15% |
| 2,460–3,440 | 1.10% |
| 3,440–4,420 | 1.05% |
| 4,420–9,820 | 1.00% |
| 9,820–14,740 | 0.95% |
| 14,740–98,240 | 0.80% |
| > 98,240 | 0.30% |

**Slippage on PumpSwap.** A new pool opens with a median of **85.0 SOL** of real reserve (OWN; p10 is 17.6 SOL).
On a constant-product pool the one-side impact is about x / R:

| pool reserve R | 0.1 SOL | 0.5 SOL |
|---|---|---|
| 85 SOL (new pool) | 0.12% per side | 0.59% per side |
| ~400 SOL (survivor near 9k SOL market cap) | 0.025% per side | 0.125% per side |

**Priority fee and tip.** The on-chain median is about 0.0001 SOL per transaction (iteration 6). Our conservative
case is **0.001 SOL per transaction**:
- at 0.1 SOL size, that is 2.0% of the round trip;
- at 0.5 SOL, 0.4%;
- at 5 SOL, 0.04%.

**Full round trip (fee + impact + 0.001 SOL tips):**

| case | 0.1 SOL | 0.5 SOL |
|---|---|---|
| bonding curve, mid-curve (impact depends on vsol) | ≈ 4.7% | ≈ 3.5% |
| new PumpSwap pool | ≈ **4.7%** | ≈ **4.0%** |
| surviving PumpSwap pool (~400 SOL reserve, 1.00% tier) | ≈ 4.1% | ≈ **2.65%** |

At a 0.0001 SOL tip, take about 1.8 pp off the 0.1 SOL figures and 0.36 pp off the 0.5 SOL figures.

**Blue-chip Solana memes through Jupiter (OWN-PRECHECK, 2026-10-05 09:2x UTC).** Each figure is a quote-implied
round trip SOL → token → SOL from `lite-api.jup.ag/swap/v1/quote` (keyless, 200). These are quotes, not fills.

| token | 0.1 SOL | 0.5 SOL | 5 SOL | 50 SOL | main route at 5 SOL |
|---|---|---|---|---|---|
| PENGU | 1.3 bp | 1.1 | 3.9 | 5.1 | Kipseli/ZeroFi (prop AMMs) |
| PUMP | 1.7 | 3.1 | 3.3 | 6.2 | BisonFi/GoonFi V2 |
| TRUMP | 0.6 | 1.6 | 8.6 | 11.2 | Kipseli/Scorch/SolFi V2 |
| USELESS | 6.7 | 6.1 | 8.8 | 20.5 | AlphaQ/Kipseli/Scorch |
| BONK | 4.6 | 5.7 | 11.3 | 37.7 | BisonFi/Deriverse/Scorch |
| FARTCOIN | 6.2 | 12.1 | 16.7 | 28.1 | GoonFi V2/Scorch/TesseraV |
| WIF | 9.1 | 13.4 | 41.6 | 78.0 | Whirlpool → Raydium |
| POPCAT | 24.3 | 45.9 | 55.7 | 99.5 | Raydium |
| SPX | 32.2 | 36.2 | 59.5 | 105.9 | Raydium |
| MOODENG | 50.1 | 50.7 | 57.7 | 126.6 | Raydium |

**This is the main new cost fact of the round.** Rounds 4–5 dropped "Solana-DEX spot leg in any form" at
25–120 bp per side, and H-FUNDCARRY charged 0.5% per side. For six memes, proprietary ("prop") AMMs now quote a
round trip of **1–17 bp** up to 5 SOL. These AMMs are oracle-updated market makers. They are >50–60% of Solana spot
volume and absorb "any highly liquid asset" ([Blockworks Research](https://app.blockworksresearch.com/unlocked/solana-dex-winners-all-about-order-flow),
[stepdata](https://stepdata.substack.com/p/prop-amms-on-solana-bisonfi-ends), leads).

**Memecoin perps.**
- **Lighter:** Standard accounts pay 0/0 behind a 300 ms taker speed bump (DOC, cited in rounds 7–8). OWN: 237
  markets, including WIF, 1000BONK, PENGU, FARTCOIN, POPCAT, PUMP, TRUMP, SPX, USELESS, DOGE and 1000PEPE.
- **Hyperliquid:** tier-0 taker 4.5 bp, maker 1.5 bp (DOC). Median spreads are 2.0–3.4 bp on the main memes
  (round 4, OWN). All-in taker round trip is about **11–13 bp**.

### Reachability (OWN-PRECHECK, 2026-10-05 09:2x–09:5x UTC)

| source | result |
|---|---|
| Jupiter `lite-api.jup.ag` `swap/v1/quote`, `tokens/v2/search`, `price/v3` | 200 with a User-Agent. `price/v3` returns 403 without one. `tokens/v2` gives `holderCount`, `organicScore`-style stats, and `stats5m/1h/6h/24h` (buy/sell volume, `numNetBuyers`, `holderChange`). |
| HL `info` `metaAndAssetCtxs`, `allMids`, `fundingHistory` | 200. 20 days of hourly funding fetched for 10 memes. |
| Lighter `api/v1/orderBookDetails`, `api/v1/funding-rates`, `api/v1/fundings?market_id=…&resolution=1h` | 200. 500 hourly funding prints per call (about 20 days). Older history needs paging by timestamp (not tried). |
| Binance `fapi.binance.com` REST | **451, restricted location.** `data.binance.vision` archive is 200. |
| Binance CMS catalog 48 | 200. 1,200 articles back to 2023-01. 385 are "Futures Will Launch … Perpetual" announcements, about 10 a month (all assets). |
| Binance Alpha token list (`bapi/defi/…/alpha/all/token/list`) | 200. 682 tokens, 70 on Solana, with `listingTime`. |
| GeckoTerminal pool OHLCV (hourly) | 200 for a recorded PumpSwap pool. Public history is limited to 180 days (fundcarry agent). |
| pump.fun `frontend-api-v3` | 200 |
| DefiLlama `summary/fees/pump.fun?dataType=dailyRevenue`, `summary/dexs/pump.fun` | 200, keyless: 948 days of revenue and 891 days of volume. |
| Solana public RPC `getTokenLargestAccounts` | **429** (method-specific rate limit). Usable slowly; a keyed RPC would be needed for bulk history. |

---

## 1. Ideas (ranked in §2)

### Idea 1. Prop-AMM cash-and-carry on Solana memes: long spot via Jupiter, short Lighter perp at 0 bp (H-PROPCARRY). Category (b), hybrid

**What is new.** This is an evidence-based iteration of H-FUNDCARRY (`reports/failures/agent_fundcarry.md`). The
parent failed for two stated reasons:
- a Solana DEX leg charged at 0.5% per side, about 1.2% per round trip with tips and bridge;
- validation n of 6–13 episodes.

The 2x family also died on liquidations. This round's quotes cut the spot leg 10–50× for six memes (table in §0).
Lighter removes the perp fee. Fixed-length weekly episodes make n a function of calendar time rather than of rare
funding onsets.

**Mechanism.**
- **Structural part (DOC, round 5):** perp funding carries a positive interest component paid by longs.
- **OWN-PRECHECK, Lighter (20 days):** WIF, PENGU, 1000BONK and TRUMP sit on a floor of **0.12 bp/h, about
  10.5%/yr**. The `funding-rates` endpoint shows 0.000096 per 8 h, which agrees. The means are higher on:
  - FARTCOIN: about 0.3 bp/h;
  - USELESS: about 0.3 bp/h (p90 0.72);
  - SPX: about 0.2 bp/h;
  - PUMP: about 0.2 bp/h.
- **OWN-PRECHECK, HL (20 days):** the mean is 0.17–0.46 bp/h (USELESS 0.46, SPX 0.29, FARTCOIN 0.26), except
  TRUMP at 0.03.
- **OWN snapshot:** HL mids sat **+3 to +21 bp above Jupiter spot** for 8 of 10 memes over four 15-s samples, and
  +29 to +33 bp for SPX. A short perp entered at a premium also earns that convergence.

**Pre-registerable rule (12 configs).**
- **Universe:** frozen before scoring. The memes whose live Jupiter quote round trip at the trade size is ≤ 20 bp
  at entry: today PENGU, PUMP, TRUMP, USELESS, BONK and FARTCOIN.
- **Weekly decision, Monday 00:00 UTC.** For each coin, if the trailing-L-hour mean Lighter funding is ≥ F:
  - buy spot through Jupiter (USDC → token);
  - short the same units on Lighter at 1x, fully collateralised. The liquidation point is far away; this is the
    parent's lesson from 2x.
- **Exit:** hold Z days, then unwind both legs. Close early only if the short's loss reaches 60% of its collateral.
- **Grid:** L ∈ {24, 168} h × F ∈ {12, 20, 35}%/yr × Z ∈ {7, 14} d = **12**.
- **Trade unit:** one coin-episode.

**Trades.** About 6 coins × 1 per week ≈ **0.9 per day**, so 50 resolved episodes take about 8 weeks forward
(Z = 7). This idea is slow. It is ranked first for robustness, not speed.

**Gross vs full cost per 7-day episode.**
- **Gross:** 20 bp (floor) to about 50 bp (FARTCOIN/USELESS level), plus 0–20 bp of entry premium if it converges.
- **Cost:**
  - spot round trip 3–17 bp (§0 table at 5 SOL);
  - USDC↔SOL hops about 1 bp each way (prop AMMs);
  - two Lighter spread crossings, about 2–5 bp each (not measured this round; HL's are 2–3.4 bp);
  - Solana fees negligible.
  - Total ≈ **10–30 bp**.
- **Ratio:** about 1–3×.
- **Capital efficiency is low.** Capital is 2× notional, so the floor carry is about 5%/yr on capital. This is a
  robustness bet, not a return bet.

**Kill risks.**
- Prop-AMM quotes are oracle-priced and can fade at execution. Only a live small fill test proves the cost.
- Funding can flip negative in sell-offs.
- Short squeezes: FUNDCARRY's worst episodes were CHILLGUY, GOAT and MOODENG.
- Lighter counterparty and venue risk.
- The floor may be the whole carry, about 20 bp/week. If the cost is 20 bp, net is zero.
- **Kill test (pre-registered):** if the train mean funding over held weeks minus measured cost is ≤ 5 bp per
  episode, stop before validation.

**Data and splits.** Not in DuckDB.
- **Funding:** Lighter `fundings` paged back to Lighter's public launch; HL `fundingHistory` as a cross-check.
- **Spot hourly:**
  - `data.binance.vision` spot klines for PENGU, PUMP, TRUMP, BONK and WIF;
  - GeckoTerminal (180 days) for FARTCOIN and USELESS.
- **Splits:** train from Lighter launch to 2026-01-31; validation 2026-02-01 to 2026-03-31; holdout ≥ 2026-04-01
  (the round-9 convention).
- **Caveat:** the prop-AMM cost is known only from today. Historical scoring must charge today's measured cost,
  plus a 2× sensitivity case.

### Idea 2. Rug and dev-overhang filter at migration, then one delayed PumpSwap entry (H-CLEANMIG). Category (a)

**What is new.** Iteration 8 bought migrated tokens 1–24 h after migration without any structural filter. Round 1
proposed "avoid-filters" (deployer-funded buyers, copycats) as an overlay; it was never run. This idea tests the
filter directly, with a single entry after the BOOST window (BOOST failed in `agent_boost(_select).md`).

**OWN-PRECHECK (feature counts at completion, from curve balances).**
- Of 2,859 completions on Oct 1–5, **1,310 (46%) had fewer than 20 curve trades.** Most are one-transaction
  "buy the whole curve" graduations: for example `F66TL99e…pump` completed with a single 793.1M-token buy. These are
  insider-controlled supply and are excluded outright.
- Among organic completions (≥ 20 trades), the median top-10 holder share is 33–47%. The three filters below pass
  together on **34 / 33 / 101 / 58 a day** (Oct 1 / 2 / 3 / 4).

**Pre-registerable rule (12 configs).**
- **Filter, from `curve_trades` up to completion only. All must hold:**
  - ≥ 20 curve trades;
  - the creator's net balance is < 0.1% of supply;
  - the top-10 holders (excluding the pool) hold < 30%;
  - wallets that bought in the create slot +1 still hold < 3%.
  - **Strict variant:** also ≥ 150 holders.
- **Entry:** 0.5 SOL on PumpSwap at completion + D. That is after the 300 s BOOST.
- **Grid:** filter {base, strict} × D ∈ {30 min, 2 h} × exit {hold 4 h, hold 24 h, hold 24 h with a −40% stop} =
  **12**.

**Trades/day.** About 30–100 (base filter); validation day (Oct 3) about 101.

**Gross vs full cost.**
- **Cost:** about **4.0%** round trip at 0.5 SOL in a new pool (1.20–1.25% fee tier per side, about 0.6% impact
  per side, 0.4% tips).
- **What the filter must do:** iteration 8's unfiltered 4 h means were −13% to −16%. The filter must move the mean
  by about **+17–20 pp** to clear cost. It is an (a) idea only if survivors of the filter carry a large right tail
  that rugs no longer cancel.

**Kill risk: high.**
- Post-migration decay is mostly organic seller exhaustion, not rugs.
- The filter mainly removes left-tail events, which caps the improvement.
- **Kill test (pre-registered):** on train, if the filtered group's 4 h median return is not at least 5 pp above
  the unfiltered group's, stop before scoring configs.

**DuckDB support: full.**
- **Train:** Oct 1 (outside the 19:15–21:15 holdout) and Oct 2.
- **Validation:** Oct 3. The 24 h exits for Oct 3 fall inside the tape, which runs to Oct 5 03:42.
- **Precondition:** check `loaded_amm_files` hour coverage first. The OWN survivor counts in idea 4 show a
  suspiciously thin Oct 2 at the 6 h age, which suggests PumpSwap tape gaps.

### Idea 3. pump.fun retail-activity pulse as a regime signal for Solana meme perps on Lighter (H-PUMPPULSE). Category (b)

**Mechanism.** pump.fun volume and revenue measure retail risk appetite for Solana memes. If on-chain launch mania
leads the liquid meme complex over hours to days, a zero-fee perp basket can express it. A PUMP-specific leg uses
daily protocol revenue, about 100% of which is spent on PUMP buybacks
([Cointelegraph](https://cointelegraph.com/news/pump-fun-62m-buybacks-pump-token-price),
[The Block](https://www.theblock.co/post/366783/pumps-average-token-buyback-price-floats-40-above-spot-market-even-as-daily-revenue-trends-lower),
leads: $1.3–2.3M/day). This differs from SOLLEAD (SOL → memes, minutes) and XLEAD (meme → meme, minutes). The
signal here is launchpad flow, at hours to days.

**Evidence.** Weak.
- Retail-cycle descriptions only, no peer-reviewed lead-lag. Pump.fun's DAU and share of Solana DEX activity are in
  the Q4-2024 study ([arXiv 2512.11850](https://arxiv.org/html/2512.11850v2), lead).
- **OWN:** the buyback is about 1% of HL PUMP's $143M daily notional, so buyback price pressure alone is negligible.
  The signal must come from regime, not flow.

**Pre-registerable rule (12 configs).**
- **Signal:** the z-score of pump.fun daily revenue (DefiLlama) or hourly curve SOL inflow (our recorder), against
  a trailing 28-day mean.
- **Basket legs:** long when z ≥ k, short when z ≤ −k, on an equal-weight Lighter basket (FARTCOIN, PUMP, WIF,
  1000BONK, PENGU, USELESS, POPCAT, SPX), hedged 1:1 against Lighter SOL.
- **PUMP leg:** PUMP − SOL on revenue z only.
- **Grid:**
  - k ∈ {1, 2} × H ∈ {1 d, 3 d} × target {basket, PUMP}, SOL-hedged = 8;
  - plus the unhedged basket at both k × H = 4;
  - **12** in total.
- **Daily version:** backfillable. **Hourly version:** forward only, a separate later registration.

**Trades/day.** Daily signal × 2 targets. Non-overlapping episodes at |z| ≥ 1 occur on about 30% of days, which
gives about 0.3–0.6 per day. 50 trades come from history easily; forward is slow.

**Gross vs cost.**
- **Cost:** Lighter 0 bp plus about 2–5 bp of spread per leg crossing, so about 10–20 bp per hedged round trip.
  HL taker alternative: about 25 bp.
- **Gross:** the meme basket's daily moves are 3–8%. A rank IC of only 0.03–0.05 would give about 15–40 bp per
  episode, so the ratio is about 1–3×.

**Kill risk.**
- **Reverse causality is the most likely failure:** meme prices pump first and launches follow, so the signal lags.
- One correlated bet per day.
- Regime shifts, such as the 2025 LetsBonk share swing.
- **Kill test:** on train, the IC of the signal on next-day basket return must exceed that of the same-day
  basket's own return (a simple momentum control). Otherwise stop.

**Data.**
- **Daily:** DefiLlama pump.fun revenue (948 days) and volume (891 days), OWN 200. Perp prices from the Binance
  archive (1d/1h klines, 2024→) as the history proxy, executed on Lighter forward.
- **Splits:** train to 2025-12-31; validation 2026-01-01 to 2026-03-31; holdout ≥ 2026-04-01.
- **DuckDB:** only the hourly forward variant uses our curve tape. Oct 1–5 is too short for train/validation.

### Idea 4. Days-old survivors of migration, gated by activity and holder growth (H-SURVIVOR). Category (a)

**Mechanism.** The hazard of dying falls steeply with age:
- 68.7% of pump.fun tokens stop trading on day 0 and 80.4% by day 1;
- 4.55% are still trading at 90 days
  ([CoinGecko via Crypto Briefing](https://cryptobriefing.com/pump-fun-token-survival-rate-study/),
  [KuCoin flash](https://www.kucoin.com/news/flash/coingecko-analysis-68-67-of-pump-fun-tokens-stop-trading-on-launch-day),
  leads; 18.67M tokens, Jan 2024–Jun 2026).

Iteration 8 decided at 1–24 h after migration. This idea decides at **24–48 h of pool age**, among pools that are
still active and growing, and holds for days. At this horizon latency is irrelevant and pool depth cuts impact.

**OWN-PRECHECK: universe size.** Pools with ≥ 10 trades and ≥ 5 traders in the hour before the decision age, and
pool reserve ≥ 200 SOL (about 2.3k SOL market cap):

| pool creation day | at 24 h | at 48 h |
|---|---|---|
| Oct 1 | 4 | 5 |
| Oct 2 | 17 | 0 |
| Oct 3 | 19 | 4 (partial) |

With the ≥ 10 trades filter alone: 10–71 a day at 24 h.

**Pre-registerable rule (12 configs).**
- **Decision age A:** active as above, pool reserve ≥ P, and the growth gate: distinct traders in the last 6 h ≥
  those in the prior 6 h. In forward runs, Jupiter `tokens/v2` `stats6h.holderChange > 0` replaces this.
- **Entry:** 0.5 SOL on PumpSwap, next trade after the decision.
- **Exit:** hold H with a −50% stop.
- **Grid:**
  - A ∈ {24, 48} h × P ∈ {200, 400} SOL × H ∈ {24, 72} h, with the growth gate = 8;
  - plus A = 24 h without the gate, at both P and H = 4;
  - **12** in total.

**Trades/day.** About 5–20. Validation inside the tape (Oct 3, 24 h, P = 200) is only n ≈ 19, which is
inconclusive. This idea is effectively **forward-first**: about 1–2 weeks to 50.

**Gross vs full cost.**
- **Cost:** about **2.65%** round trip at 0.5 SOL (1.00–1.10% fee tier per side, 0.1–0.25% impact, 0.4% tips).
- **Gross needed:** a mean of ≥ +5–6% over 24–72 h.
- **Plausibility:** only if the post-24 h survivors' right tail (a few 3–10× runners) outweighs continued decay.

**Kill risk: high.**
- Iteration 8's 24 h medians were −61% to −99%. Survivors may simply be slower deaths.
- n is small.
- Results ride on the top 3 trades, which the bar's ex-top-3 test exists for.

**Data.**
- **Decision features:** DuckDB (`amm_pools`, `amm_trades`).
- **Outcomes beyond Oct 5 03:42:** GeckoTerminal hourly OHLCV (200; 180-day limit is fine).
- **Splits:** Oct 1–2 pools for train, Oct 3 pools for validation, then forward. Outcomes for Oct 3 pools at
  48 h + 72 h are complete only after about Oct 8.

### Idea 5. On-chain CEX deposit and withdrawal flow of Solana memes, traded on Lighter perps (H-CEXDEP). Category (b)

**Mechanism.** A large SPL transfer of a meme into an exchange deposit address usually precedes a sell on that
exchange. A large withdrawal to a fresh wallet usually follows a buy. Solana settles in about 0.4 s and is fully
public, so the transfer is visible minutes before the CEX order flow ends. We trade only the perp, on Lighter (0 bp)
or HL (4.5 bp). This takes no DEX-side position and puts nothing near anyone's swap, so it is not MEV.

**Evidence.**
- **Practitioner:** exchange inflows as a bearish signal ([Bitcoinist](https://bitcoinist.com/solana-bearish-whale-26-million-binance-deposit/amp/),
  [Nansen](https://nansen.ai/post/forecasting-crypto-trends-5-proven-strategies-for-predicting-whale-movements);
  leads, marketing-grade).
- **Academic:** BTC-only and multi-day, with weak results ([JUTIF LSTM study](https://jutif.if.unsoed.ac.id/index.php/jurnal/article/view/5436), lead).
- **Labelling method:** the deposit-address heuristic. Exchanges create per-customer deposit addresses that forward
  funds to hot wallets (Victor 2020, as summarised in [Tutela, arXiv 2201.06811](https://arxiv.org/pdf/2201.06811), lead).
- **No memecoin-specific study was found. The prior is low–medium.**

**Pre-registerable rule (12 configs).**
- **Universe:** WIF, BONK, PENGU, FARTCOIN, PUMP, TRUMP, POPCAT, USELESS and SPX.
- **Hot-wallet labels:** taken from public explorer labels (leads). Each must be verified on-chain by its sweep
  pattern before use.
- **Deposit addresses:** learned on prior data only. An address qualifies if it forwarded ≥ 95% of received tokens
  to a verified hot wallet within 24 h, at least twice.
- **Signal:**
  - a transfer of ≥ Q USD from a non-exchange address into a deposit address → **short**;
  - or ≥ Q USD out of a hot wallet to a non-exchange address → **long**.
- **Execution:** Lighter perp at detection + 2 s.
- **Exit:** at + H.
- **Grid:** Q ∈ {$250k, $1M} × H ∈ {15, 60, 240} min × direction {deposit-short, withdrawal-long} = **12**.

**Trades/day.** Unknown. The first pre-check is a count from 30 days of hot-wallet ATA signatures. A guess of
5–30 a day across 9 coins at ≥ $250k needs confirming.

**Gross vs cost.**
- **Cost:** Lighter round trip about 4–10 bp of spread, 0 fee; HL about 11–13 bp.
- **Gross:** a $1M sell is several times a day's Lighter volume in SPX, POPCAT or USELESS (OWN: Lighter 24 h volume
  $4k–$155k on these three). On CEX books it is smaller, but still a plausible 10–50 bp at 1 h. That would be a ratio of
  about 2–5×.

**Kill risk.**
- Most large flows are market makers moving inventory between venues. That is non-directional, and they hedge
  first.
- OTC and custody rotations.
- Whale-alert services already broadcast these transfers, so the signal may be priced.
- Public RPC rate limits (429 on `getTokenLargestAccounts`). A keyed RPC is a project-owner decision
  (`docs/RESEARCH_PLAN.md`, decision 3).

**Data.**
- Solana RPC (`getSignaturesForAddress` on hot-wallet ATAs for history; `logsSubscribe` forward).
- Perp prices from the Binance archive 1m klines (train/validation proxy) and the HL/Lighter recorders (forward).
- Not in DuckDB.
- **Splits:** train 2026-01-01 to 02-15; validation 02-16 to 03-31; holdout ≥ 04-01.

### Idea 6. The announcement-to-launch window of new perp listings for Solana memes (H-ANNWINDOW). Category (a)

**What is new against earlier rounds.**
- **H-LIST** (round 2): buy at the announcement, exit at +15/60 min.
- **H-LISTSHORT:** short after the perp opens.

This idea holds **only between a CEX's perp-launch announcement and the moment the perp starts trading**. Binance
posts the start time in the announcement. Inside that window there is new attention and no new short-selling
venue. Once the perp opens, short-sale-constraint relief begins, which is the LISTSHORT mechanism. So the window is
where long spot should be best, and it ends before the known reversal.

**Evidence.**
- **Anecdotes** (selection-biased leads): MOODENG +90%
  ([CoinGape](https://coingape.com/moodeng-price-blows-up-90-as-binance-launches-perpetual-contract/)), CAT +40%
  ([CoinGape](https://coingape.com/cat-price-blows-up-over-40-as-binance-launches-perpetual-contract/)), BOME
  (+250% in hours, same source family).
- **Counter-evidence:** round 2's TIE/RockawayX leads say abnormal returns are concentrated *before*
  announcements.

**Pre-registerable rule (12 configs).**
- **Event:** a Binance (and, in a variant, Bybit/OKX) "Futures Will Launch … Perpetual" announcement naming a token
  whose canonical mint is an SPL memecoin. The mint map is frozen before scoring.
- **Entry:** buy on Jupiter at announcement + L.
- **Exit:** at the perp start − 5 min, at the perp start + 15 min, or at entry + 30 min.
- **Grid:** L ∈ {10, 60} s × exit (3) × venue set {Binance, Binance + Bybit + OKX} = **12**.

**Trades/day.** About **0.03–0.1**.
- OWN: Binance posted 385 perp-launch announcements since 2023-01, about 10 a month for all assets. Solana memes are
  a minority, perhaps 1–3 a month.
- Train/validation needs pooling 2023–2026. **Forward, 50 trades take years.** This is a monitor, not a bar
  candidate.

**Gross vs cost.**
- **Cost:** Jupiter round trip 24–60 bp for mid-cap memes at 0.1–5 SOL (POPCAT/SPX/MOODENG row), plus impact
  during the spike.
- **Gross (anecdotal):** tens of percent.
- **Ratio:** large *if* the edge survives the bots that scrape announcements in milliseconds.

**Kill risk.**
- Our L = 10 s is slow against announcement scrapers.
- Pre-announcement leakage.
- Selection bias in the anecdotes.
- **Spot history is the binding gap:** GeckoTerminal serves only 180 days. Older events need pool transaction
  history from RPC (429-limited) or a keyed provider.
- Not in DuckDB.

---

## 2. Ranking

| rank | idea | cat. | full round-trip cost | gross per trade (expected if real) | ratio | trades/day | DuckDB train/val? | kill risk |
|---|---|---|---|---|---|---|---|---|
| 1 | **H-PROPCARRY**: prop-AMM spot long + Lighter short, weekly episodes | b (hybrid) | 10–30 bp (Jupiter 3–17 bp OWN + Lighter spreads) | 20–50 bp/week funding + 0–20 bp premium | ~1–3× | ~0.9 | No. Lighter/HL funding API + Binance archive + GeckoTerminal. | Medium. The floor carry ≈ cost if funding sits at 0.12 bp/h; quote fade. Low income per unit of capital. |
| 2 | **H-CLEANMIG**: structural rug/overhang filter + one delayed PumpSwap entry | a | ~4.0% at 0.5 SOL (2×1.20–1.25% + 2×0.59% + 0.4% tips) | needs ≥ +17–20 pp lift over iteration 8's base | unknown, must be ≥ 2× | 30–100 | **Yes, full** (Oct 1–2 / Oct 3); check AMM tape gaps first | High. Decay is mostly not rugs. |
| 3 | **H-PUMPPULSE**: pump.fun revenue/flow z-score → meme perp basket / PUMP on Lighter | b | 10–20 bp hedged (Lighter) | 15–40 bp if IC 0.03–0.05 | ~1–3× | 0.3–0.6 | Daily: no (DefiLlama + Binance archive). Hourly: forward only. | Medium-high. Reverse causality. |
| 4 | **H-SURVIVOR**: 24–48 h-old active pools with holder growth, hold 1–3 days | a | ~2.65% at 0.5 SOL (2×1.00–1.10% + impact + tips) | needs ≥ +5–6% mean | unknown | 5–20 | Partial: features yes, outcomes via GeckoTerminal; val n ≈ 19 | High. Survivors die slower; tail-driven. |
| 5 | **H-CEXDEP**: on-chain CEX deposit/withdrawal flow → Lighter perp | b | 4–10 bp (Lighter), 11–13 (HL) | 10–50 bp if flow is directional | ~2–5× | 5–30 (to count) | No (RPC + archive); labels needed | Medium-high. MM inventory noise, RPC limits. |
| 6 | **H-ANNWINDOW**: long spot from perp-listing announcement to perp start | a | 24–60 bp + spike impact | tens of % (anecdotal) | large if real | 0.03–0.1 | No; spot history is the gap | High. Bots, leakage; n takes years. |

**Recommended order of work.**
1. **H-CLEANMIG's kill test.** It runs today on DuckDB at zero data cost.
2. **A live 0.05–0.5 SOL fill test on 2–3 prop-AMM memes.** This is the precondition for H-PROPCARRY. The cost
   claim rests on quotes only.
3. **H-PROPCARRY's funding backfill and kill test.**
4. **H-PUMPPULSE's daily IC check** (DefiLlama + Binance archive).

H-SURVIVOR and H-CEXDEP need forward data or a label set first. H-ANNWINDOW is a monitor.

---

## 3. Considered and dropped (do not re-research)

| Lead | Why dropped |
|---|---|
| **Riding PUMP buyback execution on the PUMP perp** | The buyback is $1.3–2.3M/day (leads above), about 1% of HL PUMP's $143M daily notional (OWN). Execution is spread out and timing is undisclosed (round 2). Folded into idea 3 as a regime input only. |
| **Binance Alpha listings of Solana memes** | OWN: 70 Solana tokens on the Alpha list, 39 of them listed in 2024-12/2025-01. Since 2025-06 there have been 0–3 a month (2026: 3 in January, none later). The list probably omits delisted tokens (survivorship). Covered by round 2's H-LIST monitor. |
| **Single-leg perp convergence to Jupiter spot** (fade HL/Lighter premium over on-chain spot) | OWN snapshot: the premium is persistent (+3 to +33 bp), not spiky. H-PREMCONV found spikes revert within the minute. Folded into idea 1 as an entry-premium component. |
| **CEX → prop-AMM arbitrage** | Prop AMMs are themselves oracle-updated from CEX prices, so they are the fast follower. Non-atomic CEX–DEX arbitrage is MEV-classed and excluded (round 7). |
| **Cashback coins** | Deprecated for new launches on 2026-09-12 (round 2; holder rewards replaced it and failed in iteration 14). |
| **Creator-fee claim events** | Still 0 events in train/validation (`agent_fee_claim.md`). Forward collection is running since 2026-10-05 03:09 UTC. Re-register only once there is enough forward data. |
| **Instant (single-transaction) graduations as a trade** | OWN: 46% of completions. One wallet holds most of the supply at migration, so this means trading against an insider. Used only as an exclusion in idea 2. |
| **HL perp listings (`meta` diff) → Solana spot** | HL lists with no lead time, so there is no announcement window. Rounds 2 and 9 also dropped it for low n. |
| **Lighter vs HL meme funding differential** | A venue variant of FFDIFF(-WIDE), which failed. Lighter's floor rate (0.12 bp/h) matches HL's baseline. |
| **Jupiter "verified" status changes as events** | A paid or community verification step, the same class as DEX-paid (failed, `agent_dex_paid.md`). Better used as a forward feature in idea 4. |
| **Holder-count thresholds on the bonding curve** | Covered by the heat, early-detector, aged-demand and ML-snapshot failures. Idea 4 uses holder growth only at a days-scale age. |

## 4. Gaps

- **Prop-AMM costs are quote-implied.** No swap was sent. Fill quality, quote fade and minimum sizes are unverified.
  How long these memes have been prop-AMM-quoted is unknown, so the historical cost must be an assumption.
- **Lighter funding units** are read as %/h: 0.0012 = 0.12 bp/h. This agrees with the `funding-rates` 8 h value
  (0.000096). Confirm against Lighter's docs before scoring.
- **Lighter spreads** on meme books were not measured this round.
- **Binance `fapi` REST returns 451.** Perp `onboardDate` and live premium must come from the archive or the
  websocket.
- **GeckoTerminal is limited to 180 days.** Ideas 4 and 6 lose older history.
- **Exchange hot-wallet labels on Solana** were not fetched or verified. Explorer label pages are leads only.
- **The PumpSwap tape may have hour gaps** (Oct 2 survivor counts look thin). Check `loaded_amm_files` coverage
  before any DuckDB scoring.
- Literature on days-scale memecoin survivor returns, on launchpad activity → meme-perp lead-lag, and on Solana CEX
  deposit flow was **not found** beyond the leads cited. The priors above are judgement, not evidence.
