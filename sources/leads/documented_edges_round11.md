# Documented edges, round 11: memecoin-only ideas testable within about 3 days

_Agent: round 11, 2026-10-05 (10:00–10:40 UTC, container clock, which runs about 2.8 s slow). Leads review only.
No backtest was run, and no P&L, return, markout or win rate was computed from any price path. Web content is
cited as a **lead** (`document` modality). **DOC** marks official documentation. **OWN-PRECHECK** marks a check run
from this container. Every OWN-PRECHECK is descriptive: reachability, event counts, spreads, quoted costs and
volumes. None is a strategy test. Raw pre-check files are in the session scratchpad only, not in the repo. The
memelag recorder's parquet files were **not opened** (H-LIGHTLAG-MEME / H-LIGHTFADE-MEME declare them unopened);
Lighter spreads below come from a separate REST snapshot._

**Scope.** Memecoins only (`reports/scope_memecoins_20261005.md`).

## 0. Why this round looks where it does

**Read before writing:** rounds 1–10, `reports/failures/` (all 55 notes, including cleanmig, pumppulse,
propcarry, the hllag_newcoins addendum and `paper_loop_20261003.md`), `reports/candidates/` and
`reports/paper/hllag_forward_audit.md`.

**What the failures leave open:**
- **Pump.fun spot.** Seconds-to-hours signals on the curve and in fresh PumpSwap pools are priced in, and the
  ~2.6–4.7% round trip kills everything else. CLEANMIG lost 29–43% per trade on train. PUMPPULSE found "no next-day
  information" in pump.fun revenue and asked not to retry without new evidence.
- **Meme perps.** The losers so far:
  - 1-minute cross-asset regressions (XLEAD);
  - hour-scale reversal and momentum (XSREV, ITSM, MOMENTUM);
  - funding carry and funding-clock trades (FUNDCARRY, FFDIFF, FUNDCLOCK, PROPCARRY: validation n = 41);
  - wick and flush catching (FLUSH, WICKNET, WICKNET-F);
  - premium spikes (PREMCONV).

  Most failed because their **gross was 0–5 bp against a 9–15 bp taker round trip**.
- **The one changed cost fact:** Lighter charges **0 bp** on meme perps. The cost is now only the spread. So this
  round wants gross edges of about 6–30 bp per trade, at horizons where our 0.2–0.3 s latency (plus the 300 ms bump)
  matters little or is part of the measured fill.

**Pending tests, not repeated here:**
- H-LIGHTLAG-MEME and H-LIGHTFADE-MEME (own-coin Binance→Lighter catch-up and Lighter-local fades);
- H-TWAPRIDE / H-TWAPFADE on HL meme perps;
- the H-HLLAG forward test;
- the lean pump.fun recorder (72 h).

Every idea below is a **different signal** from those. Where an idea iterates on a failure, the evidence-based
reason is stated.

### Costs (the yardstick)

**Lighter meme perps (DOC: 0/0 fees for Standard accounts, 300 ms taker speed bump).**
- OWN-PRECHECK 2026-10-05 10:2x UTC: `api/v1/orderBooks` shows `taker_fee 0.0000` and `maker_fee 0.0000` on PUMP,
  DOGE, WIF, SPX, POPCAT and 1000FLOKI.
- OWN-PRECHECK, REST `orderBookOrders` snapshot (one Monday-morning sample, so indicative only):

| coin | spread (bp) | top-5 bid / ask depth ($) | | coin | spread (bp) | top-5 bid / ask ($) |
|---|---|---|---|---|---|---|
| PUMP | 1.6 | 32.5k / 2.5k | | WIF | 5.8 | 23.2k / 25.2k |
| DOGE | 2.2 | 6.4k / 4.6k | | 1000BONK | 10.0 | 7.6k / 27.6k |
| FARTCOIN | 2.7 | 13.7k / 7.0k | | USELESS | 10.2 | 6.9k / 6.4k |
| 1000SHIB | 3.4 | 2.8k / 12.7k | | SPX | 22.0 | 104k / 93k |
| TRUMP | 3.8 | 5.0k / 1.4k | | 1000FLOKI | 23.7 | 38k / 38k |
| 1000PEPE | 4.4 | 16.4k / 19.4k | | POPCAT | 36.7 | 35.5k / 35.7k |
| PENGU | 5.1 | 7.7k / 5.3k | | | | |

- **"Tight set"** (spread ≤ 6 bp): PUMP, DOGE, FARTCOIN, 1000SHIB, TRUMP, 1000PEPE, PENGU, WIF. A taker round trip
  costs about **one full spread, 1.6–5.8 bp**, plus impact above the top level. At $1k the top level is usually
  enough; TRUMP's ask side was thin at $1.4k.
- Holds over an hour also pay or receive hourly funding (floor about 0.12 bp/h; FARTCOIN, USELESS, SPX and PUMP
  0.2–0.3 bp/h, round 10 OWN).
- **HL** (comparison only): 4.5 bp taker per side, about 11–13 bp all-in round trip.

