# H-FFDIFF: HL vs Binance funding-differential carry on memecoin perps (perp vs perp). Verdict: FAIL (train)

Family: `sources/leads/documented_edges_round4.md` idea 4 (H-FFDIFF; called "idea 3" in the round-4 ranking
table). It is the direct fix for H-FUNDCARRY (`reports/failures/agent_fundcarry.md`): the Solana DEX spot leg is
replaced with the other venue's perp, so the round trip costs 39 bp instead of about 1.2%.

**Bar** (out of sample): n ≥ 50, net > 0, PF > 1.2, net > 0 without the 3 best episodes.

**Result:**
- Out of 18 configs, none passes on train at the pre-registered base cost (5 bp slippage per leg).
- **The validation period (2025-07-01 to 2026-03-31) was not examined.** The holdout (2026-04-01 onward) was never
  fetched or loaded.

## Data (public, no keys; nothing at or after 2026-04-01 written by this family)

| item | source | cache |
|---|---|---|
| universe | `listshort_classify.candidates()` (CoinGecko meme-token rule, reused unchanged): HL meme perps whose base is also a Binance USDT-M meme perp | `data/raw/web/hyperliquid/ffdiff/universe.json` |
| HL hourly funding | HL info `fundingHistory` | fundcarry cache (read only) or `hyperliquid/ffdiff/funding_<coin>.json` |
| HL 4h perp candles | HL `candleSnapshot` (the API serves only the latest 5000, so data starts about 2024-06-23) | fundcarry cache or `hyperliquid/ffdiff/candles_4h_<coin>.json` |
| Binance funding (1/4/8h intervals) and 4h klines | data.binance.vision `futures/um/monthly/{fundingRate,klines/4h}` | `binance_fut/ffdiff/<SYM>_{funding,k4h}.parquet` |

**Universe.** There are 37 pairs:
- DOGE, kPEPE, kSHIB, MEME, ORDI, kBONK, WIF, PEOPLE, MYRO, kFLOKI, BOME, POPCAT, NOT, TURBO, BRETT, MEW, kDOGS, NEIROETH,
  kNEIRO, GOAT, MOODENG, PNUT, CHILLGUY, PENGU, FARTCOIN, AI16Z, AIXBT, ZEREBRO, GRIFFAIN, SPX, TRUMP, MELANIA, ANIME,
  VINE, TST, PUMP and USELESS.
