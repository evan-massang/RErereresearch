# Documented edges, round 7: cheaper follower venues, other leaders, and Korean flow

_Agent: round 7, 2026-10-05. Leads review only: no backtest was run and no P&L was computed. Web content is
cited as **lead** (third-party pages, marketing, search snippets) unless it is official documentation, which is
marked **DOC**. OWN-PRECHECK marks a check from this container. Each one is descriptive (reachability, spreads,
volumes, one 10-minute response profile) and none is a strategy test._

## 0. Why this round looks where it does

The lesson of rounds 1–6 and the iteration log (`reports/failures/paper_loop_20261003.md`,
`reports/failures/agent_*.md`) is about costs:
- **Taker strategies die on cost.** Round trips cost 9–14 bp on HL or Binance perps and 50 bp or more on Solana
  DEXs, against gross edges of a few bp: XLEAD, XSREV, PREMCONV, FLUSH and the whole pump.fun family.
- **Carry decayed.** FUNDCARRY, FFDIFF(-WIDE), SPOTCARRY, DATEDBASIS and LSTCARRY failed, and they also fail on n.
- **H-HLLAG is the only survivor, and it is fragile.** It has a gross of about 13–20 bp per trade against about
  9 bp in fees plus the spread. It dies at 800 ms of latency (`reports/candidates/hlanchor.md`, `hllag_newcoins.md`).

The cost side is what can still change. Since 2025, three venues have priced taker flow far below HL's 4.5 bp:

