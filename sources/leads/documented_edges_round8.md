# Documented edges, round 8: ideas built around the cost side (0–1 bp venues, or gross ≥ 25 bp)

_Agent: round 8, 2026-10-05 (07:00–07:40 UTC). Leads review only. No backtest was run and no P&L was computed. Web
content is cited as **lead** (third-party pages, marketing, search snippets) unless it is official documentation,
which is marked **DOC**. **OWN-PRECHECK** marks a check run from this container. Every OWN-PRECHECK is descriptive:
reachability, trigger counts, spreads, cross-venue mid snapshots, and one lagged-correlation profile. None of them is a
strategy test. Raw pre-check files sit in the session scratchpad only, not in the repo._

## 0. Why this round looks where it does

About 75 families have been tested or dropped (rounds 1–7, `reports/failures/`, `reports/candidates/`). They show
one pattern:
- **Measurable signals give 1–13 bp gross per trade** against 13–14 bp taker round trips. Recent examples:
  - XSREV: 0–2.5 bp;
  - ITSM: −6 to +4 bp;
  - PAIRS: −11 to +4 bp;
  - FUNDCLOCK pre-settlement leg: +2 to +11 bp;
  - LSRATIO: 0–13 bp, about 6 bp per SD;
  - QIMAKER: about 1 bp per signal against a 3 bp maker round trip;
  - TWAPRIDE (paper read): 12–22 bp against 12–16 bp.
- **Carry decayed** (FUNDCARRY, FFDIFF(-WIDE), SPOTCARRY, DATEDBASIS, the funding-only momentum holdout).

This round therefore designs **from the cost side**. Each idea must meet one of two conditions:
- **(a)** a gross plausibly **≥ 25 bp per trade** at **≥ 10 trades/day**, so that 13 bp taker costs stop mattering; or
- **(b)** a gross of **3–10 bp** executed on a venue costing **0–1 bp per side**, with the spread, the speed bump and
  adverse selection counted honestly.

**Already in flight; not repeated here.** H-HLLAG (paper), H-LIGHTLAG, H-LIGHTFADE, H-EQLAG, H-T2LAG (one
multivenue recorder), H-UPBITLEAD, H-UNLOCK, H-TWAPRIDE/TWAPFADE (with a cheap-venue cost arm already declared),
H-LSRATIO-on-Lighter (post hoc), and XS_L7_LO paper.

### Cost and venue facts re-checked this round

