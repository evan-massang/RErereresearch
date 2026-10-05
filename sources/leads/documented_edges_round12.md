# Documented edges, round 12: memecoin-only ideas that attack the four known failure modes

_Agent: round 12, 2026-10-05 (about 10:50–11:30 UTC, container clock). This is a leads review only. No backtest was run,
and no P&L, return, markout or win rate was computed from any price path. Web content is cited as a **lead**
(`document` modality). **DOC** marks official or protocol documentation. **OWN-PRECHECK** marks a check run from this
container. Every OWN-PRECHECK is descriptive only: reachability, counts, volumes, TVL and fee tiers. DuckDB counts
exclude the holdout (1790882100–1790899200) and everything at or after 1791072000. The pumplean tape was opened only
to list pool volumes in its first ~10 minutes of `amm_bars` (no prices, no returns), before its T0 split is fixed._

**Scope.** Memecoins only (`reports/scope_memecoins_20261005.md`).
**Excluded by brief:** launch-and-dump (including being the creator for that purpose), wash trading, sandwiching and
any other MEV, and non-public information.

## 0. What this round must get around

**Read before writing:** `CLAUDE.md`, the scope note, `reports/failures/paper_loop_20261003.md`, the titles and
verdicts of all 57 notes in `reports/failures/` (full text of cleanmig, pumppulse, propcarry, memelead, qhoi, night,
lpsell_clock and listshort), `reports/candidates/` (hlanchor, hllag_newcoins, momentum, unlock),
`reports/hypotheses/cbprem_preregistration.json` (no failure note exists yet), `reports/hypotheses/pumplean_notes.md`,
and rounds 3, 10 and 11.

**The four failure modes this round is aimed at:**

| # | failure mode | evidence | what an idea needs to beat it |
|---|---|---|---|
| F1 | Short-horizon meme-perp signals gross 1–6 bp against 3–30 bp of spread, even at 0 fee | MEMELEAD (+1–6 bp gross), XSREV, ITSM, WICKNET-F, QHOI, PREMCONV | **No taker signal at all**, or a horizon where the gross is in percent, not bp |
| F2 | Intraday, seasonal and flow signals do not survive | NIGHT (decays every half-year), QHOI (IC of the wrong sign), PUMPPULSE, CLOCK | **A cash flow** (fees, funding), or an event with a mechanism, rather than a pattern |
| F3 | pump.fun curve/AMM entries lose 13–43% per trade, and insider graduations dominate | CLEANMIG (−29% to −43%), iteration 8, SURVIVOR prior, LPSELL (price ratio 0.58 in 1 h) | **Do not be long the decay**: hedge it, short it, or sell it |
| F4 | Carry is real but about 3.5%/yr and too slow | PROPCARRY (validation +6.8 bp per weekly episode, n = 41) | **Stack a second income on the carry**, or take carry only where it is large (new listings) |

**Facts from earlier work that the ideas below build on:**
- **PumpSwap LP fee by tier (LPSELL, our own measurement).** LPs get **20 bp** in every `fee_bps` tier from 30 to 120.
  In the 125-bp tier, which holds 97% of young-pool sells, they get **2 bp**. LPSELL's pools were almost all in the 2-bp
  tier, and drift (median price ratio 0.58 over 1 h) swamped the fees.
- **Lighter meme perps cost 0 fee.** The round trip is one spread: 1.6–5.8 bp in the tight set and 10–37 bp otherwise
  (round 11).
- **Funding.** Lighter PUMP averaged about 19.8%/yr and FARTCOIN 18.6%/yr over validation (PROPCARRY). Hyperliquid
  meme perps averaged a **median 74%/yr over their first ~21 days after listing** (round 3 OWN-PRECHECK, 22 coins).
- **Jupiter round trips.** 1–17 bp for six large memes, 24–60 bp for POPCAT, SPX and MOODENG at 0.1–5 SOL, and
  100–900 bp for pump.fun graduates under $10M market cap (rounds 10 and 11).
- **GeckoTerminal serves only 180 days.** That is 2026-04-08 onward, which is inside the period that the
  archive-based families reserve as holdout (≥ 2026-04-01). Any family scored on GeckoTerminal history must declare
  its own splits in that window and state the overlap. Pre-April Solana minute data needs a keyed provider.

### OWN-PRECHECKS this round (2026-10-05, about 10:55–11:15 UTC)