- USELESS has no HL data before the holdout. PUMP was listed on HL in July 2025, so it has no train trades.
- **That leaves 33–35 coins trading in train.**
- **Identity check:** the median of HL close / (Binance close × multiplier) is 0.9998–1.0005 for every pair, with p1–p99
  inside ±0.8% (PUMP's p99 is 1.021).

**Effective train window:** 2024-06-23 (the first HL 4h candle) to 2025-06-30. Earlier funding-only signal onsets are
counted but not traded. For example, at L24/X40 there were 906 onsets in all of train, of which 550 fall in the window
with prices (`ffdiff_sim.py features`).

## Rules (pre-registered in the `ffdiff_sim.py` docstring before any P&L)

- **Signal.** Decisions are made on a 4h clock. D_W is the HL funding minus the Binance funding, annualised, over the
  trailing W hours.
  - It uses HL prints up to T−1h and Binance prints before T, so it is point in time.
- **Entry:** both s·D_L ≥ X and s·D_24 ≥ X, with s = sign(D_L).
  - Short the high-funding venue and long the other, at equal notional. One position per coin.
  - Fill at the 4h close on both venues.
- **Exit:** any of:
  - s·D_24 < 10%/yr;
  - Z days pass;
  - liquidation;
  - a data gap or the split end.
- **Grid (16):** L {24, 72} h × X {40, 80}%/yr × Z {7, 14} d × leverage per leg {1, 2}.
- **Costs:**
  - 2 × (HL taker 4.5 bp, from [HL fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees), tier 0, plus
    Binance USDⓈ-M taker 5.0 bp, from [Binance futures fees](https://www.binance.com/en/fee/futureFee), regular user);
  - plus 4 × slippage at 5 bp (base) or 2 bp (sensitivity);
  - **so 39 bp (base) or 27 bp per round trip.**
- **Basis:** the two perps' own 4h closes are both tracked, so the P&L includes the change in the gap between them.
  Funding is marked at the 4h close of the bar containing each print.
- **Liquidation is checked on each leg separately, with no cross-venue margin transfer.**
  - The short leg is liquidated if a later 4h high ≥ P0·(1+1/lev)/(1+mm). The long leg is liquidated if a later 4h
    low ≤ P0·(1−1/lev)/(1−mm).
  - mm_HL = 1/(2·maxLeverage), using today's `meta` value. mm_BN = 5% (assumed, conservative; the Binance brackets were
    not reachable).
  - A liquidated leg loses its whole margin, and the other leg is closed at that bar's close.
  - The check uses the trade high and low, not the mark price, so it is conservative.
- **Bookkeeping note.** The first run used a looser liquidation formula, P0·(1+1/lev−mm). It was corrected to the
  equity = maintenance identity above, and **all configs were rerun.** Only the corrected numbers are reported.

## Results

### Train, base cost (5 bp), 16 pre-registered configs: 0 / 16 pass

`evidence_ffdiff_train_slip5.json`

| config | n | net (×N) | PF | ex top 3 | funding | basis | cost | liq |
|---|---|---|---|---|---|---|---|---|
| L24 X40 Z14 1x | 396 | −3.55 | 0.19 | −3.98 | +0.92 | −2.94 | 1.53 | 16 |
| L24 X80 Z14 1x | 112 | −1.34 | 0.24 | −1.64 | +0.37 | −1.29 | 0.43 | 7 |
| L72 X40 Z14 1x | 163 | −1.12 | 0.33 | −1.44 | +0.58 | −1.07 | 0.63 | 7 |
| L72 X80 Z7 1x | 39 | +0.31 | 4.53 | +0.01 | +0.19 | +0.28 | 0.15 | 1 |
| L72 X80 Z14 1x | 39 | −0.25 | 2.72 | −0.05 | +0.19 | +0.21 | 0.15 | 2 |
| every 2x cell | 45–436 | −2.7 to −11.3 | 0.02–0.08 | <0 | — | — | — | 12–59 |

What the numbers show:
- **Funding per trade is about cost.** The D24 < 10% exit closes positions after a median of about 2 days, so the
  differential collected is 15–50 bp per trade against the 39 bp cost. **The differential mean-reverts fast.**
- **Liquidations dominate.** At 2x, the HL short leg (maxLeverage 3, so mm = 16.7%) liquidates at +28.6%. This
  happened in 12–59 episodes per cell, at a cost of −0.45 each.
  - Even at 1x, the short leg liquidates in meme pumps of about +71%: WIF, kNEIRO, MOODENG, PNUT, TURBO and VINE in
    November 2024 and April–May 2025.
  - High funding precedes squeezes, so the "hedged" pair loses its short leg's margin.
- **Two cells are the exception.** L72 X80 Z7 and Z14 at 1x are positive, but n = 39 and the result rests on one
  freak trade: TRUMP on launch day (HL short liquidated, Binance long +125%: +0.25 of the +0.31). That cell fails on n
  and on the ex-top-3 test.

### Iteration 2 (2 configs; 18 in total)

**Rationale:** the exits came too early (funding below cost), and there were liquidations at 1x.

**New exits:**
- hold until the trailing-L differential flips sign (Z = 14 d);
- close the pair when either leg's adverse close-to-entry move reaches 40%.

**Configs:** L72, lev 1, X ∈ {40, 80}. Evidence: `evidence_ffdiff_train_slip5_iter2.json`.

| config | slip | n | net | PF | ex top 3 | funding | basis | cost | liq | worst | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L72 X40 flip stop40 | **5 bp (base)** | 140 | +0.033 | 1.07 | −0.044 | +0.75 | −0.18 | 0.55 | 1 | −0.25 MOODENG | **no** |
| L72 X80 flip stop40 | 5 bp | 37 | +0.113 | 2.48 | +0.051 | +0.22 | +0.03 | 0.14 | 0 | −0.016 | no (n) |
| L72 X40 flip stop40 | 2 bp (sens.) | 140 | +0.201 | 1.50 | +0.120 | | | 0.38 | 1 | −0.25 | yes |

**Holding to the flip works on the funding side.** Median hold is 6.3 days and funding is 54 bp per trade, but **the
pass exists only at the optimistic cost end.**

At base cost, a single genuine liquidation decides the result. On 2024-11-15 MOODENG rose +46% in one 4h bar on both
venues, past both the close-based 40% stop and the 1x liquidation price at +71%. That cost −0.25, which wiped out the
cell.

Since 5 bp was the pre-registered base, **no config passed train, and validation was not opened.** Choosing 2 bp
after seeing this would be tuning the cost assumption.

### Stability and decay (train, iteration 2 L72 X40, 5 bp)

**By quarter (n, net):** 2024Q2 3, −0.007 · 2024Q3 6, +0.016 · 2024Q4 53, −0.027 · 2025Q1 40, +0.008 · 2025Q2 38, +0.043.

**Decay.** Funding collected per trade decayed from 81 bp (2024Q4) to 36–39 bp (2025Q1–Q2). The episode count held up
(38–53 per quarter).
- In the pre-registered L24 X40 cell, funding per trade fell from 38 bp to 15–18 bp.
- This is the same 2024 → 2025 regime decay that fundcarry found.

**By coin:** 20 of 33 coins are net positive. The biggest losers are MOODENG (liquidation), MELANIA (−0.028 over 12
trades) and ANIME. **Direction:** short-HL/long-Binance made +0.063 over 113 trades, and short-Binance made −0.030 over
27. HL funding is the one that runs hot. Maximum concurrent positions was 17.

## Interpretation and risks
- **The cross-venue differential is real and frequent**, at hundreds of onsets per year when pooled. It is also
  **short-lived**: most of it mean-reverts within about 2 days, and after 2024 it is worth only about 15–40 bp per
  episode.
  - That is the same size as four taker fills plus slippage.
- **The binding risk is per-leg liquidation.** It happens because the legs sit on separate venues and squeezes on
  meme perps are fast.
  - A single 4h bar of +46% (MOODENG, 2024-11-15, verified on both venues) can push a 1x short past a
    close-based stop to liquidation.
  - The only defence is margin well above 1x, which leaves capital idle and lowers the return. Moving collateral
    across venues is too slow for a 4h bar.
- **Also not modelled:**
  - ADL or delisting on one leg (several HL coins were delisted: MYRO, kDOGS, NEIROETH, AI16Z, CHILLGUY, ZEREBRO,
    VINE, TST);
  - historical HL maxLeverage tiers (today's value was used).
- **Caveats in the other direction:**
  - liquidation is checked on 4h trade highs, not the mark price;
  - mm_BN = 5% is an assumption;
  - decisions are on 4h bars, and fills at the bar close carry a few seconds of latency;
  - there is no slippage model from `bookDepth`. Measuring slippage would decide the 2–5 bp question, but should be
    done before any further look, not to rescue this cell.

Do not run validation or holdout for this family as specified. If revisited:
1. Pre-register a measured slippage model.
2. Size the margin so that a 4h +80% bar does not liquidate the short (i.e. lev ≤ 0.5 effective).
3. Then run validation once.

## Files
- `scripts/research/ffdiff_fetch.py`: universe and HL + Binance-archive fetch (guard: nothing at or after 2026-04-01 is written).
- `scripts/research/ffdiff_sim.py`: `features` | `train [slip_bp]` | `train2 [slip_bp]` | `validation L,X,Z,lev[,exit,stop]`. Validation was not run.
- `research/observations/evidence_ffdiff_train_slip5.json` and `evidence_ffdiff_train_slip2.json`: the 16-cell grid
  with all episodes.
- `research/observations/evidence_ffdiff_train_slip5_iter2.json` and `evidence_ffdiff_train_slip2_iter2.json`:
  iteration 2.

---

## Iteration 3: H-FFDIFF-MAKER (separately pre-registered). FAIL (train)

**Pre-registration:** `reports/hypotheses/ffdiff_maker_preregistration.json`, written before any run.

**What changed:** execution only. Both legs enter and exit with maker limits at the touch, proxied by the 4h close at
the decision time.
- **Fees:**
  - HL maker 1.5 bp: [HL fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees), fetched 2026-10-05.
  - Binance maker 2.0 bp: [futureFee](https://www.binance.com/en/fee/futureFee). The page is JS-gated from here
    (HTTP 202), so this is the published schedule value, not re-verified live.
- **Signal, exit, stop and liquidation:** the same as iteration 2.
- **Configs (3):** L72/X40, L24/X40 and L72/X80, all at 1x with the flip exit and the 40% stop.

**Fill model: 1h, because 4h bars cannot judge the 1-hour leg rule.**
- **The data limit.**
  - Binance 1h klines come from the archive and cover train only.
  - Hyperliquid serves only its latest 5000 1h candles (back to about 2026-03), so there are no HL 1h data in train.
- **How HL fills are judged.** The HL leg's 1h path is proxied by the Binance 1h path, with a buffer m = 0.44%. That is
  the p99 of |HL/BN − 1| over 58,588 pooled train 4h closes.
- **Fill rules.**
  - A leg fills only if bar [T, T+1h) trades *strictly through* its limit. A filled leg pays the 5 bp adverse-selection
    haircut plus the maker fee.
  - If one leg fills, the other is completed as a taker at the next 1h bar's worst price + 5 bp.
  - If neither leg fills, the entry is skipped. On a close, both legs go taker at the next bar's worst price + 5 bp.
  - Stop, split-end and gap exits are taker at the 4h close + 5 bp.
- **Funding** is counted only from after the fill hour.

### Train results (base model): 0 / 3 pass

`research/observations/evidence_ffdiff_maker_train.json`

| config | n | net | PF | ex top 3 | funding | basis incl. fills | fees | liq | one-leg opens / closes |
|---|---|---|---|---|---|---|---|---|---|
| L72 X40 | 139 | −1.009 | 0.30 | −1.082 | +0.74 | −1.62 | 0.14 | 1 | 21 / 20 |
| L24 X40 | 355 | −5.103 | 0.10 | −5.274 | +1.03 | −5.81 | 0.32 | 4 | 83 / 69 |
| L72 X80 | 36 | −0.030 | 0.85 | −0.099 | +0.23 | −0.23 | 0.04 | 0 | 5 / 3 |

**When both legs fill, maker execution helps as expected.** The round trip costs about 27 bp (haircuts about 19 bp in
the basis, plus fees) against 39 bp for taker.

**When only one leg fills, it costs 2–8% per episode.** That happens on 15–25% of the trades, and it is legging risk:
- the order that misses is the one the price moved away from;
- the taker completion then sells the low or buys the high of a volatile meme hour.

### Sensitivity (not pre-registered, not eligible): HL buffer m = 0

`research/observations/evidence_ffdiff_maker_train_sensM0.json`

| config | n | net | PF | ex top 3 |
|---|---|---|---|---|
| L72 X40 | 138 | +0.053 | 1.11 | −0.026 |
| L24 X40 | 355 | −1.18 | 0.40 | |
| L72 X80 | 36 | +0.161 | 3.93 | +0.091 |

Even with optimistic HL fills, nothing passes:
- **L72 X40 still fails.** The MOODENG 2024-11-15 liquidation (−0.25) still decides it.
- **L72 X80 still fails on n.**

**Validation was not opened, and the holdout was never examined.**

**Conclusion:** cheaper execution does not rescue the family. Two things bind:
- the tail risk of a separate-venue short being squeezed;
- legging risk on fills, which replaces the taker cost saved.

Files: `scripts/research/ffdiff_maker_sim.py` (adds a Binance 1h archive fetch:
`binance_fut/ffdiff/<SYM>_k1h_train.parquet`, 2024-06..2025-07).
