# H-DATEDBASIS: Binance dated-futures cash-and-carry held to delivery. Verdict: FAIL (one formal pass, judged not robust)

Family: buy spot `<COIN>USDT` and short the Binance quarterly (USDⓈ-M linear or COIN-M inverse) when the annualised
basis net of costs beats the 3-month T-bill plus a margin, then hold to delivery. Lead:
`sources/leads/documented_edges_round5.md`, Idea 1 (Christin et al. 2022; BIS WP 1087). These are leads, not validated findings.

**Bar** (out of sample, applied to per-trade excess return over T-bills `r_ex`): n ≥ 50, net > 0, PF > 1.2,
net > 0 without the 3 best trades.

**Result.**
- All 5 pre-registered variants pass on train. The P&L is near-mechanical once the locked basis beats costs.
- On validation, four variants fail on n (28, 2, 28, 17 trades).
- **V2 (cash hurdle only) meets the literal bar on validation**, with n = 94, PF 1.77 and ex-top-3 net +0.062. I do not
  promote it to a candidate:
  - its capital-weighted excess return over T-bills is **−0.09 %/yr**;
  - 81 % of its net comes from thin COIN-M alt contracts, whose fill-bar futures volume is about $4–37k;
  - the liquid subset has PF 1.16;
  - under worst-in-bar entry it has PF 0.15;
  - at cluster level, ex-top-3 is negative.

  The coordinator may weigh this differently. Every number is in the evidence files.

## Pre-registration
`reports/hypotheses/datedbasis_preregistration.json`. It was frozen before any price was loaded.

**Rule.**
- **Decision:** every Monday 00:00 UTC on the 1h close.
- **Window:** 21 ≤ D ≤ 120 days to delivery.
- **Entry:** `(F/S−1)·365/D − c_rt·365/D ≥ DTB3 + margin`.
- **Fill:** the next 1h close plus slippage.
- **Exit:** hold to delivery. The settlement price is the mean of the 1m index over 07:00–08:00 UTC; spot is sold at the
  spot TWAP over the same window.
