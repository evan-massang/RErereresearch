# H-FFDIFF-WIDE: HL vs Binance funding differential on every coin listed on both venues. Verdict: FAIL (train)

Family: `sources/leads/documented_edges_round5.md` Idea 4 (H-FFDIFF-WIDE; the coordinator's "idea 3"). Parent:
H-FFDIFF iteration 2 (`reports/failures/agent_ffdiff.md`).

**Bar** (out of sample): n >= 50, net > 0, PF > 1.2, net > 0 without the 3 best trades.

**Result: 0 of 3 promotable configs pass on train.** The primary config (A) misses only on PF (1.18), but its profit is
one month (November 2024); every train quarter after 2024Q4 is negative. **Validation (2025-07-01..2026-03-31) was
not examined. The holdout (>= 2026-04-01) was never fetched to disk or loaded.**

## Pre-registration

`reports/hypotheses/ffdiff_wide_preregistration.json`, written before any data of this family was fetched and before
any P&L. Two amendments were recorded before the first P&L run (no P&L had been computed):
1. HL 4h candles with volume 0 are treated as missing (14,638 of 636,195 candles on 56 coins move in price but have no
   trades: pre-listing/post-delisting oracle candles). This mirrors ffdiff's existing Binance `qv > 0` filter.
2. Another family's cache (`data/raw/web/binance_carry/`) disappeared mid-run, so all inputs are private compact copies.

**Rule (frozen, ffdiff iteration 2 unchanged):** 4h clock; D_W = annualised HL funding (prints <= T-1h) minus Binance
funding (prints < T) over trailing W h; enter when s*D72 >= X and s*D24 >= X, short the high-funding venue and long the
other at equal notional, fill at both 4h closes; exit on the D72 sign flip, 14 days, a 40% adverse close move on either
leg, per-leg liquidation, or a data gap. **Leverage 0.5 per leg** (margin 2N per venue), per-leg liquidation checked
separately on 4h highs/lows (mm_HL = 1/(2*maxLeverage), mm_BN = 5%).

**Costs:** HL taker 4.5 bp ([HL fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees), tier 0) and
Binance USDⓈ-M taker 5.0 bp ([Binance futureFee](https://www.binance.com/en/fee/futureFee), regular user) per fill, plus
pre-registered slippage per venue and leg. **Slippage model (frozen before any volume or P&L was computed):** V = median
4h quote volume / 4 over train bars, per venue (HL: v*c; Binance: kline quote volume); $10k per leg; V >= $20M/h -> 2 bp,
$5-20M -> 3, $1-5M -> 5, $250k-1M -> 8, $50-250k -> 12, < $50k -> 15 (cap). Resulting tiers: HL {2:2, 3:4, 5:7, 8:19,
12:62, 15:115 coins}; Binance {2:11, 3:29, 5:89, 8:69, 12:11}. **HL is thin for most alts (median V about $27k/h)**, so
the typical round trip is 19 bp fees + about 40 bp slippage = 57 bp mean.

**Configs (4):** A all coins X40 (primary); B non-meme only X40 (round-5's primary); C all coins X80; D = A at 2x
slippage (stress, not promotable).

## Data (public, no keys)

| item | source | private cache (compact parquet, 97 MB total) |
|---|---|---|
| universe | HL meta (cached `listshort_meta.json`, delisted included) x Binance USDT-M symbols, `listshort_classify` base rules | `data/raw/web/ffdiff_wide/universe.json` |
| HL hourly funding | HL info `fundingHistory` (from 2024-06-13) | `ffdiff_wide/hl_funding/<coin>.parquet` |
| HL 4h candles | HL `candleSnapshot` (latest 5000 only -> from about 2024-06-24) | `ffdiff_wide/hl_k4h/<coin>.parquet` |
| Binance funding and 4h klines | data.binance.vision monthly `fundingRate`, `klines/4h` (2024-06..2026-03) | `ffdiff_wide/bn_funding/`, `bn_k4h/` |

ffdiff/fundcarry JSON caches were read only and converted. No zips or JSON kept. Nothing at or after 2026-04-01 was written.

**Universe:** 216 name matches; 209 kept after the identity check (median HL/BN close ratio in [0.995, 1.005]): 36
meme, 173 non-meme. Rejected: MEGA (ratio 1.046, a different asset) and FTT, STRAX, CHIP, GRAM, PONS, USELESS (no data
on one venue before 2026-04-01). **162 coins traded in train.**

**Code check:** the same simulator run at ffdiff's settings (memes, lev 1, 5 bp) gives n 137, net +0.040, PF 1.09,
ex-top-3 -0.037, 1 liquidation, against ffdiff's published 140 / +0.033 / 1.07 / -0.044 / 1 (the 3-trade gap comes from
the zero-volume filter).

## Train results (entries 2024-06-24 .. 2025-06-30), net per unit notional N

`research/observations/evidence_ffdiff_wide_train.json` (all episodes)

| config | n | net | PF | ex top 3 | mean net | funding/trade | basis/trade | cost/trade | liq | pass |
|---|---|---|---|---|---|---|---|---|---|---|
| A all X40 | 631 | +0.321 | **1.18** | +0.171 | +5.1 bp | 59.1 bp | +3.0 bp | 57.0 bp | 0 | **no (PF)** |
| B non-meme X40 | 494 | +0.185 | 1.13 | +0.043 | +3.7 bp | 60.2 bp | +2.1 bp | 58.6 bp | 0 | no (PF) |
| C all X80 | 151 | +0.028 | 1.04 | -0.106 | +1.9 bp | 65.9 bp | -5.8 bp | 58.2 bp | 0 | no |
| D = A, slip 2x | 631 | -2.077 | 0.38 | -2.217 | -32.9 bp | 59.1 bp | +3.0 bp | 95.0 bp | 0 | no (stress) |

What it shows:
- **0.5x leverage removed liquidations entirely** (0 in every config; the meme subset's MOODENG loss is gone). The
  stop (40% adverse close) fired 116 times in A.
- **Funding collected per trade (about 60 bp) roughly equals the round-trip cost (57 bp).** Widening to non-memes did not
  raise the per-trade differential, and HL's thin books on non-memes raise the cost. The edge is a few bp per trade.
- **Doubling slippage turns A deeply negative** (PF 0.38): the result is entirely inside cost-model uncertainty.

### Concentration (A)
- 162 coins; top 3 coins TIA +0.074, TAO +0.065, FARTCOIN +0.057 = **14% of positive per-coin net**; net without the
  top 3 coins +0.125. Coin concentration is low; **time concentration is the problem.**
- Meme 137 trades, +0.136, PF 1.45; non-meme 494 trades, +0.185, PF 1.13.
- Direction: short-HL/long-Binance 511 trades +0.898; short-Binance 120 trades -0.577.
- By liquidity: trades whose two legs' slippage sum <= 15 bp made +0.47 (109 trades); the thinnest (20-30 bp) lost -0.54 (230).
- Worst trades are gap exits (LOOM -8.5%, BADGER -4.9%, VVV -3.9%): a venue stopped printing mid-position, so the exit
  price is the last close, which is optimistic.

### Per quarter and decay (A)

| quarter | n | net | mean net | funding/trade | cost/trade |
|---|---|---|---|---|---|
| 2024Q2 | 10 | -0.015 | -15 bp | 33 bp | 60 bp |
| 2024Q3 | 63 | -0.070 | -11 bp | 43 bp | 57 bp |
| 2024Q4 | 269 | **+0.819** | +30 bp | 83 bp | 56 bp |
| 2025Q1 | 141 | -0.218 | -16 bp | 33 bp | 58 bp |
| 2025Q2 | 148 | -0.194 | -13 bp | 49 bp | 58 bp |

By month, November 2024 alone is +0.676 (133 trades). **Without November 2024, A is -0.355.** The differential was only
worth more than cost during the late-2024 retail-leverage episode on HL; the last two train quarters (the most recent
regime before validation) both lose. B and C show the same pattern (C: 2025Q2 -0.149).

## Verdict

FAIL on train for all promotable configs. A's PF is 1.18 (< 1.2); even if it had cleared 1.2, its P&L is one month,
and it decays to negative from 2025Q1. Validation was not opened (no config passed train) and nothing was re-tuned.

Not modelled (each would make results worse, except the last): ADL and delistings beyond the gap exit; historical HL
maxLeverage; latency inside the 4h bar; capital cost of 2x margin on both venues (the ROC is about a quarter of 1x
returns). In the other direction: slippage is a volume-tier proxy, not a book-depth measurement; maker execution was
already tested by ffdiff (legging risk replaced the saved cost).

Do not revisit this rule unless a measured, materially cheaper HL execution cost (well under 5 bp per fill on alts) is
established first, and even then only with the 2025 quarters as the reference regime.

## Files
- `reports/hypotheses/ffdiff_wide_preregistration.json`: pre-registration and the two pre-P&L amendments.
- `scripts/research/ffdiff_wide_fetch.py`: universe and fetch, with the holdout guard.
- `scripts/research/ffdiff_wide_sim.py`: `universe` | `train` | `validation KEY` (refuses configs that did not pass train).
- `research/observations/evidence_ffdiff_wide_train.json`: 4 configs, stats and every episode.
- `data/raw/web/ffdiff_wide/`: compact parquet caches (97 MB) and `universe.json` (with liquidity and slippage tiers).
