# H-UPBITLEAD (Upbit KRW volume bursts lead Binance USDT-M perps): FAIL on train, validation not opened

Agent "upbitlead", 2026-10-05. Source idea: `sources/leads/documented_edges_round7.md`, idea 3.
Pre-registration, frozen before any minute data was downloaded: `reports/hypotheses/upbitlead_preregistration.json`.
The coin list was added as an addendum after the March-2025 selection run and before the minute download.
Scripts: `scripts/research/upbitlead_select.py`, `upbitlead_fetch.py` and `upbitlead_sim.py`.
Evidence: `research/observations/evidence_upbitlead_train_20261005.json`.

## Universe and data
- **Selection.** Of 291 Upbit KRW markets, 280 are not stablecoins, 150 had a Binance USDT-M perp in 2025-03, and 89
  passed the volume filters. The top 40 by March-2025 Upbit ÷ Binance-perp USD volume ratio were kept (ratios 0.24 to
  0.96):
  - AKT, SONIC, MOCA, SAFE, BIGTIME, ZETA, HIVE, ARK, POLYX, VANA;
  - WAXP, IOST, ENS, G, VTHO, CKB, BSV, ME, MEW, LAYER;
  - LSK, STEEM, XEC (1000XECUSDT), GLM, AGLD, VIRTUAL, GAS, STX, ANKR, ID;
  - MOVE, ANIME, ONDO, QTUM, ONG, IOTA, ZRX, POWR, T, MTL.

  Of these, 14 are HL-listed today (`hl_listed_20261005` in the addendum). Selection used only pre-train daily data.
  It is drawn from Upbit's *current* market list, so coins Upbit has since delisted are missing (survivorship).
- **Sources.**
  - Upbit public 1m candles for 40 coins plus KRW-USDT (for KRW→USD), 2025-03-24 to 2026-03-31.
  - Binance 1m klines and funding from data.binance.vision.
  - Nothing at or after 2026-04-01 was requested. The cache is 427 MB in `data/raw/web/upbitlead/`.
- **Split change, declared in the pre-registration before any P&L.**
  - Upbit history goes back further (KRW-AXS candles exist for 2024-06).
  - Train was nevertheless set to 2025-04-01..2025-12-31 for the request budget: Upbit returns 200 minutes per
    request, at most 10 requests/s.
  - Validation is 2026-01-01..2026-03-31. The holdout (2026-04-01 onward) was never fetched.
- **Data seen before P&L.** Before freezing, about 20 KRW-AXS candle pages from June 2025 (train) were fetched as a
  rate-limit probe. AXS is not in the selected universe.

## Rule (as frozen)
- **Trigger at Upbit minute close t:**
  - `z = (ln(1+USD notional_t) − 24h mean) / 24h sd ≥ Z`;
  - |Upbit USD-terms 1m return| ≥ R;
  - USD notional ≥ $10k;
  - the coin passes the trailing-7-day filters: Upbit ÷ Binance ratio ≥ 0.2, and Binance mean daily volume ≥ $1M.
- **Entry:** Binance perp at the open of bar t+1, in the direction of the Upbit move. The 1m open approximates a fill
  2 s after the Upbit close.
- **Exit:** take-profit at +2R, stop-loss at −R (stop assumed first when both are hit in one bar), otherwise time
  exit after H minutes.
- **Costs:**
  - 5 bp taker per side;
  - slippage per side by the Binance trailing-7-day volume tier: 10 bp at ≥ $100M, 15 bp at $30–100M, 20 bp at
    $10–30M, 25 bp at $1–10M;
  - actual funding.

  The round trip came to 55–60 bp on average, because most trades fall in the 25 bp tier.
- **Grid:** Z ∈ {3, 4.5} × R ∈ {1%, 2%, 4%} × H ∈ {5, 30}. Bar: n ≥ 50, net > 0, PF > 1.2, and net > 0 without the
  top 3 trades.

## Trigger counts on train, before any P&L (40 coins, 275 days)
Raw trigger minutes:

| Z | R = 1% | R = 2% | R = 4% |
|---|---|---|---|
| 3 | 1,346 (4.9/day) | 439 (1.6/day) | 94 (0.34/day) |
| 4.5 | 67 | 23 | 6 |

After one position per coin, trades number **at most 3.4 per day**. That is far below the 15–60 per day the lead
suggested.

## Train results (bp of notional per trade)

