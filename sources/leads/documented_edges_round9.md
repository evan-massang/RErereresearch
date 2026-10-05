# Documented edges, round 9: slow, wide, event-driven bets with an external reference price

_Agent: round 9, 2026-10-05 (08:20–09:15 UTC). Leads review only. No backtest was run, and no P&L, return or
win rate was computed from any price path. Web content is cited as a **lead** (`document` modality): papers,
practitioner posts and marketing pages. Official documentation is marked **DOC**. **OWN-PRECHECK** marks a
check run from this container. Every OWN-PRECHECK is descriptive (reachability, counts, spreads, history depth)
and is not a strategy test. Raw pre-check files sit in the session scratchpad only, not in the repo._

## 0. Why this round looks where it does

About 85 families have been tested or dropped (rounds 1–8, `reports/failures/`, `reports/candidates/`,
`reports/paper/`). They show one pattern:
- **Taker signals give 1–13 bp gross** against 13–60 bp costs (XSREV, ITSM, PAIRS, LSRATIO, FUNDCLOCK, QIMAKER).
- **Carry decayed** (FUNDCARRY, FFDIFF(-WIDE), SPOTCARRY, DATEDBASIS).
- **Directional factors fail out of sample.** MOMENTUM failed its holdout. UNLOCK passed only as alt-market beta
  (`reports/candidates/unlock.md`). LISTSHORT had 9 validation events.
- **Speed races are lost.** HLLAG looked good forward only because of the container clock (~2.8 s slow); our real
  latency to HL is ~190–300 ms (`reports/paper/hllag_forward_audit.md`, `hllag_scoring_amendment.json`).
  Maker ideas (HLANCHOR, QIMAKER, WICKNET(F)) die on adverse selection.

**Design rule for this round.** Each idea must have all four:
1. **Horizon of hours to weeks**, so that 0.3 s of latency is irrelevant and the cost is small against the move.
2. **A wide universe of many independent bets**, so 50 *resolved* forward trades accrue in days to a few weeks.
3. **An external reference value** for the mispricing: an options-implied probability, a physical forecast or a
   base rate. Not a pattern in our own venue's tape.
4. **Public, keyless history from before 2026-04-01** for train and validation. Data from 2026-04-01 on is the
   reserved holdout and is used here for counts only.

**Already in flight; not repeated.** HLLAG (paper), LIGHTLAG, EQLAG, LIGHTFADE, BETALAG, CLOSEDPROXY, EQOFFREV,
TWAPRIDE / TWAPFADE / TWAPXYZ, LSRATIO-LC, XS_L7_LO, and UNLOCK (a market-neutral version is recommended in its
candidate file; not repeated here).

