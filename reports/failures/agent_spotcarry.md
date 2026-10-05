# H-SPOTCARRY-WIDE: Binance spot long + USDⓈ-M perp short, all coins, entering on persistent funding. Verdict: FAIL

Family: `sources/leads/documented_edges_round5.md` idea 2 (H-SPOTCARRY-WIDE, rank 1 in its §2). Parent:
H-FUNDCARRY 1x (`agent_fundcarry.md`), which failed on validation n and on the DEX leg cost.

**Bar** (out of sample, per-episode return on capital): n ≥ 50, net > 0, PF > 1.2, net > 0 with the 3 best removed.
**Result:** all three pre-registered configs pass on train (2020-01 to 2025-06), driven by 2020–21 and 2024Q1. All three
fail on validation (2025-07 to 2026-03, run once): n = 44 / 28 / 12, net negative, PF ≈ 0.01. The holdout
(≥ 2026-04) was never downloaded or examined. Do not run it.

## Pre-registration
`reports/hypotheses/spotcarry_wide_preregistration.json`, frozen 2026-10-05T04:33Z, before any price data was downloaded.
- Signal S72 = sum of funding prints in (T−72h, T], annualised. Entry: S72 ≥ F and latest print ≥ 0.01%/8h-equivalent,
  and the symbol is ≥ 30 days old on both legs with trailing-7d spot volume ≥ $2M/day. Fill at the next 1h close on both legs.
- Exit: S72 < 10%/yr, 14 days, perp 1h high ≥ 1.5× entry (stop), delisting (close at the last bar, −2% of capital), or split end.
  Re-entry is allowed from the next hour.
