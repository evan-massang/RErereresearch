# H-FUNDCARRY: delta-neutral funding carry on Solana-memecoin perps (Hyperliquid). Verdict: FAIL

Family: short Hyperliquid perp and hold the same number of spot units, collecting hourly funding while
funding stays high. Sources: `sources/leads/documented_edges_round3.md` idea 5 (BIS WP 1087
Schmeling/Schrimpf/Todorov; He, Manela, Ross & von Wachter arXiv 2212.06888). Idea 6 (H-LISTSHORT) was **not**
tested here; its 23 listings had already been seen by the round-3 pre-check.

**Bar** (out of sample): n ≥ 50, net > 0, PF > 1.2, net > 0 without the 3 best episodes.
**Result:** the pre-registered 2x family fails on train (12/12 configs). A 1x iteration passes on train in 3/12
cells, but on validation none of the three reaches 50 trades (n = 13, 8, 6). The holdout was not fetched or
looked at.

## Data (all public, no keys; cached, nothing at or after 2026-07-01 written to disk)

| item | source | cache |
|---|---|---|
| perp universe, max leverage | HL `info` `{"type":"meta"}` (234 assets) | `data/raw/web/hyperliquid/meta.json` |
| hourly funding + premium | HL `fundingHistory`, paginated by 500 | `data/raw/web/hyperliquid/funding_<coin>.json` |
| perp candles 1d / 4h | HL `candleSnapshot` | `data/raw/web/hyperliquid/candles_{1d,4h}_<coin>.json` |
| Solana mint mapping | hand map in `fundcarry_fetch.py`, each mint checked against DexScreener `tokens/v1/solana/<mint>` (symbol match) | `data/raw/web/hyperliquid/universe_map.json` |
| spot 1h | Binance (`data-api.binance.vision`), else OKX, else MEXC: the first venue covering the perp listing | `data/raw/web/spot_ohlcv/<coin>_1h.json` |

**Universe.** There are 23 Solana memecoin perps on HL with a verified mint: WIF, kBONK, POPCAT, MEW, BOME, MYRO, GOAT,
MOODENG, PNUT, CHILLGUY, FARTCOIN, AI16Z, ZEREBRO, GRIFFAIN, TRUMP, MELANIA, VINE, JELLY, LAUNCHCOIN, PUMP,
USELESS, PENGU and YZY.
- CASHCAT and PONS were excluded because no Solana mint could be found for them.
- USELESS was listed on HL only in Sep 2026 (holdout), so it has no data.
- AI16Z, LAUNCHCOIN and YZY have no public hourly spot history (MEXC/OKX/Binance), so they were dropped.
- **That leaves 19 coins simulated.** They cover 2023-11 to 2026-06, with 100% spot coverage of held hours.
- Venues: Binance for BOME, PNUT, TRUMP and PENGU; OKX for MEW and VINE; MEXC for the rest.

**Limits that forced proxies.**
- HL `candleSnapshot` serves only the latest 5000 candles, so there are no 1h perp prices in train.
- GeckoTerminal public OHLCV covers only the last 180 days (HTTP 401 before that).
- Bybit is geo-blocked, and Binance's main API returns 451 (restricted location).

The proxies are:
- **Perp price** = spot × (1 + HL hourly `premium`). Checked against HL 4h perp closes in train (n = 45,337 coin-4h
  points): median absolute error 0.07%, p95 0.29%, mean +0.006%
  (`research/observations/evidence_fundcarry_proxycheck.json`). That is small next to the costs.
- **Spot leg** = the CEX hourly close, used as the price of the Solana DEX leg. DEX costs are added explicitly.
- **Max leverage** is today's value from `meta`. The historical tier may have differed.

## Rules (pre-registered in the `fundcarry_sim.py` docstring before any result)

- **Signal:** the trailing L-hour mean of HL hourly funding, annualised. It is observed at print t, and the trade fills
  at the spot close of the bar ending at t. The position earns prints t+1 through the exit.
- **Entry:** signal ≥ F.
- **Exit:** any of:
  - signal < 10%/yr;
  - Z days pass;
  - margin stop: perp loss ≥ 50% of the initial margin, checked on hourly close;
  - liquidation: the intrahour spot high × (1+premium) reaches the isolated liquidation price, with maintenance
    margin = ½ of the initial margin at max leverage (HL margining docs). The whole margin is assumed lost and the
    spot is sold at the hour's close;
  - split end or a data gap.
- **Grid (12):** L ∈ {24, 72} h × F ∈ {30, 50, 100}%/yr × Z ∈ {7, 14} d.
- **Costs per side:**
  - HL perp taker 0.045% (base tier; https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees);
  - perp impact 0.05%;
  - Solana DEX fee+slippage 0.5% (sensitivity 0.3% / 1.0%);
  - $0.10 tip per swap;
  - $2 bridge per round trip on a $10k notional.
  - The legs hold equal units, so no delta rebalancing is needed. Margin top-ups are not modelled (that is the stop).