### Reachability (OWN-PRECHECK, 2026-10-05 10:0x–10:3x UTC)

| source | result |
|---|---|
| `data.binance.vision` USDⓈ-M **aggTrades** (daily and monthly) | 200 for DOGE, 1000BONK, POPCAT, WIF, SPX (`trades` as well) and SOL spot. A daily meme file is 0.4–10.7 MB zipped (DOGE 2026-03-02: 4.2 MB; 1000PEPE: 10.7 MB). A monthly WIF file (2025-06) is 112 MB. |
| `data.binance.vision` USDⓈ-M **bookTicker** | **404 for every date tried from 2024-04-01 on.** 2024-03-01 is 200 (94 MB for one WIF day). So no historical Binance quotes exist for 2024-04 onward; trades only. |
| `data.binance.vision` `metrics` | 200 (WIF 2026-03-01) |
| HL `candleSnapshot` 1m | 200, but only about the last 5,000 candles: a window 9–10 days back returned `[]`. HL 1m history is therefore forward-only. |
| HL `recentTrades` | 200, and each trade carries `users: [buyer, seller]`. |
| HL `clearinghouseState` for any address | 200, unauthenticated |
| **Lighter `api/v1/candles`** (`market_id`, `resolution=1m`, ms timestamps) | **200, with 1m OHLCV back to at least 2025-09-01** (FARTCOIN). `api/v1/candlesticks` returns 403. **This is new: a historical execution-venue price series for Lighter memes.** |
| Coinbase Exchange public `products/<X>-USD/candles` (1m, 300 per call) and `stats` | 200, keyless. All 12 memes are listed: DOGE, SHIB, PEPE, BONK, WIF, PENGU, TRUMP, FARTCOIN, POPCAT, PUMP, FLOKI and SPX. WIF and USDT-USD have 1m history at 2025-02-03; FARTCOIN, PENGU and PUMP do not at that date (listed later). |
| Jupiter `lite-api.jup.ag` `tokens/v2/search`, `toptrending`, `swap/v1/quote` | 200 with a User-Agent |
| Disk | **3.9 GB free** (252 GB volume at 90%). Archive downloads must be streamed and reduced; the zips cannot be kept. |

---

## 1. Ideas (ranked in §2)

### Idea 1. Cross-meme diffusion at seconds: a liquid meme leader moves, laggard memes are taken on Lighter at 0 bp (H-MEMEDIFF). Category (b)

**What is new.**
- **H-XLEAD** (`agent_xlead.md`) regressed 1-minute meme returns on lagged 1-minute BTC, SOL and meme-index
  returns, executed at HL's 9 bp plus slippage. It failed:
  - out-of-sample R² < 0;
  - shock-minute predictions reversed;
  - the own-lag variant was +14 bp gross at delay 0 but +1.4 bp at delay 1, so **whatever predictability exists
    lives inside the minute.**

  That is the evidence-based reason to go to seconds.
- **H-LIGHTLAG-MEME** (pending) is **own-coin**: Binance WIF moves, take Lighter WIF. This idea is **cross-coin**,
  and it explicitly **excludes** events where the follower's own Binance price has already moved. So the two
  ideas cannot share trades.

**Mechanism.** Memes move as a sector. Market makers in thin meme books re-quote off their own coin's flow first.
The cross-asset update comes from slower inventory or hedging flow, so a follower's price catches up to a leader
shock over seconds to minutes.