- **USDⓈ-M:** 1x isolated margin, so capital = 2 × notional. Margin event if the future rises 60 % or more.
- **COIN-M:** hold Q = V/F_in coins, posted as coin collateral (an exact USD hedge), so capital = spot cost.
- **Costs:**
  - spot fee 0.10 % per side ([Binance fee schedule](https://www.binance.com/en/fee/schedule));
  - futures taker 0.05 % ([Binance FAQ 360033544231](https://www.binance.com/en/support/articles/360033544231));
  - settlement 0.05 %, an assumption;
  - slippage 2 bp per leg on BTC/ETH and 5 bp elsewhere;
  - T-bill opportunity cost on **all** capital (spot plus margin), from [FRED DTB3](https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3).

**Variants:**

| Variant | Hurdle | Early exit | Coins |
|---|---|---|---|
| V1 base | T-bill + 2 % | none | all |
| V2 | T-bill + 0 % | none | all |
| V3 | T-bill + 5 % | none | all |
| V4 | T-bill + 2 % | close when the remaining basis is below the T-bill | all |
| V5 | T-bill + 2 % | none | BTC/ETH only |

## Universe and data
data.binance.vision, cached as 47 MB of parquet in `data/raw/web/binance_dated/`. No zips are kept.
- **Contracts:**
  - USDⓈ-M BTCUSDT/ETHUSDT quarterlies from 210326;
  - COIN-M quarterlies for BTC, ETH, BNB, XRP, SOL, ADA, BCH, DOT, LINK and LTC from 2020;
  - EOS, ETC, FIL and TRX (two contracts each);
  - BUSD monthlies excluded.
- **Train:** 133 contracts. **Validation:** 22 contracts expiring 250926, 251226 or 260327; the alt COIN-M quarterlies end at 250926.
- **Holdout:** contracts expiring after 2026-03-31 were never downloaded.

Settlement index vs Binance spot TWAP over 133 train contracts: mean −0.3 bp, sd 5.8 bp, range −15 to +12 bp.
The settlement-mismatch risk is small.

## Results (sum of r_ex; ann = capital-time-weighted return, raw and excess over T-bills)

| | n | clusters | net | PF | ex-top3 | mean/trade | ann raw | ann excess |
|---|---|---|---|---|---|---|---|---|
| **Train V1** | 1054 | 133 | +20.90 | 47.2 | +20.62 | +1.98 % | 11.0 % | 8.8 % |
| Train V2 | 1342 | 160 | +21.08 | 23.9 | +20.79 | +1.57 % | 9.2 % | 6.8 % |
| Train V3 | 774 | 117 | +19.76 | 148.8 | +19.47 | +2.55 % | 13.2 % | 11.3 % |
| Train V4 | 1054 | 133 | +22.48 | 50.8 | +22.11 | +2.13 % | 13.5 % | 11.3 % |
| Train V5 | 433 | 50 | +6.35 | 15.2 | +6.08 | +1.47 % | 8.5 % | 6.0 % |
| **Val V1** | **28** | 11 | +0.096 | 9.1 | +0.066 | +0.34 % | 5.1 % | 1.1 % |
| **Val V2** | **94** | 15 | +0.095 | **1.77** | +0.062 | +0.10 % | 3.9 % | **−0.09 %** |
| Val V3 | 2 | 1 | +0.002 | inf | 0 | +0.09 % | 5.0 % | 0.9 % |
| Val V4 | 28 | 11 | +0.094 | 12.0 | +0.067 | +0.34 % | 5.5 % | 1.4 % |
| Val V5 | 17 | 7 | +0.055 | 5.7 | +0.028 | +0.32 % | 4.8 % | 0.8 % |

**Train robustness.** All of these pass:
- slippage ×2;
- BNB spot fee;
- 30-min settlement window;
- USDⓈ-M margin 0.5;
- excluding 2024Q4;
- the cluster-level bar;
- the post-hoc worst-in-bar entry stress (V1 PF 6.7, n 546).

Train income is concentrated in bull regimes: 2020Q4–2021Q4 and 2024Q1–Q4. There were zero or few entries in 2022Q2–2023Q3.
COIN-M (coin-collateral, capital ≈ 1× notional) earned a mean of +2.3 %/trade. USDⓈ-M (capital 2×) earned +0.4 %.

**Validation V2 diagnostics** (`evidence_datedbasis_validation_stress.json`):

| Check | Result |
|---|---|
| Trades by market | COIN-M: 64 trades, +0.207. USDⓈ-M: 30 trades, −0.112, of which 3 margin events in ETHUSDT_250926. |
| Thin contracts (24h futures volume < $1M) | 26 trades carry 81 % of net; median fill-bar volume is ADA $3.9k, LINK $7.2k, LTC $13.8k |
| Liquid subset | n = 68, PF 1.16. **Fails.** |
| Worst-in-bar entry | n = 22, PF 0.15. **Fails.** |
| Cluster level, 15 (coin, contract) | ex-top-3 −0.027. **Fails.** |
| Capital-weighted excess | −0.09 %/yr. Raw 3.9 %/yr vs T-bill about 4 %. |

## Interpretation
- **The mechanism is real and contractual.** Basis locked at entry is realised at delivery within about ±15 bp of
  settlement mismatch.
- **The edge over cash is regime-dependent and has decayed.** In 2020–21 and 2024 the quarterly basis was 10–30 %/yr.
  In the validation period (mid-2025 to Q1 2026) it sat at roughly T-bill level, so the trade earned cash-like returns.
  This matches BIS WP 1087 (carry decays and is driven by leverage demand) and the round-5 note on Ethena yields.
- **The only variant with enough validation trades (V2, zero risk margin) lives off the noise of thin alt quarterlies.**
  Its liquid part does not clear PF 1.2.
- **Trade counts overlap heavily:** weekly entries into the same contract. Effective n in validation is only 11–15 clusters.

## Risks not modelled
- **Exchange counterparty risk**, in FTX style: the whole capital sits on Binance.
- USDT/USD depeg: COIN-M index is USD-based and the spot leg is USDT.
- Contract-size rounding.
- Index composition changes.
- Jurisdiction.
- 1h-close fills on thin quarterlies, which the stress test suggests are not executable.

## Files
- **Scripts:**
  - `scripts/research/datedbasis_fetch.py`
  - `scripts/research/datedbasis_sim.py`
  - `scripts/research/datedbasis_stress.py` (post-hoc, not used for selection)
- **Evidence:**
  - `research/observations/evidence_datedbasis_train.json`
  - `research/observations/evidence_datedbasis_validation.json`
  - `research/observations/evidence_datedbasis_train_stress.json`
  - `research/observations/evidence_datedbasis_validation_stress.json`

  The evidence files include per-trade lists.
- **Pre-registration:** `reports/hypotheses/datedbasis_preregistration.json`.