- Equal units, 1x isolated perp. Capital = spot notional + perp margin (≈ 2N).
- Configs (3, no others run): **L72/F30/Z14 stop50** (frozen round-5 rule), **F50** and **F100** (fundcarry's 1x train cells).

## Data (data.binance.vision only; months ≤ 2026-03; 310 MB compact parquet, zips never written)
- S3 listing: 988 fundingRate symbols, 3,710 spot kline symbols, giving **478 USDT perp↔spot pairs**. That includes
  7 `1000X` perps mapped to spot X with a ×1000 multiplier (PEPE, SHIB, BONK, FLOKI, LUNC, XEC, BTTC).
  - 8 pairs miss a dataset, and 462 load.
  - Eligible (liquidity and age) at some time: 402 symbols in train, 389 in validation.
- **No survivorship:** the archive keeps delisted symbols. About 89 perps show post-delisting filler bars.
- Cache: `data/raw/web/binance_carry/{funding,perp,spot}/`, with manifests holding the sha256 of every zip.
  The funding manifest lacks the first 20 symbols because the first run crashed on a Unicode symbol URL; their data is cached.

## Costs
- Spot taker 0.10%/side ([Binance fee schedule](https://www.binance.com/en/fee/schedule)).
- Perp taker 0.05%/side (Binance FAQ 360033544231). Both are as cited in the round-5 doc.
- Slippage per leg per side by trailing-7d spot volume: 5 bp at ≥ $20M/day, 15 bp at $2–20M.
- No borrow: spot is bought with cash and the perp margin is posted in USDT. Funding is valued at the perp 1h close (mark proxy).
- Margin check: the 1x isolated liquidation is at about 1.95× entry and the stop is at 1.5×. No train or validation episode
  gapped through the liquidation price at a bar open. Max perp MAE (bar high) was 1.44 in train and 1.67 in validation,
  i.e. intrabar wicks past the stop. Those are filled at the stop price, which may be optimistic for wicks.

## Fixes made after pre-registration (simulation bugs, not parameters)
1. **Stop fill.** Selling spot at the bar close after an intrabar perp stop credited the rest of the spike to the spot leg.
   Spot is now sold at min(bar close, stop fill × S0/P0), which is conservative. Found on 2 pairs' train episodes, before any aggregate.
2. **Delisting.** The archive emits flat filler bars (open = high = close) after a perp is delisted. One case was STRAX, whose
   1:10 redenomination produced a fake −42%. Runs of ≥ 24 flat bars now count as missing, and a 24h gap in either leg counts
   as a delisting. Found on train, before validation.

## Train (entries ≤ 2025-06-30) — `research/observations/evidence_spotcarry_train.json`
| config | n | net | PF | ex top 3 | funding | basis | cost | coins | top-3-coin share | net ex top-3 days |
|---|---|---|---|---|---|---|---|---|---|---|
| F30 | 4020 | +11.24 | 2.27 | +11.07 | +32.97 | −7.04 | 14.69 | 320 | 6.2% | +10.16 |
| F50 | 2733 | +11.37 | 2.84 | +11.20 | +26.50 | −5.45 | 9.67 | 312 | 5.9% | +10.13 |
| F100 | 982 | +8.22 | 4.09 | +8.04 | +14.51 | −2.95 | 3.35 | 215 | 6.3% | +6.81 |

**Decay (F30 net by year, n):**

| year | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 H1 |
|---|---|---|---|---|---|---|
| net | +1.13 | +8.51 | −0.02 | +0.23 | +2.07 | −0.67 |
| n | 414 | 1601 | 7 | 565 | 1419 | 14 |

- **Mean per episode:** 0.53% in 2021, 0.04% in 2023 and 0.15% in 2024.
- **2021Q1 alone is +5.45**, half the total.
- **From 2024Q2 the quarters are about zero or negative.** 2025Q1 is −0.67, from the AMB pre-delisting squeeze (−0.42) and
  BNX/LINA delistings.
- **Without 2024Q4** the result barely changes (+10.7 to +11.2).

**Cost sensitivity on train:**
- BNB 0.075% spot fee: all three pass.
- Slippage ×2: all three pass (F30 PF 1.24).
- Slippage ×3: F30 fails (PF 0.71), F50 is marginal (PF 1.07), F100 passes.

## Validation (2025-07-01 to 2026-03-31, run once, all 3 configs) — `research/observations/evidence_spotcarry_validation.json`
| config | n | net | PF | ex top 3 | funding | basis | cost | coins | worst |
|---|---|---|---|---|---|---|---|---|---|
| F30 | 44 | −0.896 | 0.018 | −0.907 | +0.147 | −0.686 | 0.357 | 20 | CHESS −0.21 (delist) |
| F50 | 28 | −0.693 | 0.014 | −0.703 | +0.110 | −0.518 | 0.286 | 16 | CHESS −0.21 |
| F100 | 12 | −0.414 | 0.006 | −0.414 | +0.068 | −0.356 | 0.126 | 8 | CHESS −0.20 |

- **By quarter (F30):**

  | quarter | net | n |
  |---|---|---|
  | 2025Q3 | −0.53 | 24 |
  | 2025Q4 | −0.05 | 8 |
  | 2026Q1 | −0.32 | 12 |
- **Exits (F30):** 17 stops, 9 delistings, 11 signal exits and 6 time exits.
- **Concentration:** losses come from HIFI (−0.28), CHESS (−0.21), BANANAS31, A2Z and ALPINE, mostly delisting-squeeze names.
  There is no positive top-3-coin share to speak of: the best coin made +0.006.
- **Even at zero slippage** F30 nets −0.785, because funding (+0.15) does not cover fees alone. The failure does not depend
  on the slippage model or on the conservative stop fill.

## Interpretation
- **The incidence of persistent high funding collapsed.** On eligible symbols, S72 ≥ 30% held in 11.4% of symbol-hours in train
  (696k of 6.12M) but in 0.21% in validation (2.5k of 1.17M), across only 20 symbols.
- **What still triggers is the wrong kind of carry.** It is mostly illiquid names facing delisting, where the perp is squeezed
  against a falling spot. That is BIS WP 1087's "high carry predicts crashes" in its worst form.
- **Train profit is a regime artefact.** It comes from 2020–21 and 2024Q1, before arbitrage capital (e.g. Ethena-scale
  basis trades) compressed Binance funding. Per-episode yield decayed from 0.5% to about 0.1% and then went negative.
- **The bar fails for several reasons at once:** too few episodes (n < 50 for all three configs), net negative,
  PF far below 1.2, and negative net without the top 3.
- **Caveats:**
  - funding is valued at the perp close, not the exact mark;
  - stop wicks are filled at the stop price;
  - the archive's perp history starts 2020-01, so older listings look ≥ 30 days old from then;
  - historical fee tiers are taken as today's.

## Files
- `reports/hypotheses/spotcarry_wide_preregistration.json`
- `scripts/research/spotcarry_universe.py`: S3 listing to `universe.json`
- `scripts/research/spotcarry_fetch.py`: archive fetch to compact parquet (holdout months excluded)
- `scripts/research/spotcarry_sim.py`: `python scripts/research/spotcarry_sim.py train|validation [--spotfee x] [--slipx k]`
- `research/observations/evidence_spotcarry_{train,validation}.json`
