# H-PUMPPULSE: pump.fun activity z-score → memecoin perp basket. Verdict: FAIL

_Agent run 2026-10-05. Real data, `is_synthetic = false`. All numbers are our own computations (DefiLlama
pump.fun revenue + data.binance.vision klines and funding). The lead itself (`sources/leads/documented_edges_round10.md`
idea 3) is a `document`-modality lead with weak evidence._

Pre-registration, frozen before any activity value or return was computed (one amendment, also before any computation,
fixing the PUMPUSDT contract start): `reports/hypotheses/pumppulse_preregistration.json`.

## Verdict

**FAIL on train. None of the 12 pre-registered configs passes the bar.**
- Eight configs have net < 0.
- The four with net > 0 all have **n < 50** or PF ≤ 1.21, and every one has **net ex top-3 < 0**.

As pre-registered, validation was run **once**, for information only, on the config with the highest train net mean
(`LZ_k2_H1_unhedged`). It also fails: net −7 bp per basket-day, PF 0.96, n = 37.

The holdout (2026-04-01 onward) was never touched:
- No price for that period was downloaded.
- Activity rows from that date onward are dropped at load.

## Data

| item | source | cache |
|---|---|---|
| pump.fun bonding-curve daily revenue (child `Solana`/`pump.fun` of the parent `Pump` breakdown) | `api.llama.fi/summary/fees/pump?dataType=dailyRevenue`, unauthenticated, HTTP 200 | `data/raw/web/pumppulse/fees_pump_dailyRevenue.json` |
| curve volume (robustness only) | `api.llama.fi/summary/dexs/pump.fun`, unauthenticated, starts 2024-04-26 | `dexs_pumpfun.json` |
| 1h klines, 8 basket perps + SOLUSDT, 2024-01..2026-03 | data.binance.vision `futures/um/monthly/klines/<SYM>/1h` | `data/raw/web/pumppulse/k1h/` |
| daily klines (tiers, membership), funding | reused read-only from `data/raw/web/momentum/{klines,funding}` | — |

- **Download size:** 6.7 MB. Disk free stayed at about 4.3 GB.
- **Launch counts:** no unauthenticated DefiLlama endpoint gives daily launch counts, so launches were not tested (NULL).
  `summary/fees/pump-launchpad` returns 400.
- **Point in time:**
  - Day d's value is used at 06:00 UTC on d+1, assuming a 6 h publication lag.
  - DefiLlama serves the **current revision**, not the vintage that was visible at the time. Adapter back-fills and
    fee-slice changes are therefore an unremovable look-ahead risk in the level of the series. This would favour the
    strategy, and it fails even so.
- **Quality:**
  - Revenue before 2024-03-12 is a tracking ramp-up of $300–6k/day, and it sits inside the z-window until about
    2024-04-10. Dropping the 0–9 affected train episodes changes no verdict (information-only check).
  - 2 days are missing (2024-05-18/19).
- **PUMPUSDT:** archive bars before 2025-07-10 belong to an earlier, different contract and are excluded.

Scripts: `scripts/research/pumppulse_fetch.py`, `scripts/research/pumppulse_sim.py`.

## Method (as pre-registered)

- **Signals:** level_z is ln revenue against its trailing 28-day mean/sd. change_z is the daily log change against
  its trailing 28-day mean/sd.
- **Trade:**
  - If z ≥ k, long the basket; if z ≤ −k, short it.
  - Hedged configs take the opposite side in SOLUSDT at 1:1 notional.
  - Enter at 06:00 UTC d+1 and hold H days. Episodes do not overlap.
- **Basket:** equal weight over PUMP, WIF, 1000BONK, FARTCOIN, PENGU, TRUMP, 1000PEPE and POPCAT, each eligible once
  it has ≥ 30 prior daily bars. The average is 4.6 members in train and 7.7 in validation. The 2024 basket is only
  PEPE/BONK/WIF, joined by POPCAT from 2024-09.
- **Costs:**
  - 5 bp taker plus a 2/5/10/20 bp slippage tier (by trailing-30d quote volume) per leg per side.
  - Binance funding on every print.
  - Lighter variant: 0 + 3 bp per leg per side, information only.
- **Trade unit:** one basket-day. Episodes are the independent signals.

## Train (episodes entered 2024-04-01..2025-06-30)

Means are in bp of basket notional per basket-day.