| Venue / account | Taker | Maker | Catch | Source |
|---|---|---|---|---|
| **Lighter, Standard account** (API allowed) | **0** | **0** | **300 ms taker speed bump**; 4,000 sendTx/min | DOC [Lighter account types](https://apidocs.lighter.xyz/docs/account-types) ("Taker Latency: 300 ms"). A search snippet of the same page said maker/cancel latency is 200 ms; the fetched page says 0 ms. Re-read before freezing. |
| Lighter, Premium (0 LIT staked) | 2.8 bp | 0.4 bp | 140–200 ms taker latency | same page |
| **HL HIP-3 "growth mode" markets** (trade[XYZ] equities, metals, FX) | **0.9 bp** | 0.3 bp | Only for markets disjoint from validator perps, so **no crypto** | DOC [trade.xyz fees](https://docs.trade.xyz/perpetuals/mechanics/fees.md) ("Taker 0.0090%"); lead [The Defiant](https://thedefiant.io/hyperliquid-to-roll-out-growth-mode-to-supercharge-new-markets), [FXStreet](https://www.fxstreet.com/cryptocurrencies/news/hyperliquid-unveils-hip-3-growth-mode-slashing-fees-by-90-to-boost-new-markets-202511191148) |
| Aster Pro | 3.5 bp | 1 bp | Stock perps 0/0 (lead) | lead [Coin Bureau](https://coinbureau.com/review/what-is-aster-crypto) |
| MEXC futures | 2 bp | 0 | API order entry for futures has historically been restricted; unverified | MARKETING [MEXC guide](https://www.mexc.com/ru-RU/crypto-pulse/article/mexc-trading-fees-complete-guide-39643) |
| Paradex | 0 (retail UI) / 2 bp (API) | 0 / 0.3 bp | 500 ms speed bump for retail; 3 orders/s | lead [FalconX](https://www.falconx.io/newsroom/paradex-dime-the-zero-fee-privacy-first-perps-dex) |
| *Reference:* HL validator perps, tier 0 | 4.5 bp | 1.5 bp | — | DOC [HL fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees) |
| *Reference:* Binance USDⓈ-M, VIP0 | 5 bp | 2 bp | — | round 6 |

A rule with H-HLLAG's gross of about 13 bp nets roughly +1 to +4 bp on HL. On a 0–1 bp venue it would net about
+10 bp, **if the gross survives the venue's latency and its own market makers.** That condition is what ideas 1–2
test. Ideas 3–4 look for leaders other than Binance, and ideas 5–6 cover the remaining requested directions.

### Reachability from this container (2026-10-05, 06:00–06:25 UTC)

| Source | REST | Websocket | History |
|---|---|---|---|
| Binance USDⓈ-M | `fapi` 451 (round 6) | **OK**: `fstream.binance.com` bookTicker, about 50 msg/s per liquid coin | data.binance.vision 200, including **equity and metal perps** (TSLA, NVDA, INTC, COIN, HOOD, MSTR, SPY, QQQ, XAU, XAG USDT perps, 1m klines for 2026-09-01). The daily archive lags 1–2 days (2026-10-04 returned 404). |
| **Lighter** | **200**: `mainnet.zklighter.elliot.ai/api/v1/orderBookDetails` (237 markets, `taker_fee` "0.0000" on all), `orderBookOrders`, `recentTrades`, `trades` (recent only) | **OK only with `?readonly=true`**: `wss://mainnet.zklighter.elliot.ai/stream?readonly=true`, channels `order_book/{id}` and `trade/{id}`. Without the parameter: HTTP 400. | `candlesticks` returned 403. The trade history found is recent-only, so **forward only.** |
| HL validator + HIP-3 | 200 (`perpDexs`, `metaAndAssetCtxs` with `dex:"xyz"`, `l2Book` for `xyz:TSLA`) | OK (`bbo` for `xyz:TSLA`) | Tardis free days (validator perps; HIP-3 coverage unchecked) |
| Aster | 200 (`fapi.asterdex.com`, Binance-compatible) | OK (`fstream.asterdex.com`) | — |
| OKX | 200 | **OK on `wss://ws.okx.com/ws/v5/public` (port 443)**; port 8443 resets | — |
| Bybit | **403** (CloudFront geo-block) | **OK** (`stream.bybit.com/v5/public/linear`) | public.bybit.com trade archives (round 5) |
| Gate, Bitget, MEXC, KuCoin | 200 | OK (Gate, Bitget, MEXC tested) | — |
| **Upbit** | **200**: `ticker`, `market/all` (291 KRW markets), **`candles/minutes/1` with `to=` paging back to at least 2025-03** | **OK** (`api.upbit.com/websocket/v1`, trade channel) | Minute candles historical; ticks only ~7 days |
| Upbit notices (`api-manager.upbit.com`) | **403** | — | — |
| Bithumb | 200 | OK (`pubwss.bithumb.com`) | — |
| Binance announcements CMS (`bapi/composite/v1/public/cms/article/list/query`) | 200 | — | listing pages |
| Paradex | 200 (`/markets`, `/bbo`, `/orderbook`, **`/trades` with `start_at` back to 2025-03**) | not tested | yes |
| Solana public RPC | 200 (`getSlot`) | OK (`slotSubscribe`) | — |
| Jupiter `lite-api.jup.ag/price/v3` | 200 | — | — |
| GeckoTerminal | 429 on burst, 200 after a 20 s pause (pools, trades) | — | 15m OHLCV |
| Tokenomist unlocks | **401** (key) | — | — |
| DeFiLlama `api.llama.fi/emissions` | **402** (paid) | — | — |

---

## 1. Ideas (ranked in §2)

Common rules, as in rounds 4–6:
- **Freezing.** Freeze `reports/hypotheses/<id>_preregistration.json` (rule, grid, cost and fill model) before the
  first scored forward record.
- **Splits.** Where history exists, use the perp calendar: train ≤ 2025-06-30, validation 2025-07-01 to
  2026-03-31, and holdout ≥ 2026-04-01 untouched. Keep 2026-08 and 2026-09-01 out.
- **Reporting.** Report by day and by coin as well as by trade.
- **Latency.** Decisions use local receive time. Our order arrives at decision + 300 ms, plus the venue's speed bump.
- **Size and unit.** Units are $1k, and one round trip counts as one trade.

### Idea 1. Binance → Lighter catch-up on a zero-fee venue (H-LIGHTLAG)

**Mechanism.**
- This is H-HLLAG's mechanism (price formation on Binance; a follower venue's book catches up and then drifts with
  the leader for seconds), moved to a venue where taker flow pays **0 bp**.
- The round-trip cost falls from about 9 bp plus the spread to **the spread only**.
- The price is Lighter's 300 ms taker speed bump. The bump is there to protect Lighter's makers, who can cancel
  with no delay, from exactly this flow.

**Evidence.**
- **H-HLLAG markout profile** (OWN, `research/observations/evidence_hlanchor_train_20261005.json`): mean gross
  markout from the fill.

  | config | 1 s | 5 s | 30 s |
  |---|---|---|---|
  | θ40, L 300 ms | +9.4 bp | +14.7 bp | +15.9 bp |
  | θ25, L 300 ms | +4.7 bp | +7.3 bp | +8.2 bp |
  | θ25, L 800 ms | −0.1 bp | +1.6 bp | +2.5 bp |
  | θ15, L 800 ms | — | — | +0.2 bp |

  So **most of the gross is gone between 300 and 800 ms.** On new coins (TRUMP, SPX), θ40 L300 gave +13 to
  +20 bp (`evidence_hllag_newcoins_20261005.json`).
- **Lead-lag across Binance, HL and Lighter** (lead, practitioner blog using a Hayashi–Yoshida estimator on trade
  tapes of 29 assets over 16 days to 2026-02-26; [Arrakis](https://arrakis.finance/blog/crypto-price-discovery)):
  - "Binance led Hyperliquid" for 29 of 29 assets, by about 700 ms;
  - "Binance led Lighter" for 23 of 29, by only about 100 ms;
  - "Lighter led Hyperliquid" for 27 of 29.

  **This is the main warning.** Lighter re-prices about 600 ms faster than HL, so after a 300 ms bump plus our own
  300 ms, the instantaneous catch-up may be gone. Only the continuation would be left.
- **OWN-PRECHECK, 10-minute multi-venue recording** (2026-10-05 06:08–06:18 UTC; a quiet Monday morning, so
  **tiny n, indicative only**).
  - **Method.** Binance bookTicker mid moves of 5 bp or more in 1 s, non-overlapping within 5 s. For each follower,
    the signed move in bp from 1 s before the event, measured at +0 ms, +600 ms and +30 s after the event:

    | Coin, Binance move | n | Binance next 30 s | OKX | Gate | Aster | HL bbo | Lighter (trade prints) |
    |---|---|---|---|---|---|---|---|
    | PUMP, ≥ 5 bp (mean 7.0) | 14 | +3.9 | 6.4 / 7.2 / 10.7 | 6.0 / 6.4 / 9.9 | 2.4 / 6.9 / 10.4 | 2.3 / 3.3 / 10.1 | 1.3 / 2.9 / 9.8 |
    | PUMP, ≥ 10 bp (mean 11.4) | 3 | +8.8 | 10.3 / 11.9 / 24.1 | 9.6 / 10.1 / 21.3 | 5.7 / 11.1 / 22.9 | 0.0 / 6.2 / 20.5 | 1.0 / 1.0 / 17.8 |
    | HYPE, ≥ 5 bp (mean 5.4) | 4 | −1.5 | 4.3 / 5.0 / 2.8 | 4.7 / 5.3 / 2.8 | 2.7 / 5.0 / 3.3 | −0.1 / 3.0 / 2.4 | −0.7 / 3.7 / 1.6 |

  - **Reading.** OKX and Gate move with Binance within the 50 ms grid. Aster lags by about 300 ms. HL and Lighter
    trail by 0.6–1 s.
  - **Caveat.** Lighter is measured on sparse trade prints, which biases it toward looking slow. Use
    `order_book/{id}` mids forward.
- **OWN-PRECHECK, Lighter spreads** (orderBookOrders, 2026-10-05 06:1x UTC):
  - spreads in bp: ZEC 0.2, HYPE 1.0, SOL 1.3, XRP 1.5, ENA 1.7, NEAR 2.1, 1000PEPE 2.3, WLD 2.5, AAVE 2.5,
    DOGE 2.8, TAO 2.9, PUMP 3.1, SUI 3.3, LINK 3.4, FARTCOIN 4.9, PENGU 5.1, TRUMP 5.3, WIF 7.9, SPX 14.7;
  - top-5 bid depth is $1.3k–85k, enough for $1k on most.

  These are Sunday-night volumes: SOL $40M and HYPE $25M a day, with WIF, kBONK and SPX at $0.1M or less.

**Data.** Forward only.
- **Binance:** `fstream` bookTicker, already recorded by `scripts/research/hllag_forward.py`.
- **Lighter:** `order_book/{id}` and `trade/{id}` over `wss://…/stream?readonly=true`, with local receive time.
- **Adapter:** a new adapter, `pipeline/sources/lighter.py`. Extending `hllag_forward.py` is about 60 lines.

**Pre-registerable rule (12 configs).**
- **Universe, frozen from the 2026-10-05 snapshot:**
  - **A**, spread ≤ 2 bp: HYPE, SOL, XRP, ENA, ZEC, NEAR;
  - **B**, spread 2–3.5 bp: A plus 1000PEPE, WLD, AAVE, DOGE, TAO, PUMP, SUI, LINK.

  Each must also have a Binance USDⓈ-M perp.
- **Trigger:** the Binance mid moves by θ bp or more within 2 s (the HLLAG trigger), and Lighter's mid has moved
  less than θ/2 in the same direction at decision time. Decision time is the receipt of the Binance tick.
- **Entry:** Lighter taker, arriving at decision + 300 ms (ours) + 300 ms (speed bump). It walks Lighter's recorded
  book at arrival. A book update arriving inside the bump window counts against us.
- **Exit:** Lighter taker at entry + H, with the same 300 + 300 ms. Cooldown 10 s per coin; at most one position per coin.
- **Grid:** θ ∈ {15, 25, 40} bp × H ∈ {5, 30} s × universe ∈ {A, B} = **12**.
- **Costs:** 0 fee, the full book walk at entry and exit, and funding ignored (holds last seconds; Lighter funding
  is hourly).

**Expected trades/day.**
- HLLAG produced about 350/day at θ25 and about 90/day at θ40 on 3 meme coins (8 Tardis days, FARTCOIN-heavy).
- Universe B has 14 coins, but they are less volatile than memes. Expect **≥ 15/day at θ25 on normal days**; a
  quiet morning gave 14 PUMP events at 5 bp in 10 minutes.
- Count θ crossings on 3 recorded days before freezing θ.

**Gross vs cost.**
- **Cost:** about 1–3.5 bp per round trip (one spread plus walk).
- **Gross:** for HLLAG at an effective 600–700 ms, interpolate between L300 and L800 at the same θ: about +4–10 bp
  at 30 s for θ25–40. Lighter's faster repricing (Arrakis) pushes this toward the low end, or below it.
- **Ratio:** about 1.5–4× if the continuation part survives, and below 1 if only the instant catch-up was real.

**Kill risk.**
1. **Lighter's makers re-price inside our 600 ms**, so we buy the already-moved price and only continuation is
   left. The HLLAG L800 markout is about 0, so this is the likely failure.
2. **Terms.** The speed bump or fees may change (Lighter adjusted account tiers in 2025–26).
3. **Small books** for size; deposits run through an Ethereum L2 bridge.

**Kill test.** On the first forward day, measure the mean Lighter mid change from decision + 600 ms to +30 s after
θ25 triggers. If it is below 3 bp, stop.

---

### Idea 2. Lead-lag on tokenized-equity and metal perps across Binance, HL HIP-3 (0.9 bp) and Lighter (0 bp) (H-EQLAG)

**Mechanism.**
- In 2025–26, three crypto venues list perps on the same US stocks and metals:
  - Binance TradFi perps (TSLAUSDT, NVDAUSDT, XAUUSDT and others are in the archive);
  - HL's trade[XYZ] HIP-3 dex, at about **$654M** 24 h notional on a Sunday (OWN-PRECHECK, `metaAndAssetCtxs`
    with `dex:"xyz"`, 131 markets, `growthMode: "enabled"`);
  - Lighter (TSLA, NVDA, XAU, XAG, US100, SPY, QQQ and others, at 0 bp).
- The market makers on these books are mostly crypto MMs hedging with each other, or with the cash or CME market
  when it is open. When the cash market is shut (nights and weekends), one perp venue must lead and the others follow.
- Followers here are the **cheapest taker venues that exist**: xyz at 0.9 bp in growth mode, Lighter at 0. So a
  gross of 3–5 bp per trade, too small for any crypto venue, could clear costs.

**Evidence.**
- **Fees.** xyz growth-mode taker is 0.9 bp (DOC
  [trade.xyz fees](https://docs.trade.xyz/perpetuals/mechanics/fees.md)). Lighter Standard is 0 bp (DOC, above).
- **Weekend price discovery is real but noisy** (all leads):
  - [Blockworks Research](https://app.blockworksresearch.com/unlocked/hyperliquid-weekend-price-discovery-in-24-7-markets):
    over 23 HIP-3 equity markets and 146 weekends, the pre-open HL mid beat Friday's close only 50.7% of the time
    (search summary, not a verbatim quote).
  - [Allium](https://www.allium.so/reports/when-wall-street-sleeps): about 25 bp closer to the Monday open than
    Friday's close (search summary).
  - [4pillars](https://research.4pillars.io/en/research/can-hyperliquids-weekend-trading-predict-monday-opens-for-korean-stocks):
    Korean stocks, 45/62 direction calls correct.

  These concern open prediction, not seconds-scale lead-lag. No study of cross-venue lag on equity perps was found.
- **Spreads** (OWN-PRECHECK, 06:2x UTC Monday, cash market shut). Binance values come from a 5-s `fstream` sample.

  | Name | xyz (bp) | Lighter (bp) | Binance (bp) |
  |---|---|---|---|
  | TSLA | 0.54 | 0.81 | 0.27 |
  | NVDA | 0.43 | 0.34 | 0.42 |
  | MU | 0.93 | 1.11 | 0.09 |
  | XAU | 0.24 | 0.39 | 0.02 |
  | XAG | 0.82 | 0.18 | 1.63 |
  | COIN | 2.15 | 2.25 | 1.07 |
  | MSTR | 1.83 | 2.43 | 1.22 |
  | INTC | 1.71 | 3.51 | 0.86 |

- Other HIP-3 dexes also list TSLA, NVDA, GOLD and SILVER, but carried **$0 volume**: flx, km, cash and hyna are
  dead. Only xyz, plus io for SNDK/NBIS/ANTH, trades.

**Data.**
- **Forward:** Binance `fstream` bookTicker, HL WS `bbo`/`trades` for `xyz:<NAME>`, and Lighter `order_book/{id}`.
  All three are reachable.
- **History:** Binance 1m klines only; Tardis HIP-3 coverage is unchecked. Treat it as forward-only.

**Pre-registerable rule (12 configs).**
- **Pre-check 0 (one recorded day, not scored).** For each name, find the leader by Hayashi–Yoshida or
  cross-correlation of 100 ms mid returns, separately for cash-open and cash-closed hours. Freeze the leader map
  per name × session.
- **Names, fixed now:** TSLA, NVDA, MU, INTC, COIN, MSTR, XAU, XAG (on all three venues).
- **Trigger:** the leader's mid moves by θ or more within 2 s, and the follower's mid has moved less than θ/2.
- **Entry:** follower taker at + 300 ms (+ 300 ms on Lighter), walking the recorded book.
- **Exit:** taker at + H.
- **Grid:** θ ∈ {5, 10, 20} bp × H ∈ {5, 30} s × follower ∈ {xyz, Lighter} = **12**.
- **Costs:** xyz 0.9 bp per side (re-check `deployerFeeScale` and growth-mode status daily, and freeze them);
  Lighter 0. Plus the book walk.

**Expected trades/day.** Unknown; it must be counted on the pre-check day. xyz volume (about $650M/day) and eight
names make **≥ 15/day at θ5–10 plausible**. Moves of θ20 or more happen mostly around US news and the open.

**Gross vs cost.**
- **Cost:** xyz about 1.8 bp in fees plus 0.5–2 bp of spread, so **≈ 2.5–4 bp**; Lighter **≈ 0.5–3.5 bp**.
- **Gross:** if the follower captures half of a θ = 10 bp move, that is about 5 bp. **The ratio is about 1.5–2×, the
  thinnest absolute margin in this round**, but it is the only place where fees are near zero on both venues used.

**Kill risk.**
- During cash hours, all three venues follow the same external leader (the stock or CME futures), which we cannot
  see. So "lead" between them may be noise.
- Off-hours moves are small.
- Growth mode can end per market (`lastFeeScaleChangeTime` is present), which raises xyz to 9 bp taker.
- **Jurisdiction:** tokenized-stock perps may be restricted for the team. Check before anything beyond paper.

---

### Idea 3. Korean retail flow on Upbit leads Binance/HL perps on Korea-heavy alts (H-UPBITLEAD)

**Mechanism.**
- Korean retail trades altcoins on Upbit and Bithumb in KRW. Capital controls slow arbitrage between KRW and
  offshore markets.
- When an Upbit-driven pump starts, offshore perps on the same coin have to absorb it through the few arbitrageurs
  who can move coins between venues and through informed copy-traders watching Upbit.
- If that transmission takes minutes rather than milliseconds, the offshore perp is a follower. That is a new
  leader, not Binance. The moves are percent-scale, not bp-scale, which is what lets the gross clear 10–14 bp of
  taker cost.

**Evidence.**
- **Volume and composition** (leads):
  - Kaiko: Korean volume is about 85% altcoins; "tail assets" are 58% of Upbit volume vs 23% on Binance
    ([Kaiko, Korean liquidity](https://research.kaiko.com/reports/the-state-of-liquidity-on-korean-crypto-markets),
    via search snippet; [4pillars](https://research.4pillars.io/en/research/the-tale-of-the-tail-in-the-korea-cex)
    returned 429).
  - **Against the idea:** Upbit lists tokens about 28 days after Binance Futures on average (same snippet), so for
    new tokens Upbit is a late venue.
- **Capital-control friction** is documented for BTC: the "kimchi premium" persists because cross-border arbitrage
  is restricted. Choi, Lehar and Stauffer, "Bitcoin Microstructure and the Kimchi Premium" (working paper; cited from
  memory as a lead, not fetched; verify before use).
- **OWN-PRECHECK, Upbit vs Binance-perp USD volume on 2026-10-03** (Upbit daily candle ÷ 1,353 KRW/USDT; Binance
  archive 1d kline quote volume):

  | Coin | Upbit ÷ Binance perp |
  |---|---|
  | SOON | 0.59 |
  | AXS | 0.49 |
  | LA | 0.43 |
  | ZIL | 0.35 |
  | ZKP | 0.35 |
  | CARV | 0.30 |
  | ONDO | 0.29 |
  | AKT | 0.29 |
  | IOTA | 0.20 |
  | XLM, TRUMP | 0.18 |
  | SOL | 0.01 |
  | DOGE, PUMP | 0.03 |

  Upbit volume is very bursty. Over the 24 h to 2026-10-05 06:00 UTC, BEAM did $44M on Upbit against $0.2M on the
  prior day, and SAND did $134M against $1,065M on Binance. POD, FOLD and BLAST trade heavily on Upbit with no
  Binance USDⓈ-M perp.
- No study of minute-scale Upbit→offshore return transmission was found. **The lead direction is untested.**

**Data.**
- **History, no key:**
  - Upbit `candles/minutes/1?market=KRW-X&to=…&count=200`, which pages back to at least 2025-03 (OWN-PRECHECK). It
    gives per-minute KRW notional and OHLC.
  - KRW-USDT on Upbit for conversion.
  - Binance 1m klines from data.binance.vision.

  This allows a **train/validation test at 1-minute resolution** on the perp calendar.
- **Forward:** Upbit websocket `trade` (reachable), Binance `fstream`, HL WS.
- **Adapter:** `pipeline/sources/upbit.py`.

**Pre-registerable rule (12 configs).**
- **Universe, point in time:** coins with a KRW-X Upbit market and a Binance USDⓈ-M perp, where the trailing
  7-day Upbit ÷ Binance-perp USD volume is at least 0.2.
- **Trigger at minute close t:**
  - Upbit minute notional ≥ 10 × the trailing 24-h median minute notional;
  - |Upbit minute return in USDT terms| ≥ r;
  - the Binance perp's return over the same minute is less than half of Upbit's, in the same direction (the gap).
- **Entry:** Binance-perp taker at the next minute open + 300 ms; on paper, the 1m open plus slippage. Direction
  follows Upbit, with longs and shorts symmetric.
- **Exit:** taker at + H.
- **Grid:** r ∈ {1%, 2%, 4%} × H ∈ {5, 30} min × gap condition ∈ {on, off} = **12**. One position per coin;
  cooldown H.
- **Costs:** Binance 5 bp taker per side, plus round-6 tier slippage (2–20 bp per side by volume tier; most of this
  universe is in the 10–20 bp tiers), plus funding if a settlement is crossed. **Round trip ≈ 30–50 bp for this
  universe.** HL as the execution venue (4.5 bp) where the coin is listed.

**Expected trades/day.** 291 KRW markets, of which roughly 100–150 have a Binance perp (not counted). Burst
minutes of 10× median with |r| ≥ 1% plausibly give **15–60/day** in active markets. **Count this on train before
any P&L.**

**Gross vs cost.**
- **Gross:** if transmission is minutes-slow, a 1–4% Upbit move with half not yet on Binance leaves 50–200 bp to
  capture, against 30–50 bp of cost. Ratio about 2–4×.
- **If Binance leads** (as for majors), the gross is about 0 or negative: we would be buying after the move.

**Kill risk.**
- The direction is untested, and for most coins Binance probably leads.
- The 1-minute bar test cannot see sub-minute transmission. If the lag is seconds, history overstates it, and only
  the forward websocket test is valid.
- Korean pumps reverse hard. H = 30 min may sit in the dump.
- Some Upbit coins have no Binance perp, which narrows the universe.

---

### Idea 4. Fade Lighter-local dislocations as a zero-fee taker, only while Binance is quiet (H-LIGHTFADE)

**Mechanism.**
- H-HLANCHOR failed because **resting** quotes are filled precisely when Binance is about to move through them
  (markout −2.5 to −4.4 bp at 30 s).
- A **taker** can choose instead. It acts only when (a) the follower's mid has moved away from the Binance-implied
  fair value, and (b) Binance itself has been flat for the last 2 s, so the move is local flow (a retail market
  order, a liquidation sweep on a thin book) rather than lag.
- Then it takes the reverting side. On HL this pays 9 bp per round trip, more than the reversion is worth. On
  Lighter it pays the spread only.

**Evidence.**
- **Short-horizon liquidity provision earns a reversal premium when liquidity is scarce:** Nagel, RFS 2012
  (peer-reviewed, cited in round 4).
- **Cross-venue deviations exist and revert:** Makarov and Schoar, JFE 2020 (round 4).
- **Deviation counts** (OWN-PRECHECK from round 4, HL vs Binance on 2026-09-01; Lighter not yet measured):

  | Coin | > 10 bp | > 20 bp |
  |---|---|---|
  | WIF | 177 | 11 |
  | FARTCOIN | 304 | 14 |
  | PUMP | 416 | 31 |
  | kBONK | 428 | 47 |

- **Against:** Arrakis (lead) finds Lighter tracks Binance within about 100 ms and leads HL. So Lighter
  dislocations may be rarer and shorter than HL's, and the 300 ms bump may arrive after they close.

**Data.** As idea 1, forward only (the two ideas share one recorder).

**Pre-registerable rule (12 configs).**
- **Fair value:** F = Binance mid × (1 + b), where b is the trailing 10-min median of Lighter mid ÷ Binance mid − 1.
- **Trigger:**
  - |Lighter mid ÷ F − 1| ≥ k;
  - |Binance 2-s return| < k/4 at decision;
  - the deviation has persisted for at least 200 ms, so a single stale print does not count.
- **Entry:** Lighter taker toward F, arriving at + 300 + 300 ms, walking the book. **Skip** the entry if, at
  arrival, the Lighter book has already closed half the gap.
- **Exit:** taker when |mid ÷ F − 1| < k/4, or at + T, or on a stop at 2k against.
- **Grid:** k ∈ {6, 10, 15} bp × T ∈ {5, 30} s × universe ∈ {A, B from idea 1} = **12**.

**Expected trades/day.** On HL, 10 bp dislocations ran at 177–428 per coin per day on memes. Lighter's will be
fewer; even a tenth of that over 14 coins is **≥ 15/day**. Measure it on the first forward day.

**Gross vs cost.**
- **Cost:** about 1–3.5 bp.
- **Gross:** if half the gap closes, k/2 = 3–7.5 bp. The ratio is about 1.5–3× at k ≥ 10.

**Kill risk.**
1. **Adverse selection survives the "Binance quiet" filter.** Lighter-local flow may be informed (Arrakis says
   Lighter sometimes leads), in which case the HLANCHOR result repeats.
2. The 600 ms delay means we often arrive after reversion. The skip rule then shrinks n.
3. The same fill-model caveats as HLANCHOR apply: snapshot cadence and no queue model.

---

### Idea 5. On-chain flow leads perps for DEX-native tokens in their first weeks on Binance/HL (H-DEXLEAD)

**Mechanism.**
- This is the reverse of CEX→DEX arbitrage. For a Solana token whose **spot volume is still mostly on-chain**
  when Binance or HL list a perp, real buying pressure arrives first on PumpSwap, Raydium or Meteora. The perp
  market makers hedge by watching those pools.
- A large on-chain swap moves the pool price at once. If perp MMs re-quote with a lag (RPC latency, block time
  about 400 ms), the perp is the follower. We would trade the **perp** (HL 4.5 bp, or Lighter 0 bp if listed), never
  the DEX. That avoids the 25–125 bp DEX cost that killed every DEX-leg idea, and it puts no transaction near
  anyone's swap. No MEV.

**Evidence.**
- Hansen, Kim and Kimbrough (arXiv 2109.12142, round 3): DEX prices adjust slowly to CEX prices. That is the
  opposite direction, and it explains why this idea is conditional on DEX-dominant tokens.
- **OWN-PRECHECK: for mature memes, the DEX is not the leader.** FARTCOIN's six largest Solana pools did about
  **$1.5M combined in 24 h** (GeckoTerminal, 2026-10-05), with Orca/Raydium SOL pools about $0.7M each. That is a
  small fraction of perp turnover, so this idea applies only to **newly perp-listed, DEX-native tokens**.
- No study of DEX→perp lead for new listings was found. The prior is low.

**Data.**
- **Forward:**
  - Solana public RPC websocket (`logsSubscribe` on the top pool's program-and-account; `slotSubscribe` checked
    OK), or GeckoTerminal `/pools/{id}/trades` polled every 10–20 s. The latter is too slow for seconds-scale work
    and suits only minute-scale H.
  - Binance `fstream` and HL WS.
- **Candidate list:** Binance CMS announcements (reachable) and HL `meta` for new listings. Keep a token in the
  universe while 24-h DEX volume ≥ 50% of its perp volume.

**Pre-registerable rule (12 configs).**
- **Trigger:** within one slot, the swap notional on the token's top-3 pools is at least S × the trailing-1-h median
  swap, in one direction, and the pool price impact is at least θ.
- **Entry:** perp taker (HL or Binance) at RPC receipt + 300 ms.
- **Exit:** at + H.
- **Grid:** θ ∈ {30, 60} bp × H ∈ {10 s, 60 s, 5 min} × venue ∈ {HL, Binance} = **12**.

**Expected trades/day.** It depends on how many such tokens are live. With 2–4 qualifying tokens, large-swap events
are plausibly 10–40 a day. **This may fail the ≥ 15/day requirement in quiet listing months.**

**Gross vs cost.**
- **Cost:** 9–10 bp round trip plus about 5–20 bp of spread on new perps.
- **Gross:** if the perp lags a 30–60 bp pool move by more than 1 s, then 15–40 bp. The ratio is about 1–2×, the
  weakest in this round.

**Kill risk.**
- Perp MMs already subscribe to pool accounts through private RPCs, so their lag is shorter than our public-RPC lag.
- Few qualifying tokens.
- Public RPC rate limits.

---

### Idea 6. Same-signal check across second-tier CEX perps: cheap-taker followers (H-T2LAG). Pre-check: weakened

**Mechanism.** HLLAG with the follower swapped for a CEX perp that is cheaper than HL and slower than Binance:
Aster (3.5 bp taker; 0 on stock perps), MEXC (2 bp), Gate/OKX/Bybit/Bitget (about 5–6 bp).

**Evidence.**
- **OWN-PRECHECK:** in the 10-minute recording (idea 1 table), OKX and Gate re-priced with Binance at once
  (+0 ms ≈ the 600 ms value). Aster lagged by about 300 ms, then matched.
- **Bybit:** the WS is reachable, but no PUMP data arrived. On HYPE (n = 4, Binance move 5.4 bp), Bybit had moved
  2.2 / 3.8 / 4.1 bp at +0 / +300 / +600 ms. That is a partial lag of a few hundred ms, on tiny n.
- **So their lag is shorter than our own 300 ms.** The only remaining gross is continuation, the same unknown as
  idea 1, and here it pays fees of 2–6 bp.

**Rule (if kept, 12 configs).**
- **Grid:** θ ∈ {25, 40} bp × H ∈ {5, 30} s × follower ∈ {Aster, MEXC, Gate}.
- **Data:** forward only (WS reachable for all three; MEXC API order entry unverified).

**Expected trades/day.** The same trigger count as idea 1.

**Gross vs cost.**
- **Cost:** 4–7 bp in fees plus 1–3 bp of spread.
- **Gross:** continuation only, probably 0–5 bp.
- **Ratio:** at or below 1. **Kept only as the control arm for idea 1.** Running it shows whether any profit on
  Lighter comes from Lighter's lag or from Binance continuation, which would also appear here.

---

## 2. Ranking (gross ÷ cost × testability × time to 50 forward trades)

| Rank | Idea | Round-trip cost | Expected gross per trade | Gross ÷ cost | History | Trades/day (est.) | Days to 50 | Evidence | Main kill risk |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **H-LIGHTLAG**: Binance → Lighter (0 fee, 300 ms bump) | 1–3.5 bp | 4–10 bp (HLLAG profile at 600–700 ms) | ~1.5–4× | Forward only | 15–100 | 1–3 | OWN (HLLAG markouts); lead (Arrakis lead-lag); DOC (fees) | Lighter makers re-price inside our 600 ms (Lighter lags Binance by only ~100 ms) |
| 2 | **H-UPBITLEAD**: Upbit KRW bursts lead perps | 30–50 bp | 50–200 bp if transmission takes minutes | ~2–4× | **Full, 1m** (Upbit candles + Binance archive) | 15–60 (to count) | 1–3 forward; train today | lead (Kaiko shares), OWN (volume ratios) | Binance leads instead; Korean pumps reverse |
| 3 | **H-EQLAG**: equity/metal perps, follower xyz (0.9 bp) or Lighter (0) | 0.5–4 bp | 3–5 bp | ~1.5–2× | Forward (Binance 1m only) | ≥ 15 (to count) | 1–4 | DOC (fees); OWN (spreads, xyz $654M/day); lead (weekend studies) | All venues follow an unseen cash leader; growth mode ends |
| 4 | **H-LIGHTFADE**: zero-fee taker fade of Lighter-local dislocations | 1–3.5 bp | 3–7.5 bp | ~1.5–3× | Forward only (shares idea 1's recorder) | ≥ 15 (to count) | 1–3 | DATA (Nagel; Makarov–Schoar), OWN (HL deviation counts) | HLANCHOR-style adverse selection; arrive after reversion |
| 5 | **H-DEXLEAD**: on-chain flow leads perps for DEX-native new listings | 15–30 bp | 15–40 bp | ~1–2× | Forward only | 10–40 when tokens qualify | 2–5+ | Weak (reverse of Hansen et al.); OWN shows mature memes are CEX-led | Few qualifying tokens; MMs watch pools faster |
| 6 | **H-T2LAG**: Aster/MEXC/Gate as follower (control arm) | 5–10 bp | 0–5 bp | ≤ 1× | Forward only | as idea 1 | 1–3 | OWN 10-min profile: these follow within ≤ 300 ms | No lag left beyond our own latency |

**Suggested order.**
1. **Build one recorder now.**
   - Add Lighter `order_book/{id}` and `trade/{id}` (readonly WS), HL `xyz:*` `bbo`/`trades`, Binance equity and
     metal `bookTicker`, Aster and Gate bookTicker to `hllag_forward.py`'s connection pattern. Put a Lighter
     adapter in `pipeline/sources/`.
   - That one recorder serves ideas 1, 2, 4 and 6.
   - Day 1 is the unscored pre-check: trigger counts, the Lighter post-600 ms markout kill test, and the equity
     leader map. Then freeze the four pre-registrations.
2. **Run H-UPBITLEAD on train today.** Upbit minute candles page back to 2025, and Binance 1m klines are already
   fetched by the round-5/6 archive fetcher.
   - Count triggers first.
   - Measure the Binance-perp response profile at +1/+5/+30 min to Upbit bursts (a direction test). Stop if
     Binance does not lag.
   - Start the Upbit WS recorder in parallel for the sub-minute forward version.
3. Idea 5 only if a DEX-native token gets a Binance or HL perp while the recorder runs.

---

## 3. Considered and dropped (do not re-research)

| Lead | Why dropped |
|---|---|
| **Binance → Solana DEX pools (CEX→DEX arbitrage)**, including low-fee Orca/Meteora/prop-AMM pools | It is classed as MEV (non-atomic arbitrage, won by priority-fee and Jito-tip auctions), which the brief excludes. It is also the DEX-cost trap dropped in rounds 4–5. Mature meme DEX volume is small (FARTCOIN's top 6 pools ≈ $1.5M/24 h). |
| **Paradex as a follower** | Zero fees only for UI retail flow behind a 500 ms bump and 3 orders/s; API takers pay 2 bp (lead, FalconX). The public SOL-USD-PERP book at 06:2x UTC showed bid 120.56 against ask 120.80 (about 20 bp) with 0.1-SOL ask levels: no usable book for API takers. Paradex `/trades` history (from 2025-03) could serve as a lead-lag *measurement* source if ever needed. |
| **Other HIP-3 dexes as equity followers** (flx, km, cash, hyna, mkts) | $0.0–1.5M in 24 h volume (OWN-PRECHECK). Only xyz (and io for 3 names) trades. |
| **Bybit/OKX as leaders for HL** | Our 10-min profile shows them moving with Binance, not ahead of it. Arrakis finds Binance leads every venue tested. Bybit REST is geo-blocked (403), though its WS works. |
| **Binance / Upbit listing announcements** | Fewer than 1–5 events a day; fails ≥ 15/day (round 6). The Upbit notice API is 403 from here. LISTSHORT covered direction. |
| **Token unlocks** | A few events a week across liquid perps. The schedule sources are keyed or paid (Tokenomist 401, DeFiLlama emissions 402). |
| **Extending H-HLLAG to more HL coins** | Not a new hypothesis. It is already queued (PENGU, kSHIB per `reports/candidates/hllag_newcoins.md`) and shares HLLAG's latency fragility and 9 bp cost. Ideas 1 and 6 test the cost and venue variants instead. |
| **Lighter as a leader for HL** (Arrakis: Lighter leads HL for 27/29) | Execution would still be on HL at 9 bp. This is a signal-source variant of HLLAG. Add Lighter mids to the HLLAG forward record as a diagnostic, not as a new hypothesis. |
| **HL weekend equity pricing → Monday open** | One trade per name per week; fails n. The studies (Blockworks, Allium) find little or mixed signal. |

## 4. Gaps

- **Lighter docs disagree.** The fetched page says Standard maker latency is 0 ms; a search snippet says 200 ms
  maker and cancel. The taker figure is 300 ms in both. Lighter's market-maker programme and how its makers hedge
  are unknown.
- **Arrakis** is a practitioner blog (an LP manager's research), not peer-reviewed. Its window ended 2026-02-26,
  and only the summary was read.
- **The 10-minute response profile** is one quiet Monday-morning window with n = 3–14 events per coin. It is a
  reachability-plus-shape check, not evidence of an edge. Lighter was measured on sparse trade prints, not mids.
  The raw recording stays in the session scratchpad and is not kept in the repo.
- **Equity perps.** Binance TradFi-perp taker fees, trading hours and price limits were not checked. Neither was
  Lighter's equity-perp behaviour around the US open, nor whether Tardis covers HIP-3.
- **Upbit.** The Choi–Lehar–Stauffer kimchi-premium reference is from memory, not fetched. The Kaiko and 4pillars
  figures come from search snippets (4pillars returned 429). No minute-scale Upbit→offshore transmission study was
  found. KRW conversion used one USDT/KRW snapshot (1,353) for the volume pre-check only.
- **Fees** for Aster and MEXC come from marketing pages. MEXC futures API order entry may be closed to retail.
- **Jurisdiction.** Lighter, HL HIP-3 equity perps, Binance TradFi perps, Aster and MEXC must all be legal for the
  team before anything goes beyond paper (round 4 §3).
