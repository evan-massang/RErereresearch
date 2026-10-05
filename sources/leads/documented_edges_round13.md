# Documented edges, round 13: memecoin-only ideas from "who loses, and why"

_Agent: round 13, 2026-10-05 (container clock). This is a leads review only. No backtest was run, and no P&L, return,
markout, IC or win rate was computed from any price path. Web content is cited as a **lead** (`document` modality).
**DOC** marks official or protocol documentation. **OWN-PRECHECK** marks a check run from this container. Every
OWN-PRECHECK is descriptive only: reachability, article and filing counts, archive coverage. No price was loaded. The
precheck working files are in the session scratchpad, not in the repo._

**Scope.** Memecoins only (`reports/scope_memecoins_20261005.md`).
**Excluded by brief:** launch-and-dump (including being the creator), wash trading, sandwiching and any other MEV, and
non-public information. **Participant:** slow (≥ 1 s), small size, public data only.

**Read before writing:**
- `CLAUDE.md`, the brief and the scope note.
- `reports/failures/paper_loop_20261003.md` in full.
- The titles and verdicts of all 63 notes in `reports/failures/`. The longer reads were lsratio, flush, listshort,
  listbasis and memexs_holdout.
- `reports/candidates/` (hlanchor, hllag_newcoins, memexs, momentum, unlock).
- `reports/hypotheses/memexs_preregistration.json`, `liqmap_preregistration.json` and `pumplean_notes.md`.
- Rounds 10, 11 and 12 in full, plus the "considered and dropped" tables of rounds 2–11.

## 0. Framing: who loses money in memecoins, and which of those flows are still open to us

| who loses | how they lose | status in this project |
|---|---|---|
| Curve and young-pool buyers on pump.fun | They buy tokens that decay, against insiders, snipers and devs | Every long entry failed (H1–H8, iterations 1–24, CLEANMIG: −13% to −43% per trade). There is no short instrument. LP is the only seller-side route (LPSELL failed; LPHEDGE iteration 2 is running). **Closed.** |
| KOL and trend followers | They arrive after the informed flow | KOL front-run and Decu oracle failed. **Closed.** |
| Leveraged perp longs in manias | Funding, liquidations, and buying near the top | Carry was tested delta-neutral (FUNDCARRY, PROPCARRY, FFDIFF, LISTBASIS). Liquidation reactions were tested at minutes to hours (FLUSH, WICKNET). Positioning was tested hourly (LSRATIO) and cross-sectionally weekly (MEMEXS FUND7). **Open: the time-series, multi-day, crowding-conjunction version (idea 1).** |
| Lottery buyers of the whole meme sector | They overpay for right-skew; most memes decay | Within-meme cross-sections failed (MEMEXS holdout). **Open: the sector-level, beta-hedged "lottery premium" (idea 2).** |
| Small HL accounts | About 75–83% of HL addresses lose money (leads below) | Smart-wallet following was dropped (Zhai markout < fee). **Open: aggregate retail flow as a daily contrarian or momentum signal (idea 3).** |
| Attention-driven buyers | They buy at peak attention; Barber et al. find −3% over 5 days for stocks | NARRPEAK is blocked on pump.fun search completeness. **Open: Wikipedia pageviews, a public, long, retail-specific attention series (idea 4).** |
| Retail who buy scheduled "institutional" news | ETF launches, treasury-company announcements ("sell the news") | Exchange listings are covered (LISTSHORT, LISTANN, ANNWINDOW). **Open but n-limited: non-listing regulated catalysts (idea 5).** |
| Over-levered positions hit by scheduled margin-rule changes | Forced reduction at a pre-announced timestamp | **Open, n-limited (idea 6, monitor only).** |

**Two lessons constrain every idea below:**
1. **Gross must be in percent, not bp.** That means multi-day horizons (failure mode F1 of round 12).
2. **Validation n ≥ 50 in the 9-month 2025-07..2026-03 window.** Single-event families keep dying on this (LISTSHORT 9,
   LISTBASIS 12). Ideas 1–3 are continuous signals across coins; ideas 4–6 are events and are flagged accordingly.

**Shared holdout caveat.** Ideas 1, 2, 4 and 6 use the Binance archive split: train ≤ 2025-06-30, validation 2025-07-01
to 2026-03-31, holdout ≥ 2026-04-01. The momentum and memexs agents already ran holdouts on 2026-04..09 meme and
broad-perp prices. Those runs reported aggregate results only, but the period is no longer pristine for meme-sector
direction (memexs holdout: −131 bp a week; long rising-volume legs +0.34, short legs −0.67). Each pre-registration must
state this, and **forward data from the freeze date is the real judge**.

### OWN-PRECHECKS this round (2026-10-05)