| config | episodes (L/S) | n basket-days | gross | net | PF | net sum | net ex top-3 | Lighter net | 2024 net (n) | 2025H1 net (n) | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LZ k1 H1 hedged | 186 (99/87) | 186 | −1.7 | −37.7 | 0.80 | −0.70 | −1.40 | −14.3 | −35 (118) | −42 (68) | no |
| LZ k1 H3 hedged | 85 (43/42) | 255 | +4.0 | −8.2 | 0.95 | −0.21 | −0.95 | −0.4 | −7 (156) | −10 (99) | no |
| LZ k2 H1 hedged | 42 (27/15) | 42 | +63.4 | +25.6 | 1.12 | +0.11 | −0.47 | +50.0 | +47 (27) | −13 (15) | no |
| LZ k2 H3 hedged | 27 (18/9) | 81 | −9.0 | −22.1 | 0.90 | −0.18 | −0.85 | −14.1 | −32 (54) | −2 (27) | no |
| CZ k1 H1 hedged | 100 (47/53) | 100 | −9.9 | −45.4 | 0.77 | −0.45 | −0.78 | −21.8 | −12 (53) | −83 (47) | no |
| CZ k1 H3 hedged | 66 (39/27) | 198 | −46.8 | −58.6 | 0.71 | −1.16 | −1.50 | −50.7 | −78 (114) | −33 (84) | no |
| CZ k2 H1 hedged | 25 (15/10) | 25 | +65.2 | +30.2 | 1.21 | +0.08 | −0.11 | +52.7 | +57 (16) | −17 (9) | no |
| CZ k2 H3 hedged | 21 (15/6) | 63 | +13.7 | +1.9 | 1.01 | +0.01 | −0.19 | +9.4 | +11 (39) | −13 (24) | no |
| LZ k1 H1 unhedged | 186 (99/87) | 186 | −1.4 | −24.5 | 0.92 | −0.46 | −1.37 | −9.2 | −39 (118) | +1 (68) | no |
| LZ k1 H3 unhedged | 85 (43/42) | 255 | +1.8 | −6.7 | 0.98 | −0.17 | −1.15 | −1.6 | −34 (156) | +37 (99) | no |
| **LZ k2 H1 unhedged** (selected) | 42 (27/15) | 42 | +182.8 | +157.6 | 1.71 | +0.66 | **−0.13** | +174.0 | +150 (27) | +172 (15) | no (n, ex-top-3) |
| LZ k2 H3 unhedged | 27 (18/9) | 81 | +10.4 | +0.7 | 1.00 | +0.01 | −0.89 | +5.9 | +7 (54) | −13 (27) | no |

Other train facts:
- **Selected config:**
  - With 2× slippage: +145 bp, PF 1.64, ex-top-3 −0.18.
  - With the curve-volume series instead of revenue: +1 bp, PF 1.00 (n = 54).
  - The unhedged k2 H1 gain sits on 3 basket-days, and on long, high-beta exposure: long +309 bp, short −115 bp.
- **Short legs lose in 11 of 12 configs.**
- **Spearman rank IC, train, 452 days, information only:**

  | signal | next-day hedged | next-day basket | same-day hedged | same-day basket |
  |---|---|---|---|---|
  | level_z | −0.06 | −0.01 | −0.01 | +0.04 |
  | change_z | 0.00 | +0.05 | +0.08 | +0.10 |

## Validation (2025-07-01..2026-03-31), run once: LZ_k2_H1_unhedged, information only

| episodes (L/S) | n basket-days | gross | net | PF | net sum | net ex top-3 | win | Lighter net | slip ×2 net | 2025H2 net (n) | 2026Q1 net (n) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 37 (14/23) | 37 | +20.1 | −7.3 | 0.96 | −0.03 | −0.31 | 57% | +13.6 (PF 1.08) | −24.3 | +21 (24) | −60 (13) |

- **By side:** long +35 bp, short −33 bp.
- **Rank IC, 273 days:**

  | signal | next-day hedged | next-day basket | same-day hedged | same-day basket |
  |---|---|---|---|---|
  | level_z | +0.01 | −0.04 | −0.02 | 0.00 |
  | change_z | +0.07 | +0.06 | −0.04 | +0.05 |

## Reading

- **There is no next-day information in daily pump.fun revenue for the liquid meme-perp complex.**
  - Rank ICs are within ±0.07 and change sign between train and validation.
  - The lead's assumed IC of 0.03–0.05 would itself have been close to the cost line.
  - The only positive cells are high-k configs with 21–42 episodes, all of which lose without their 3 best days.
- **Reverse causality is weakly visible in train.** change_z correlates more with the same-day basket return (+0.10)
  than with the next day (+0.05), which is consistent with prices and launches moving together. The lead named this
  as the main kill risk. It is not stable in validation.
- **Costs are not the binding problem.** The hedged k1 configs are already negative gross, or near zero, before about
  25–40 bp of round-trip cost. Lighter's lower cost does not rescue them: the Lighter train net is still negative
  for 7 of 12 configs.
- **This matches the cost lessons of H-MOMENTUM, H-XSREV and H-ITSM.** One correlated bet per day, with a gross edge
  smaller than or similar to the round-trip cost.
- **Caveats:**
  - Few independent signals: 21–186 episodes in train, 37 in validation.
  - The basket is small and changes composition (3 coins in mid-2024, 8 in 2026).
  - DefiLlama series are current revisions.
  - The 6 h lag is assumed, not measured.
  - The hourly-inflow (forward-only) version was not tested.

## Not done / not to retry without new evidence

- Re-selecting k, window or hold on these results.
- The PUMP-only leg (from the lead's grid). It was not in this registration because the PUMP perp exists only from
  2025-07-10, which leaves no train data.

Evidence:
- `research/observations/evidence_pumppulse_train_20261005.json`
- `research/observations/evidence_pumppulse_validation_20261005.json`
- Slices: `data/raw/web/pumppulse/slices_{train,validation}_*.parquet`
- Validation lock: `data/raw/web/pumppulse/VALIDATION_RUN.lock`
