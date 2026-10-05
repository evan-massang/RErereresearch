# H-LPHEDGE (delta-hedged PumpSwap LP, short on Lighter): FAIL on train (agent lphedge, 2026-10-05)

> **Follow-up 2026-10-05:** iteration H-LPHEDGE-2 (corrected coverage rule, one a-priori config P1 b5 1h) PASSED its single validation run: see `reports/candidates/lphedge2.md`.

**Verdict: FAIL on the pre-registered train test. 0 of 12 configs pass. Historical validation (2026-07-25 to 2026-10-05) was not examined.**
- Every config fails on n: P1 has 39 scored pool-days, and P1+P2 has 46. The bar is 50.
- Every config also fails on **net excluding the top 3 days**, which is −$35 to −$94 for all 12.
- The best net is P1 b10 60m: +$18.57 on $5k over 39 days, PF 1.26.

Pre-registration: `reports/hypotheses/lphedge_preregistration.json`.
- It was written at 11:25Z (file mtime), after the fee schedule was confirmed.
- That was before any pool OHLCV, liquidity history, Lighter candle or funding was downloaded (11:27–11:32Z), and before any pumplean file was opened.
- No trading took place. All data is public and read-only.

## Files
- **Scripts:**
  - `scripts/research/lphedge_fee_check.py` (step 1)
  - `scripts/research/lphedge_fetch.py` (data)
  - `scripts/research/lphedge_sim.py` (simulation)
- **Evidence:**
  - `research/observations/evidence_lphedge_fees.json`: fee schedule, its history, and the forward exact-fee check.
  - `research/observations/evidence_lphedge_train.json`: grid, stress and daily rows. It also holds a post-hoc diagnostic, clearly labelled.
- **Raw data:** `data/raw/web/lphedge/` (about 15 MB).

## Step 1: LP fee rate (on-chain, decoded swaps)
| pool | swaps decoded | lp / protocol / creator bps | lp_fee ÷ quote |
|---|---|---|---|
| PumpSwap PUMP/USDC `2uF4Xh61…oiSd` | 60 (recent) + 32 sampled on 8 dates, 2026-05-04 to 10-05 | **25 / 5 / 0** in every swap | 24.93–25.00 bp |
| PumpSwap PENGU/SOL `9qKxzRej…ythA` | 58 (recent) + 32 on 5 dates, 2026-04-20 to 08-01 | **25 / 5 / 0** in every swap | 24.93–25.00 bp |
| PumpSwap Fartcoin/SOL `eUsB7o5H…Rjk6` (not in universe; TVL about $50k) | 60 | 20 / 5 / 90 or 95 | ≈ 20 bp |

- **The LP fee is 25 bp, not the 20 bp the lead assumed.**
- **TRUMP, BONK and WIF have no PumpSwap pool of the real token.** GeckoTerminal search found only copycats.

## Method (as pre-registered)
- **Size:** $5k of liquidity per pool, held through the split. It is 0.018% of P1 (median train TVL $12.9M) and 0.29% of P2 (about $1.4M).
- **Fee income:** our share of the pool per bar is L_ours/(L_pool+L_ours). The pool's liquidity history is exact: it is rebuilt from the pools' Deposit/WithdrawEvents (81 for P1 and 9 for P2 since March, via the LP-mint signatures). Fee income per bar is the GeckoTerminal 15m USD volume × 25 bp × our share.
- **Reconciliation:** the rebuilt liquidity gives P1 TVL ≈ $29M today, which matches GeckoTerminal's $28M.
- **Hedge:**
  - **Legs:** Lighter PUMP, and for P2 also Lighter PENGU and SOL.
  - **Rule:** rebalance when |LP units − short| > b × LP units, checked every 15 min or every hour.
  - **Prices:** Lighter 15m closes, so the pool-vs-perp basis is in the P&L.
  - **Funding:** Lighter hourly funding. Shorts received in about 97% of hours.
- **Costs:**
  - Half the median measured $1k round trip: PUMP 1.88 bp, PENGU 3.56 bp, SOL 0.24 bp (76/76/30 snapshots).
  - The Lighter fee is 0.
  - Gas: 2 transactions a day at 0.0005 SOL each.
  - Setup, charged once per split: 30 bp pool fee plus price impact to buy and sell the token half.
- **Discretisation:** LP value is exact (path-independent). Hedge P&L and threshold checks use bar closes at the check interval. Intra-bar noise between pool and perp adds variance but no expected bias. Fees are not compounded.