| Fact | Value | Source |
|---|---|---|
| Lighter Standard account fees | maker 0, taker 0 | DOC [Lighter account types](https://apidocs.lighter.xyz/docs/account-types), fetched 2026-10-05 07:0x |
| **Lighter Standard latencies** | **Taker 300 ms, Maker 0 ms, Cancel/Modify 300 ms** | same page. **This settles round 7's open question.** On a Standard account, *cancels* are delayed as much as taker orders. |
| Lighter Premium (0 LIT staked) | maker 0.40 bp, taker 2.80 bp; maker and cancel 0 ms; taker 140 ms | same page |
| Lighter equity perps | `taker_fee` 0.0000 on TSLA, NVDA, MSTR, COIN, HOOD, CRCL, AAPL, AMZN, GOOGL, META, AMD, PLTR, MU, INTC, SPY, QQQ, US100, XAU, XAG, BMNR | OWN-PRECHECK, `orderBookDetails` (237 markets). 24-h quote volume at 07:1x UTC Monday: $0.4–4.3M per single name, $15–16M for US100 and XAU. |
| trade[XYZ] growth-mode fees | taker **0.90 bp**, maker 0.30 bp (tier 0) | DOC [trade.xyz fees](https://docs.trade.xyz/perpetuals/mechanics/fees.md) |
| **trade[XYZ] growth-mode exclusions** | "Perps on crypto-holding vehicles like MSTR" and "Gold perps" pay the standard **9.0 bp** taker (tier 0) | same page. OWN-PRECHECK `metaAndAssetCtxs` `dex:"xyz"`: 118 of 131 markets have `growthMode: "enabled"`. Not enabled: GOLD, MSTR, BMNR, STRC, PURRDAT. (EQLAG's pre-registration already prices this correctly.) |
| trade[XYZ] oracle | Cash hours: "the externally-derived fair price is transmitted as the oracle price". Off-hours: "a continuous-time exponentially weighted moving average that incrementally adjusts the previous oracle price by a fraction of the impact price difference", τ = 30 min | DOC [trade.xyz oracle price](https://docs.trade.xyz/perpetuals/mechanics/oracle-price.md) |
| Aster stock perps | "0% maker and taker fees across all listed stock perp contracts" (announced 2025-12-10; whether it is time-limited is not stated) | lead [Crypto Briefing](https://cryptobriefing.com/aster-stock-perpetual-trading/). OWN-PRECHECK: `fapi.asterdex.com/fapi/v1/exchangeInfo` lists TSLA, NVDA, AAPL, QQQ, SPY, XAU, HOOD, CRCL, MSTR and COIN USDT perps as TRADING (`underlyingSubType: STOCK`). The API commission rate needs a key, so it is unverified. |
| Binance TradFi perps | Index "aggregates data from multiple vendors, updating every second during market hours, and outside these hours, it remains fixed at the last value"; off-hours mark is an EWMA | lead, search summary of Binance-sourced pages ([onekey](https://onekey.so/blog/ecosystem/binance-reboots-us-equity-exposure-will-the-tsla-perpetual-contract-spark-a-new-rally-20260127134951), [Trade Informer](https://www.tradeinformer.com/broker-news/binance-launches-non-crypto-perpetual-futures-starting-with-gold-and-silver)). Official FAQ not fetched. |

### Reachability from this container (new this round)

| Source | Result |
|---|---|
| **Binance `markPrice@1s` (gives the index `i`)** | **OK only on the `/market` route**: `wss://fstream.binance.com/market/ws/<sym>@markPrice@1s`. The legacy `/ws/` path accepted the connection but delivered nothing in 25 s; `bookTicker` on `/ws/` still works. At 07:08 UTC Monday (03:08 ET), the TSLAUSDT index moved by about ±0.3 bp tick to tick, so it is not frozen in the overnight session. Its vendor composition is unverified. |
| **Pyth Hermes** (`hermes.pyth.network`) | Metadata is free: `/v2/price_feeds` lists 1,250 equity feeds (1,052 US) with market-hours schedules, `min_channel fixed_rate@50ms`. **Prices return HTTP 401** (`/v2/updates/price/latest` and `/stream`). Benchmarks `/v1/updates/price/<t>` is also 401. **Pyth is not a free leader any more.** |
| HL `candleSnapshot` for `xyz:*` | 200. Capped at about 5,000 candles: 1m covers about 3.5 days, and 5m reaches back to 2026-09-17. **All of this falls inside the reserved period (≥ 2026-04-01), so use it for counts only, never for P&L.** |
| Binance archive, equity perps | 1m klines exist from 2026-01 (TSLAUSDT) and 2026-02 (MSTR, COIN, HOOD, CRCL); XAUUSDT from 2025-12. **So pre-holdout history is at most 2026-01..03.** |
| Hypurrscan `/twap/*` | 200. 544 rows in 24 h, including **79 builder-dex (HIP-3) TWAPs**. The current TWAP recorder already stores them but excludes them from TWAPRIDE. |
| Aster REST `bookTicker` for stock perps | 200 |

---

## 1. Ideas (ranked in §2)

**Common rules, as in rounds 4–7:**
- **Freezing.** Freeze `reports/hypotheses/<id>_preregistration.json` before the first scored forward record.
- **Holdout.** Data dated ≥ 2026-04-01 is the reserved holdout. For families that only exist since 2025–26, history
  in that window may be used for **trigger counts only**. Scoring is forward.
- **Latency.** Decisions use local receive time; our order arrives at decision + 300 ms, plus the venue's bump
  (Lighter Standard +300 ms on takes **and on cancels**).
- **Size.** Units are $1k, and one round trip counts as one trade.
- **Reporting.** Report by day and by name as well as by trade.
- **Jurisdiction.** Equity perps on Lighter, HIP-3, Aster and Binance must be legal for the team before anything
  goes beyond paper (round 4 §3).

### Idea 1. Ride visible TWAPs on HIP-3 growth-mode markets at 0.9 bp (H-TWAPXYZ)

**Mechanism.**
- H-TWAPRIDE rides validator-perp TWAPs. There, the paper's gross (12–22 bp start to completion for TWAPs of
  23 min to 1 day) roughly equals the 12–16 bp HL taker round trip, so the expected net is about 0 to +8 bp.
- The same public, protocol-native TWAP mechanism runs on HIP-3 builder dexes. On trade[XYZ] growth-mode markets the
  round trip costs **about 2.5–4 bp**: 2 × 0.9 bp in fees plus a 0.5–2 bp spread.
- The TWAPRIDE pre-registration explicitly **excludes builder-dex perps**
  (`reports/hypotheses/twap_preregistration.json`: "Spot and builder-dex perps excluded"). So this is a separate,
  untested population on a venue that is 4–5× cheaper.
- The equity books are thinner than crypto majors, and TWAP size relative to daily volume is often large. That is
  the regime where impact grows (Barone and Lillo: impact ∝ ϕ^0.30, keyed to size, not participation).

**Evidence.**
- **Impact path** (DATA, preprint): Barone and Lillo, arXiv 2606.15715, read in full in
  `sources/leads/twap_paper_notes.md`.
  - TWAPs of 23 min to 1 day move the price **12–22 bp** in their direction from start to completion (Figure 3
    reading). For TWAPs under 23 min the move is 4–11 bp.
  - About 70–95% of the move persists after completion.
  - TWAPs "begin with the trend: +18.2 basis points on average" (p. 11, verbatim).
- **Gap:** the paper covers "All 201 HL perpetual markets", 2025-07-28 to 2026-03-23, which are validator perps. **HIP-3
  TWAPs are not in its sample.** Their impact is an open question, and it could be larger (thin books) or smaller
  (hedging flow by stock-token issuers).
- **OWN-PRECHECK** (Hypurrscan `/twap/*`, one call, 24.0 h to 2026-10-05 ~07:10 UTC; ϕ uses the *current*
  `dayNtlVlm`, not point-in-time values):
  - 79 builder-dex TWAPs, 73 of them on xyz.
  - **19 with ϕ = notional ÷ 24-h notional ≥ 0.3%, not reduce-only, ≥ 30 min.** About 8 of those have ϕ ≥ 1%.
  - Examples: AMZN $151k over 895 min (ϕ 4.9%), GOOGL $144k (2.3%), NVDA $153k (0.8%), CL $167k (0.3%), CBRS $179k
    (0.37%), TLT $50k (58%), UNITREE $24k (7.2%), HIMS $7k (9.9%).
  - Two pairs of rows are identical (BRENTOIL and CL). They may be duplicates, so de-duplicate by hash.
  - Sunday/Monday volumes are low, which inflates ϕ.
- **Ethics and legal:** same as TWAPRIDE. Read `twap_paper_notes.md` §3 first. This is trading on publicly broadcast
  order terms, not on non-public information, and no transaction is placed around anyone's transaction. The open
  questions for the owner in §3.4 apply unchanged.

**Data.** Forward only, and **already being recorded**:
- `scripts/research/twap_recorder.py` stores builder-dex Hypurrscan rows, and its `ctx_*` files include builder dexes
  that have a tracked TWAP.
- **Add** HL WS `bbo` and `trades` for each `xyz:<NAME>` with an active qualifying TWAP. Also take a 1-min
  `metaAndAssetCtxs dex:"xyz"` snapshot to get point-in-time ϕ, growth mode and `deployerFeeScale`.

**Pre-registerable rule (12 configs).**
- **Qualifying TWAP:**
  - xyz market with `growthMode: "enabled"` at first sight;
  - not reduce-only, no trigger;
  - 30 min ≤ duration ≤ 24 h;
  - notional ≥ $10k;
  - first seen ≤ 60 s after its block time;
  - ϕ = notional ÷ point-in-time 24-h xyz notional.
- **Entry:** xyz taker in the TWAP direction at first sight + 300 ms, walking the recorded book.
- **Exit:** taker at the earliest of H, the TWAP's completion, or termination seen by `twapHistory`.
- **Position:** one position per name. Overlapping same-direction TWAPs count once.
- **Grid:** ϕ ≥ {0.3%, 1%} × H ∈ {30 min, 2 h, completion capped at 6 h} × session ∈ {all hours, underlying cash
  market closed only} = **12**.
- **Costs:** 0.9 bp per side × `deployerFeeScale`, the book walk, and hourly HIP-3 funding.

**Trades/day.** About 19 a day at ϕ ≥ 0.3% and about 8 at ϕ ≥ 1%, from one 24-h snapshot. **Reaching 50 takes 3–7
days.** Builder-dex TWAPs may grow with HIP-3 volume. A search summary says trade[XYZ] is "52% of all Hyperliquid
perpetual volume"; the source was probably
[Blockeden](https://blockeden.xyz/blog/2026/04/29/hyperliquid-hip3-builder-markets-1b-oi-commodities/), but the
attribution is uncertain, so treat it as a lead.

**Gross vs full cost.** If HIP-3 impact matches validator perps, the gross is 12–22 bp against **≈ 2.5–4 bp** of cost
(fee 1.8 bp + spread 0.4–2 bp; xyz spreads in round 7 were 0.24–2.15 bp), a ratio of **about 3–6×**. The entry is
about 10 s late on the Hypurrscan lag (p50 9.8 s, `twap_data_notes.md`), which is negligible against a ≥ 30-min
execution.

**Kill risk.**
1. **HIP-3 TWAPs may be hedges.** Issuers or market makers hedging tokenized stock or cash positions could create
   flow that market makers absorb without drift. The sunshine effect may be stronger on thin books.
2. **Small n.** About 8–19 a day, concentrated in a few names. Report by name-day.
3. **Growth mode can end per market**, taking the taker fee to 9 bp. The fee is read from the hourly meta.
4. **Ethics review** (TWAPRIDE §3) is required before any live use.

**Kill test.** After 30 qualifying TWAPs, if the mean xyz mid move from entry + 300 ms to the exit is below 4 bp in
the TWAP direction, stop.

---

### Idea 2. BTC leads crypto-linked equity perps (MSTR, COIN, HOOD, CRCL) on zero-fee venues (H-BETALAG)

**Mechanism.**
- MSTR, COIN, HOOD and CRCL perps carry a large BTC beta. When their cash market is closed (about 17.5 of 24 weekday
  hours, and all weekend), **BTC is the only real-time fundamental input**, and it trades on far deeper books than
  these perps.
- If the market makers on Lighter, xyz and Aster adjust to BTC with a lag of seconds to minutes, the follower perp
  under-reacts. That is XLEAD's mechanism, but with a leader whose relationship to the follower is fundamental
  (MSTR's balance sheet), and executed at 0–0.9 bp instead of 13 bp.
- XLEAD failed at a 15 bp cost with 1–14 bp gross. Here the cost is 2–4 bp.

**Evidence.**
- **OWN-PRECHECK, descriptive** (HL `candleSnapshot` 1m, the last 5 days to 07:1x UTC; HL BTC vs `xyz:*`;
  close-to-close log returns; correlation of BTC(t) with the follower at t + k):

  | Follower | Session | Minutes | k = 0 | k = 1 | k = 2 | k = 3 |
  |---|---|---|---|---|---|---|
  | MSTR | weekend | 2,880 | 0.41 | **0.14** | **0.13** | −0.01 |
  | MSTR | weekday | 2,136 | 0.65 | **0.11** | 0.01 | 0.04 |
  | COIN | weekend | 2,880 | 0.38 | 0.07 | 0.10 | −0.05 |
  | COIN | weekday | 2,159 | 0.41 | **0.15** | 0.03 | 0.03 |
  | CRCL | weekend | 2,880 | 0.38 | **0.13** | 0.07 | 0.02 |
  | CRCL | weekday | 2,134 | 0.51 | 0.09 | −0.01 | 0.06 |
  | HOOD | weekend | 2,880 | 0.14 | 0.09 | 0.04 | −0.01 |
  | HOOD | weekday | 2,167 | 0.34 | 0.09 | 0.05 | 0.03 |
  | TSLA (control) | weekend | 2,880 | 0.05 | 0.02 | 0.05 | 0.01 |
  | TSLA (control) | weekday | 2,174 | 0.22 | 0.01 | −0.01 | 0.01 |

  - **Reading:** a lag-1 correlation of 0.07–0.15 on the crypto-linked names and about 0 on the TSLA control. That is
    consistent with part of the BTC response arriving one minute late.
  - **Big caveat:** these are last-trade closes. On weekends the median |1-min return| of COIN, MSTR and HOOD was
    **0.0 bp**, so many minutes had no trade. Stale prints create spurious lagged correlation (non-synchronous
    trading, the Epps effect). **This is not evidence of a tradeable lag.** Only mids recorded forward can settle it.
- **Trigger frequency:** BTC 1-min moves of ≥ 10 bp occurred 135 times in the ~1.5 weekday days of the sample and 14
  times over the (quiet) weekend.
- No study of second-to-minute BTC → MSTR or COIN lead-lag was found. A search
  ([Benzinga](https://benzinga.com/z/37913767), [Decrypt](https://decrypt.co/249643/microstrategy-coinbase-stock-dip-bitcoin-price-momentum-cools))
  found only news on daily co-movement (ANECDOTAL).
- **Fees:** Lighter MSTR/COIN/HOOD/CRCL 0 bp (DOC + OWN-PRECHECK). xyz COIN/HOOD/CRCL 0.9 bp, but **xyz MSTR is 9 bp
  (not growth-eligible, DOC)**. Aster lists all four at 0 bp (lead).
- **Spreads:** Lighter COIN 2.25 bp, MSTR 2.43 bp; xyz COIN 2.15 bp, MSTR 1.83 bp (round-7 OWN-PRECHECK).

**Data.**
- **Forward:** Binance BTCUSDT `bookTicker` (already recorded); Lighter `ticker/<id>` for MSTR (122), COIN (109), HOOD
  and CRCL (ids from `orderBookDetails`); xyz `bbo` for COIN, HOOD, CRCL. MSTR and COIN are already in
  `multivenue_recorder.py`. HOOD and CRCL must be added before freezing.
- **History:** Binance 1m klines for MSTR, COIN, HOOD and CRCL perps (2026-02..03) and BTCUSDT. These are pre-holdout,
  but they sit in the generic validation window, and the perps there are Binance's, not the execution venue's.
  - If used, pre-register 2026-02 as this family's train and 2026-03 as its validation, as an explicit deviation from
    the perp calendar, approved before the download. Otherwise run forward only.

**Pre-registerable rule (12 configs).**
- **Beta:** β_i,s is the trailing 7-day regression of the follower's 1-min mid return on BTC's, estimated separately
  for session s ∈ {cash open, cash closed} from data before day d, and frozen per day.
- **Trigger:** the BTC mid moves by θ or more over 10 s. Expected follower move: E = β × that move. Fire if the
  follower's realised move over the same 10 s, in the same direction, is ≤ E/2.
- **Entry:** follower taker at + 300 ms (Lighter: + 600 ms), walking the book.
- **Exit:** taker at + H. One position per name; cooldown H.
- **Grid:** θ ∈ {10, 20} bp × H ∈ {30 s, 2 min, 10 min} × venue ∈ {Lighter (MSTR, COIN, HOOD, CRCL), xyz (COIN,
  HOOD, CRCL)} = **12**. Report cash-open and cash-closed separately (not a config).
- **Costs:** Lighter 0 bp; xyz 0.9 bp × `deployerFeeScale`; plus the book walk.

**Trades/day.** At θ = 10 bp, BTC fires roughly 50–90 times a weekday (1-min ≥ 10 bp count above; a 10-s window fires
less). With 3–4 followers and the E/2 filter, expect **≥ 20/day on weekdays** and far fewer on quiet weekends.

**Gross vs full cost.**
- **Gross:** with β ≈ 1–2, a 10–20 bp BTC move implies 10–40 bp for the follower. If 20–30% of it is still missing
  600 ms after the trigger, the gross is **about 3–10 bp**.
- **Cost:** Lighter about 2–2.5 bp (one spread); xyz about 4 bp.
- **Ratio:** about 1–3×.

**Kill risk.**
1. **The lag is a stale-print illusion.** The forward mids will show this on day 1.
2. **Followers' market makers quote off BTC already** (they are crypto MMs), so the lag is under 600 ms.
3. **Spreads widen exactly on BTC jumps**, so the walk eats the gross.

**Kill test.** On the first two forward days, take the mean follower mid move from trigger + 600 ms to + 2 min at
θ = 10 bp. If it is below 3 bp, stop.

---

### Idea 3. Open-market proxies lead closed-market perps on trade[XYZ] (H-CLOSEDPROXY)

**Mechanism.**
- When an underlying's home market is closed, its xyz oracle stops using external prices and becomes an EWMA of the
  xyz book with τ = 30 min (DOC). Price discovery then depends on xyz traders alone.
- When a *related* market is open, its xyz perp has an external oracle and fresh information. The obvious case is
  Korea against the US:
  - **US hours (13:30–20:00 UTC, Korea closed):** EWY (MSCI Korea ETF), MU and SOXL (US semis) and SKHY are open, and
    they should lead SMSN (Samsung) and SKHX (SK Hynix).
  - **Korean hours (00:00–06:30 UTC, US closed):** SMSN and SKHX are open, and they should lead EWY, SKHY, MU and SOXL.
- If closed-market perps catch up with a lag, a taker on xyz pays 0.9 bp per side.
- This is new relative to EQLAG, which is the same asset across venues. Here it is a different asset on the same
  cheap venue, at a session boundary.

**Evidence.**
- **Closed-market perps aggregate information.** "Hyperliquid correctly predicted the opening direction in 45 of 62
  cases, or 73.8%", and Samsung was "15 of 16 weekends" (lead, search summary of
  [4pillars](https://research.4pillars.io/en/research/can-hyperliquids-weekend-trading-predict-monday-opens-for-korean-stocks);
  the page returned 429, so not verbatim).
  - **Against:** Blockworks found the pre-open mid closer to the open "only 50.7% of the time", with "a median
    improvement of approximately 0.4 bps — effectively no signal" (verbatim,
    [Blockworks Research](https://blockworks-research.beehiiv.com/p/when-markets-sleep), 23 HIP-3 equity markets, 146
    weekend samples).
  - So the information content of closed-market perps is contested. A lag is not ruled out either way.
- **Korean retail concentration** in Samsung and SK Hynix and 24/7 perps on SMSN, SKHX, HYUNDAI and EWY are reported
  by [4pillars](https://research.4pillars.io/en/research/korean-stocks-now-trade-247-marketsxyz-and-the-retail-opportunity)
  (lead, search snippet).
- **Hazard.** SKHX "briefly fell to $927" and recovered "within roughly two minutes" on 2026-07-28 during Korean
  pre-market, with the cause unresolved (lead,
  [CryptoSlate](https://cryptoslate.com/inside-the-brutal-2-minute-flash-crash-sending-a-400m-south-korean-market-plunging-on-hyperliquid/)).
- **OWN-PRECHECK volumes** (xyz 24 h at 07:15 UTC Monday): SKHX $14.9M, SKHY $9.0M, SMSN $8.1M, EWY $7.3M, MU $21.3M,
  SOXL $11.6M. Thin, and excluded: KR200 $0.1M, HYUNDAI $0.2M, EWJ $0.3M, JP225 $0.8M, NIFTY and IBOV $0.0M. All
  listed names are in growth mode.
- No study of intraday cross-session lead-lag on HIP-3 was found.

**Data.**
- **Forward:** HL WS `bbo`/`trades` plus `activeAssetCtx` (oraclePx) for xyz SMSN, SKHX, SKHY, EWY, MU and SOXL. The
  same connection pattern as the recorder's `hl` stream.
- **History:** xyz 5m candles back to 2026-09-17. That is **inside the reserved window, so counts only.**

**Pre-registerable rule (12 configs).**
- **Leader/follower map, frozen now:**
  - US cash hours: leaders {EWY, MU, SOXL}, followers {SMSN, SKHX};
  - Korean cash hours: leaders {SMSN, SKHX}, followers {EWY, SKHY, MU, SOXL}.
  - Only pairs whose follower is *closed* and leader *open* by exchange calendar. US half-days and Korean holidays
    follow the Pyth schedule strings, which are free metadata.
- **β:** per pair, from the trailing 10 sessions of 5-min mid returns in that configuration, frozen daily.
- **Trigger:** the leader mid moves by θ or more over 60 s. Fire if the follower's same-direction move is ≤ β × move ÷ 2.
- **Entry:** follower taker at + 300 ms. **Exit:** taker at + H. One position per follower; cooldown H.
- **Grid:** θ ∈ {10, 20} bp × H ∈ {1, 5, 15} min × leader price ∈ {xyz mid, xyz oraclePx} = **12**.
- **Costs:** 0.9 bp per side × `deployerFeeScale`, the book walk, and funding if a settlement is crossed.

**Trades/day.** Unknown. Count 10–20 bp 60-s moves of the leaders on the 5m-candle window before freezing θ.
Roughly 13 open-leader hours a day across two sessions makes **10–30/day plausible** at θ = 10 bp.

**Gross vs full cost.**
- **Gross:** EWY → SMSN β is probably 0.5–1, so a 15 bp EWY move implies 7–15 bp. If the closed-market perp absorbs
  half within 1–15 min, the gross is **about 4–8 bp**.
- **Cost:** about 2.5–4 bp.
- **Ratio:** about 1.5–2.5×.

**Kill risk.**
1. **Intraday co-movement across closed sessions may be weak** (the US and Korea have different news), so β is noisy.
2. **Followers are retail-heavy and thin.** Flash events like SKHX produce top-3 outliers.
3. **The internal EWMA oracle and funding pull the follower back toward its stale oracle**, slowing exactly the
   catch-up we bet on. That is in the bet's favour for lag but against short-H capture.

---

### Idea 4. Cross-venue basis convergence between zero-fee equity perps: Lighter, Aster and trade[XYZ] (H-EQBASIS)

**Mechanism.**
- The same stock perp lists on three cheap venues, each with **different off-hours anchors**:
  - xyz: an internal EWMA oracle (DOC);
  - Binance: an index fixed at the last value, with an EWMA mark (lead);
  - Lighter and Aster: not documented here.
- So their funding pulls toward different references, and venue-local flow (retail market orders, liquidations)
  dislocates one venue's mid from the others.
- A two-leg convergence trade (sell the rich venue, buy the cheap one) is market-neutral, unlike EQLAG's directional
  catch-up, and it pays 0–0.9 bp per side per leg.

**Evidence.**
- **Cross-venue deviations exist and revert** (Makarov and Schoar, JFE 2020, round 4; DATA, crypto spot).
- **Cash-hours bases are small**: "Gold/silver ±10 bps. WTI/Brent ±15–25 bps" (verbatim,
  [Allium](https://www.allium.so/reports/when-wall-street-sleeps)).
- **OWN-PRECHECK, snapshot** (07:13 UTC Monday, cash closed; mids in bp relative to xyz):

  | Name | Lighter | Aster |
  |---|---|---|
  | TSLA | +0.4 | +6.7 |
  | NVDA | +1.7 | +9.6 |
  | COIN | −0.2 | +15.3 |
  | HOOD | +7.3 | +11.3 |
  | CRCL | +8.5 | +6.6 |
  | MSTR | −1.2 | +7.6 |
  | AMZN | +1.8 | +9.9 |
  | GOOGL | +2.6 | +5.5 |
  | META | −0.8 | +5.7 |
  | AAPL | +1.8 | +11.4 |

  **Aster sits 5–15 bp above xyz on every name**, so that is a level, not a dislocation, and the rule de-means it.
  Lighter is within ±3 bp except HOOD and CRCL.
- **OWN-PRECHECK, 10-minute sampler:** see the addendum at the end of this idea.

**Data.**
- **Forward:** Lighter `ticker/<id>`, xyz `bbo`, and Aster `bookTicker` for stock perps. The recorder's Aster stream
  currently covers crypto only, so add TSLA, NVDA, COIN, HOOD, CRCL, MSTR, AAPL and QQQ.
- **Funding:** hourly snapshots of each venue's funding.
- **History:** none for Lighter or Aster.

**Pre-registerable rule (12 configs).**
- **Basis:** for each name and venue pair (i, j), b = ln(mid_i ÷ mid_j). The level m is the trailing 60-min median of
  b, and the deviation is x = b − m.
- **Entry:** when |x| ≥ k and both books show ≥ $1k at the touch, take both legs: sell rich, buy cheap. Leg arrival is
  + 300 ms (Lighter + 600 ms). Walk both books. Skip if x has halved by arrival.
- **Exit:** both legs taker when |x| ≤ k/4, or at T.
- **Grid:** k ∈ {6, 10, 15} bp × T ∈ {5, 30} min × pair ∈ {Lighter–xyz, Aster–xyz} = **12**. Names: TSLA, NVDA,
  COIN, HOOD, CRCL, AMZN, GOOGL, META, AAPL. MSTR is in the Lighter–Aster arm only via a later amendment; it is not in
  this grid, because xyz MSTR is 9 bp.
- **Costs:** fees (xyz 0.9 bp per side; Lighter and Aster 0, re-checked hourly), both books walked, and funding on
  both legs.
- **Trade unit:** one pair round trip, both legs costed.

**Trades/day.** Unknown. Count |x| ≥ k on the first forward day. Nine names × two pairs, with dislocations driven by
retail flow in thin books: **≥ 10/day plausible at k = 6–10**.

**Gross vs full cost.**
- **Gross:** about 0.75 × k = **4.5–11 bp**.
- **Cost:** two spreads plus 1.8 bp of xyz fees, so **≈ 3–7 bp**. Lighter equity spreads were 0.3–3.5 bp and xyz
  0.2–2.2 bp in round 7.
- **Ratio:** about 1–2× at k = 6, and 1.5–3× at k = 10–15. This is the thinnest margin of the round, and it needs the
  wider k.

**Kill risk.**
1. **Deviations are funding-driven and persistent**, not flow noise, so they do not revert within T.
2. **Two-leg legging risk** with a 300 ms gap between venues.
3. **Aster's real API fee and any speed bump are unverified.**
4. **Capital sits on 2–3 venues and bridges**, which is operational, not P&L.

**Addendum, OWN-PRECHECK 10-minute sampler:** _filled below (§1.4a)._

---

### Idea 5. Fade off-hours moves on equity perps when crypto is quiet (H-EQOFFREV)

**Mechanism.**
- Off-hours, equity-perp prices are made by small traders: weekend "median trade size drops from $1,245 to $196" and
  "Weekend volume across HIP-3 runs at roughly 0.31x of weekday levels" (verbatim, Blockworks).
- The off-hours oracle is an EWMA of the venue's own book, so nothing external anchors the price.
- If off-hours prices carry little information ("effectively no signal", Blockworks), then **moves made off-hours
  without a crypto driver are mostly liquidity shocks, and they revert** (Nagel, RFS 2012, short-horizon reversal
  as a liquidity-provision premium).
- A single-venue taker fade on xyz (0.9 bp) or Lighter (0 bp) is cheap enough to collect a reversal that 13 bp of
  cost would erase.

**Evidence.**
- **For:** Blockworks (above), 50.7% and 0.4 bp. Liquidity-provision reversal: Nagel 2012 (round 4).
- **Against:**
  - Allium: "Friday's close misses Monday's open by 113 bps", while "the Sunday afternoon onchain perp gets you to
    ~80 bps, a 25 bps structural edge" (verbatim, Allium, 60 days of 5-min data). Weekend moves are partly informed.
  - Real off-hours news (earnings after 20:00 UTC, macro releases, M&A) moves prices permanently.
- **Weekend spreads are tight:** "median 0.93 bps versus 2.4 bps during normal hours" (verbatim, Blockworks).
- This is distinct from XSREV, which was cross-sectional, crypto, 1–4 h, at 13 bp cost.

**Data.**
- **Forward:** xyz `bbo` and Lighter `ticker` for 10 large single names: TSLA, NVDA, AAPL, AMZN, GOOGL, META, MU, AMD,
  INTC, PLTR.
- **Calendar:** the Pyth schedule strings (free metadata) or the NYSE calendar.
- **Leader filter:** Binance BTCUSDT.
- **History:** xyz 5m candles back to 2026-09-17 (reserved window, counts only).

**Pre-registerable rule (12 configs).**
- **Window:** cash closed, **excluding** 20:00–22:00 UTC (after-hours earnings news) and 12:00–13:30 UTC (pre-open
  macro releases).
- **Signal:** the name's 15-min mid return r is at least k × σ, where σ is that name's trailing 10-day sd of 15-min
  off-hours returns. **And** |BTC 15-min return| < 30 bp, **and** the cross-section of the 10 names did not move the
  same way (median 15-min return of the others < r/3). The last two leave crypto- and macro-driven moves to ideas 2
  and 3.
- **Entry:** taker against r at + 300 ms (Lighter + 600 ms). **Exit:** taker at H, or at the next cash open, whichever
  is first.
- **Grid:** k ∈ {2, 3} × H ∈ {30 min, 2 h, until next cash open (capped 60 h)} × venue ∈ {xyz, Lighter} = **12**.

**Trades/day.** Unknown; count it on the candle window before freezing k. Ten names over about 17.5 off-hours hours a
day: a 2σ isolated move per name-day gives **≈ 10/day**, more on weekends.

**Gross vs full cost.**
- **Gross:** off-hours 15-min σ is maybe 8–15 bp, so a 2–3σ move is 16–45 bp. If half reverts, that is **about
  8–20 bp**.
- **Cost:** xyz about 2.5–4 bp; Lighter about 1–3.5 bp.
- **Ratio:** about 3–5× if the reversal exists; below 1 if Allium is right that off-hours moves are informed.

**Kill risk.**
1. **Informed off-hours news.** An unseen news calendar causes the top-3 losers. The 20:00–22:00 exclusion helps but
   does not cover weekend headlines.
2. **Trend-following off-hours flow** (TWAPs begin with the trend; idea 1) carries the move on.
3. **The 60-h hold variant carries weekend gap risk** at the open.

---

### Idea 6. Catch liquidation wicks with deep resting orders on meme perps (H-WICKNET), category (a)

**Mechanism.**
- Liquidation sweeps and fat-finger market orders on thin perp books print far through the fair price for seconds,
  then snap back once the forced flow ends.
- A **resting** post-only order placed d bp from a reference (the Binance mid for cross-listed coins, or the coin's own
  trailing 2-min median) fills **only** on such prints. Per fill it collects most of d (target ≥ 25 bp) when the wick
  reverts.
- **Why this is not HLANCHOR:**
  - HLANCHOR quoted at the touch (k = 10–20 bp from fair), where fills come from informed flow ahead of Binance.
  - A 50–200 bp resting order fills only in local dislocations. A market-wide filter (skip when Binance itself has
    moved) removes the informed-flow case.
  - Fees are irrelevant at ≥ 25 bp: maker 1.5 bp on HL, 0 on Lighter.
- **Why this is not FLUSH:**
  - FLUSH bought 15–120 min after minute-bar OI and price flushes, and those kept falling.
  - Here the hold is seconds to minutes, and the reference is the *other venue's* price, which the wick has not moved.

**Evidence.**
- Brogaard, Carrion, Moyaert, Riordan, Shkilko and Sokolov (2018), "High frequency trading and extreme price
  movements", JFE 128(2) 253–265 (DATA; search summary of
  [the abstract](https://digitalcommons.memphis.edu/facpubs/11579)):
  - HFTs supply liquidity during single-stock extreme price movements and "speed up the reversal process";
  - but when several stocks move at once, "HFT liquidity demand dominates their supply".
  - That is the basis for the market-wide filter.
- Liquidation-cascade structure on HL (Garcia Seuma, arXiv 2608.03616; DATA-weak, single author,
  [IDEAS](https://ideas.repec.org/p/arx/papers/2608.03616.html)): 88% of forced selling came within 30 min, and 63% was
  absorbed off-book by HL's backstop.
  - **This cuts against the idea for HL**, because the backstop absorbs flow that would otherwise wick.
- **Anecdotes:**
  - "CASHCAT wicked to $0.08 in three minutes on Hyperliquid, about 60% down, then snapped right back" (lead,
    [DEXTools](https://www.dextools.io/news/cashcat-hyperliquid-liquidation-wick-leverage-july-2026));
  - the SKHX two-minute crash and recovery (idea 3).
- **OWN-PRECHECK, trigger counts only** (cached Tardis HL `trades`, train and validation days, pre-2026-04). HL prints
  deviating from the coin's own trailing 2-min median, de-duplicated within 60 s, per coin-day:

  | Coin (days) | ≥ 50 bp mean / median | ≥ 100 bp mean / median | ≥ 200 bp mean / median |
  |---|---|---|---|
  | FARTCOIN (15) | 129 / 53 | 22 / 4 | 2.4 / 0 |
  | PUMP (8) | 96 / 68 | 8.0 / 3.5 | 0.5 / 0 |
  | WIF (17) | 27 / 25 | 1.1 / 1 | 0 / 0 |
  | kBONK (17) | 24 / 19 | 1.3 / 1 | 0 / 0 |

  - At d = 50 bp, four coins give ≥ 10/day easily.
  - At d = 100 bp, counts are bursty: the mean is far above the median, so a few volatile days dominate.
  - These are counts of prints that would *touch* a resting order, not fills, and not outcomes.

**Data.** **History exists.**
- Tardis free first-of-month HL `quotes` and `trades` plus Binance `book_ticker`, already cached for WIF, kBONK,
  FARTCOIN and PUMP (`data/raw/web/tardis/parquet/`, 57 coin-days), and for TRUMP and SPX (newcoins).
- So train (≤ 2025-06) and validation (2025-07..2026-03) can be run on the perp calendar before any forward record.
- **Forward:** HL `trades`/`l2Book` and Lighter `trade`/`order_book`.

**Pre-registerable rule (12 configs).**
- **Quotes:** keep a post-only bid at ref × (1 − d) and an ask at ref × (1 + d). Refresh when ref moves more than
  d/5. Every place or cancel takes 300 ms (Lighter Standard: cancels also + 300 ms, DOC).
- **Fill:** only on a print strictly through our price while the order is live (HLANCHOR trade-through rule).
- **Market-wide filter:** do not quote, or cancel, while |Binance BTC 60-s move| ≥ 30 bp or |the coin's own Binance
  mid 10-s move| ≥ d/2.
- **Exit:**
  - a post-only exit at ref, or taker at + H;
  - a 2d stop.
- **Inventory:** one unit per coin.
- **Grid:** d ∈ {50, 100, 200} bp × H ∈ {30 s, 5 min} × ref ∈ {Binance mid × (1 + trailing-10-min basis), own
  trailing 2-min median} = **12**.
- **Costs:** HL maker 1.5 bp + taker 4.5 bp on a timed exit; Lighter 0. The full spread on a taker exit.

**Trades/day.** At d = 50 bp, likely 10+ fills a day across 4–6 meme coins. That is fewer than the touch counts above,
because a trade-through is required and the BTC filter removes some. At d ≥ 100 bp, below 10/day except on volatile
days. **Count fills on train before any P&L.**

**Gross vs full cost.**
- **Gross:** if half of the wicks revert to ref within H, the gross is roughly 0.5d − 0.5 × continuation. At d = 50,
  that is **≈ 25 bp** only if continuation losses stay small.
- **Cost:** 6–9 bp on HL; 0–3 bp on Lighter.

**Kill risk.**
1. **Falling knives** (the FLUSH lesson): fills cluster in real crashes, and the 2d stop and the top-3 rule bite.
2. **Fill-model optimism:** a single liquidation print through our price may have been smaller than our size.
   Require print size ≥ our size.
3. **HL's backstop (HLP or liquidator) absorbs** the flow that would wick.

**Kill test (train).** If the mean signed markout of filled orders at + 30 s, before fees, is below +15 bp at d = 50,
stop.

---

### Idea 7. The Binance TradFi index as a visible cash-hours leader for equity perps (H-IDXLEAD), lowest

**Mechanism.**
- Round 7's EQLAG names its main kill risk: during cash hours all perp venues follow an **unseen** leader, the stock
  itself.
- Pyth's equity feeds now return HTTP 401, so they are not free. But Binance publishes its TradFi **index** (built
  from "multiple vendors, updating every second during market hours") on the free `markPrice@1s` stream (`i` field,
  `/market` route).
- If that 1-s index leads the perp mids on Lighter, xyz or Aster by more than our 300–600 ms, a cash-hours taker on a
  0–0.9 bp venue can trade it.
- **Scheduled stratum:** at 13:30 UTC the open auction prints. The index jumps to it, and all perps converge.

**Evidence.**
- Index cadence and off-hours fixing come from Binance-sourced pages (lead, above).
- OWN-PRECHECK: the stream works on `/market` only, and the index is live at 03:08 ET.
- No study was found.
- **Prior: low.** A 1-s, multi-vendor index is probably *slower* than perp market makers who see direct exchange
  feeds.

**Data.** Forward only. `wss://fstream.binance.com/market/stream?streams=<sym>@markPrice@1s` for the recorder's
equity names, added next to `bookTicker`.

**Pre-registerable rule (12 configs).**
- **Trigger:** the index moves by θ or more between consecutive 1-s updates, and the follower's mid has moved less than
  θ/2.
- **Entry:** follower taker at + 300 ms (Lighter + 600 ms). **Exit:** + H.
- **Grid:** θ ∈ {3, 6, 10} bp × H ∈ {5, 30} s × follower ∈ {Lighter, xyz} = **12**.
- **Pre-check 0 (day 1, unscored):** a Hayashi–Yoshida lead estimate of the index against each perp mid. **Stop if the
  index does not lead.**

**Trades/day.** Unknown. Count it on day 1. Single stocks move 3–10 bp per second mostly around the open and on news.

**Gross vs full cost.** If it leads, about 2–5 bp gross against 0.5–4 bp of cost. The ratio is about 1–2×.

**Kill risk.** The index lags the perps, which is the likely outcome. The 1-s cadence is too coarse. Its vendor
composition is unknown.

---

## 2. Ranking

The score is gross ÷ cost × evidence × time to 50 forward trades, and novelty against rounds 1–7.

| Rank | Idea | Cat. | Venue (cost/side) | Round-trip cost | Expected gross/trade | Gross ÷ cost | History | Trades/day (est.) | Days to 50 | Evidence | Main kill risk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **H-TWAPXYZ**: ride HIP-3 TWAPs | b (gross near a) | xyz growth 0.9 bp | 2.5–4 bp | 12–22 bp (validator-perp paper) | ~3–6× | Forward (recorder already captures it) | 8–19 (OWN, 24 h) | 3–7 | DATA preprint (other population), OWN counts | HIP-3 TWAPs are hedges with little drift; ethics review |
| 2 | **H-WICKNET**: deep resting orders catch wicks | a | HL maker 1.5 / Lighter 0 | 6–9 bp HL, 0–3 Lighter | ~25 bp at d = 50 if wicks revert | ~3× (HL) | **Full: Tardis train/valid cached** | 10+ at d = 50 (OWN touch counts) | train today; forward 1–5 | DATA (Brogaard et al. 2018), OWN counts, anecdotes | Falling knives (FLUSH); fill-model optimism |
| 3 | **H-BETALAG**: BTC → MSTR/COIN/HOOD/CRCL perps | b | Lighter 0 / xyz 0.9 | 2–4 bp | 3–10 bp | ~1–3× | Binance 1m 2026-02..03 (proxy venue), forward | ≥ 20 weekdays | 2–4 | OWN lag-1 corr 0.07–0.15 (stale-print caveat) | Lag is a stale-print illusion; MMs hedge off BTC |
| 4 | **H-EQOFFREV**: fade isolated off-hours equity moves | b | xyz 0.9 / Lighter 0 | 1–4 bp | 8–20 bp if reversal exists | ~3–5× or < 1 | Counts only (reserved window) | ≈ 10 (to count) | 5–10 | DATA-weak (Blockworks vs Allium disagree), Nagel | Off-hours moves are informed (Allium) |
| 5 | **H-CLOSEDPROXY**: open-market proxy → closed-market perp (US ↔ Korea) | b | xyz 0.9 | 2.5–4 bp | 4–8 bp | ~1.5–2.5× | Counts only | 10–30 (to count) | 2–5 | lead (4pillars 45/62, contested by Blockworks) | Weak intraday cross-session β; thin, flash-prone followers |
| 6 | **H-EQBASIS**: two-leg convergence across Lighter/Aster/xyz | b | 0–0.9 per leg | 3–7 bp | 4.5–11 bp | ~1–3× | Forward only | ≥ 10 (to count) | 2–5 | DATA (Makarov–Schoar), OWN snapshot + sampler | Funding-driven persistent basis; legging; Aster API fees unverified |
| 7 | **H-IDXLEAD**: Binance TradFi index leads perps in cash hours | b | Lighter 0 / xyz 0.9 | 0.5–4 bp | 2–5 bp if it leads | ~1–2× | Forward only | unknown | 1–5 | none (OWN reachability only) | Index lags the perps |

**Suggested order.**
1. **H-WICKNET on train today.** It is the only idea with cached pre-holdout history (Tardis HL and Binance, 57+
   coin-days) and the only category-(a) idea. Count trade-through fills first, then run the +30 s markout kill test,
   then P&L.
2. **H-TWAPXYZ: freeze now.** The data is already being recorded; only `xyz:*` bbo/trades for active TWAP names need
   adding. Run the ethics review in parallel (as for TWAPRIDE).
3. **Extend `multivenue_recorder.py` once, for ideas 2–5 and 7:**
   - Lighter `ticker` for HOOD, CRCL, AAPL, AMZN, GOOGL, META, AMD, PLTR;
   - xyz `bbo` plus `activeAssetCtx` (oraclePx) for COIN, HOOD, CRCL, SMSN, SKHX, SKHY, EWY, MU, SOXL and the 10
     EQOFFREV names;
   - Aster stock-perp `bookTicker`;
   - Binance `markPrice@1s` on the `/market` route.

   Then count triggers for 1–2 days (unscored) and freeze θ, k and the beta windows.
4. **H-BETALAG history** (Binance 1m MSTR/COIN/HOOD/CRCL, 2026-02..03) only if the owner approves the split
   deviation. Otherwise run forward only.

---

## 3. Considered and dropped (do not re-research)

| Lead | Why dropped |
|---|---|
| **Passive quoting on Lighter, protected by the taker speed bump (H-LIGHTMAKER)** | The Lighter doc fetched this round says Standard **Cancel/Modify latency is 300 ms**, the same as the taker bump, so a Standard maker has no speed advantage over a Standard taker. Premium makers cancel at 0 ms, but Premium takers arrive at 140 ms plus their own reaction (a few ms for co-located firms), while our cancel arrives at about 300 ms (brief). We are still last. This is HLANCHOR's adverse selection with a 0.4 bp maker fee instead of 1.5 bp. QIMAKER showed the touch-level signal is about 1 bp. |
| **Pyth equity prices as the cash-hours leader** | Hermes price endpoints return **401** from here (`latest`, `stream`, benchmarks). Metadata is free (1,250 equity feeds, 50 ms channels). Replaced by idea 7's Binance index. |
| **FUNDCLOCK pre-settlement leg executed on Lighter** | The only gross-positive cell (PRE_w5_thr0.10%, +10.6 bp gross) traded 782 times in 2.5 years, **about 0.85/day**. At 0.03%, n is enough (6.6/day) but the gross is +2.3 bp, about one Lighter spread. It fails (a) and (b). |
| **ITSM, XSREV, PAIRS, QIMAKER moved to a 0 bp venue** | Their gross was 0–4 bp (XSREV 0–2.5, ITSM ≤ +4.3 at best, PAIRS train −11 to −0.1, QIMAKER ≈ 1). That is one Lighter spread or less. LSRATIO-on-Lighter is already the post-hoc candidate. |
| **xyz MSTR or GOLD as the execution venue** | Not growth-eligible (DOC): 9 bp taker. Use Lighter (0 bp) or Aster for MSTR and Lighter for XAU. EQLAG's pre-registration already prices this. |
| **Weekend → Monday-open convergence** (trade the Friday close against the Sunday perp) | One trade per name per week, which fails n. The literature disagrees (Blockworks 50.7% / 0.4 bp; Allium 25 bp). Idea 5 uses the intraday version. |
| **Korean-stock open-gap trades** (4pillars' 45/62 direction calls) | One per name per day, on 3–4 liquid names: fails ≥ 10/day. Idea 3 uses the continuous version. |
| **HIP-3 funding carry off-hours** (EWMA oracle against the book) | Carry decayed across five families. HIP-3 funding at 07:1x UTC was 0.06–0.31 bp/h on the listed names: too small, and hourly. |
| **SKHX/SKHY ADR premium arbitrage** ([Webull](https://www.webull.com/news/15259972833993728) reports a 51% SKHY premium) | Not a convergence trade with a known horizon. The premium is structural (ADR access constraints), and it needs a cash-ADR leg that we cannot trade. |
| **Liquidation-cascade early warning** (Garcia Seuma, arXiv 2607.27070) | The author finds the warning signals event-heterogeneous ("silent in exactly the two sudden-news (tariff) shocks"), and seven events a few years apart fail n. |

## 4. Gaps

- **Barone and Lillo cover validator perps only.** Whether HIP-3 TWAPs have comparable impact is unknown. The
  H-TWAPXYZ counts are one 24-h window on a Sunday–Monday, with current, not point-in-time, volume.
- **Aster stock-perp fees** come from a December 2025 news item. The API commission and any order-entry delay need a
  key to verify. The Aster premium of +5–15 bp over xyz was not explained.
- **The Binance TradFi index** composition, and whether it covers the overnight session (it moved at 03:08 ET), come
  from secondary pages. The official FAQ was not fetched.
- **The BETALAG lagged correlations** use last-trade 1m closes with many zero-volume minutes. They are a
  feature-shape check, not evidence of lead.
- **4pillars pages returned 429**, so their figures come from search summaries. Blockworks and Allium were fetched,
  and the quotes are verbatim from the fetched pages.
- **Brogaard et al. (2018)** was read from an abstract summary only.
- **WICKNET counts** are touches against the coin's own median, not trade-through fills against a Binance reference.
- **Jurisdiction and ethics.** Equity perps on any of these venues need a legal check. H-TWAPXYZ inherits TWAPRIDE's
  ethics questions.