- **Splits:** train = entries to 2025-12-31 (positions force-closed at the boundary); validation =
  2026-01-01 to 2026-06-30, looked at once.
- **P&L** is per unit of short notional N. Capital is N(1 + 1/lev).

## Results

### Iteration 1: 2x isolated (pre-registered). FAIL on train, all 12 cells
- PF 0.10–0.38 and net −3.4 to −13.3 (sum of per-episode returns), even at 0.3% DEX cost.
- Funding collected is positive in every cell (+1.4 to +3.2), and basis is positive (+0.15 to +0.68).
- What kills it:
  - **Liquidations.** At 2x with max leverage 3, a +28.6% spot move liquidates the short. That happened in 18–58
    episodes per cell, at about −0.2 to −0.3 each. In the L24/F100/Z14 cell, 22 liquidations cost −4.06 against a
    cell net of −3.36.
  - **Costs** of about 1.2% per round trip.
- Worst episodes: CHILLGUY −0.54 (Nov 2024 squeeze), GOAT −0.37, MOODENG −0.33.
- Evidence: `research/observations/evidence_fundcarry_train_lev2.json`.

### Iteration 2: 1x isolated (rationale: liquidations above). The same 12 cells, 24 configs examined in total
At 0.5% DEX cost, three cells pass on train (`evidence_fundcarry_train_lev1.json`):

| cell | n | net | PF | net ex top 3 | funding | basis | cost | max DD | worst | liq |
|---|---|---|---|---|---|---|---|---|---|---|
| L72 F50 Z14 | 150 | +0.297 | 1.28 | +0.144 | +2.59 | +0.18 | 1.80 | 0.71 | JELLY −0.43 | 2 |
| L72 F100 Z7 | 86 | +0.223 | 1.48 | +0.115 | +1.46 | +0.11 | 1.05 | 0.36 | JELLY −0.31 | 1 |
| L72 F100 Z14 | 70 | +0.582 | 2.43 | +0.416 | +1.61 | +0.11 | 0.84 | 0.32 | JELLY −0.31 | 1 |

Warning signs already visible in train:
- **None of the three passes at 1% DEX cost.** PF is 0.35, 0.30 and 0.83.
- **The profit is all from 2024.** 2025Q1 is −0.28 to −0.43 (the JELLY squeeze, and VINE in the F50 cell), and
  2025Q2–Q4 is about flat.
- **The 2025 episode count collapsed.** The F100 cells had only 15 entries in all of 2025.
- **It is concentrated in four coins:** WIF, kBONK, POPCAT and MYRO.

### Validation (2026 H1, run once, 1x, three cells): FAIL on n
`research/observations/evidence_fundcarry_validation_lev1.json`

| cell | n | net | PF | net ex top 3 | funding | coins |
|---|---|---|---|---|---|---|
| L72 F50 Z14 | 13 | +0.206 | 7.5 | +0.007 | +0.35 | ZEREBRO 5, GRIFFAIN 4, VINE 3, CHILLGUY 1 |
| L72 F100 Z7 | 8 | +0.127 | 12.6 | +0.009 | +0.23 | ZEREBRO 4, GRIFFAIN 2, VINE 2 |
| L72 F100 Z14 | 6 | +0.164 | 22.3 | −0.001 | +0.24 | ZEREBRO 3, GRIFFAIN 2, VINE 1 |

The episodes were profitable, with no liquidations and a worst episode of −2%. But n is 6–13, far below 50. The
result rests on ZEREBRO; without the 3 best episodes it is about zero, and at 1% DEX cost it is negative.
**The bar is not met.**

## Interpretation
- **The carry is real but thin.** Funding on Solana-meme perps was persistently high in 2024. Since 2025 the
  persistent, high-funding regime has largely gone (arbitrage capital arrived, or meme leverage demand fell).
  2026 H1 produced only 6–13 qualifying episodes across 19 coins.
- **The binding risks** are the short-squeeze liquidations (BIS: "high carry predicts crashes"; JELLY, CHILLGUY
  and MOODENG) and the DEX round-trip cost. At 2x the liquidations dominate. At 1x the capital need doubles,
  which halves the return on capital.
- **Caveats:**
  - the spot leg is a CEX proxy;
  - historical max leverage is unknown;
  - liquidation is checked on hourly highs, so a real wick could be worse;
  - funding paid into isolated margin is ignored, which is conservative.

Do not run the holdout for this family: no config passed validation.

## Files
- `scripts/research/fundcarry_fetch.py`: universe map, mint verification, HL + spot fetch (holdout guard)
- `scripts/research/fundcarry_diag.py`: premium-proxy check
- `scripts/research/fundcarry_sim.py`: episode simulator. Run `python scripts/research/fundcarry_sim.py <train|validation> <lev> [L,F,Z ...]`
- `research/observations/evidence_fundcarry_{proxycheck,train_lev2,train_lev1,validation_lev1}.json`