| check | result |
|---|---|
| `python -m pipeline check-network` | X, Solana RPC and PyPI reachable. GeckoTerminal returned 403 to this check, and DexScreener's root returned 404. |
| **Binance options archive** (`data.binance.vision/data/option/daily/EOHSummary/`) | Symbols: BNB, BTC, **DOGE**, ETH and XRP. **DOGEUSDT has only 31 daily files (2023-08-30 to 2023-10-20).** BVOLIndex covers BTC and ETH only. The live `eapi.binance.com` returns **451**. |
| Meme options elsewhere | Deribit (any currency) lists BTC, ETH, SOL, HYPE, XRP, AVAX and TRX. Aevo lists BTC, ETH, SOL and HYPE. OKX option underlyings are SOL, BTC, ETH and XAU. Bybit returns 403. **No meme options history is reachable.** |
| **Binance CMS "Latest Binance News" (catalog 49)** | 4,439 articles, 2017-07 to 2026-10. **215 are leverage/margin-tier updates** (2021: 14, 2022: 29, 2023: 32, 2024: 49, 2025: 61, 2026: 29). Their bodies were parsed for 31 meme perp symbols. **72 articles name a meme.** A table-level parse gives meme-symbol tier events of about **140 train / 16 validation / 13 holdout**. The train count is inflated by multi-symbol 2024 tables. Median lead from announcement to effective time is **about 70 h** (52 events with a parsed effective time). |
| **Binance CMS "Latest Activities" (catalog 93)** | 3,167 articles. 1,189 are competition- or reward-like. **Only 17 name a meme** (train 10, validation 3, holdout 4), and most are referral or Earn promotions, not meme trading competitions. |
| **SEC EDGAR full-text search** (`efts.sec.gov`, keyless, 200) | Filing hits, 2024-01-01 to 2026-10-05: "Dogecoin" 1,307 (S-1 209, 8-K 145); "Shiba Inu" 219 (S-1 37); "Bonk" 868 (mostly fund boilerplate, so noisy); "Pudgy Penguins" 34; "Pepe" 308 (noisy); "Fartcoin" 0; "dogwifhat" 12. "Official Trump" returned HTTP 500. **Usable as timestamps only after manual curation.** |
| **Wikimedia pageviews API** (keyless) | 200 for Dogecoin, Shiba_Inu_(cryptocurrency), Pump.fun (from 2024-11-23), Popcat (an ambiguous article) and Memecoin. Others (Pepe, Bonk, Dogwifhat, Fartcoin, $Trump, Pudgy_Penguins, Moo_Deng, Floki) returned **429 rate limits**, so their existence is unverified. The API serves data back to 2015-07. |
| CoinGecko `/search/trending` | 200. Forward only, with no history. |
| pump.fun `coins/king-of-the-hill` | **404** (relevant to the KOTH example in §3). |
| Local caches | `data/raw/web/lsratio/metrics` holds Binance 5-min OI and ratio metrics for the daily top-30 HL-listed perps, 2023-01..2026-03 (memes included when in the top 30). `data/raw/web/momentum/{klines,funding}` holds daily klines and funding for 683/686 USDT-M symbols to 2026-03. The memexs 74-symbol meme universe is frozen in its pre-registration. `data/raw/web/liqmap/` holds HL `hl_trades`, `positions` and `ctx` for about 2 h on 2026-10-05; the recorder is not running now. |

---

## 1. Ideas (ranked in §2)

### Idea 1. Crowding blow-off and squeeze: fade the over-levered side of a meme perp at a multi-day horizon (H-BLOWOFF)

**Who loses.**
- **Short arm:** late leveraged longs who pile in after a run. They pay high funding and are liquidated when it unwinds.
- **Long arm:** crowded shorts in a low-float meme. They pay deeply negative funding and are squeezed.

**Why this is not a variation of what failed:**

| tested family | what it did | what is different here |
|---|---|---|
| MEMEXS `FUND7_low_long` | Weekly **cross-sectional sort** on 7-day funding | A per-coin **time-series event**: only extremes relative to the coin's own history, and only when three independent crowding gauges agree |
| LSRATIO | **Hourly** decisions on Binance account-ratio changes, held 1–8 h | Daily decisions, 3–7 day holds, and funding plus OI rather than account ratios |
| FLUSH / WICKNET | Buying **after** a deleveraging flush, at minutes to hours | Positions **into** the build-up of leverage, before the flush, and holds through it |
| FUNDCARRY / PROPCARRY | Delta-neutral; earns funding only | Directional (hedged against the meme basket); funding received is a secondary income |

