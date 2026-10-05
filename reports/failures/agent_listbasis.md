# H-LISTBASIS: delta-neutral listing carry on new Solana-meme perps (FAIL: validation n too small)

_Agent: listbasis, 2026-10-05. Source idea: `sources/leads/documented_edges_round12.md`, idea 2._
_Evidence: `research/observations/evidence_listbasis_counts.json`._
_Scripts: `scripts/research/listbasis_count.py`, `scripts/research/listbasis_census.py`. Raw cache:
`data/raw/web/listbasis/` (39 MB)._

## Verdict

**FAIL before any P&L: validation cannot meet n >= 50.** The validation window (2025-07-01 to 2026-03-31) holds
**12** Solana-meme perp listing events across Hyperliquid, Binance USDT-M and Lighter, counting every venue-coin
pair, the coins round 3 had already seen, and events whose spot data could not be confirmed. Only **3** are
clean (not seen by round 3, spot available). The round-12 lead set the stop line at about 40; the bar is 50.

What was not done, on purpose: no preregistration file, no funding or price download for P&L, no train
selection, no validation run. The holdout (listings from 2026-04-01) was recorded as symbol names only.

## Universe (declared before any outcome)

- **Solana memecoin:** CoinGecko category `solana-meme-coins` (2,251 coins, fetched 2026-10-05). The venue base
  symbol (with `k`, `1000`, `1000000` and `1M` prefixes removed) must match it, and the matched coin must be the
  largest-mcap CoinGecko coin with that ticker (the LISTSHORT collision rule).
- **Identity overrides** (asset identity only, no prices; listed in `listbasis_count.py`):
  - Removed: gold and palladium perps (XAU, XPD) that collided with Solana tickers, RONIN, FOOTBALL, and
    1MBABYDOGE (BSC-native).
  - Added: PUMP, YZY, LAUNCHCOIN, AI16Z, GRIFFAIN, JELLYJELLY and CASHCAT. These are Solana-native but sit
    outside the category, or the collision rule dropped them.
  - Binance `PUMPUSDT`: the archive starts in 2025-04 with a different asset, frozen at 0.0471 until 2025-07-09.
    pump.fun PUMP trades under the symbol from 2025-07-10, which is used as its listing date.
- **Listing dates:**
  - HL: first 1d candle from `candleSnapshot`.
  - Binance: first 1d kline in `data.binance.vision` `futures/um/monthly`.
  - Lighter: `orderBooks.created_at`. This matches the first funding stamps PROPCARRY fetched (PUMP 07-14,
    PENGU 07-23, TRUMP 01-30).
- **Completeness check:** a census of the first dates of all 234 HL and all Binance USDT perps
  (`census_first_dates.json`) was reviewed by hand for Solana memes the category might miss. Besides PUMP and YZY
  (added), none of the 190 validation-window listings is a Solana memecoin. Most are BSC memes (4, GIGGLE,
  币安人生, 我踏马来了, 龙虾, BULLA), Base tokens (TOSHI, ZORA, CLANKER), or non-meme launches.
- **Event:** one venue-coin first trading day. **Clean** means the coin is not in round 3's seen set (the 23 HL
  listings plus PUMP, USELESS and YZY, the same rule as LISTSHORT), and spot is available.
- **Spot available:** at least 90% of 4h bars over [listing, listing + 21 d], starting no later than listing + 1 d,
  from the Binance spot archive, MEXC or Gate. GeckoTerminal only covers the last 180 days, which is all holdout.

## Counts

| split | venue events (all) | HL / BN / Lighter | with spot over 21 d | clean (spot, not seen) | distinct coins |
|---|---|---|---|---|---|
| train (to 2025-06-30) | 50 | 20 / 24 / 6 | 45 | **4** (PONKE, ACT, BAN, PIPPIN; all BN) | 25 |
| validation (2025-07-01 to 2026-03-31) | **12** | 2 / 3 / 7 | 7 | **3** (BN BIRB, LT BIRB, LT PIPPIN) | 7 |
| holdout (from 2026-04-01) | names only: BN PENGUSDT, WENUSDT, GMEUSDT; HL CASHCAT, USELESS; LT ANSEM, CASHCAT, WEN, GME | | | | |

**Validation events:**

| venue | coin | date | status |
|---|---|---|---|
| HL | PUMP | 07-10 | seen; no spot before 07-12 (perp opened pre-market) |
| BN | PUMP | 07-10 | seen; no spot before 07-12 (perp opened pre-market) |
| LT | PUMP | 07-14 | seen; spot available |
| LT | PENGU | 07-23 | seen; spot available |
| LT | LAUNCHCOIN | 07-29 | seen; no spot |
| BN | USELESS | 08-15 | seen; spot available |
| LT | USELESS | 08-20 | seen; spot available |
| HL | YZY | 08-21 | seen; no CEX spot at listing |
| LT | YZY | 08-21 | seen; no CEX spot at listing |
| BN | BIRB | 2026-01-29 | clean |
| LT | BIRB | 02-05 | clean |
| LT | PIPPIN | 02-05 | clean |

## Why it fails, and what would be needed

- The validation window had **7 distinct Solana-meme coins** get any new perp in 9 months. Pooling venues only
  adds correlated re-listings: 7 of the 12 events are Lighter re-listings of coins that already had a perp, and
  for those the "new listing" mechanism (crowded longs, slow arbitrage capital) is weaker.
- Most of the meme-perp listing flow after mid-2025 is BSC (Binance Alpha) memes, not Solana. The Solana-meme
  perp wave was 2024 Q4 to 2025 Q1. This is the same regime concentration that LISTSHORT hit, and the train side
  is almost entirely the round-3 seen set: only 4 clean train events.
- Only a wider family could reach n >= 50: all-chain meme or all-altcoin listings, or more venues (Bybit, OKX,
  Gate, MEXC perps; the spot leg then no longer needs to be Jupiter). That is a different hypothesis with its own
  train and validation design. Forward accumulation at about 0.3 clean Solana events a month would take more than
  10 years.
- The holdout was not examined.