## Train results, 2026-04-08 to 2026-07-24 (pre-registered scoring: day needs ≥ 90/96 pool bars and ≥ 90/96 perp candles)
| config | n | net $ | PF | net ex top-3 $ | mean bp/day | hedge trades |
|---|---|---|---|---|---|---|
| P1 b2 15m | 39 | −19.57 | 0.99 | −72.81 | −0.16 | 105 |
| P1 b5 15m | 39 | +15.70 | 1.26 | −42.38 | +1.74 | 12 |
| P1 b5 60m | 39 | +18.03 | 1.28 | −34.61 | +1.90 | 10 |
| P1 b10 60m (best) | 39 | +18.57 | 1.26 | −35.44 | +2.08 | 2 |
| P1+P2 b5 60m | 46 | +2.41 | 1.41 | −61.19 | +2.48 | 16 |
| P1+P2 b2 15m | 46 | −35.14 | 1.14 | −93.60 | +0.78 | 140 |

All 12 configs are in the evidence file. **Stress at 2× spread:** none pass, and the nets move by only $1–4, because hedge cost is tiny.

**P1 decomposition, b5 60m, per scored pool-day, in bp of LP value:**

| component | bp/day |
|---|---|
| fee | **+4.88** |
| funding | **+1.34** |
| LP + hedge (realised LVR + basis) | **−4.15** |
| hedge spread | −0.01 |
| gas | −0.16 |

The ex-post diagnostic σ²/8 is 9.0 bp/day (daily σ 8.3%). The realised LP+hedge loss is about half of that, consistent with the fee/arbitrage reduction of LVR. V/TVL is 0.195 a day.

## Post-hoc diagnostic (NOT pre-registered; not used for the verdict)
- **Why it was run:** about 64% of P1 train days fail the ≥ 90/96-bar coverage rule. GeckoTerminal omits 15m bars with no trades, so most missing bars are probably zero-volume rather than data gaps. That is not verified against on-chain data.
- **What it shows:** with every train day scored (P1 n = 108), 4 of 12 configs would clear the bar. They are P1 b5 15m, P1 b10 15m, P1 b10 60m (+$157, PF 1.50, ex-top-3 +$89) and P1+P2 b10 60m.
- **Mean P1 net is small:** fee 3.0 + funding 1.4 − LP+hedge 2.9 bp a day. That is about 1–3 bp/day on LP value, or roughly 4–12%/yr on 1.5× capital.
- **The best of them hedge very rarely:** the b10 configs make 2–3 trades over 39 days and carry up to 10% residual delta. Their edge over b5 is partly unhedged direction during a period when PUMP rose about 3.5×. It is not a clean hedging result.
- **P2 (PENGU/SOL) loses on its own** (−$46 over 108 days). Fees are 1.3 bp a day at V/TVL 0.05, as the lead predicted.
- **Changing the coverage rule now would be tuning after outcomes.** So the verdict stays FAIL, and the untouched validation window is still clean.
- If the coordinator wants to continue, it should be a new iteration (`add-hypothesis --rationale`, parent = this run):
  - Declare a coverage rule that checks GeckoTerminal's missing bars against on-chain swaps.
  - Fix ONE P1 config, preferably b5 rather than the barely-hedged b10.
  - Run the untouched 2026-07-25 to 10-05 validation once.

## Forward (pumplean) exact-fee check
- **Data:** pumplean `amm_bars` `other_5m` for both pools, read-only, about 10:40–12:05Z on Oct 5, which ends at the declared 12:03Z outage. No LP events fall in the window.
- **Exact fee:** sqrt(k) growth measured from logged reserves was 0.200 bp for PUMP/USDC.
- **Model:** GeckoTerminal volume × 25 bp ÷ (2 × quote reserve) predicts 0.206 bp. The ratio is **1.03**, inside the pre-registered ±30% gate, so the historical fee model is not biased.
- The recorder's own on-chain volume predicts 0.84×. Public-RPC log drops explain the shortfall; reserves are unaffected.
- PENGU/SOL: recorded volume predicts 0.90× of exact.
- **Not done:** forward P&L scoring. The 24 h forward-train segment is not complete, and it could give at most 1 pool-day per segment, so it would be inconclusive by construction.

## Holdout and caveats
- The historical period overlaps the archive-perp holdout (≥ 2026-04-01) of earlier perp tests. That holdout does not apply to this new pool dataset, as stated in the pre-registration. No earlier hypothesis was touched.
- **Not modelled:**
  - Lighter liquidation and margin risk on the 1× short during PUMP's rise.
  - Price impact of hedge trades above the measured $1k depth.
  - Fee compounding.
- Funding sign convention: direction `long` means longs pay. This is inferred from Lighter's docs, as in `propcarry_sim.py`.