| check | result |
|---|---|
| **GeckoTerminal `tokens/{mint}/pools`** for 10 perp-listed memes | 200. Each pool's TVL and 24 h volume are in the table under idea 1. **PUMP's largest pool is the PumpSwap PUMP/USDC pool: $28.1M TVL, $6.1M 24 h volume (V/TVL 0.22 a day), created 2025-07-14.** Most full-range pools of other memes turn over 0.03–0.15 of TVL a day. |
| **pumplean `amm_bars` `other_5m`**, first ~10 min (volumes only) | About 9,000 PumpSwap swaps a minute go to bars, against about 1,200 to `amm_swaps`. **Most PumpSwap flow is in old pools**, which the old DuckDB tape (pools created after Oct 1 only) never held. PUMP has **12 PumpSwap pools** in that window (89 SOL of volume in 10 min). PENGU and TROLL pools also trade. |
| **DuckDB `amm_trades`, pool-days aged ≥ 24 h** (Oct 1–3, outside the holdout) | 385 pool-days at age day 1, of which **39 are in the 20-bp LP tier** (median `fee_bps` ≤ 120). 30 of those turn over ≥ 0.5 of TVL a day, and 10 turn over ≥ 1 with ≥ 50 users. At age day 2 there are 239 pool-days, 9 in the 20-bp tier. The median aged pool turns over **0.003** of TVL a day: almost all aged pools are dead. |
| **DuckDB `curve_creates`**, name or symbol containing a perp meme's ticker (~3.6 days, 127,876 creates) | trump 971, pepe 972, doge 614, shib 588, pengu 168, fart 126, bonk 104, useless 81, troll 76, spx 20, pnut 11, moodeng 9, popcat 5. Substring matching over-counts short tickers such as "wif" (990, which includes "wife" and "swift") and "pump" (2,650). Word-boundary matching is needed. |
| **pump.fun `frontend-api-v3` coin search** | `/coins?searchTerm=…&sort=created_timestamp` returns 200 with `created_timestamp`. The `/coins/search` path returns 404. Whether the search paginates exhaustively over 2024–2026 is **unverified**. |
| **Listing announcements** | OKX `api/v5/support/announcements?annType=announcements-new-listings` returns 200, but only 5 pages. Bybit `v5/announcements` returns **403**, and Upbit notices return **403** (as in round 7). The Binance CMS catalog returns 200 (round 10: 1,200 articles back to 2023-01). |
| **Recorders** | The full recorder is **not running**, so `fee_events` (creator-fee claims) is not being collected. pumplean subscribes to the pump and PumpSwap program logs but does not decode claim events. |

---

## 1. Ideas (ranked in §2)

### Idea 1. Delta-hedged PumpSwap LP: earn the 20-bp LP fee and short-side funding, hedge the price on Lighter (H-LPHEDGE). Attacks F1, F3 and F4

**What is new.** LPSELL was an **unhedged** LP in **young** pools in the **2-bp** tier, so it was long the decay. This
idea is an LP only where a liquid perp exists to short away the token exposure. What remains is fee income, minus
loss-versus-rebalancing (LVR), minus hedge costs, plus the funding the short receives. No taker signal is involved
(F1). There is no net long exposure to decay (F3). The funding carry is stacked on top of LP fees (F4).

**Mechanism.**
- A constant-product LP holds value V split evenly between the token and the quote. Its token delta is V/2.
- Short V/2 of the token's perp and rebalance as the delta drifts.
- The hedged P&L is then, per unit time: fees − LVR (σ²/8 of pool value per unit time, in the continuous limit) −
  hedge rebalancing cost + funding on the short.
- The quote side is USDC for the PUMP/USDC pool, so no SOL leg is needed. SOL-quoted pools would need a SOL perp leg
  as well.