**Evidence.**
- A tick-level BTC→Cardano lead of **16–118 s, average about 57 s** (Anderson, *Investment Management and
  Financial Innovations* 2023, [businessperspectives.org](https://www.businessperspectives.org/images/pdf/applications/publishing/templates/article/assets/17735/IMFI_2023_01_Anderson.pdf);
  lead, peer-reviewed but small).
- "Binance led Lighter for 23 of 29 assets, by about 100 ms" ([Arrakis](https://arrakis.finance/blog/crypto-price-discovery),
  round 7, lead). This is own-coin, so it says nothing about cross-coin lags.
- **No meme-specific seconds-scale cross-asset study was found. The prior is low–medium.**

**OWN-PRECHECK: leader event counts.** Binance USDⓈ-M aggTrades, 1-s last-trade grid, |2-s log move| ≥ θ,
non-overlapping within 10 s. Counts only; no follower outcome was looked at.

| leader | Mon 2026-03-02, ≥15 / ≥25 / ≥40 bp | Sat 2026-03-07, ≥15 / ≥25 / ≥40 bp | notional that day |
|---|---|---|---|
| DOGE | 44 / 5 / 0 | 8 / 3 / 0 | $646M / $296M |
| 1000PEPE | 138 / 10 / 0 | 25 / 9 / 6 | $444M / $210M |
| SOL (for idea 5) | 73 / 3 / 0 | 9 / 1 / 0 | $3.1B / $1.0B |
| FARTCOIN (for scale; a follower here) | 427 / 75 / 8 | 67 / 20 / 9 | $45M / $27M |

**Pre-registerable rule (12 configs).**
- **Leaders:** L1 = DOGE ∪ 1000PEPE (an event in either), or L2 = SOL. SOL is kept as a leader arm here; idea 5
  is its own registration, so freeze only one of the two SOL arms.
- **Followers:** the tight set minus the leader: PUMP, FARTCOIN, 1000SHIB, TRUMP, PENGU, WIF, plus DOGE or
  1000PEPE when it is not the leader.
- **Point-in-time beta:** β_f = trailing-7-day OLS beta of the follower's 1-min Binance return on the leader's.
- **Event:** the leader's 2-s move |r_L| ≥ θ, at most one per 10 s.
- **Follower eligible if both:**
  - its own Binance 2-s move in the leader's direction is < β_f·θ/3 (it has not followed yet);
  - β_f ≥ 0.4.
- **Entry:** a Lighter taker order in the leader's direction, arriving at event + 600 ms (our ~300 ms plus the
  300 ms bump). Fill at the Lighter touch at arrival, walking the book for $1k.
- **Exit:** taker at +H.
- **Grid:** leader {L1, L2} × θ ∈ {15, 25} bp × H ∈ {5 s, 30 s, 120 s} = **12**.

**Trades/day.** From the counts above, with about 3–6 eligible followers per event:
- θ = 15: roughly **100–500 a day** on weekdays and 40–150 on weekends.
- θ = 25: roughly 15–60 a day.

**Gross vs full cost.**
- **Cost:** about 1 spread, **1.6–5.8 bp** (median about 3.5 bp).
- **Gross if real:** with β ≈ 0.6–0.9 and an unfollowed follower, the full catch-up is 9–22 bp. Capturing a third
  to a half after the 600 ms delay gives **about 4–10 bp**. The ratio is about **1.2–3×**.

**Kill risk: medium-high.**
- Cross-asset MM quoting may already be sub-second, as Arrakis implies for own-coin.
- XLEAD's shock-minute reversals.
- Last-trade bounce in the historical proxy.
- **Pre-registered kill test (train, Binance proxy):** the mean signed follower return from +600 ms to +30 s after
  θ = 15 L1 events must be ≥ 1.5 × the median tight-set Lighter spread (about 5 bp). Otherwise stop before scoring
  configs.

**Data and splits.**
- **History:** Binance aggTrades, streamed and reduced to 100-ms last-price and signed-volume grids per coin. Day
  sample fixed by seed before download:
  - train: 20 days from 2025-07-01 to 2025-12-31;
  - validation: 20 days from 2026-01-01 to 2026-03-31;
  - holdout ≥ 2026-04-01, not downloaded.

  About 25 MB a day for 10 coins, so about 1 GB processed in total.
- **The history is a proxy.** It scores follower *Binance* prices and charges the Lighter spread. Lighter had no
  quote history before the recorders.
- **Forward:** the memelag recorder (Binance + Lighter + HL bbo for 11 memes) plus multivenue (PUMP, DOGE). First
  24 h of a new frozen window for train, next 24 h for validation. Score on `ts_us` only, never mixing it with
  exchange timestamps (clock audit).

---

### Idea 2. Overnight seasonality in meme perps at 0 bp: long 22:00–24:00 UTC (H-NIGHT). Category (b)

**What is new.** No time-of-day hypothesis has been tested in this project:
- H-CLOCK was about pump.fun burst periodicity;
- H-ITSM was first-session → last-session momentum;
- the quarter-hour effect was dropped at 0.5 bp per boundary.

This is a fixed-window calendar effect. It was not worth testing at HL's 11–13 bp. At 1.6–6 bp it is.

**Evidence.**
- Padyšák and Vojtko, "Seasonality, Trend-following, and Mean reversion in Bitcoin" ([SSRN 4081000](https://ssrn.com/abstract=4081000),
  via [Quantpedia](https://quantpedia.com/strategies/intraday-seasonality-in-bitcoin); lead, working paper):
  - BTC 2015–2021;
  - "the returns for 22:00 and 23:00 (UTC +0) seem to be the most economically significant";
  - long 22:00 → 00:00 earned about 33%/yr, Sharpe 1.58, max drawdown −34%.

  That is about **9 bp per daily trade on BTC.**
- **Against:** Baur, Cahill, Godfrey and Liu ([UWA repository](https://research-repository.uwa.edu.au/en/publications/bitcoin-time-of-day-day-of-week-and-month-of-year-effects-in-retu/),
  lead) find "time-varying effects but no consistent or persistent patterns".
- **Liquidity side:** volume and spreads follow human trading hours (Aleti and Mizrach 2021, as summarised in
  [arXiv 2109.12142](https://arxiv.org/pdf/2109.12142), lead).
- **No meme-perp study was found.**

**Pre-registerable rule (12 configs).**
- **Window:**
  - W1: long at 22:00, exit at 24:00 UTC (the paper's window);
  - W2: long 23:00 → 24:00;
  - W3: long 14:00 → 16:00 UTC (the practitioner "US session" claim, [CoinDesk 2024-02-15](https://coindesk-coindesk-prod.cdn.arcpublishing.com/markets/2024/02/15/bitcoins-rise-to-52k-is-driven-by-strong-us-demand-the-coinbase-price-premium-suggests),
    lead).
- **Universe:**
  - U1: the tight set;
  - U2: every Lighter meme perp that also has a Binance archive. The list is frozen from today's
    `orderBooks` before any return is computed.
- **Hedge:** none, or short Lighter BTC at 1:1 notional, to isolate meme-specific seasonality from crypto beta.
- **Grid:** window (3) × universe (2) × hedge (2) = **12**.
- **Trade unit:** one coin-window.

**Trades/day.** 8 (U1) or about 15–20 (U2) coin-legs a day per config. U2 meets the ≥ 15/day requirement; U1 is
just under it. History gives thousands of trades.

**Gross vs full cost.**
- **Cost:**
  - one spread (U1 1.6–5.8 bp; U2 includes POPCAT, SPX and FLOKI at 22–37 bp, so charge each coin its own measured
    spread);
  - 2 h of funding (about 0.3–0.6 bp);
  - plus the BTC leg's spread (Lighter BTC under 1 bp) when hedged.
- **Gross if real:** about 9 bp on BTC; memes with beta 1.5–2 would give **about 12–20 bp**. Ratio about **3×**
  in U1.

**Kill risk: medium-high.**
- Calendar effects decay once published (2022). Baur et al. find no persistence.
- One correlated bet per window, so the effective n is days, not coin-legs. Report the per-day t-statistic as
  well as per-trade PF.
- **Kill test:** on train, the W1/U1 mean gross per coin-leg must be ≥ 2 × the mean charged cost, and positive in
  at least 2 of 3 half-years. Otherwise stop.

**Data and splits.** Fastest to test of all ideas here.
- **Binance 1h klines are already cached:**
  - `data/raw/web/xsrev/k1h/` (208 HL-listed symbols, 2023-01 to 2026-03);
  - `data/raw/web/pumppulse/k1h/`.
- **Lighter `candles` 1m** (from at least 2025-09) re-scores validation on the execution venue's own prices.
- **Splits:** train ≤ 2025-06-30; validation 2025-07-01 to 2026-03-31; holdout ≥ 2026-04-01, not downloaded.
  PUMPUSDT only from 2025-07-10 (`agent_pumppulse.md`).

---

### Idea 3. Quarter-hour opening order imbalance → 4–12 h continuation on meme perps (H-QHOI). Category (b)

**What is new.** Round 4 dropped the quarter-hour effect because the *opening return* is about 0.5 bp per
boundary. The same paper's second result was not examined: **opening order imbalance predicts returns 4–12 h
ahead.** That horizon makes latency irrelevant, and on Lighter the cost is one spread plus funding.

**Evidence.** Kim and Hansen, "The Quarter-Hour Effect: Periodic Algorithmic Trading and Return Predictability in
Cryptocurrency Futures" ([arXiv 2607.09426](https://arxiv.org/html/2607.09426); lead, preprint).
- Six Binance perps, **including DOGE**.
- **Opening imbalance:** volume-normalised taker flow in the first 10 s after minutes 0, 15, 30 and 45.
- "Opening order imbalance predicts returns over four to twelve hours, with much weaker effects at finer
  clock-time frequencies" (abstract, verbatim).
- "the coefficient is small or negative at short horizons but becomes positive at medium horizons in every
  market."
- Significant at 95% "for four of the six contracts at every horizon."
- **No basis-point size is reported** for the 4–12 h effect.

**Pre-registerable rule (12 configs).**
- **Per coin, from aggTrades:**
  - imb_q = (taker buy − taker sell) ÷ total volume in [boundary, boundary + 10 s);
  - S = mean of imb_q over the last 16 boundaries (4 h), z-scored against the coin's trailing 30-day S
    (point in time).
- **Decisions:** at 00, 04, 08, 12, 16 and 20 UTC. If |z| ≥ k, take a position in sign(z) on Lighter, one
  position per coin, held H.
- **Control arm** (tests the paper's specificity): the same S built from *all* 10-s windows, not only openings.
  This can come from 1m klines' taker-buy volume.
- **Grid:** k ∈ {1, 2} × H ∈ {4, 8, 12} h × source {openings, all-window control} = **12**.
- **Universe:** the tight set (DOGE, 1000PEPE, 1000SHIB, FARTCOIN, WIF, PENGU, TRUMP, PUMP).

**Trades/day.** At k = 1 about 32% of decisions fire: 8 coins × 6 × 0.32 ≈ **15/day** at H = 4 h, falling to about
8/day at H = 12 h. k = 2 gives about 2–4/day. It is history-rich.

**Gross vs full cost.**
- **Cost:** one spread (1.6–5.8 bp) plus 4–12 h of funding on the paying side (±0.5–3.6 bp).
- **Gross:** 4–12 h meme moves have an sd of about 150–400 bp. A rank IC of 0.02–0.04 gives about **5–15 bp**.
  The ratio is about **1–3×**. Unproven: the paper gives no magnitude.

**Kill risk: medium.**
- Six large contracts in the paper; memes may differ.
- The effect may be tiny.
- **Kill test:** on train, the openings arm's IC must exceed the control arm's IC, and the k = 1, H = 4 h gross must
  be ≥ 2 × cost. Otherwise stop.

**Data and splits.**
- **Data:** Binance aggTrades, streamed and reduced to boundary-window sums. A full daily set for 8 coins is about
  5–25 MB zipped a day. Train 2025-01 to 2025-06 and validation 2025-07 to 2026-03 is about 455 days, roughly
  6–10 GB streamed. That is several hours of download, but **nothing is kept beyond about 50 MB of aggregates**
  (3.9 GB free).
- **Splits:** as idea 2.

---

### Idea 4. US-retail demand gauge: the Coinbase meme premium leads meme perps by 15–60 min (H-CBPREM). Category (b)

**What is new.**
- H-PREMCONV traded *Binance perp vs Binance spot* premium spikes back to zero, with two legs.
- Round 6 dropped "Binance spot as a leader for perps".

This idea is directional. It uses a **different venue's retail demand**: Coinbase USD spot, which is US retail,
against the Binance USDT perp, which is global and levered. The perp is traded toward the Coinbase signal.
Coinbase now lists all 12 target memes (OWN), which was not true for most of them a year ago.

**Mechanism.** US retail buys memes on Coinbase. Arbitrage between Coinbase and offshore perps is slowed by
USD/USDT rails, so a persistent Coinbase premium measures net US demand that offshore prices absorb over the next
minutes to hours.

**Evidence.**
- BTC "Coinbase premium" as a US-demand gauge ([CoinDesk](https://coindesk-coindesk-prod.cdn.arcpublishing.com/markets/2024/02/15/bitcoins-rise-to-52k-is-driven-by-strong-us-demand-the-coinbase-price-premium-suggests),
  [BIT knowledge hub](https://www.bit.com/insights/knowledge-hub/coinbase-premium); leads, practitioner-grade).
- Cross-exchange deviations are persistent and revert slowly where capital controls bind (Makarov and Schoar, JFE
  2020, round 4).
- **No meme study, and no peer-reviewed BTC predictive test, was found. The prior is low–medium.**

**OWN-PRECHECK: Coinbase 24 h volume in coin units, converted at the last price.**
- DOGE: about $13M.
- PUMP: about $13M.
- PENGU: about $3.7M.
- FARTCOIN: about $3.0M.
- PEPE: about $2.8M.
- BONK: about $2.4M.
- TRUMP: about $1.3M.
- WIF: about $1.0M.
- SPX: about $0.9M.
- FLOKI: about $0.7M.
- POPCAT: about $0.2M.

This is small next to the perps, so the premium is plausibly a **demand signal**, not an arbitrage-anchored
price.

**Pre-registerable rule (12 configs).**
- **Premium:** p = ln(Coinbase X-USD close ÷ (Binance perp close × USDT-USD)), on 1m bars. Its level is the
  trailing 24 h median. x = 15-min mean of (p − level), z-scored against its trailing 7 days.
- **Trade:** at each 15-min boundary, if |z| ≥ k, take a Lighter position in sign(z) and hold H. One position per
  coin.
- **Grid (12):**
  - tight set ∩ Coinbase: k ∈ {1.5, 2.5} × H ∈ {15, 60} min × US-hours gate {off, on (13:30–20:00 UTC)} = 8;
  - all 12 memes, each charged its own spread, no gate: k × H = 4.

**Trades/day.** 8–12 coins × 96 boundaries × P(|z| ≥ 1.5) of about 5–10%, capped by H. That is **about 20–60/day**
at k = 1.5 and 5–15/day at k = 2.5.

**Gross vs full cost.**
- **Cost:** one spread, 1.6–5.8 bp in the tight set.
- **Gross:** a 15–60 min meme sd of about 50–120 bp × IC 0.04–0.08 gives **about 3–10 bp**. The ratio is about
  **1–2×**, and positive only if the IC is real.

**Kill risk: medium-high.**
- The premium may be mostly quote staleness on a thin Coinbase book. The level must be de-meaned, and 1m closes
  on thin pairs are noisy.
- USDT/USD moves; that is why USDT-USD is in the formula.
- Reverse causality: Coinbase may follow.
- **Kill test:** on train, the IC of z on the next-H perp return must exceed the IC of the perp's own past 15-min
  return (a momentum control), with the same sign in both half-years.

**Data and splits.**
- **Coinbase 1m:** 300 candles per call, keyless. About 9 months × 12 coins is about 1,300 calls per coin, about
  16k calls in all; under an hour at a polite rate.
- **Binance perp 1m klines:** partly cached in `data/raw/web/binance_fut/xlead/`.
- **Coinbase USDT-USD 1m:** OWN 200.
- **Listing dates differ** (FARTCOIN, PENGU and PUMP are absent in 2025-02). Each coin enters once it has 30 days of
  Coinbase history.
- **Splits:** train to 2025-12-31 (listings are late, so train is shorter than ideas 2–3); validation 2026-01-01 to
  2026-03-31; holdout ≥ 2026-04-01.

---

### Idea 5. SOL shocks → Solana-native meme perps at seconds, on Lighter (H-SOLBETA-S). Category (b)

**What is new.**
- **H-SOLLEAD** tested SOL → *pump.fun spot tokens* at 1 minute (no lead; curve cost ≥ 2.5%).
- **H-XLEAD** included SOL in 1-minute regressions.

Neither tested **seconds-scale SOL → meme-perp** catch-up at 0 bp. The mechanism differs from idea 1 (base-asset
beta, not sector diffusion). SOL is the deepest leader: $1–3B a day on Binance (OWN).

**Evidence.** As idea 1 (Anderson 2023; Arrakis). SOL-denominated pump.fun meme demand ties Solana memes' USD
prices to SOL. No study exists for perps.

**Pre-registerable rule (12 configs).**
- **Event:** SOLUSDT perp |2-s move| ≥ θ.
- **Followers:** the Solana-native tight memes FARTCOIN, PUMP, WIF, PENGU and TRUMP, plus 1000BONK at its own
  spread.
- **Eligibility and execution:** as idea 1.
- **Grid:** θ ∈ {10, 15, 25} bp × H ∈ {5, 30} s × follower gate {unfollowed only (< β·θ/3), all} = **12**.
- If idea 1 is frozen with its L2 arm, freeze this one **without** θ = 15 / 25 duplicates. Pre-register only one
  of the two.

**Trades/day.** SOL ≥ 15 bp events numbered 9–73 a day (OWN, two days). At θ = 10, several times that. Times 3–6
followers: **about 30–300/day.**

**Gross vs full cost.**
- **Cost:** 1.6–5.8 bp (BONK about 10 bp).
- **Gross:** Solana-meme betas to SOL of about 1–1.5 give a 10–22 bp catch-up for a 10–15 bp SOL move; capturing a
  third gives about 3–7 bp. Ratio about **1–2×**, the thinnest of the seconds ideas.

**Kill risk: high.**
- SOL is the most arbitraged leader of all, and meme MMs quote off it directly.
- SOLLEAD and XLEAD found nothing at 1 minute.
- **Kill test:** as idea 1, on SOL events.

**Data.** As idea 1, sharing the same reduced aggTrades grids. SOL perp aggTrades are larger (7 MB zipped a
weekday).

---

### Idea 6. Public HL liquidation-price clusters as targets: trade toward a nearby cluster on Lighter (H-LIQMAP). Category (b), forward-only

**What is new.** Every earlier liquidation idea was **reactive**: fade after a flush (FLUSH, FLUSH-MW, the
forceOrder fade, WICKNET, WICKNET-F). The "cascade early warning" idea was market-level and rare (round 8). This
one is **anticipatory and per coin**. HL positions are public. Their liquidation prices are therefore known before
price gets there, which no Binance-archive idea can see.

**Evidence.**
- Glassnode, "Pressure Points: Liquidation Heatmaps & Market Bias" ([research.glassnode.com](https://research.glassnode.com/liquidation-heatmaps/),
  2025-09-23; lead):
  - HL liquidation clusters "tend to align closely with the spikes in aggregate market liquidations";
  - "monitoring these clusters in advance may help anticipate volatility spikes and cascade events";
  - **no hit rates or horizons are reported.**
- Vendor "magnet" claims ([kiyotaka.ai](https://kiyotaka.ai/blog/liquidation-heatmaps-for-hyperliquid),
  [mmt.gg](https://mmt.gg/learn/hyperliquid-heatmaps); marketing-grade leads).
- **The prior is low–medium.** The direction (magnet vs support) is itself unknown, so both are in the grid.

**OWN-PRECHECK.**
- HL `recentTrades` returns both counterparties' addresses (`users`).
- `clearinghouseState` is public for any address. Per HL's API, the position objects include `liquidationPx`;
  **confirm this field on a live meme position before freezing.**
- Address discovery is therefore free: collect every `users` entry on the 11 meme coins from the WS trades
  stream, then poll positions. The poll rate is bounded by HL's REST weight limit (to confirm in the DOC).

**Pre-registerable rule (12 configs).**
- **Clusters, every 2–5 min:** for each coin, sum the tracked notional by liqPx in 10-bp bins. A cluster is a 30-bp
  window whose notional ≥ X × the coin's trailing-1 h HL traded notional.
- **Trigger:** the HL mid comes within d bp of the nearest cluster edge, with no trigger on that cluster in the last
  30 min.
- **Trade:** a Lighter taker trade **toward** the cluster (magnet) or **away** from it (support).
- **Exit:**
  - take-profit when the mid crosses the far edge of the cluster (toward arm);
  - otherwise at T;
  - stop at d beyond entry, on the far side.
- **Grid:**
  - d ∈ {50, 100} bp × X ∈ {0.5, 2} × direction {toward, away} at T = 30 min = 8;
  - plus toward-only at T = 5 min for the 4 (d, X) pairs;
  - **12** in total.
- **Size:** $1k. It is far too small to push price toward anyone's liquidation. Any rule that adds size near a
  cluster to *cause* the cascade is excluded.

**Trades/day.** Unknown. Count triggers on the first forward day. Eleven memes on volatile days plausibly give
15–40 approaches within 100 bp. In quiet markets it may fail ≥ 15/day.

**Gross vs full cost.**
- **Cost:** one Lighter spread (1.6–5.8 bp tight set, 10–37 bp otherwise).
- **Gross:** a breached cluster typically cascades 30–200 bp. Approaches that stall cost roughly d/2. Profitable
  only if the breach probability is well above about 50%. Unknown; the ratio could be large or below 1.

**Kill risk: high.**
- We see only the addresses we have discovered, and HL is a minority of meme open interest.
- Clusters may act as support (hence the "away" arm).
- Polling lag of 2–5 min.
- **Kill test:** in the first 24 h (train), at least 15 triggers, and the toward arm's breach rate within T at least
  10 pp above the away arm's or below it, with a sign. Otherwise stop.

**Data.** Forward only. HL positions history is not public in bulk. A new adapter is needed:
`pipeline/sources/hl_positions.py`, using the HL WS trades `users` field and `clearinghouseState`. First 24 h are
train, next 24 h validation. It needs only REST and WS that are already reachable.

---

## 2. Ranking

Cost is the Lighter round trip: one spread, using the OWN snapshot. "Hist?" says whether train and validation can
be done from archives within about 3 days.

| rank | idea | full cost | gross if real | ratio | trades/day | hist? / forward | kill risk |
|---|---|---|---|---|---|---|---|
| 1 | **H-MEMEDIFF**: DOGE/PEPE 2-s shock → unfollowed tight memes on Lighter | 1.6–5.8 bp | 4–10 bp | 1.2–3× | 15–60 (θ25) to 100–500 (θ15) | Yes: Binance aggTrades proxy, 40 sampled days; forward on the memelag recorder | Medium-high: MM cross-quoting may be sub-second; XLEAD reversals |
| 2 | **H-NIGHT**: long 22–24 UTC (and 23–24, 14–16) on meme perps | 1.6–5.8 bp + about 0.5 bp funding | 12–20 bp (BTC paper about 9 bp × beta) | about 3× | 8 (U1) to 15–20 (U2) coin-legs | **Yes, already cached** (Binance 1h) + Lighter 1m candles | Medium-high: published 2022, decay; one bet per day |
| 3 | **H-QHOI**: 10-s quarter-hour opening imbalance → 4–12 h continuation | 1.6–5.8 bp ± funding | 5–15 bp | 1–3× | about 15 (k1, H4h) | Yes: aggTrades streamed (6–10 GB, reduced) | Medium: size unreported, memes may differ |
| 4 | **H-CBPREM**: Coinbase USD premium → perp, 15–60 min | 1.6–5.8 bp | 3–10 bp | 1–2× | 20–60 (k1.5) | Yes: Coinbase 1m + Binance 1m; train shorter because of listings | Medium-high: staleness, reverse causality |
| 5 | **H-SOLBETA-S**: SOL 2-s shock → Solana memes on Lighter | 1.6–10 bp | 3–7 bp | 1–2× | 30–300 | Yes, shares idea 1's data | High: SOL is the most arbitraged leader; SOLLEAD/XLEAD nulls |
| 6 | **H-LIQMAP**: trade toward or away from public HL liquidation clusters | 1.6–37 bp | 30–200 bp on breach, −d/2 on stall | unknown | unknown, needs counting | **Forward only** (new HL positions adapter) | High: partial visibility; direction unknown |

**Recommended order of work (fits about 3 days).**
1. **H-NIGHT kill test.** Data are already on disk, so it takes hours.
2. **Download and reduce the aggTrades grids once for ideas 1, 3 and 5.** Run H-MEMEDIFF's and H-SOLBETA-S's
   kill tests; pre-register only one SOL arm. Then H-QHOI's opening-vs-control IC test.
3. **H-CBPREM:** a Coinbase backfill, then the IC kill test.
4. **H-LIQMAP:** start the positions recorder on day 1, so that 48 h of forward data exist by day 3.

The forward legs of ideas 1 and 5 reuse the running memelag and multivenue recorders. They need no new collector.

---

## 3. Considered and dropped (do not re-research)

| lead | why dropped |
|---|---|
| **Spot-led meme perp moves using the Jupiter prop-AMM price** | Prop AMMs are oracle-updated from CEX prices, so they follow (round 10 drop). OWN-PRECHECK, Jupiter `tokens/v2` 24 h on-chain volume: PUMP $64M (organic $3.5M), TRUMP $9.8M, PENGU $9.3M, BONK $1.9M, WIF $1.1M. FARTCOIN's 5-min window showed about $3.6k. That is small against perp turnover (HL PUMP about $143M/day), the same finding as H-DEXLEAD. Cheap spot does not make spot the leader. |
| **pump.fun cohorts at milestones with prop-AMM-cheap exits** | OWN-PRECHECK, Jupiter quotes at 0.5 SOL on 37 trending pump.fun graduates. Tokens graduated in Sept–Oct 2026 with a market cap ≤ $10M quote **round trips of about 100–900 bp**, mostly through Pump.fun AMM, sometimes "Hadron" or Meteora DLMM (Hadron is unidentified; no source found). Only old $18M+ tokens reach ≤ 51 bp (neet 4 bp, pippin 27, ANSEM 46). Two quotes came back negative (−262 and −310 bp), because price moved between the two quotes 0.4 s apart: quotes on young tokens are not usable cost evidence. The exit is not cheap until a token is already a large cap, and that cohort is iteration 8, CLEANMIG or H-SURVIVOR. |
| **Hourly pump.fun inflow → PUMP / meme basket ("lean recorder" PUMPPULSE)** | `agent_pumppulse.md`: "no next-day information"; ICs within ±0.07 that flip sign; "not to retry without new evidence". No new evidence exists, and the buyback is about 1% of PUMP perp volume (round 10). |
| **Meme perp reaction to big pump.fun / PumpSwap graduations** | A graduation adds about 85 SOL of pool reserve (round 10 OWN), with no channel to WIF, BONK or FARTCOIN perp flow. The aggregate version is PUMPPULSE (failed). SOL → pump.fun at 1 min found nothing (SOLLEAD). |
| **Lighter-vs-HL meme basis convergence** | Single-leg versions are pending (H-LIGHTFADE-MEME: Lighter vs Binance-implied fair) or failed (HLANCHOR). A two-leg version pays HL's 4.5 bp × 2. The same structure on zero-fee equity perps was **weakened** (H-EQBASIS: bases are persistent levels with an sd of 0.5–2 bp). The memelag recorder already logs HL bbo, so count Lighter–HL deviations as a diagnostic arm only. |
| **Funding-settlement effects on meme perps** | FUNDCLOCK (Binance top 20, memes included): PRE leg +2 to +11 bp gross, POST wrong-signed. The Lighter execution of the PRE leg was dropped in round 8 (0.85 trades/day at the gross-positive threshold). The meme-only subset is a re-cut of failed data. |
| **Liquidation-cluster bounces from Binance aggTrades** | Covered by FLUSH (21 configs), FLUSH-MW, the forceOrder fade (round 6), WICKNET and WICKNET-F (validation: gross +3.4 bp, PF 0.75). aggTrades also carry no liquidation flag, and the `liquidationSnapshot` archive is empty (round 4). Idea 6 is the anticipatory alternative. |
| **Metaorder (algo child-order) footprints in Binance aggTrades → ride on Lighter** | OWN-PRECHECK on 6 coin-days (DOGE, 1000PEPE, FARTCOIN, 2026-03-02 and 03-07): runs of ≥ 6 same-side, identical-quantity prints of ≥ $500 at regular intervals (CV < 0.25, ≤ 15 min) numbered **0–3 per coin-day**. Child orders are size-randomised, so detection from public prints is too sparse for ≥ 15/day. TWAPRIDE (pending) uses HL's visible TWAPs instead. |
| **Following "smart" HL wallets, executed on Lighter at 0 bp** | Zhai's top-ventile markout of 3.11 bp (round 4) is about one tight-set Lighter spread. That is the round-8 rule for 0-bp re-runs: drop when gross ≤ one spread. |
| **Weekend-only meme reversal / Monday Asia open** | One event per week per coin fails n (rounds 7–8). The weekend arm of seasonality can be read inside H-NIGHT's results as information only. It is not a separate config. |
| **Hour-scale big-meme → small-meme lead-lag (Lo–MacKinlay)** | Equivalent to H-XSREV's equal-weight residual signal (gross 0–2.5 bp per leg). Fails at any cost. |
| **Binance spot (aggTrades archive) as leader for meme perps** | Round 6 drop; perps lead spot. The archive's availability changes the data, not the economics. |

## 4. Gaps

- **Lighter spreads are a single REST snapshot** (Monday 10:2x UTC). Score with recorded spreads (memelag
  recorder) once those files may be opened, or from a fresh 24 h REST sampler.
- **No historical Binance quotes after 2024-03** (bookTicker 404). Every historical seconds-scale test (ideas 1
  and 5) uses last-trade prices, with bid-ask bounce. The kill tests use 30 s horizons, and the forward recorder
  confirms with quotes.
- **Lighter 1m candle depth before 2025-09 is not checked.** Lighter meme funding history starts 2025-01 to
  2025-08 by coin (propcarry).
- **HL `liquidationPx` field and REST weight limits** (idea 6) are to confirm in the DOC and live before freezing.
- **The Coinbase listing date per meme** must be found by paging (idea 4).
- **Padyšák and Vojtko** was read via Quantpedia's summary, not in full. **Kim and Hansen** report no basis-point
  size for the 4–12 h effect.
- **"Hadron"** (a Jupiter route label on young pump.fun tokens) is unidentified.
- **Disk:** 3.9 GB free. Ideas 1, 3 and 5 must stream and reduce archives; idea 3's full set is 6–10 GB zipped.