**Mechanism.** In a leverage cycle (Geanakoplos-style), new leveraged buying lifts price, OI and funding together. When
all three are extreme against the coin's own history, the marginal buyer is exhausted, and the stock of leveraged
longs is the future forced seller. The mirror case is crowded shorts in low-float memes: negative funding plus rising
OI on a falling price is the squeeze set-up, and the long collects funding while waiting.

**Evidence (leads).**
- **For:** [Schmeling, Schrimpf & Todorov, BIS WP 1087](https://www.bis.org/publ/work1087.htm): high crypto carry
  (futures premium) predicts future crashes; carry is driven by trend-chasing small investors (cited in round 12).
- **For:** [He, Manela, Ross & von Wachter, arXiv 2212.06888](https://arxiv.org/html/2212.06888v5): perp–spot
  deviations are large and persistent.
- **For (squeeze arm):** project evidence from `reports/candidates/momentum.md`. That candidate's validation pass came
  from negative-funding receipts on squeezed coins. **Caveat:** that observation came from looking at the validation
  window, so the long arm's validation is **contaminated**. The long arm must be judged on train plus forward only, and
  the pre-registration must say so.
- **Against:** [Kogan, Makarov, Niessner & Schoar, "Are Cryptos Different?", JFE 2024](https://www.nber.org/papers/w31317):
  retail traders follow momentum in crypto (contrarian in stocks), so crowding can persist. A practitioner lead says
  funding is "a crowd meter, not a prophecy" ([luxalgo](https://www.luxalgo.com/library/concept/funding-rate.md),
  marketing-grade).
- **Against:** round 5 dropped the *unhedged cross-sectional* funding sort because HL price moves swamp funding
  (Robot Wealth lead). This idea is hedged and conditioned on a conjunction.

**Pre-registerable rule (12 configs).**
- **Universe:** the frozen memexs 74-symbol meme list and its eligibility (≥ $5M 30-day mean daily quote volume, ≥ 35
  daily bars).
- **Daily features at 00:00 UTC, using data stamped before t:**
  - F = sum of funding over the last 72 h;
  - O = ln(OI_t / OI_{t−72h}), from the 5-min metrics;
  - R = the 72 h return.
  - Each is ranked against the coin's own trailing 180 days, giving percentiles pF, pO and pR.
- **Short arm (blow-off):** pF ≥ q, pO ≥ q and pR ≥ q. Short at the next 1h open.
- **Long arm (squeeze):** pF ≤ 1 − q (funding negative in absolute terms as well), pO ≥ q and pR ≤ 1 − q. Go long.
- **Hedge:** the opposite position in the equal-weight eligible meme basket, at 60-day β.
- **Exit:** after H days, or on a stop at 2.5× the coin's 30-day daily σ against the position.
- **Grid:** arm {short, long} × q {0.90, 0.95} × H {1, 3, 7} d = **12**.
- **Diagnostics (not configs):** unhedged; a BTC hedge; a perp-volume/spot-volume trigger in place of O; and Binance
  funding-interval shortening (8 h → 4 h, which is visible in the `fundingRate` timestamps) as an alternative crowding
  flag.
- **Placebo:** the same coins on random non-event days, and the opposite sign.
- **Kill test (train):** the short arm's mean gross must be > 2 × cost in both train halves, with the placebo
  indistinguishable from 0. Otherwise stop before validation.

**Trades/week.** Not yet counted. A guess is 1–4 per arm across about 25–60 eligible memes, given that the three
gauges are correlated. Count events per split **before freezing**; if validation has fewer than 50 per arm at q = 0.90,
pool the arms or stop.

**Gross vs full cost.**
- **Cost:** Binance proxy of 5 bp taker per side plus 2–20 bp slippage per side by liquidity tier (the memexs tiers),
  about 15–50 bp per round trip, plus the hedge leg's cost. On Lighter the tight set costs 2–10 bp (round 11).
- **Funding:** in the short arm, funding is *received* (high positive). In the long arm, negative funding is
  *received*. This is a second income.
- **Gross needed:** the 3–7 day σ of a single meme is about 15–25%. A 2–4% mean reversal per event is **200–400 bp,
  about 5–10× cost.**

**Data.** Everything is archived and public.
- Binance `metrics` (5-min OI, from about 2021-12): cached for top-30 HL-listed symbols in `lsratio/metrics`. The
  remaining memes are a small fetch.
- `fundingRate` and klines: cached in `momentum/`.
- Splits: train ≤ 2025-06-30, validation 2025-07-01..2026-03-31, holdout ≥ 2026-04-01 (see the caveat in §0).
- Forward: Lighter funding and 1m candles, with HL `metaAndAssetCtxs` for OI.

**Kill risk: medium.**
- Crowding can trend (Kogan et al.), and squeezes hurt the short arm. The stop and the 1-day hold arm bound this.
- The thresholds are coin-relative, so newly listed coins need 180 days of history, which removes the most crowded
  episodes. **That is deliberate:** it keeps LISTSHORT's territory out.
- The long arm's validation is contaminated (see above).

---

### Idea 2. The meme lottery premium: a beta-hedged short of the meme-perp sector (H-LOTTOSHORT)

**Who loses.** Holders of the meme sector as a whole: investors who prefer lottery-like right skew, plus leveraged longs
who pay funding most of the time. New memes keep diluting attention, and most perp-listed memes decay after their
mania (LISTSHORT's pre-hedge drift; the UNLOCK note: "coins with heavy vesting fall all the time").

**Why this is not a variation of what failed.**
- MEMEXS and momentum select **within** a cross-section (meme versus meme, or perp versus perp). This is a bet on the
  **sector against BTC**. The selection question is not asked.
- Carry was delta-neutral spot against perp. Here funding is collected as a by-product of a directional, beta-neutral
  short.

**Mechanism.** Lottery preference (Kumar 2009; Bali, Cakici & Whitelaw 2011) makes skewed assets overpriced, and
short-sale constraints keep them so (Miller 1977). Perps lift the constraint, but retail leverage (the funding premium)
keeps the long side crowded.

**Evidence (leads).**
- **For:** Grobys & Junttila, "Speculation and lottery-like demand in cryptocurrency markets", *J. Int. Fin. Markets,
  Inst. & Money* 2021 ([IDEAS](https://ideas.repec.org/a/eee/intfin/v71y2021ics1042443121000081.html),
  [JYX](https://jyx.jyu.fi/handle/123456789/74624)): the low-minus-high MAX quintile return exceeds 1.5% a week,
  robust to Bitcoin risk.
- **Against:** round 12 cited Özdamar, Akdeniz & Şensoy 2021, with high-MAX coins earning *more*. The two leads
  conflict, so the prior is low–medium.
- **Against:** Liu, Tsyvinski & Wu (*J. Finance* 2022, from memory, link not checked): a size premium in small coins.
- **Against:** meme manias (2024 Q1, 2024 Q4) produced squeezes of +100–300% in the basket.
- **Context:** this project's own holdout notes record a meme-sector decline in 2026-04..09 (memexs). That period
  therefore **cannot** serve as an untouched test (§0).

**Pre-registerable rule (12 configs).**
- **Rebalance:** each Monday at 00:00 UTC, using the memexs universe and eligibility.
- **Position:** short the meme basket and long BTC (or BTC plus SOL) at 60-day β-matched notional. Gross 1×, with 0.5×
  as a diagnostic.
- **Basket weighting:** equal weight, or inverse 30-day volatility.
- **Gate:**
  - G0: always on;
  - G1: on only if the basket's trailing 7-day mean funding > 0 (we are paid to hold);
  - G2: G1 and the basket's 28-day return < its 90-day median (do not short into an active mania).
- **Grid:** hedge {BTC, BTC/SOL 50/50} × weighting {EW, inverse-vol} × gate {G0, G1, G2} = **12**.
- **Unit and bar:** a coin-week leg (for n), plus a separate rule that the number of traded weeks is ≥ 26 per split,
  because legs within a week are one correlated bet.
- **Kill test (train):** net > 0 in at least 3 of 4 train half-years, and max drawdown < 35% at 1× gross.

**Trades/week.** About 25–60 legs, but one independent bet. Train (2023-01..2025-06) has about 130 weeks, and
validation about 39.

**Gross vs full cost.**
- **Cost:** low turnover (weights drift, so only about 10–30% of the weight is resized weekly), giving about **5–15 bp a
  week**. The BTC leg is about 1 bp.
- **Funding:** received at a 10–20%/yr basket mean, about **20–40 bp a week** while G1 holds (round 3 and PROPCARRY
  funding levels).
- **Gross if the lottery premium is about 20–50%/yr β-adjusted:** 40–100 bp a week. **Ratio about 3–8×.**

**Data.** Fully cached: momentum klines and funding to 2026-03, plus the memexs universe. Survivorship is the same as
memexs: today's CoinGecko list, with delisted symbols included through the archive.

**Kill risk: medium-high.**
- One bet per week, and it is regime-dependent. Mania squeezes produce the max-drawdown kill.
- The conflicting MAX evidence.
- The 2026 drift is known to us, so the forward period is the only clean test.

---

### Idea 3. Aggregate retail flow on HL meme perps, attributed by wallet, at a daily horizon (H-HLRETAIL). Forward only

**Who loses.** Small HL accounts. Leads: about 75% of HL addresses lose money
([HTX news, 2026](https://www.htx.com/news/data-75-of-traders-on-hyperliquid-are-losing-money-what-are-R2h1lIXH/)),
and only 166 of 1,000 sampled traders were profitable
([The Coin Republic, 2025-06](https://www.thecoinrepublic.com/2025/06/16/hyperliquid-crypto-only-166-of-1000-traders-profitable-whats-going-on/)).
Both are journalism-grade.

**Why this is not a variation of what failed.**
- LSRATIO used Binance's *aggregate account ratios* at hourly horizons.
- Smart-wallet following was dropped (Zhai: a top-ventile markout of 3.11 bp, below the fee).
- Here the signal is the **net taker flow of the losing population**, built from public per-trade wallet attribution:
  HL WebSocket trades carry `users = [buyer, seller]`, as confirmed in `liqmap_preregistration.json`. It is aggregated
  to a daily coin signal and traded over 1–3 days, so the gross is in percent.

**Mechanism.**
- **Fade arm:** attention-driven herding by retail predicts negative returns ([Barber, Huang, Odean & Schwarz, "Attention-Induced Trading and Returns: Evidence from Robinhood Users"](https://profiles.wustl.edu/en/publications/attention-induced-trading-and-returns-evidence-from-robinhood-use/):
  −3% (−6% for extreme herding) over 5 days).
- **Follow arm:** retail are momentum traders in crypto ([Kogan et al., JFE 2024](https://www.nber.org/papers/w31317)),
  so their flow could be informative or persistent.
- **Both arms are pre-declared. The sign is the hypothesis.**

**Pre-registerable rule (12 configs).**
- **Wallet class:** at first sight, look up `clearinghouseState` (public). "Small" means account value < $10k and
  maximum position leverage ≥ 5×. Reclassify weekly. The classifier is frozen before any return is computed.
- **Signal:** per meme per UTC day, S = net taker notional of small wallets (taker side from the trade's `side`), divided
  by the coin's total daily notional. z is against the coin's trailing 14 days.
- **Trade:** at 00:00 UTC, if |z| ≥ k, trade against S (fade) or with S (follow) on Lighter, at 0 fee and one spread.
  Hold H.
- **Grid:** arm {fade, follow} × k {1.5, 2.5} × H {1 d, 3 d} × universe {Lighter tight set (6 memes), all 20 TWAPRIDE
  memes} = 16. Freeze 12 by dropping k = 2.5 on the tight set, which is too sparse.
- **Kill test (first 3 weeks):** the rank IC of S against the next 1-day return must have the same sign in both halves.
  Otherwise stop.

**Trades/week.** 20 memes × about 5% of days with |z| ≥ 2 gives about **7 a week per arm**. n = 50 takes about **7–8
weeks**.

**Gross vs full cost.** The cost is Lighter's 2–10 bp (22–37 bp for SPX and POPCAT) plus 1–3 days of funding. A 1–3 day
meme σ is 8–15%, so a 1% conditional effect is 100 bp, **10× or more over cost**.

**Data.**
- `scripts/research/liqmap_recorder.py` already subscribes to HL trades with users and polls positions. It holds about
  2 h of data and is **not running**. It needs a daily-aggregation mode and a wallet-class cache.
- **Lookup budget:** HL `info` weights limit `clearinghouseState` calls. Classify only wallets above a notional floor
  (for example $500 a day).
- There is no history: the HL S3 archive is requester-pays (round 4).

**Kill risk: medium-high.**
- Forward-only, with a slow n.
- Wallet classification is noisy: many small wallets are sub-accounts of bots.
- The sign is ambiguous between Barber et al. and Kogan et al.
- Flow-based families have failed often in this project (QHOI, CBPREM, LSRATIO). **What differs is the horizon (days)
  and a population we know loses.**

---

### Idea 4. Peak-attention fade from Wikipedia pageviews (H-WIKIATTN)

**Who loses.** Buyers who arrive at peak public attention: non-crypto-native retail who look the coin up.

**Why this is not a variation of what failed.**
- MEMEXS VOLG used *trading volume* growth.
- NARRPEAK (pump.fun copycat counts) is **blocked on data completeness**, not failed.
- Wikipedia pageviews are a different, non-market, retail-specific attention series, keyless, with history from 2015.
  That covers the DOGE 2021 mania and every split.

**Mechanism.** An attention spike brings uninformed buyers. Once attention turns down, the price pressure reverses
(Da, Engelberg & Gao 2011; Barber et al. above).

**Evidence (leads).**
- **For:** [Kristoufek 2013, *Scientific Reports*](https://proquest.com/scholarly-journals/bitcoin-meets-google-trends-wikipedia-quantifying/docview/1898094865/se-2):
  strong *bidirectional* causality between Wikipedia/Google interest and Bitcoin prices, with asymmetric effects in
  bubbles.
- **Against:** Liu & Tsyvinski (*RFS* 2021): attention predicts *positive* 1–2 week crypto returns.
- **Against:** the memexs holdout's rising-volume (attention) long legs made money in 2026.

**Pre-registerable rule (12 configs).**
- **Series:** daily `user`-agent views for a frozen article list. Verified 200: Dogecoin, Shiba_Inu_(cryptocurrency),
  Memecoin and Pump.fun. To verify after the 429s: Pepe, Bonk, Dogwifhat, Fartcoin, $Trump and Pudgy_Penguins. The
  "Popcat" article is ambiguous (the cat meme), so exclude it.
- **Spike:** z = ln(views) against the trailing 28 days. The event is z(d−1) ≥ k and views(d) < views(d−1), i.e. the
  peak has passed.
- **Trade:** short the coin's Binance perp at 00:00 UTC of d+1 (a "Memecoin" or "Pump.fun" article spike shorts the
  meme basket), hedged with BTC. Hold H.
- **Grid:** k {2, 3} × H {1, 3, 7} d × target {own-coin articles, sector articles → basket} = **12**.
- **Controls:** the long sign, and random non-spike days.
- **Kill before any price:** count events per split. If validation has fewer than 30, stop. If it has 30–49, it is a
  monitor only.

**Trades/week.** Low: about 0.2–1, to count. Most spikes cluster in manias.

**Gross vs full cost.** The cost is 15–50 bp (Binance proxy) or 2–10 bp (Lighter). A 3–5% reversal over 3–7 days is
**300–500 bp, about 10× cost**, if the sign is right.

**Data.** Wikimedia REST pageviews (keyless; send a polite User-Agent and pace requests, since 429s were seen). Prices
are in the Binance archive cache. An adapter is needed: `pipeline/sources/wikimedia_pageviews.py`.

**Kill risk: high.**
- n (a small universe; few articles exist for Solana memes).
- The sign conflict.
- Reverse causality: a price spike causes views. The "peak passed" rule only partly addresses this.

---

### Idea 5. Scheduled regulated and institutional catalysts: buy the run-up, sell the news (H-CATCAL). Monitor

**Who loses.** Retail who buy a widely pre-announced "institutional" event on the day it happens: meme ETF launches,
treasury-company (DAT) purchase announcements, and regulated-futures launches.

**Why this is not a variation of what failed.** LISTSHORT, LISTANN and ANNWINDOW cover **exchange listings**. This idea
covers non-listing catalysts whose **date is known in advance**:
- the SEC's statutory 19b-4 deadlines;
- ETF effectiveness and first trading days;
- treasury-company 8-Ks;
- CME / Coinbase Derivatives futures launch dates.

**Evidence (leads).**
- **DOGE ETF (DOJE), 2025-09-18:** DOGE rose 13–17% in the week before; it "dipped by around 2 percent" in the first
  24 h, then rallied toward $0.30 ([Cointelegraph](https://cointelegraph.com/news/how-high-can-doge-price-go-first-dogecoin-etf-goes-live),
  [Analytics Insight](https://www.analyticsinsight.net/amp/story/dogecoin/dogecoin-etf-launch-marks-big-step-from-meme-to-wall-street);
  journalism, mixed).
- DOJE was expected to list alongside BONK and TRUMP ETFs (Cointelegraph lead). Meme ETF filings therefore span
  several coins.
- [Benedetti & Nikbakht, SSRN 3267392](https://papers.ssrn.com/abstract_id=3267392): event returns around access
  events (round 12).

**OWN-PRECHECK.**
- EDGAR full-text search works keyless: "Dogecoin" has 209 S-1 and 145 8-K filings in 2024-01..2026-10; "Shiba Inu"
  has 37 S-1; "Fartcoin" has 0.
- These are filings, not events. A curated event list (first S-1, 19b-4 acknowledgment, each statutory deadline,
  launch day, DAT 8-K) must be **frozen before any price is loaded**.
- Most events fall in 2025. **Expected n: train 15–30, validation 20–40.** This fails the bar unless forward data is
  added.

**Pre-registerable rule (12 configs).**
- **Event classes:** {deadline/decision day, first trading day, DAT announcement}.
- **Arms:** run-up long from T−7 d to T−1 d, or sell-the-news short from T to T+H.
- **Grid:** class (3) × arm (2) × H {2, 5} d for the short arm. The run-up arm has a fixed window, so 3 + 6 = 9 cells;
  add 3 placebo-shifted cells (T−30) to make 12.
- **Hedge:** the meme basket.

**Trades/week.** About 0.3–1.

**Gross vs cost.** The cost is 15–50 bp. Anecdotal moves are 5–20%.

**Kill risk: high.**
- n.
- Subjective event curation, so freeze the list with sources first.
- Leakage: deadlines are often decided early or extended.

**Use:** as a forward monitor and as an **exclusion window** for ideas 1 and 2 (do not short into a scheduled
catalyst).

---

### Idea 6. Pre-announced margin-tier cuts on Binance meme perps: forced deleveraging at a known time (H-TIERCHG). Monitor

**Who loses.** Large leveraged positions that must add margin or cut size when maintenance-margin rates rise or maximum
leverage falls at a pre-announced timestamp. The official text says "Existing positions opened before the update will
be affected" (Binance CMS, DOC).

**What is new.** No family has used exchange risk-parameter changes. The event is public, timestamped, and announced
about 70 h ahead (OWN-PRECHECK median). The crowded side, from the funding sign, gives the direction.

**Rule sketch.**
- Short (long) the perp from announcement + 1 h to the effective time + 2 h when funding is positive (negative).
- Hedge with the meme basket.
- Grid: entry {announcement + 1 h, effective − 6 h} × exit {effective + 2 h, + 24 h} × hedge {none, basket} ×
  direction-rule {funding sign, always short} = **16**. Trim to 12.

**OWN-PRECHECK.** Of 215 tier-update articles, 72 name a meme. The table parse gives about **16 meme events in
validation** (and 13 in the holdout window). **That is far below 50.** The effect is also probably small: only
notional above the tier boundaries is affected, and most holders add margin.

**Verdict now: do not run historically.** At most, run a cheap descriptive kill check: does OI fall at the effective time
relative to a placebo hour? Keep it as a forward monitor, or pool it with HL `meta` maxLeverage changes if a recorder
diffs `meta` daily.

---

## 2. Ranking

| rank | idea | who we take the other side of | full cost | gross if real | ratio | trades/week | train/val data | kill risk |
|---|---|---|---|---|---|---|---|---|
| 1 | **H-BLOWOFF**: crowding conjunction (funding + OI + return extremes), fade over 1–7 d, basket-hedged | Late leveraged longs; crowded shorts in low-float memes | 15–50 bp (Binance proxy), 2–10 bp (Lighter), plus a hedge; funding is *received* | 200–400 bp per event | about 5–10× | 1–4 per arm (count first) | **Full archive**, mostly cached (lsratio metrics, momentum klines/funding) | Medium: crowding persists (Kogan et al.); the long arm's validation is contaminated |
| 2 | **H-LOTTOSHORT**: short the meme-perp basket vs BTC (or BTC/SOL), funding-gated, weekly | Lottery-seeking sector holders; leveraged longs paying funding | 5–15 bp a week | 40–100 bp a week, plus 20–40 bp a week of funding | about 3–8× | 25–60 legs, 1 independent bet | **Full archive, cached** | Medium-high: mania squeezes; conflicting MAX evidence; 2026 already seen |
| 3 | **H-HLRETAIL**: daily net flow of small HL wallets on meme perps, fade or follow, traded on Lighter | Small HL accounts (75–83% lose, leads) | 2–10 bp plus funding | 100+ bp if a 1% effect | 10×+ | about 7 per arm | **Forward only** (the liqmap recorder exists but is stopped; it needs a wallet-class cache) | Medium-high: sign ambiguity, classification noise, slow n |
| 4 | **H-WIKIATTN**: short after a Wikipedia pageview peak passes (coin or sector article) | Peak-attention retail buyers | 15–50 bp or 2–10 bp | 300–500 bp per event | about 10× | 0.2–1 | Wikimedia 2015→ (keyless, 429s) + Binance archive | High: n, sign conflict (Liu–Tsyvinski), reverse causality |
| 5 | **H-CATCAL**: scheduled ETF, DAT and futures-launch catalysts: run-up long / sell-the-news short | Retail buying institutional news on the day | 15–50 bp | 5–20% (anecdotal) | large if real | 0.3–1 | EDGAR (keyless) + manual curation + Binance archive | High: validation n is about 20–40; curation subjectivity. Monitor, and use as an exclusion window |
| 6 | **H-TIERCHG**: pre-announced Binance margin-tier cuts on meme perps | Over-levered large positions | 15–50 bp | unknown, probably small | unknown | about 0.4 (validation) | Binance CMS (parsed) + archive | **n fails now (16 validation events)**. Monitor only |

**Recommended order of work.**
1. **H-BLOWOFF.** Count events per arm and split from cached features (no returns) before freezing. Then freeze the
   12 configs and run the train kill test.
2. **H-LOTTOSHORT.** Freeze it with an explicit statement that 2026-04..09 is not a clean test. Run train, then
   validation once, then forward.
3. **H-HLRETAIL.** Restart the liqmap recorder with a daily-aggregate mode and a wallet-class cache. Freeze the
   classifier before the first daily signal is computed.
4. **H-WIKIATTN.** Count spikes per split (views only) before loading any price.
5. **H-CATCAL / H-TIERCHG.** Monitors only.

## 3. Considered and dropped (do not re-research)

| lead | why dropped |
|---|---|
| **pump.fun King-of-the-Hill / front-page exposure** (example 3 in the request) | Already failed: iterations 15–16 (KOTH: 900 train trades, PF 0.59–0.73; validation worse). Neighbours also failed: livestream viewers (iteration 12, viewers rise *after* buying), BOOST, DEX-paid and round levels. Round 3's ATTNEXIT covers its use as an exit overlay. The public `coins/king-of-the-hill` endpoint returns 404 here (OWN-PRECHECK). |
| **Multi-hour mean reversion of meme perp basis across Lighter, HL and Binance** (example 4) | Round 11 dropped Lighter–HL basis convergence; H-EQBASIS was weakened; FFDIFF and FFDIFF-WIDE failed; PREMCONV found spikes revert within the minute. At multi-hour horizons the perp–perp basis is mostly the funding differential (a few bp to about 20 bp). A two-venue round trip costs 0–9 bp per leg plus 2–37 bp of spread. The gross is capped by the deviation itself. |
| **Post-rug / post-dump recovery in graduates with prop-AMM exits** (example 5) | Crash bounce failed (crashes continue: 0.82× after 300 s); iteration 8 failed (hour-scale; 24 h medians −61% to −99%); CLEANMIG failed. Round 11 found **100–900 bp round trips** for graduates under $10M, which prop AMMs do not quote cheaply. For large perp-listed memes, "buy after a dump" is FLUSH or MEMEXS R7_rev (both failed). |
| **Selling meme option volatility** (DOGE variance premium; retail overpays for right-skew) | **No data or venue.** The Binance DOGE options archive has 31 days (2023-08/10), and `eapi` returns 451. Deribit, Aevo and OKX list no meme options, and Bybit returns 403 (OWN-PRECHECK). Revisit only if a meme option venue with history becomes reachable. |
| **Binance meme trading competitions** (volume subsidies, then the unwind) | Only 17 meme-named reward articles among 3,167 (train 10, validation 3), and most are Earn or referral promotions (OWN-PRECHECK). Also too close to rewarding wash volume. |
| **Polymarket memecoin price ladders** ("PUMP above X", "DOGE hits Y") as a favourite-longshot sale | They are memecoin-referenced, but the user dropped the prediction-market families (H-PMDIGI, H-PMFLB) on 2026-10-05. **Ask the user** before reopening. |
| **Fading DOGE/TRUMP spikes after Musk or Trump posts** | Post history is paid (X API) or archive-only (Truth Social archive site reachable, 200). There are few crypto posts a year, so it fails n. The entry side is a seconds-scale race. |
| **Leveraged-ETF rebalancing flow** (2× DOGE/TRUMP ETFs, end-of-day) | Not measured. Judged immaterial: ETF AUM is a tiny fraction of DOGE perp volume. |
| **Treasury-company (DAT) meme purchases as flow** | Purchases are lumpy, with undisclosed execution timing. Announcements are folded into idea 5 as an event class. |
| **Tier-2 CEX spot listings (MEXC, Gate, Bitget) of pump.fun graduates** | High n, but the only position available is long DEX spot in small graduates at 100–900 bp round trips (round 11). It is a sibling of round 12's LISTANN. |
| **Reverse carry: long perp + borrow-and-sell spot when meme funding is deeply negative** | A carry-family variant (FUNDCARRY, PROPCARRY: too few episodes). Binance margin borrow-rate history is behind keyed `sapi` endpoints (not checked this round). Its directional half is idea 1's long arm. |
| **Attention substitution: short incumbent memes after a new meme perp listing** | The events are listings: validation has 9–12 (LISTSHORT, LISTBASIS). It fails n. |

## 4. Gaps

- **Event counts for ideas 1 and 4 are not done.** They need features or views only, with no returns, and come before
  any freeze.
- **The TIERCHG parse is approximate.** The effective time was parsed for 52 events; the leverage direction was not
  parsed reliably.
- **Wikipedia article existence** for Pepe, Bonk, Dogwifhat, Fartcoin, $Trump and Pudgy Penguins is unverified (429).
- **HL wallet classification cost** (the `clearinghouseState` weight budget) is not measured.
- **2026-04..09 is used up** for meme-sector direction by earlier holdout runs, so ideas 1, 2 and 4 need forward tests
  as the real judge.
- **Literature:** no study of time-series crowding conjunctions on meme perps, wallet-attributed HL retail flow, or meme
  Wikipedia attention was found. The priors above are judgement plus the cited general-crypto leads.