**Scope flag for the owner.** Ideas 1–3 trade **prediction markets** (Polymarket, Kalshi), not Solana memecoins or
perps. That is outside `docs/RESEARCH_BRIEF.md`'s memecoin scope. They are listed because the orchestrating request
asked for them. If any is pursued, the change of direction should be recorded in the brief with a date. Both venues
have jurisdiction limits (Polymarket's international book excludes US persons; Kalshi requires US KYC). Anything
beyond paper needs a legal check first.

### Reachability and history from this container (2026-10-05, 08:2x–09:1x UTC, OWN-PRECHECK)

| Source | Result |
|---|---|
| **Binance CMS announcements** `www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=…` | **200, keyless.** Catalog 48 (New Cryptocurrency Listing): `total` 2,276; page 20 × 50 reaches 2023-10. Catalog 161 (Delisting): `total` 439. The last 50 delisting articles span 2026-05-25 → 2026-10-01 (about 10/month; many are margin-pair or Alpha removals, not full token delists). |
| OKX `api/v5/support/announcements` | 200. `announcements-delistings` returns only 1 page (18 items back to 2025-09-01), so its history is too short. |
| Upbit `/v1/market/all` | 200 (notices API was 403 in round 7). Bithumb `/v1/notices` returns 302 (not usable). |
| **Polymarket Gamma** `gamma-api.polymarket.com/events`, `/markets` | 200. Closed 2025 markets are listed, e.g. `bitcoin-above-111000-on-june-3` (2025-06-03), `bitcoin-price-on-june-3` (5 range markets). |
| **Polymarket CLOB** `clob.polymarket.com/prices-history` | 200. For a closed 2025-06 market, `interval=max` returned **0 points**, but explicit `startTs/endTs` with `fidelity=10` returned **504 points at 10-min spacing**. Use explicit windows. |
| **Polymarket data-api** `data-api.polymarket.com/trades?market=<conditionId>` | 200 for the same 2025 market: trade-level side, size, price and timestamp. |
| Polymarket live short-dated crypto events (ending 10-05 → 10-07) | 100 events / 287 markets in the first page: daily "above" and "price range" ladders for BTC, ETH, SOL and XRP, plus ETF-flow and MicroStrategy markets. **Median quoted spread 2.0c** on the 35 markets priced 10–90c. |
| **Kalshi** `api.elections.kalshi.com/trade-api/v2` (`markets`, `events`, `historical/trades`, `historical/markets`) | 200, keyless. `historical/trades` returns 2025-01-01 trades, including `KXBTCD-25JAN0117-T94249.99` (BTC hourly/daily threshold), each with `taker_side`. `historical/markets?series_ticker=KXHIGHNY` returned 200 settled NYC high-temperature markets. The Climate and Weather category lists **417 series**. |
| **Deribit public API** `get_book_summary_by_currency`, `get_volatility_index_data` | 200. DVOL daily from 2024-01 returned. BTC: 946 option instruments; ETH: 786; USDC-linear options on BTC, ETH, SOL, XRP, AVAX, TRX and HYPE (3,316 instruments). |
| **Deribit history** `history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time` | 200 for 2024-01-01 option trades, with `iv`, `mark_price` and `index_price` per trade. |
| Binance options archive `data.binance.vision/data/option/daily/` | Prefixes `BVOLIndex/` and `EOHSummary/` exist. Date range not checked. |
| **DefiLlama fees** `api.llama.fi/overview/fees?dataType=dailyHoldersRevenue` | 200, keyless: 1,156 protocols, **87 with > $100k holders revenue in 30 days**. `summary/fees/hyperliquid?dataType=dailyHoldersRevenue` gives 647 daily points from 2024-12-23. |
| DefiLlama `stablecoins.llama.fi/stablecoinprices` | 200: 2,101 daily rows, 219 pegged assets. |
| Snapshot `hub.snapshot.org/graphql` | 200 (governance proposals). |
| **NOAA NBM archive** `noaa-nbm-grib2-pds.s3.amazonaws.com` | 200: `blend.20250101/13/core/…` listed. |
| **Iowa Environmental Mesonet ASOS** `mesonet.agron.iastate.edu/cgi-bin/request/asos.py` | 200: hourly NYC (Central Park) temperature for 2025-01-01. |
| NWS `api.weather.gov/points/…` | 200. |
| Open-Meteo historical-forecast / previous-runs | **429: daily limit exceeded on the shared IP.** The live ensemble API answered 200. Do not rely on Open-Meteo for history; use the NBM S3 archive. |
| HL `api.hyperliquid.xyz/info` | GET returns 405 (it needs POST, as in earlier rounds). Not used this round. |

**Fee facts used below.**

| Fact | Value | Source |
|---|---|---|
| Polymarket taker fee | `fee = C × feeRate × p × (1 − p)`. feeRate: Crypto 0.07, Sports 0.05, Finance / Politics / Tech / Mentions 0.04, Economics / Culture / **Weather** / Other 0.05, **Geopolitics 0**. **Makers pay 0.** | DOC [docs.polymarket.com/trading/fees](https://docs.polymarket.com/trading/fees), fetched 2026-10-05 |
| Polymarket fee history | Taker fees started on 15-min crypto markets (early 2026), then Fee Structure V2 across most categories from **2026-03-30**. A share of fees funds maker rebates. | lead: [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates), [Action Network](https://www.actionnetwork.com/news/polymarket-fees-explained-how-polymarket-trading-fees-work-in-2026) |
| Kalshi taker fee | `$0.07 × P × (1 − P)` per contract, rounded up to the cent on the order (≈ 1.77% of price at 50c on 100 contracts). Makers were free until April 2025; **maker fees have applied since**. The current maker schedule per series must be read from Kalshi's fee schedule before freezing (not fetched this round). | lead: Bürgi, Deng & Whelan, [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf) §2 |
| Deribit options | Taker/maker ~0.03% of underlying per option, capped at 12.5% of the option price (to be confirmed against the DOC page before freezing; not fetched this round). | from memory of the published schedule, **unverified this round** |

**Consequence for back-tests.** Polymarket training data (before 2026-04) were mostly fee-free. Every Polymarket
simulation must charge today's schedule retroactively. Likewise Kalshi maker fees must be charged on pre-2025-04
data.

---

## 1. Ideas (ranked in §2)

**Common rules, as in rounds 4–8:**
- **Freezing.** Freeze `reports/hypotheses/<id>_preregistration.json` before the first scored forward record.
- **Holdout.** Data dated ≥ 2026-04-01 is reserved. Use it for trigger counts only. Scoring is forward.
- **Trade unit.** One trade is one position from entry to **resolution or exit**. Forward trades count only once
  resolved. One trade per *event cluster* where outcomes are mechanically linked: one strike ladder, one city-day,
  one token. This keeps the 50-trade bar about independent bets.
- **Fills.** No order-book history exists for Polymarket or Kalshi. Taker fills use the recorded trade or
  `prices-history` point plus half the median spread at that price. **Maker fills count only when a later
  recorded taker trade printed strictly through our price** (queue-position conservative).
- **Sizing.** $100 per trade for prediction markets (books are thin); $1k for perps and options.
- **Reporting.** By day, by event cluster and by underlying, as well as by trade. Report results without the top 3 trades.

### Idea 1. Prediction-market crypto threshold contracts against the options-implied probability (H-PMDIGI)

**Mechanism.** Polymarket and Kalshi list daily ladders on BTC, ETH, SOL and XRP: "above $K at 12:00 ET on date D"
(digital) and "price range" buckets. Kalshi also lists hourly ones (`KXBTCD`). Each contract is a cash-or-nothing
digital. A digital's fair value can be read off the **Deribit (or Binance) option smile** for the same expiry:
P(S_T > K) ≈ −∂C/∂K, from a call spread around K or from the smile's slope. Prediction-market prices are set by
retail flow that does not see the smile. When the two differ by more than costs, buy the cheap side on the
prediction market and hold to resolution. An optional arm hedges the delta with an HL or Binance perp.

**Evidence (leads).**
- [Portnaya, "Do Prediction Markets Match Option Prices? Bitcoin Threshold Evidence from Binance and Polymarket",
  arXiv 2606.19517](https://arxiv.org/abs/2606.19517) (June 2026): mean gap **5.6 pp** (t = 6.46) on the main
  BTC contract (214 hourly obs.), 6.3 pp pooled, **11 pp against Deribit**. The gap is **largest at low
  option-implied probabilities and long maturities**, mean-reverting with an **AR(1) half-life of ~4 h**. A
  delta-hedged arbitrage "remains profitable after conservative transaction costs, though with marginal
  statistical precision". **DATA-weak**: single author, three BTC contracts, mostly 2023, small n.
- FC'26 DeFi workshop paper [market-efficiency-prediction-markets.pdf](https://fc26.ifca.ai/defi/papers/market-efficiency-prediction-markets.pdf)
  (via search snippet only, not read): Polymarket "broadly tracks" Deribit option-implied benchmarks, with
  **systematic mispricing in complex / path-dependent bets, in tails and in high-volatility periods**. Simple
  directional bets align closely. **DATA-weak (not read in full).**
- [podshopguy, "Polymarket overprices volatility"](https://podshopguy.substack.com/p/polymarket-overprices-volatility)
  (2025-01-21): "what price will BTC hit" touch contracts priced well above IBIT-option-implied touch
  probabilities. **ANECDOTAL** (one example, no realised trades).
- The Polymarket longshot bias in idea 2 points the same way: low-probability strikes are overpriced.

**Data for train/validation (before 2026-04).**
- Polymarket: Gamma event lists + `prices-history` (10-min, explicit windows) + data-api trades. Verified on a
  2025-06 market. Daily BTC ladders exist from at least mid-2025.
- Kalshi: `historical/trades` with `taker_side` from at least 2025-01 for `KXBTCD`.
- Reference: `history.deribit.com` option trades with `iv` and `index_price` (verified 2024-01). Rebuild a smile
  per expiry from trades in the hour before the decision. Settlement uses Binance BTCUSDT 1m (data.binance.vision)
  for Polymarket and the CF Benchmarks index for Kalshi; this mismatch is a modelled basis.
- **Point-in-time traps.** Deribit daily expiries are at 08:00 UTC, but Polymarket resolves at 12:00 ET (16:00
  UTC in winter, 16:00/17:00 around DST). Interpolate total variance between the bracketing expiries, never use a
  later one. Use only option trades stamped before the decision.

**Pre-registrable rule (≤ 12 configs).**
- Universe: every Polymarket "above" or "price range" contract and every Kalshi `KXBTCD`/`KXETHD` threshold
  contract on BTC, ETH, SOL, XRP that resolves within 6–36 h of the decision. SOL and XRP use Deribit USDC-linear
  smiles. Skip if the option smile has fewer than 3 strikes traded within ±5% of K in the last 2 h.
- Decision times: 2 per day, 00:00 and 12:00 UTC.
- Signal: gap = q_PM − p_opt, where q_PM is the executable price (ask to buy YES, 1 − bid to buy NO).
- Trade: if |gap| ≥ θ, buy the underpriced side, **one contract per event ladder per decision** (largest |gap|).
  Hold to resolution.
- Grid: θ ∈ {3, 5, 8 pp} × execution ∈ {taker, maker at mid with a 2-h order life} × hedge ∈ {none, delta with HL
  perp} = **12 configs**.
- Costs: Polymarket crypto taker fee 0.07·p(1−p), Kalshi 0.07·P(1−P) rounded up; maker 0 (Polymarket) or the
  current Kalshi maker rate; perp hedge 4.5 bp per side + funding.

**Trades/day.** 4 underlyings × 2 venues × 2 decisions ≈ up to 16 ladders a day. If a third clear θ, that is
~5/day: **50 resolved trades in ~10 days**.

**Gross vs cost.** At a 5 pp threshold, buying at 20c costs 0.07 × 0.2 × 0.8 = 1.1c in fee plus ~1c of half-spread.
Expected gross 5c against ~2.1c cost, about 2.4× cost. In return-on-premium terms, a 5 pp edge on a 20c contract
is +25% gross. Payoffs are binary, so per-trade variance is large. 50 trades can only detect a gap of about 6 pp or
more; say so in the pre-registration.

**Kill risks.**
- The 2023 gap may have closed: Polymarket now runs liquidity rebates that pay market makers who quote off the smile.
- Risk-neutral vs physical probability: over 1 day the drift term is negligible, but the smile's risk premium
  (put skew) makes p_opt too high for downside strikes. That biases "buy YES above K" trades. Report by moneyness.
- Thin books: $100 may move the price. Use maker arms.
- Settlement mismatch (Binance 1m close vs Deribit index vs CF index) near K.

### Idea 2. Maker-side favourite buying across short-dated prediction markets (H-PMFLB)

**Mechanism.** Prediction-market prices show a **favourite–longshot bias**: contracts under 10c win far less often
than their price implies, and contracts above ~70c win slightly more often. The bias comes from takers with extreme
beliefs who overpay for longshots. Buying favourites **as a maker** (posting bids on high-probability YES or NO) earns
the bias without paying the taker fee. Many unrelated markets resolve every day (sports, economics, weather,
politics, crypto), so bets are close to independent across events.

**Evidence (leads).**
- [Bürgi, Deng & Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market"](https://www.karlwhelan.com/Papers/Kalshi.pdf)
  (UCD WP2025_19; CESifo WP 12122, 2026; [VoxEU column](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market)).
  Transaction-level data, 2021 → April 2025, 313,972 Yes/No contract prices.
  - "Average loss rates for contracts costing 10c and under are over 60%."
  - "For contracts above 70c, there is evidence of statistically significant, though small, positive post-fee returns."
  - "A 95c contract that wins 98% of the time has a pre-fee average return of 3.1%."
  - Makers average −9.64% and takers −31.46%. "On average, Makers who buy contracts costing 50c and over earn a 2.6%
    rate of return."
  - **DATA** (working paper with stated data). Sample ends before Kalshi's maker fees (April 2025) and before the
    2025 sports boom.
- Princeton senior thesis ["The Price is (Almost) Right"](https://theses-dissertations.princeton.edu/entities/publication/d5708372-5ea3-4252-b669-7f9cee07387c)
  (2026-04-09; via search snippet, not read): **Polymarket**, 188,509 resolved binary markets, Nov 2022 – Dec 2025.
  Logistic recalibration shows prices compressed toward 0.5 (longshots overpriced, favourites underpriced) "across
  all market domains", worse at longer horizons. **DATA-weak (thesis, not read in full).**
- [Quantpedia, "Systematic Edges in Prediction Markets"](https://quantpedia.com/systematic-edges-in-prediction-markets/)
  (2025-11-27): survey listing longshot bias and arbitrage as the documented edges. It notes that most arbitrage
  disappears after costs. **lead (survey).**

**Data for train/validation (before 2026-04).**
- Kalshi `historical/trades` (with `taker_side`) and `historical/markets` (settlement results), keyless, from 2025-01 at least (OWN-PRECHECK).
- Polymarket Gamma (closed markets with outcome) + data-api trades + `prices-history`.
- Train 2025-01 → 2025-09; validation 2025-10 → 2026-03.

**Pre-registrable rule (≤ 12 configs).**
- Universe: binary markets (or one leg of a mutually exclusive event) that resolve **within 1–7 days** of entry,
  with ≥ $5k traded in the prior 24 h. Exclude crypto price markets (idea 1 owns them) and markets whose resolution
  depends on a single person's discretionary statement (mention markets). Record the category.
- Entry: once per market at the first decision time (every 6 h) when the favourite side's last trade is in the
  band. Post a bid at last − 1c for 6 h. Filled only if a later taker trade prints at or below our bid.
- Grid: price band ∈ {70–85c, 85–95c, 95–98c} × venue ∈ {Kalshi, Polymarket} × category set ∈ {all, excluding
  sports} = **12 configs**.
- Cap: one position per event (the highest-priced leg in the band).
- Costs: maker fee (Polymarket 0; Kalshi current maker schedule), no exit (hold to resolution), and capital lock-up
  reported as return per day held.

**Trades/day.** Kalshi alone lists thousands of markets resolving each week. With one per event and a $5k volume
floor, an estimated **20–100 fills/day**: 50 resolved trades in **2–4 days** (counts to be confirmed on holdout-era data).

**Gross vs cost.** Paper: makers buying ≥ 50c earned +2.6% per contract after (zero) maker fees; a 95c favourite
that wins 98% earns +3.1% pre-fee. Polymarket maker cost is 0. Kalshi's maker fee is about 0.0175·P(1−P)
(if that is the current rate), so ~0.08c at 95c ≈ 0.1%. Expected net per trade is +1–3% of stake over 1–7 days.
That is small per trade but **costs are 0–0.3%, not 13–60 bp of a 1–13 bp gross**.

**Kill risks.**
- **Adverse selection on maker fills, the same failure as HLANCHOR and QIMAKER.** A resting 90c bid fills
  precisely when news makes the favourite less likely. The paper's maker returns *include* this, but only for the
  2021–2025 maker population.
- The bias was earned when Kalshi makers paid nothing. Maker fees from 2025-04 and Polymarket rebates attract
  professional makers, so the bias may be thinner now. The validation window (2025-10 → 2026-03) tests this.
- Tail outcomes: one 95c loser wipes out ~19 winners. The "profitable without the top 3 trades" rule is easy here,
  but the **"without the worst 3"** view matters more; report it.
- Resolution disputes (UMA on Polymarket) and rule ambiguity.

### Idea 3. Kalshi daily-temperature markets against the NOAA National Blend of Models (H-WXKALSHI)

**Mechanism.** Kalshi lists daily-high (and low) temperature brackets for 20+ US cities. They settle on the NWS
Daily Climate Report for a named station (e.g. Central Park). NOAA's **National Blend of Models (NBM)** publishes
calibrated forecast percentiles of the daily maximum for each station, several times a day, for free. Retail
participants anchor on the point forecast in phone apps (gridpoint, not station), which is biased at some stations.
Buy the bracket whose market price is furthest below the NBM-implied probability; hold to settlement (≤ 36 h).

**Evidence (leads).**
- [Weather Edge](https://weatheredge.it.com/) / [Weather Edge MCP](https://mcpservers.org/pt-BR/servers/rjw34/weather-edge-mcp):
  claims NWS gridpoint forecasts overshoot settlement stations (Miami by ~3°F, NYC Central Park by ~1°F) and a
  "67% win rate" from NWS + GFS ensemble picks. **MARKETING.** No sample size or returns.
- [weatherstationadvisor.com](https://weatherstationadvisor.com/home-weather-station-prediction-market/): the
  station-vs-forecast mismatch argument. **ANECDOTAL.**
- The structural support is idea 2's favourite–longshot evidence. Temperature buckets are multi-outcome ladders
  where the 1–2 longshot buckets attract lottery buyers.
- **No peer-reviewed study of Kalshi weather pricing was found.** This is the weakest-evidence idea, but its
  reference value (a calibrated physical forecast) is the most objective of the round.

**Data for train/validation (before 2026-04).**
- Kalshi `historical/markets?series_ticker=KXHIGHNY` (and the other 400+ weather series): settled markets, strikes,
  results. `historical/trades` for prices. OWN-PRECHECK: 200 markets returned for NYC.
- NBM archive on AWS (`noaa-nbm-grib2-pds`, keyless; verified for 2025-01-01). The `qmd` text products carry
  station max-temperature percentiles; GRIB2 core files are a fallback.
- Truth: IEM ASOS hourly (verified) and the archived NWS CLI products (IEM also stores them) for exact settlement.
- Train 2025-01 → 2025-09; validation 2025-10 → 2026-03 (covers both seasons).

**Pre-registrable rule (≤ 12 configs).**
- Universe: all Kalshi daily-high series for US stations with an NBM station match.
- Decision: at the first NBM cycle after 12:00 UTC on day D−1 (for day-D markets), and at 13:00 UTC on day D.
  Use only NBM runs whose file timestamp precedes the decision.
- p_NBM(bracket) by interpolating the NBM percentiles, with a ±0.5°F integer rounding rule matching the CLI.
- Trade: buy YES on the bracket with the largest p_NBM − ask (or NO on the bracket with the largest
  bid − p_NBM) if the gap is ≥ θ. **One trade per city-day.**
- Grid: θ ∈ {5, 10, 15 pp} × decision ∈ {D−1, D} × execution ∈ {taker, maker 1c inside for 3 h} = **12 configs**.
- Costs: Kalshi taker 0.07·P(1−P) rounded up; maker per the current schedule.

**Trades/day.** ~20 cities × 1 = up to 20 city-days/day; with a 10 pp threshold maybe 5–10.
**50 resolved trades in 5–10 days.**

**Gross vs cost.** At θ = 10 pp on a 30c bracket, fee 0.07 × 0.3 × 0.7 = 1.5c and ~1c spread: 10c gross against
2.5c cost. Day-ahead NBM skill is high (typical max-temperature MAE ~2°F), so a 10 pp gap is plausible on 2°F-wide
brackets. That is untested.

**Kill risks.**
- Professional weather traders (energy desks, quant hobbyists with NBM feeds) may already price the blend; the
  marketing claims suggest the edge is being sold.
- CLI settlement nuances: midnight local standard time, not daylight time; data revisions.
- Thin books: $100 per bracket may be the limit.
- Correlated errors across cities on synoptic days. Report by date cluster.

### Idea 4. One-day variance risk premium on Deribit daily options, gated by an implied-vs-forecast spread (H-VRP1D)

**Mechanism.** Option sellers earn a premium for bearing crash and jump risk. BTC's variance risk premium has been
large historically. Deribit lists **daily expiries** (08:00 UTC) on BTC and ETH, so each day is a fresh, short,
independent bet. Sell an ATM straddle (or a 0.15–0.25-delta strangle) on the next daily expiry only when implied
variance exceeds a HAR-RV forecast of the next 24 h by a margin. Hold to expiry.

**Evidence (leads).**
- [Alexander & Imeraj, "The Bitcoin VIX and its variance risk premium"](https://sro.sussex.ac.uk/id/eprint/91094/)
  (J. Alternative Investments; Deribit 2017–2022 per the snippet): BVRP ≈ 0.14 (much larger than the S&P's ≈ 0.02),
  higher in low-volatility clusters (0.17 vs 0.12). **DATA** (pre-2023 sample).
- [Harbourfront Quant, "Return and Variance Risk Premia in the Bitcoin Market"](https://harbourfrontquant.substack.com/p/return-and-variance-risk-premia-in) and
  [Amberdata on ETH vol](https://blog.amberdata.io/eth-vol-trading-out-of-favor-favorite-opportunity): practitioner
  write-ups of a positive implied-minus-realised spread. **DATA-weak.**
- No post-2024 study of **1-day** option VRP net of Deribit costs was found. **Gap.**

**Data for train/validation (before 2026-04).**
- `history.deribit.com` option trades with `iv`, `mark_price`, `index_price` (verified 2024-01); DVOL daily (verified).
- BTC/ETH 1m prices from data.binance.vision for realised variance and the HAR forecast.
- Train 2024-01 → 2025-03; validation 2025-04 → 2026-03.
- **Point-in-time:** use only trades stamped before the 08:00 UTC entry. Mark-price fills are not allowed; use the
  trade-implied bid/ask proxy (nearest trades on each side within 30 min), else skip.

**Pre-registrable rule (≤ 12 configs).**
- Universe: BTC and ETH daily options expiring 24 h after the decision (entry at 08:00 UTC, right after the previous expiry).
- Signal: s = IV_ATM(1d) − σ̂_HAR(24 h), in vol points.
- Grid: structure ∈ {ATM straddle, 0.2-delta strangle} × s threshold ∈ {0, 5, 10 vol pts} × execution ∈ {taker at
  the recorded ask/bid, maker at mid − ¼ spread} = **12 configs**. No delta hedge (keeps it one trade per day).
- Risk: 1% of capital premium per trade; skip a day if an FOMC or CPI release falls inside the option's life
  (calendar known in advance).

**Trades/day.** 2 (BTC, ETH), 7 days a week. **50 trades in ~25 days.** It is the slowest of the non-event ideas.
SOL/XRP/HYPE USDC-linear dailies exist but showed ~$100–550 of daily volume at ATM (OWN-PRECHECK), so they are not usable.

**Gross vs cost (OWN-PRECHECK snapshot, 09:0x UTC).**
- BTC-6OCT26 ATM: put 0.0047/0.0055 and call 0.0055/0.0065 BTC, mark IV 27.7%. The straddle mid ≈ 0.011 BTC
  (≈ 1.1% of spot). Crossing both spreads costs ≈ 0.0009 BTC (≈ 8% of premium); fees ≈ 2 × 0.0003 BTC (≈ 5.5%).
  **A taker round trip costs ≈ 13% of the premium collected.**
- A 14-vol-point VRP on a ~60-vol level was ≈ 40% of variance; at today's ~28 IV, if realised runs ~22–24, the
  edge is ≈ 25–35% of the variance premium, about 15–20% of the straddle premium. **The gross is only ~1–1.5× the
  taker cost**, so the maker arm is the real test.

**Kill risks.**
- Crash days: one 6–10% move loses 5–9× the premium. 50 trades may contain no tail and flatter the result; report
  the expected-shortfall view.
- The VRP may have compressed. DVOL at ~28 is far below the 2017–2022 average, and ETF-era option selling (covered
  calls) is crowded.
- Weekend and event clustering: daily options spanning weekends behave differently. Report by weekday.

### Idea 5. Exchange delisting and monitoring-tag events: short the token on a surviving perp venue, hedged against the alt basket (H-DELIST)

**Mechanism.** When Binance announces it will delist a token's spot pairs (or adds a Monitoring Tag, or delists its
USDⓈ-M perp), the token loses its main liquidity and its future index weight, and holders must exit before a
deadline. The first reaction is fast (a speed race we lose). The hypothesis is a **slower drift over the next days**
as forced holders (margin, Simple Earn, other venues' market makers) unwind. Short on HL, Bybit or OKX perps, which
outlive the Binance listing, hedged with an equal-notional long in the alt basket (the UNLOCK lesson: without the
hedge this is a beta bet).

**Evidence (leads).**
- [The Block, "Binance to delist WAVES, OMG and XEM on June 17, sparking price plunges"](https://www.theblock.co/post/298063/binance-to-delist-waves-omg-and-xem-on-june-17-sparking-price-plunges)
  (2024): WAVES −~30% on the announcement. **ANECDOTAL.**
- [eldorado.io](https://eldorado.io/en/blog/binance-delistings-impact-crypto-trading) and MEXC news reposts:
  "immediate price drops and reduced liquidity". **ANECDOTAL / MARKETING.**
- **No academic event study of post-announcement drift after 2023 was found.** The idea rests on the mechanism
  (forced, deadline-bound selling) and the abundant public event list.

**Data for train/validation (before 2026-04).**
- Events: Binance CMS catalog 161 (439 articles, keyless, OWN-PRECHECK), with release timestamps to the
  millisecond. Parse titles: "Binance Will Delist X, Y on …", "Binance Futures Will Delist USDⓈ-M XUSDT …",
  Monitoring Tag notices (Latest Binance News catalog), and separately Alpha removals and margin-pair removals,
  which are excluded.
- Prices: data.binance.vision USDⓈ-M klines (delisted symbols kept), plus HL candles via POST (5,000-candle cap,
  which covers ~3.5 days at 1m, so daily candles for history).
- Train ≤ 2025-03; validation 2025-04 → 2026-03.

**Pre-registrable rule (≤ 12 configs).**
- Event: the first announcement naming the token (spot delist, perp delist, or monitoring tag). The token must have
  a perp on a venue that stays listed through the hold.
- Entry: at the announcement + Δ, with Δ ∈ {1 h, 24 h}. This deliberately skips the first-minute race.
- Hold H ∈ {3 d, 10 d}.
- Event type ∈ {spot or perp delist, monitoring tag, all} → 2 × 2 × 3 = **12 configs**.
- Hedge: long the equal-weight top-30 Binance perp basket, same notional.
- Costs: 4.5 bp taker per side on HL plus a size-dependent impact (15–60 bp for sub-$10M ADV names), and funding
  paid or received (delisting names often carry very negative funding, which shorts pay).

**Trades/day.** Full token-level events are about **10–25 per month** across spot delists, perp delists and
monitoring tags (the 50 latest catalog-161 articles cover ~4 months, many of them multi-token batches).
**50 forward trades take ~2–4 months.** This fails the "accrue fast" goal and is ranked accordingly.

**Gross vs cost.** Moves are measured in percent: −30% on announcement day (anecdote), unknown afterwards. Costs of
~40–130 bp round trip including funding and impact are small against multi-percent drifts, if a drift exists.

**Kill risks.**
- **Squeezes.** Delisted names are illiquid and heavily shorted; funding turns very negative, and HL or Bybit may
  delist too (JELLY precedent). Stops at 35% adverse, as in UNLOCK.
- The drift may be entirely front-loaded into the first hour.
- Survivorship: perps that never existed on a surviving venue are excluded by construction.

### Idea 6. Holder-revenue (buyback, burn and distribution) yield as a market-neutral cross-sectional factor (H-HOLDREV)

**Mechanism.** Since 2024 many tokens route protocol revenue to holders: HYPE (Assistance Fund buybacks), PUMP,
JUP, RAY, AERO and others. A token's holder-revenue yield (30-day holders revenue × 12 ÷ market cap) is a
fundamental cash return. If markets under-react to it, as equity markets do to payout yield, a weekly long-high /
short-low book earns the spread with tiny cost relative to weekly moves.

**Evidence (leads).**
- [Artemis, "Crypto Factor Model Analysis"](https://research.artemis.ai/p/crypto-factor-model-analysis)
  (2025-11-14): a **Value** factor on `mc_fees_ratio` (long the lowest market cap ÷ fees), weekly rebalance,
  ≥ $100M cap, ≥ $35M weekly volume: **+9.3% annualised, 41% cumulative over ~3.9 years**. The author warns it may
  be a **sector effect** (DeFi vs L1). **DATA-weak** (vendor research, no costs stated).
- [The Defiant](https://thedefiant.io/news/research-and-opinion/crypto-token-buybacks-surge-fivefold-as-projects-return-more-revenue-to-holders):
  tokenholder payouts grew >5× since 2024, with 64% of revenue distributed across 12 major projects; many buybacks
  are funded from treasuries rather than revenue. **lead.**
- [4pillars, "Token buybacks are defense not offense"](https://research.4pillars.io/en/research/token-buybacks-are-defense-not-offense)
  (title only; the fetch returned 429): argues that buybacks do not lift prices. **lead, counter-evidence.**
- [Keyrock, "Designing Token Buybacks"](https://keyrock.com/designing-token-buybacks/). **lead.**

**Data for train/validation (before 2026-04).**
- DefiLlama `summary/fees/<protocol>?dataType=dailyHoldersRevenue` (keyless; 87 protocols with > $100k/30 d now).
  Hyperliquid's series starts 2024-12-23.
- **Vintage trap.** DefiLlama adapters are revised and back-filled. Today's series is not what was visible then (the
  same problem as UNLOCK's schedules). Lag the signal 7 days and treat any adapter whose history starts after its
  token's listing as unavailable before its first appearance. Even so, train results are an upper bound.
- Market cap from `coins.llama.fi`; prices and funding from data.binance.vision perps.
- History is short: 2024-06 → 2026-03 gives ~90 weekly rebalances.

**Pre-registrable rule (≤ 12 configs).**
- Universe: tokens with a Binance or HL perp, ≥ $100M cap, mapped to a DefiLlama protocol with holders revenue > 0
  over the prior 90 days (the yield may be 0 for the short leg's comparison set: all perp tokens with ≥ $100M cap
  and a DefiLlama fees adapter).
- Weekly (Monday 00:00 UTC) rank by yield. Long top N, short bottom N, equal notional, beta-neutral to BTC.
- Grid: N ∈ {5, 10} × yield window ∈ {30 d, 90 d} × sector control ∈ {none, rank within sector (DeFi vs other)}
  × hold ∈ {1 week, 4 weeks with 1/4 overlapping tranches} = **16. Cut to 12** by dropping the 4-week hold for the
  sector-controlled arm.
- Trade unit: one position-week per name.

**Trades/day.** 2N position-weeks per week: 10–20 a week, **50 in 3–5 weeks**. The bets are **not independent**
(one factor return per week), so 50 trades are only ~4 weekly observations. **The 50-trade bar cannot validate a
9%/yr factor.** It is listed because it is structurally different, cheap (one rebalance a week at 4.5–5 bp per
side) and has public data.

**Gross vs cost.** 9.3%/yr ≈ 18 bp per week of factor return against ~2 × 5 bp × turnover (~30%/week) ≈ 3 bp per week.
Cost is not the problem; statistical power and vintage are.

**Kill risks.** Sector confound; data vintage; a few large names dominate holder revenue (HYPE, PUMP); short leg
squeezes.

---

## 2. Ranking

| Rank | ID | External reference | Evidence (best) | Pre-2026-04 history | Configs | Resolved trades to 50 | Gross vs cost | Main kill risk |
|---|---|---|---|---|---|---|---|---|
| 1 | **H-PMDIGI** | Deribit/Binance smile → digital probability | DATA-weak: arXiv 2606.19517 (5.6–11 pp gap, 4 h half-life, net-positive delta-hedged arb) | Polymarket 10-min prices + trades (2025), Kalshi trades (2025-01+), Deribit trades with IV (2024+) | 12 | **~10 days** (~5/day) | 5 pp gap vs ~2c cost (≈ 2.4×) | gap closed since 2023 / rebate-funded makers; skew bias |
| 2 | **H-PMFLB** | Base-rate calibration | **DATA**: Bürgi–Deng–Whelan, 313,972 Kalshi contracts; Polymarket thesis (188k markets, 2022–25) | Kalshi trades + settlements (2025+), Polymarket closed markets | 12 | **~2–4 days** (20–100/day) | +1–3%/trade vs 0–0.3% maker cost | adverse selection on maker fills; bias thinned after maker fees |
| 3 | **H-WXKALSHI** | NOAA NBM percentiles | MARKETING only (Weather Edge); structural support from idea 2 | Kalshi weather (417 series), NBM S3, IEM ASOS/CLI | 12 | **~5–10 days** | 10 pp gap vs ~2.5c | pros already price NBM; thin books |
| 4 | **H-VRP1D** | HAR-RV forecast vs 1-day IV | DATA (pre-2023 BVRP ≈ 0.14); no post-2024 1-day study | Deribit trades with IV, DVOL (2024+) | 12 | ~25 days (2/day) | ~1–1.5× taker cost; maker arm decides | crash tail; VRP compressed (DVOL ~28) |
| 5 | **H-DELIST** | Alt basket (hedge) | ANECDOTAL (WAVES −30%) | Binance CMS 439 delisting articles + perp archive | 12 | **~2–4 months** | % moves vs 40–130 bp | drift front-loaded; squeezes; too slow for the bar |
| 6 | **H-HOLDREV** | DefiLlama holder revenue | DATA-weak: Artemis Value +9.3%/yr | DefiLlama (vintage-biased), Binance perps | 12 | 3–5 weeks, but ~4 independent weekly obs. | 18 bp/wk vs ~3 bp/wk | power; data vintage; sector confound |

**Recommended order of work.** Ideas 1–3 share a keyless prediction-market loader (Gamma, CLOB `prices-history`,
data-api trades, Kalshi `historical/*`) and the same conservative maker-fill rule. Build that once, under
`pipeline/sources/`. Idea 2 is the cheapest to pre-check: win rate by price band on 2025-H1 Kalshi settlements needs no
reference model. Ideas 1–3 need a **brief-scope decision by the owner first** (§0).

## 3. Considered and dropped (do not re-research)

| Lead | Why dropped |
|---|---|
| **Binance / OKX / Upbit new-listing announcements** (long the token elsewhere) | Rounds 2, 6 and 7 already dropped this: ≤ 1 event/day (catalog 48 shows ~50 articles per 2 months now, many of them perp listings of already-listed tokens), and LISTSHORT covered the direction. OKX's announcement history is only 1 page. |
| **HL perp listings** (Binance drift after HL lists a token) | A few per month; the same low-n problem as LISTSHORT. |
| **Intra-Polymarket bundle arbitrage** (negRisk sums ≠ $1) and **Kalshi–Polymarket cross-venue arbitrage** | [Saguillo et al., arXiv 2508.03474](https://arxiv.org/abs/2508.03474v1) find ~$40M extracted in Apr 2024 – Apr 2025, but [Quantpedia](https://quantpedia.com/systematic-edges-in-prediction-markets/) reports that cross-venue opportunities "typically exist only for a few seconds, at best a few minutes". That is a speed race like HLLAG. Taker fees since 2026-03-30 (except Geopolitics) take 1–1.75c per leg on multi-leg bundles. Resolution-rule mismatch across venues is an unhedgeable risk. |
| **Polymarket / Kalshi 15-min and hourly "BTC up or down"** | A seconds-scale lead from Binance is a latency race (HLLAG lesson), and the crypto taker fee peaks at 1.75c (3.5% of a 50c contract). Idea 1 uses the 6–36 h ladders instead. |
| **Kalshi Fed-decision markets vs CME FedWatch** | 8 meetings a year; fails n. |
| **Stablecoin depeg-recovery buys** (DefiLlama 219 pegged assets) | Tradable depegs on cheap CEX books (FDUSD, USDe, USDC in 2023) are a handful a year; the rest trade only on DEX pools at 5–30 bp plus impact, against professional arbitrageurs (the round-4/5 DEX cost trap). |
| **Governance / treasury events** (Snapshot proposals: fee switches, buybacks) | Snapshot is reachable, but material proposals on perp-listed tokens are a few a month and classifying "material" is subjective, so it is hard to pre-register. Folded into idea 6's slower measure. |
| **One-off buyback announcements** (PUMP, HYPE AF) | Single large-cap tokens with undisclosed execution timing (round 2). |
| **Options skew / term structure predicting BTC/ETH returns** | One bet per day per asset at most; directional (MOMENTUM-like failure risk). Idea 4 keeps the options angle market-neutral in direction. |
| **MicroStrategy purchase markets on Polymarket** | Weekly, 1–2 markets; the outcome is disclosed in an 8-K that some participants can anticipate from ATM-program filings. Low n and close to the non-public-information line. |

## 4. Gaps

- The FC'26 Polymarket–Deribit paper and the Princeton calibration thesis were seen only as search snippets; read
  them in full before freezing ideas 1 and 2.
- Deribit's and Kalshi's current fee schedules (makers in particular) were not fetched. Confirm them as DOC before freezing.
- Kalshi `historical/*` depth before 2025-01 and the boundary between `markets` and `historical/markets` were not
  mapped. Polymarket's daily crypto ladder start date was not mapped (seen from mid-2025).
- Open-Meteo history is rate-limited on the shared IP; the NBM S3 archive was listed but no `qmd` file was parsed.
- No count of resolved short-dated Kalshi/Polymarket markets per day was made for idea 2's 20–100/day estimate. It
  is an estimate, not a pre-check.
- The Binance delisting catalog was not fully parsed into token-level events; the 10–25/month figure is an estimate
  from one page of titles.
