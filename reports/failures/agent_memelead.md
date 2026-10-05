# H-MEMELEAD (meme-perp leader → follower, 5–60 s, Lighter execution): FAIL on train; validation (information only) also fails

Agent "memelead", 2026-10-05. The data is real (`is_synthetic = false`) and every number here is our own computation.
- **Pre-registration:** `reports/hypotheses/memelead_preregistration.json`, written before any aggTrades archive was
  downloaded.
- **Scripts:** `scripts/research/memelead_fetch.py`, `memelead_spreads.py`, `memelead_sim.py`.
- **Evidence:** `research/observations/evidence_memelead_train.json` and `evidence_memelead_validation.json`.
- **Trade-level data:** `data/raw/web/memelead/trades_{train,validation}.parquet`.

**Bar (per split, primary cost = 1.5 × the measured Lighter $1,000 round-trip spread):** n ≥ 50, net > 0, PF > 1.2,
net > 0 without the top-3 trades.

## How this differs from the earlier lead-lag and sympathy failures

| earlier test | what it did | what H-MEMELEAD does instead |
|---|---|---|
| H-XLEAD | BTC/SOL/meme-index lags in 1-min klines; always-on regression signal; HL taker fee ~13–19 bp; its edge vanished at a 1-minute delay | Rare large 2-s shocks in the most liquid meme perps; second-level aggTrades with an explicit 600 ms fill delay; follower must still be unmoved; 0 fee, spread-only cost. It tests XLEAD's open caveat ("not without tick data and sub-second execution"). |
| H-SOLLEAD | SOL leading pump.fun curve/AMM tokens at 1 min | Perp-to-perp within the meme complex |
| sympathy | narrative copies on the curve, 5–30 min | No narrative matching, 10–60 s, perps |
| H-LIGHTLAG | same coin, Binance → Lighter | Cross-coin; only Lighter's cost and latency conventions are borrowed, and no LIGHTLAG data or result was opened |

## Data

- **Source:** data.binance.vision USDⓈ-M daily aggTrades on the 8th of each month, 2025-01 to 2026-03 (15 days, fixed in the pre-registration).
- **Download:** 176 coin-days, 671 MB in total, 0 errors.
  - The zips were deleted after processing. Each one's URL, size and sha256 are in `data/raw/web/memelead/manifest.jsonl`.
- **Compact store:** 1-s tables in `data/raw/web/memelead/s1/` (262 MB).
  - Bid proxy = last seller-initiated trade price; ask proxy = last buyer-initiated trade price.
  - Each is stored at the end of the second and at +600 ms.
- **Holdout (2026-04-01 onward):** never downloaded.
- **One-day-per-month sampling:** this keeps total downloads under 800 MB (two days a month would have been about 1.5 GB).
- **PUMPUSDT:** data before 2025-07-11 is a different token under the same symbol and was excluded.
- **Unused files:** FARTCOIN, PENGU and SPX were fetched for 2025-01-08 but not used, because each had fewer than 30 days of history.
- **Universe (13 coins):** DOGE, 1000PEPE, WIF, FARTCOIN, PUMP, POPCAT, 1000FLOKI, PENGU, SPX, TRUMP, 1000BONK, 1000SHIB, USELESS.
  - All are active on Lighter with a 0/0 fee.
  - **Leaders, decided point in time each day:** the top 3 by mean daily quote volume over the previous 30 days. In practice these were DOGE and 1000PEPE plus one of FARTCOIN, TRUMP, WIF, PUMP or PENGU.
  - **Followers:** all other coins.

## Costs: Lighter public order books, measured 2026-10-05 (46 snapshots per coin, ~10:21–10:52Z)

Costs are the $1,000 round trip, (VWAP to buy − VWAP to sell) / mid, in bp.

| coin | median | ×1.5 (primary) | coin | median | ×1.5 |
|---|---|---|---|---|---|
| DOGE | 3.2 | 4.8 | PENGU | 6.3 | 9.4 |
| 1000PEPE | 4.4 | 6.7 | TRUMP | 6.2 | 9.3 |
| FARTCOIN | 3.5 | 5.3 | 1000SHIB | 7.7 | 11.6 |
| PUMP | 3.3 | 4.9 | 1000BONK | 10.0 | 15.0 |
| WIF | 7.3 | 11.0 | USELESS | 12.0 | 18.1 |
| SPX | 21.4 | 32.0 | 1000FLOKI | 29.1 | 43.7 |
| POPCAT | 38.6 | 57.9 | | | |

## Train (6 days, 2025-01-08 .. 2025-06-08): all 12 configs fail

The "net" column is the mean net per trade in bp at the primary cost.