**Evidence (leads).**
- LVR: [Milionis, Moallemi, Roughgarden & Zhang, arXiv 2208.06046](https://arxiv.org/abs/2208.06046). A hedged LP
  earns fees minus σ²/8.
- Fees and block time: [Milionis, Moallemi & Roughgarden, arXiv 2305.14604](https://arxiv.org/abs/2305.14604).
  "faster blockchains will result in reduced LP losses"; with fees, LVR is scaled down by the fraction of blocks that
  offer a profitable arbitrage. Solana's ~400 ms slots are the favourable case.
- **Against:** about half of Uniswap V3 LPs lose money, and LPs are profitable only in low-volatility pools
  ([Heimbach, Schertenleib & Wattenhofer, arXiv 2205.08904](https://arxiv.org/abs/2205.08904), round 3).
- **Fee split:** 0.20% to LPs and 0.05% to the protocol on standard pools; canonical pump.fun pools add a creator fee
  ([madeonsol](https://madeonsol.com/blog/what-is-pumpswap), [medium/jump_bit](https://medium.com/@jump_bit/pumpswap-lp-fees-explained-how-to-earn-125-day-from-your-memecoin-pool-6cf6b2c2a918);
  leads). Deposits are permissionless (round 3, Solana Tracker docs). LPSELL measured 20 bp on-chain in tiers 30–120.
  The PUMP/USDC pool's tier is **not yet measured**.
- **No study of hedged memecoin LP returns was found.**

**OWN-PRECHECK: candidate pools** (GeckoTerminal, 24 h snapshot; TVL and volume in $):

| meme (perp on Lighter) | best full-range LP-able pool | TVL | 24 h volume | V/TVL a day |
|---|---|---|---|---|
| **PUMP** | **PumpSwap PUMP/USDC** | 28.1M | 6.11M | **0.22** |
| PUMP | Meteora PUMP/SOL (2 pools) | 2.0M / 0.53M | 0.97M / 1.35M | 0.47 / 2.56 |
| PENGU | PumpSwap PENGU/SOL | 1.75M | 0.13M | 0.08 |
| USELESS | Raydium USELESS/SOL | 5.31M | 0.79M | 0.15 |
| FARTCOIN | Raydium Fartcoin/SOL | 9.16M | 0.78M | 0.09 |
| WIF | Raydium $WIF/SOL | 7.03M | 0.58M | 0.08 |
| SPX | Raydium SPX/SOL | 2.48M | 0.24M | 0.10 |
| POPCAT | Raydium POPCAT/SOL | 4.17M | 0.21M | 0.05 |
| MOODENG | Raydium MOODENG/SOL | 3.09M | 0.10M | 0.03 |

Concentrated pools (Orca, Meteora DLMM, Raydium CLMM) show V/TVL up to 5.7, but their LVR scales with the
concentration too. "humidifi" is a prop AMM and cannot be LP'd.

**Arithmetic (not a backtest) for PUMP/USDC.**
- **Fees:** 20 bp (assumed) × 0.22 = **about 4.4 bp of pool value a day** (about 16%/yr).
- **Funding:** the short is half the LP value. At Lighter PUMP's ~19.8%/yr validation mean, that is about **+2.7 bp a
  day** on LP value.
- **LVR:** at a PUMP daily σ of 4–6% (to be measured), σ²/8 is **2–4.5 bp a day**, before the fee/block-time
  reduction.
- **Hedge:** rebalancing crosses the Lighter PUMP spread (about 1.6–3.3 bp) on the traded delta only. At a 2–5% delta
  band that is about **0.3–1 bp a day**.
- **Entry and exit:** a balanced deposit and withdrawal pays no swap fee, only Solana fees.
- **Net if the assumptions hold: about +1 to +5 bp a day on LP value, roughly 4–18%/yr on 1.5× capital (LP plus 1x
  short collateral).** The ratio of gross income (fees + funding) to LVR + hedge cost is about **1.3–3×**.
- For Raydium full-range pools at V/TVL 0.03–0.15 and a 25-bp fee (LP share to verify), fees are 0.6–3 bp a day,
  against meme LVR of 3–8 bp a day. **Most of them should lose.** That is a prediction the test can falsify.

**Pre-registerable rule (12 configs).**
- **Pools:** P1 = PumpSwap PUMP/USDC only; P2 = every full-range (CPMM) pool of a Lighter-listed meme with TVL ≥ $1M
  and trailing 7-day V/TVL ≥ v.
- **Entry:** deposit balanced at day start (00:00 UTC). Short the token on Lighter for exactly the LP's token holding
  at 1x collateral. For SOL-quoted pools, also short Lighter SOL for the SOL side's beta, or exclude them in a
  variant.
- **Rebalance:** whenever |LP token units − short units| > b × LP token units.
- **Exit:** withdraw at day end (unit = pool-day), or immediately if the pool's 1 h volume is 0 or the perp is paused.
- **Grid:** pools {P1, P2 with v ≥ 0.1} × band b ∈ {2%, 5%, 10%} × hedge {perp only, perp + SOL leg / USDC-only} ×
  hold {1 d, 7 d} = **2 × 3 × 1 × 2 = 12** (the hedge arm applies to P2 only; P1 is USDC-quoted).
- **Trade unit:** a pool-day.
- **Kill test (train):** the mean of (measured LP fee growth + funding) must be ≥ 1.5 × (realized LVR + hedge cost)
  per pool-day. Otherwise stop.

**Trades.** P1 gives 1 pool-day a day plus about 5–30 hedge rebalances. P2 gives 3–8 pool-days a day. In
"trades/week" this is about **7 (P1) to 50 (P2) pool-days**.

**Data for train and validation.**
- **Exact accounting (forward):** the pumplean tape. `other_5m` bars carry open and last reserves and buy/sell volumes
  for every PumpSwap pool, including PUMP/USDC. The fee growth of k between bars gives the LP fee exactly, as LPSELL
  did with swaps.
- **Gap:** bars cannot chain individual swaps. The pool's LP bps should be confirmed once from ~50 decoded swaps
  (`getTransaction` on the pool, public RPC).
- Lighter PUMP 1m candles and hourly funding (APIs 200, from 2025-09) give the hedge leg.
- **72 h only gives one train day and one validation day per pool.** The pumplean split plan applies, and the result
  is a kill test, not a bar.
- **Longer history:** GeckoTerminal minute OHLCV and volume for each pool (180 days, so 2026-04-08 onward) gives fees
  as rate × volume. LVR comes from the minute path; it is understated at 1 min, so stress it ×2.
  - Splits for this family: train 2026-04-08..2026-07-15, validation 2026-07-16..2026-09-30.
  - This **overlaps the ≥ 2026-04-01 holdout that other archive families reserved**. This family has never looked at
    that period. State the overlap in the pre-registration.
- **Not in DuckDB:** the old tape holds only pools created from Oct 1.

**Kill risk: medium.**
- PUMP/USDC flow may be mostly arbitrage against prop AMMs. That is toxic, and it is exactly the LVR term, so the kill
  test catches it.
- The fee tier is unverified.
- Gap risk: an overnight −30% move hedged in 5-min steps.
- Venue risk: Lighter, plus PumpSwap program risk.
- Capacity is large ($28M TVL), but our deposit dilutes the fee share only slightly.
- **Even if it works, it is a few %/yr to the high teens. It beats PROPCARRY's 3.5%/yr only if V/TVL holds.**

---

### Idea 2. Delta-neutral listing carry: short a newly listed meme perp, long the same token on Jupiter, for the first 7–21 days (H-LISTBASIS). Attacks F3, F4 and the LISTSHORT squeeze

**What is new.** This is an evidence-based iteration of three failures:
- **LISTSHORT** (`agent_listshort.md`): the post-listing short was mostly crypto beta and squeezes, with full-window
  MAE up to +10,988% and 3–19 liquidations at 1x. A spot long removes both.
- **FUNDCARRY/PROPCARRY**: carry at the 0.12 bp/h floor is too slow (F4). Funding is high exactly in the first weeks
  after a listing: **median 74%/yr over the first ~21 days** across 22 HL Solana-meme listings (round 3
  OWN-PRECHECK). That is 1.4% a week, against a 3.5%/yr carry.
- **Spot cost:** prop AMMs and Jupiter now quote 24–100 bp for mid-cap memes (round 10), against FUNDCARRY's
  0.5%/side.

**Mechanism.** At a new perp listing, leveraged longs crowd in. Arbitrage capital is slow to arrive, and shorting is
otherwise constrained. Funding and the opening perp premium pay whoever supplies the short side hedged (BIS WP 1087:
carry is driven by trend-chasing small investors and scarce arbitrage capital).

**Evidence (leads).**
- [Schmeling, Schrimpf & Todorov, BIS WP 1087](https://www.bis.org/publ/work1087.htm): carry of 10% to 40–60% a year,
  and high carry predicts crashes.
- [He, Manela, Ross & von Wachter, arXiv 2212.06888](https://arxiv.org/abs/2212.06888): perp–spot deviations and
  high-Sharpe arbitrage that shrinks over time.
- Our round-3 OWN funding table: FARTCOIN 91%, GOAT 100%, MOODENG 72%, PNUT 55%, CHILLGUY 134%, PUMP 83%/yr in their
  first ~21 days. VINE and JELLY were negative.

**Pre-registerable rule (12 configs).**
- **Event:** the first trading hour of a perp on an SPL meme, on HL or Binance (each venue-coin pair is one event).
  The token must have an LP-able Solana pool with Jupiter round trip ≤ 100 bp at $5k.
- **Entry:** at listing + N. If trailing funding since open (annualized) is ≥ F: short the perp at 1x full
  collateral and buy the same units on Jupiter.
- **Exit:** at listing + Z days, or earlier when 24 h funding falls below 10%/yr or the basis widens ≥ 5 pp against.
  Close both legs together.
- **Grid:** N ∈ {4 h, 24 h} × F ∈ {30%, 80%} × Z ∈ {7, 21} d × venue {HL only, HL + Binance} = **16**. Trim to 12 by
  fixing venue = HL + Binance for Z = 21. State which 12 before scoring.

**Trades/week.** About 0.5–1 Solana-meme listings a week across HL and Binance (LISTSHORT: 51 earliest listings in
2.5 years of train and 9 in 9 months of validation). Counting second-venue listings roughly doubles that.

**Gross vs full cost.**
- **Gross:** 7 days at 74%/yr is about **140 bp**, and 21 days about **425 bp**, plus any opening premium that
  converges.
- **Cost:** a Jupiter round trip of 24–100 bp, a perp round trip (HL 12 bp, Binance 12 bp, Lighter one spread), and a
  basis-risk allowance.
- **Ratio about 1.5–5×.** Capital is 2× notional.

**Data.**
- HL `fundingHistory` (full history, paged) and Binance archive `fundingRate` and klines, both cached in part
  (`data/raw/web/propcarry`, `momentum`, `hyperliquid`).
- **Spot leg:** Binance spot (if listed), MEXC spot klines (cached for some coins), and GeckoTerminal for 2026-04 on.
  **Pre-2026-04 Solana DEX spot is a proxy**, as in PROPCARRY.
- **Splits:** train ≤ 2025-06-30, validation 2025-07-01..2026-03-31, holdout ≥ 2026-04-01.
- **Contamination:** the 23 HL listings that round 3 looked at are "seen". Report them separately, as LISTSHORT did.

**Kill risk: medium-high.**
- **Validation n is the known killer:** LISTSHORT had only 9 clean validation listings. Pooling venue-pairs helps
  but correlates episodes.
- Basis blowouts at listing: the spot can be the thing that squeezes.
- HL funding caps.
- Delistings (JELLY).
- **Kill test (train):** the mean funding received over held days minus measured cost must be ≥ 50 bp per episode.

---

### Idea 3. Short the parent meme perp when its pump.fun copycat wave peaks (H-NARRPEAK). Attacks F2 and F3 (short side)

**What is new.**
- Every pump.fun narrative test so far (sympathy, narrative_cluster) was **long a curve token** after a leader moved.
  Same-narrative tokens drifted down.
- This idea takes the **short side of the liquid parent** (PENGU, TRUMP, FARTCOIN, BONK, WIF, PEPE, DOGE, SHIB,
  USELESS, TROLL, SPX, POPCAT, MOODENG) on a perp, at days horizon. It uses pump.fun launch activity as a
  retail-attention gauge.
- It is not PUMPPULSE: that used aggregate revenue to time a basket. This is a **per-coin** attention measure.

**Mechanism.**
- Copycat launches ("baby PENGU", "TRUMP 2.0") are created when a parent's narrative is at peak retail attention.
- When the copycat rate spikes and then turns down, retail attention has peaked. Attention-driven buying reverses
  over days to weeks.

**Evidence (leads).**
- **For reversal:** Da, Engelberg & Gao, "In Search of Attention", *J. Finance* 2011. An attention spike predicts
  higher prices for about 2 weeks, then a reversal.
- **For reversal:** Barber, Huang, Odean & Schwarz, *J. Finance* 2022. Robinhood top-mover herding is followed by
  −4.7% over 20 days (round 3).
- **Against (sign risk):** Liu & Tsyvinski, "Risks and Returns of Cryptocurrency", *RFS* 2021. In crypto, investor
  attention predicts **positive** returns at 1–2 weeks. Hence the "peak passed" condition and a long control arm.
- **No study of pump.fun copycats as an attention measure was found.**

**OWN-PRECHECK.**
- Copycat counts over 3.6 days of `curve_creates` (§0): roughly 270/day for TRUMP and PEPE, 170/day for DOGE, about
  45/day for PENGU, and 2–5/day for SPX, MOODENG and POPCAT.
- A historical series looks possible from pump.fun's search API (`created_timestamp`, 200). Exhaustiveness is
  unverified.

**Pre-registerable rule (12 configs).**
- **Signal:** c_i(d) = new pump.fun coins on day d whose name or symbol matches coin i's ticker as a whole word (case
  folded; a frozen alias list such as "fart"/"fartcoin"). z = ln(1 + c) against its trailing 28 days.
- **Peak:** z(d−1) ≥ k, and c(d) < c(d−1).
- **Trade:** short coin i's perp at 00:00 UTC of d+1, hold H, with a stop at +25%.
- **Hedge:** none, or long an equal-weight basket of the other memes (removes sector beta).
- **Grid:** k ∈ {2, 3} × H ∈ {1, 3, 7} d × hedge {none, basket} = **12**.
- **Control (not a config):** the same events with a long sign, and a placebo using random non-peak days.

**Trades/week.** About 2–6 events across 13 coins (to be counted from the history before scoring).

**Gross vs full cost.**
- **Cost:** Lighter one spread (2–10 bp, 22–37 bp for SPX and POPCAT) plus 1–7 days of funding (+ for shorts most of
  the time). Binance proxy: 10–25 bp.
- **Gross if real:** a 3–7 day meme sd of 10–20%. A modest reversal of 1–3% per event is **100–300 bp, a ratio of
  10× or more.** This is the idea in this round with the most room over cost, and the least prior evidence.

**Data.**
- **Signal history:** the pump.fun search API (adapter needed: `pipeline/sources/pumpfun_search.py`) back to 2024-01.
  Cross-check counts against DuckDB `curve_creates` for Oct 1–5 and pumplean `curve_creates` forward.
- **Prices:** Binance USDT-M 1h/1d archive (cached for most coins), Lighter 1m from 2025-09.
- **Splits:** train ≤ 2025-06-30, validation 2025-07-01..2026-03-31, holdout ≥ 2026-04-01 (not fetched).

**Kill risk: medium-high.**
- The search API may be capped or ranked, so it would not give complete daily counts. **Kill before any price is
  loaded** if the API's Oct 1–5 counts differ from `curve_creates` by more than 30%.
- Ticker ambiguity (DOGE, PEPE and TRUMP are generic words on pump.fun).
- The Liu–Tsyvinski sign.
- **Kill test (train):** the short arm's mean gross must exceed 2 × cost, with the long control arm's gross lower, in
  both train halves.

---

### Idea 4. Weekly cross-sectional selection among large, aged Solana memes, beta-hedged on Lighter (H-AGEDXS). Attacks F1, F2 and F3

**What is new.**
- The project's momentum candidate is on broad Binance perps, long-only and fragile (`reports/candidates/momentum.md`).
- All pump.fun tests traded young tokens at seconds to hours.
- This idea selects **once a week** among Solana memes that are already large, liquid and old: pump.fun graduates and
  other Solana memes with market cap ≥ $20M, age ≥ 30 days, and Jupiter round trip ≤ 60 bp at 5 SOL. At that size,
  round 11 found exits at 4–51 bp.
- It holds the top names and shorts a Lighter meme basket against them, so it is not long the sector's decay.
- **Turnover is low.** With 30–50% weekly name turnover and 5–60 bp round trips, cost is about **5–30 bp a week of
  capital**.

**Mechanism.** Weekly crypto cross-sectional momentum and MAX effects:
- Liu, Tsyvinski & Wu, "Common Risk Factors in Cryptocurrency", *J. Finance* 2022 (cited from memory, link not checked this round):
  1–4 week momentum (lead).
- High-MAX coins earn **+1.5% to +3.0% a week** more (Özdamar, Akdeniz & Şensoy 2021, round 3, lead).

Survivor tokens with sustained holder growth would be the "real communities". The hedge isolates selection from the
meme beta.

**Pre-registerable rule (12 configs).**
- **Universe:** frozen weekly, point in time. CoinGecko category `solana-meme-coins` ∪ `pump-fun`, mcap ≥ $20M, ≥ 30
  days of history, Jupiter quote ≤ 60 bp. In history, quotes are unavailable, so use a volume ≥ $2M/day proxy.
- **Signal:** S ∈ {R28 (4-week return), MAX7 (max daily return of the last week), holder growth 7d (forward only)}.
- **Portfolio:** long the top quintile, equal weight. Short Lighter's equal-weight tight-set meme basket at
  β-matched notional (60-day β).
- **Grid:** S {R28, MAX7} × rebalance {weekly, bi-weekly} × hedge {basket, SOL} × size {top 5, top quintile} = **16**.
  Freeze 12 by dropping SOL-hedge × bi-weekly.

**Trades/week.** About 5–10 name changes; episodes are coin-weeks, about 10 a week.

**Gross vs cost.**
- Gross if the published effects transfer: about 50–300 bp a week of hedged excess.
- Cost: 5–30 bp a week, plus the hedge's 2–10 bp.
- **Ratio about 2–10×. The prior that it transfers to Solana memes is low–medium.**

**Data.**
- CoinGecko `coins/{id}/market_chart` daily (public; the 365-day depth for keyless or demo access is **to verify**).
- GeckoTerminal for 180 days. Jupiter `tokens/v2` for holder growth (forward).
- **Survivorship is the main data risk:** category membership is today's, and dead coins may be missing. A
  point-in-time universe needs CoinGecko's inactive list or our own weekly snapshots from now on.
- **Splits:** about 2025-10..2026-01 train and 2026-02..2026-03 validation if 365 days are available. Otherwise
  forward-first. Holdout ≥ 2026-04-01.

**Kill risk: medium-high.**
- Survivorship.
- Momentum crashes (meme rotations).
- Small universe: about 25–60 names.
- One correlated bet per week, so effective n is weeks.
- The momentum candidate's validation pass leaned on funding and squeeze episodes that do not exist in spot.

---

### Idea 5. Pooled-venue listing announcements → long Solana spot until trading starts (H-LISTANN). Attacks F1 and F2 (event with % moves)

**What is new.** Round 10's H-ANNWINDOW used Binance perp announcements only, which is 0.03–0.1 events a day. This
pools every **public, timestamped announcement** of a new listing for an SPL meme that is already trading on Solana:
- Binance spot, futures and Alpha (CMS catalog 48, 200);
- OKX spot and perps (announcements API, 200, but only 5 pages: recent history only);
- Bybit and Upbit **only if** reachable (both 403 here);
- Coinbase "roadmap" posts if a timestamped public feed is found.

Execution is a Jupiter buy at announcement + L. The exit comes **before** the market opens, where "sell the news"
(LISTSHORT, The TIE) starts.

**Evidence (leads).**
- [Benedetti & Nikbakht, "Returns and network growth of digital tokens after cross-listings" (SSRN 3267392)](https://papers.ssrn.com/abstract_id=3267392):
  3,625 tokens, 108 marketplaces; a **16% market-adjusted return in the two weeks around the first cross-listing**.
- Anecdotes: MOODENG +90%, CAT +40% (round 10; selection-biased).
- **Against:** round 2's The TIE and RockawayX leads put most of the move **before** the announcement (leakage).

**Pre-registerable rule (12 configs).**
- **Event:** the announcement timestamp (venue API or CMS). The SPL mint map is frozen from contract addresses.
- **Entry:** buy on Jupiter at +L.
- **Exit:** at trading start − 5 min, trading start + 15 min, or entry + 60 min.
- **Grid:** L ∈ {15 s, 120 s} × exit (3) × venue {Binance only, all reachable} = **12**.

**Trades/week.** About 0.5–2 pooled.

**Gross vs cost.**
- Cost 24–100 bp (mid caps), plus spike impact. Gross anecdotally 5–40%.
- **Ratio large if real, but n is not.**

**Data.**
- Announcements from the Binance CMS (2023→) and OKX.
- **Spot:** GeckoTerminal minute data (180 days only), so historical events are 2026-04→ only: perhaps 10–25 events.
  Pre-April minute spot needs a keyed provider.
- Binance spot and perp archives cover only after the event.

**Kill risk: high.**
- Announcement scrapers act in milliseconds, so our 15 s is slow.
- Leakage.
- **50 events take about a year forward.** This is a **monitor**, as round 10 said. Pooling venues only shortens the
  wait.

---

### Idea 6. Unhedged LP only in aged PumpSwap pools in the 20-bp tier (H-LPAGED). Attacks F3 directly, as an evidence-based iteration of LPSELL

**Reason to iterate (parent: H-LPSELL, failing run `evidence_lpsell_train.json`).**
- 97% of LPSELL's sells were in the 125-bp tier, which pays LPs 2 bp. Its pools were 10 min–4 h old, where drift is
  steepest.
- This idea moves to the **20-bp tier** (pool market cap ≥ 420 SOL), which pays 10× the LP fee per unit volume, and to
  pools aged **≥ 3 days**, past the steepest hazard (68.7% of tokens stop trading on day 0, CoinGecko via round 10).
- Most PumpSwap flow is in old pools (§0), which the old tape never covered.

**Rule (12 configs).**
- **Eligible:** age ≥ A, median `fee_bps` ≤ 120 over the last 24 h, trailing 24 h V/TVL ≥ v, and ≥ 50 distinct users
  per day (`n_users` in bars).
- **Entry:** a balanced deposit at the decision (swap half at the exact pool price with fee).
- **Exit:** at H, or when the mid falls to 0.6× entry (the LPSELL stop).
- **Benchmarks:** hold-token and cash, as LPSELL.
- **Grid:** A ∈ {3 d, 7 d} × v ∈ {0.5, 2} × H ∈ {24 h, 72 h} × stop {on, off} = **16**. Freeze 12 by dropping
  stop-off at H = 24 h.

**Trades/week.** On the old tape, 30 pool-days a day met V/TVL ≥ 0.5 in the 20-bp tier at age day 1, and almost none
by day 2. With all PumpSwap pools in pumplean bars, the count at ≥ 3 days is **unknown**. Count it on the first 24 h
before freezing. A guess is 5–30 a day.

**Gross vs cost.**
- **Fees:** 20 bp × V/TVL of 0.5–2 = **10–40 bp a day**.
- **Cost:** two deposit/withdraw transactions plus the half-swap (fee 1.0–1.2% on half the stake is **0.5–0.6%**, the
  binding cost) and tips.
- **The LP must lose less than about 0.2–0.4% a day to drift.** Iteration 8's 24 h medians were −61% to −99% for
  1–24 h old pools. Aged pools must be far flatter than that.

**Data.**
- pumplean `amm_bars` `other_5m` (all PumpSwap pools, 5-min reserves and volumes) and `amm_swaps` for pools < 7 days.
  Pool age comes from `amm_pools`, the seed tables, or GeckoTerminal `pool_created_at`.
- Splits follow `pumplean_notes.md` (train first 24 h covered, validation next 24 h). 72-h holds do not fit the
  72-h tape, so H = 72 h is forward-only.
- DuckDB `amm_trades` contributes only pools created from Oct 1 that reach age ≥ 3 days by Oct 4 (very few).

**Kill risk: high.** LPSELL's reading ("the LP gives up the upside and eats the drift") probably holds at any age.
**Kill test (train):** mean fee growth must be ≥ 2 × mean LP drift loss (1 − √(P1/P0)) per pool-day. Otherwise stop.
It is ranked low but cheap: the data is being recorded now.

---

### Idea 7. Creator-fee annuity tokens: aged graduates whose creator keeps claiming fees and never sells supply (H-FEEANNUITY). Creator-fee economics, not launch-and-dump

**What is new.**
- COMMITTED_DEV tested "dev holds" at 60–300 s and was priced in. FEE_CLAIM had 0 events.
- Under the Project Ascend tiers a creator earns up to **0.95% of volume** at 420–1,470 SOL market cap
  ([Blockworks](https://blockworks.com/news/pumpdotfun-fee-model), lead). A creator who claims repeatedly over days
  and does **not** sell supply is running the token as a fee business: their income depends on continued volume.
- **Decision at age ≥ 3 days, hold days.** We are only a holder, never the creator.
- Tokens whose creator sells after claiming are logged as the "avoid" set and used as the control.

**Evidence.** Fee tiers only (Blockworks, The Defiant; leads). **No study of creator behaviour after graduation was
found. The prior is low.**

**Rule (12 configs).**
- **At age A ∈ {3, 7} d:** the creator made ≥ m ∈ {2, 4} claim events on distinct days, has a net token balance
  change ≥ 0 since migration, and ≥ 50 daily users.
- **Trade:** buy 0.5 SOL and hold H ∈ {3, 7, 14} d.
- **Grid:** (A, m) restricted to 4 pairs × H (3) = **12**.

**Trades/week.** Unknown. A guess is 2–10.

**Gross vs cost.** The cost is the survivor round trip of about **2.65% at 0.5 SOL** (round 10). The gross needed is
≥ +5% over the hold. This is a selection bet against the F3 decay.

**Data.** Not collected now.
- The full recorder (`fee_events`) is stopped, and pumplean does not decode claims.
- Requires adding claim-event decoding to pumplean (the same program logs are already subscribed). History is
  possible through RPC `getSignaturesForAddress` on creator-vault PDAs, slowly at 429.
- **Forward-only:** about 2–4 weeks to n = 50.

**Kill risk: high.** It is still long a decaying asset, and creators can claim and then dump. **Kill test (train):**
the qualifying group's median 3-day return must be ≥ 10 pp above the age-matched non-qualifying group's.

---

## 2. Ranking

The cost is the full round trip for the stated trade unit. "Train/val data" says what exists now.

| rank | idea | failure modes attacked | full cost | gross if real | ratio | trades/week | train/val data | kill risk |
|---|---|---|---|---|---|---|---|---|
| 1 | **H-LPHEDGE**: PumpSwap PUMP/USDC (and perp-meme CPMM pools) LP, delta-hedged short on Lighter | F1, F3, F4 | LVR 2–4.5 bp/day + hedge 0.3–1 bp/day | fees about 4.4 bp/day + funding about 2.7 bp/day | about 1.3–3× | 7 (P1) to 50 (P2) pool-days, plus rebalances | pumplean bars (exact, 72 h) + GeckoTerminal 180 d (overlaps archive holdout era) + Lighter 1m/funding | Medium: toxic arb flow = LVR; unverified LP tier; still only about 4–18%/yr |
| 2 | **H-NARRPEAK**: short parent meme perp after its pump.fun copycat wave peaks | F2, F3 | 2–37 bp + funding | 100–300 bp/event if reversal | 10×+ | 2–6 | pump.fun search API (exhaustiveness unverified) + Binance archive; DuckDB/pumplean for cross-check | Medium-high: search-API completeness; attention-momentum sign (Liu–Tsyvinski) |
| 3 | **H-LISTBASIS**: short new meme perp + long Jupiter spot, first 7–21 days | F3, F4 | 40–120 bp | 140–425 bp of funding per episode | 1.5–5× | 0.5–2 | HL/Binance funding (full) + spot proxy (MEXC/Binance; GeckoTerminal from 2026-04) | Medium-high: validation n (LISTSHORT had 9); basis blowouts |
| 4 | **H-AGEDXS**: weekly top-quintile aged Solana memes, short Lighter meme basket | F1, F2, F3 | 5–30 bp/week + hedge | 50–300 bp/week if effects transfer | 2–10× | about 10 coin-weeks | CoinGecko daily (depth to verify) + GeckoTerminal; survivorship | Medium-high: survivorship, momentum crashes, small universe |
| 5 | **H-LISTANN**: Jupiter long from pooled-venue listing announcement to trading start | F1, F2 | 24–100 bp + spike impact | 5–40% (anecdotal) | large | 0.5–2 | Binance CMS + OKX; spot minute data only from 2026-04 | High: scrapers, leakage, n takes about a year (monitor) |
| 6 | **H-LPAGED**: unhedged LP in ≥ 3-day-old, 20-bp-tier PumpSwap pools | F3 (iterates LPSELL) | about 0.6% per entry/exit + tips | 10–40 bp/day in fees | unknown (drift) | about 35–200 pool-days (to count) | pumplean bars (72 h; H = 72 h forward-only) | High: drift still dominates |
| 7 | **H-FEEANNUITY**: buy aged graduates whose creator claims fees and never sells | F3 | about 2.65% at 0.5 SOL | needs ≥ +5% | unknown | 2–10 | Forward only; claim decoding must be added to pumplean | High: still long decay |

**Recommended order of work.**
1. **H-LPHEDGE kill test** on the pumplean train day. It needs no new data except ~50 decoded PUMP/USDC swaps to
   confirm the LP bps. Run the GeckoTerminal 180-day version only after the pre-registration declares its splits and
   the holdout-era overlap.
2. **H-NARRPEAK data-completeness check**: compare pump.fun search counts with `curve_creates` for Oct 1–5. Only if
   they agree, backfill the history and run the train kill test.
3. **H-LISTBASIS:** count clean venue-listing events per split before anything else. If validation n is below about
   40, stop, as LISTSHORT did.
4. Add claim-event decoding to pumplean now (cheap), so that H-FEEANNUITY has data in 2–4 weeks. Count H-LPAGED's
   eligible pools on the first 24 h.

## 3. Considered and dropped (do not re-research)

| lead | why dropped |
|---|---|
| Unhedged LP in young pools, or LP "selected" by flow features | LPSELL: 0/18, and the hold-token benchmark beat the LP. Idea 6 changes the tier and age; anything younger repeats LPSELL. |
| LP in pools with heavy volume-bot or wash flow "to collect the bot subsidy" | Fees from wash volume do accrue to LPs, but choosing pools *for* wash activity puts us in the dev's wash scheme (rule excludes wash trading). Wash-heavy pools are also where devs dump. Not pursued. |
| Hedging a pump.fun token's LP with a meme-perp basket | The idiosyncratic decay of a single graduate is not spanned by WIF, BONK or FARTCOIN (PUMPPULSE and SOLLEAD found no channel). The hedge would remove beta only, which is not the loss. |
| Concentrated-liquidity (Orca/DLMM) range orders as "limit sells" on perp memes | The same economics as idea 1, with LVR scaled by the concentration. Add it as a later arm only if idea 1 passes. |
| Shorting pump.fun tokens directly | No borrow, lending market or perp exists for curve or young PumpSwap tokens. |
| Short meme perps after Upbit or Coinbase listing pumps ("sell the news") | LISTSHORT's n and squeeze problem. Upbit notices are 403 here. Folded into idea 5 as the exit timing only. |
| Selling DOGE options volatility (variance premium) | Out of the Solana/pump.fun focus. Option-data reachability for DOGE was not checked. Revisit only if the user widens scope to meme options. |
| Creating tokens to earn creator fees | Being the creator for a launch-and-dump is excluded by the brief. A non-dump "run a token" business is not a trading strategy. |
| Holder-reward tokens | Iteration 14: the yield is an order of magnitude below cost and decay. |

## 4. Gaps

- **PumpSwap PUMP/USDC LP fee bps are not measured.** 20 bp is assumed from LPSELL's tiers and docs. Confirm from
  decoded swaps.
- **PUMP's realized σ** (for LVR) was not computed. That is deliberate: it is a price statistic and belongs to the
  pre-registered kill test.
- **GeckoTerminal "reserve_in_usd"** for concentrated pools is total deposits, not active liquidity. The V/TVL values
  for those pools are not comparable with full-range pools.
- **pump.fun search API:** pagination depth, ranking and rate limits are unverified.
- **CoinGecko keyless history depth**, and whether inactive coins remain in categories, were not checked.
- **Bybit and Upbit announcements are 403.** OKX returns only 5 pages.
- **No pre-2026-04 Solana minute spot** without a keyed provider (Birdeye, Codex). This limits ideas 1 (history),
  2 (spot leg) and 5.
- **Literature** on hedged memecoin LP returns, pump.fun copycat attention and creator-fee behaviour was not found.
  The priors above are judgement, not evidence.