| config | n | mean gross | mean net | net sum | PF | net ex top-3 | pass |
|---|---|---|---|---|---|---|---|
| Z3 R1% H5 | 943 | −1.8 | −59.1 | −55,690 | 0.28 | −56,200 | no |
| Z3 R1% H30 | 882 | −2.8 | −59.8 | −52,768 | 0.35 | −53,278 | no |
| Z3 R2% H5 | 304 | −19.1 | −74.3 | −22,599 | 0.41 | −23,709 | no |
| Z3 R2% H30 | 280 | −18.9 | −73.9 | −20,693 | 0.50 | −21,803 | no |
| Z3 R4% H5 | 73 | −5.0 | −60.3 | −4,405 | 0.61 | −6,665 | no |
| Z3 R4% H30 | 69 | −39.3 | −94.8 | −6,543 | 0.56 | −8,803 | no |
| Z4.5 R1% H5 | 51 | −6.4 | −66.4 | −3,386 | 0.20 | −3,806 | no |
| Z4.5 R1% H30 | 47 | −3.4 | −63.4 | −2,978 | 0.29 | −3,398 | no |
| Z4.5 R2% H5 | 18 | −35.5 | −95.5 | −1,720 | 0.21 | −2,180 | no |
| Z4.5 R2% H30 | 17 | −35.6 | −95.6 | −1,625 | 0.36 | −2,452 | no |
| Z4.5 R4% H5 | 4 | +89.2 | +29.2 | +117 | 1.47 | −218 | no (n) |
| Z4.5 R4% H30 | 4 | −184.6 | −244.6 | −979 | 0.02 | −460 | no |

- **No config meets the bar.** The gross is about zero or negative before costs in 11 of 12 configs. The one
  positive config has 4 trades.
- Under the pre-registered selection rule, **no config is chosen and validation P&L was not computed.** The +1 minute
  delay, slippage ×2 and HL-fee variants apply only to a chosen config, so they were not run.
- The +1 minute delay could only make the result worse, since Binance has already moved by the next open (see below).

## Informational: direction of the lead (train, Z3 R1%, all 1,346 trigger minutes, no cooldown)

**Binance in the same minute as the Upbit burst**
- Binance's signed return is a median **0.58×** the Upbit move.
- In 57% of bursts Binance has already made at least half the move inside the same 1-minute bar.

**Binance after the burst (signed in the Upbit direction, from the open of t+1)**

| horizon | mean | median |
|---|---|---|
| +1 m | +2.0 bp | −2.8 bp |
| +5 m | +13.2 bp | −8.9 bp |
| +30 m | +10.2 bp | −15.4 bp |

The means come from a few tail continuations. The typical event drifts back. Even the mean is far below the 55–60 bp
cost.

**Upbit after its own burst (from the close of t)**

| horizon | mean | median |
|---|---|---|
| +1 m | −8.2 bp | −6.7 bp |
| +5 m | −10.1 bp | −28.4 bp |
| +30 m | −25.3 bp | −50.9 bp |

Korean burst minutes partly **reverse**.

**Reverse direction: Binance bursts (same z/R definition on Binance quote volume and return)**
- There were 4,406 events in the same coins, against 1,346 Upbit bursts.
- Upbit's signed return afterwards:

  | horizon | mean | median |
  |---|---|---|
  | +1 m | +5.0 bp | −0.5 bp |
  | +5 m | +22.9 bp | −4.7 bp |
  | +30 m | +9.5 bp | −20.2 bp |

- Upbit follows Binance bursts at least as much as Binance follows Upbit bursts. **Nothing at 1-minute resolution
  suggests Upbit leads.** The two venues move largely within the same minute.

## Verdict
**FAIL on train.**
- At 1-minute resolution, Upbit burst minutes on Korea-heavy mid/small caps do not leave a Binance-perp move to
  capture:
  - Binance has already done most of the move inside the same minute;
  - the subsequent median is negative;
  - the realistic 55–60 bp round trip on these illiquid perps puts every adequately sized config at PF 0.2–0.6.
- Event frequency (≤ 3.4 trades/day across 40 coins) also misses the ≥ 15/day target in the lead.

## Limitations
- 1m bars cannot see sub-minute transmission. If Upbit leads by seconds *within* the minute, only a websocket test
  could find it. But the same-minute evidence says Binance has caught up by the minute close, which is the earliest a
  candle-based signal can act. A tick-level Upbit websocket version would be a different hypothesis (a speed race)
  and is not supported by this result.
- The coin list reflects Upbit's current markets (survivorship).
- Train is shorter than the full available history (declared before P&L).
- The slippage tiers are a proxy, not measured book depth. They do not matter here: even the gross is not positive.