| config | n | distinct leader triggers | gross bp | cost bp | net bp | PF | net ex top-3 (bp sum) | cluster t | days + |
|---|---|---|---|---|---|---|---|---|---|
| b1_th25_H10 | 5367 | 811 | +1.8 | 24.7 | −22.9 | 0.02 | −123,063 | −70.9 | 0/6 |
| b1_th25_H30 | 4489 | 718 | +1.4 | 24.7 | −23.4 | 0.07 | −105,503 | −40.3 | 0/6 |
| b1_th25_H60 | 3826 | 620 | +1.7 | 24.8 | −23.1 | 0.12 | −88,804 | −27.7 | 0/6 |
| b1_th40_H10 | 1088 | 151 | +2.1 | 24.9 | −22.7 | 0.03 | −24,856 | −31.4 | 0/5 |
| b1_th40_H30 | 996 | 140 | +2.7 | 25.0 | −22.3 | 0.09 | −22,435 | −17.3 | 0/5 |
| b1_th40_H60 | 947 | 135 | +1.9 | 25.0 | −23.0 | 0.14 | −22,207 | −12.6 | 1/5 |
| b1_th60_H10 | 226 | 31 | +5.0 | 24.9 | −19.9 | 0.05 | −4,586 | −10.1 | 1/3 |
| b1_th60_H30 | 211 | 29 | +4.4 | 24.9 | −20.6 | 0.11 | −4,466 | −7.0 | 0/3 |
| b1_th60_H60 | 203 | 28 | −0.9 | 25.0 | −25.9 | 0.10 | −5,457 | −6.4 | 0/3 |
| bT_th40_H10 | 442 | 123 | +1.8 | 28.8 | −27.0 | 0.03 | −12,041 | −14.8 | 0/5 |
| bT_th40_H30 | 396 | 114 | +2.3 | 29.3 | −27.0 | 0.09 | −10,930 | −10.3 | 0/5 |
| **bT_th40_H60** | 372 | 109 | +2.7 | 29.3 | −26.6 | **0.18** | −10,273 | −8.0 | 1/5 |

- **Correlated trades:** one leader trigger opens up to 8 follower trades. Effective n is the trigger or cluster count
  (28–811), not the trade count. Clusters (any leader within 5 s) are almost the same as triggers.
- **Concentration:** 2025-02-08 alone produced 11,909 of the train trades, on a FARTCOIN shock day. Every day is negative at θ = 25.
- **Cost sensitivity:**
  - At 1.0× the median spread, the best config by PF (b1_th40_H30, PF 0.18) still nets −14.0 bp per trade.
  - The 1.5 × p90 stress is worse.
- **Gross by follower is +1 to +6 bp for every follower.** POPCAT is the highest, at +4 to +9.5 bp, but it costs 58 bp. That is
  below even the cheapest followers' 1× spread (PENGU 6.3, 1000SHIB 7.7, WIF 7.3). No follower is net positive at θ ≤ 40. At θ = 60
  the best are PENGU at −3.5 bp and WIF at −5.7 bp, on 30 trades each.

## Validation (9 days, 2025-07-08 .. 2026-03-08): run once on bT_th40_H60, information only

As pre-registered, nothing passed train, so the config with the highest train PF among n ≥ 50 was run for information.

| n | distinct triggers | gross | cost | net | PF | net ex top-3 | cluster t | win | days + |
|---|---|---|---|---|---|---|---|---|---|
| 517 | 80 | +4.4 bp | 20.8 bp | −16.4 bp | 0.18 | −8,700 bp | −7.0 | 23% | 0/9 |

- At 1.0× cost: −9.5 bp per trade, PF 0.34.
- The only followers with net > 0 are FARTCOIN (+0.5 bp, n 41) and PUMP (+1.0 bp, n 24). These are post-hoc slices and are not
  evidence.
- DOGE-led trades have a negative gross (−9.1 bp).

## Verdict

**FAIL.** Large 2-second shocks in the liquid meme perps do carry over into smaller memes after a 600 ms delay, but only
by about 2–5 bp over 10–60 s. Lighter's measured follower spreads are 6–39 bp (×1.5 gives 9–58 bp), so the gross edge is
smaller than one spread for every follower. The result matches XLEAD, ITSM and XSREV: a few bp of cross-asset
predictability against a cost that is several times larger. Removing the fee (Lighter's 0 bp) does not help, because
the follower spreads on Lighter are themselves wider than the edge.

## Caveats (all of them favour the strategy, so they do not rescue it)

- **Binance as a proxy for Lighter fills.**
  - Binance mid proxies stand in for Lighter fills. Lighter followers may already have re-priced by t + 600 ms, which would shrink the gross further.
  - The mid proxy comes from the last buy and sell trade prices and can be stale. Fills are mid ± spread, not book walks.
- **Spreads were measured in Oct 2026 and applied to 2025–26.** Lighter books were probably thinner earlier, and some markets may not have been listed.
- **Sampling:** one day a month. The 2025-01-08 universe had only 7 rankable coins.
- **Not tried:** maker entry. ITSM, XSREV and HLANCHOR all found passive quotes adverse-selected, and a 2–5 bp gross gives no room for it.
