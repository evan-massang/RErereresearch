# H-ITSM: per-coin intraday time-series momentum on HL-listed Binance USDT-M perps. Verdict: FAIL

_Agent run 2026-10-05. Real data (data.binance.vision), `is_synthetic = false`. All numbers are our own computations.
The papers are leads (`document` modality) and were not read in full here._

Source idea: `sources/leads/documented_edges_round6.md`, idea 7 (Shen, Urquhart & Wang 2022; Gao et al. 2018).
Pre-registration, frozen before any 15m kline was downloaded: `reports/hypotheses/itsm_preregistration.json`.

## Verdict

**FAIL on train. All 12 pre-registered configs fail**, and every one fails every leg of the bar:
- PF is 0.48–0.74.
- Mean net is −8.8 to −18.7 bp per trade.
- The t-statistic of daily net P&L is −2.9 to −14.0.
- Every year 2022–2025H1 is negative, except one: F60_L60_k1 in 2025H1 at +0.5 bp.

The gross edge is −5.7 to +4.3 bp per trade, against a 13 bp round-trip cost. As pre-registered, validation was run
**once** on the config with the best train daily t (F60_L60_k1), for information only. It loses more: −24.8 bp per
trade, PF 0.46. The holdout (2026-04 onward) was never downloaded. The last bar on disk is 2026-03-31 23:45 UTC.

## Data

| item | source | cache |
|---|---|---|
| Monthly universe: top 30 HL-mapped USDT-M perps by M−1 quote volume (≥ 28 daily bars, no stables) | `data/raw/web/momentum/klines`, daily, reused read-only | `data/raw/web/itsm/universe.json` (144 unique symbols over 51 months) |
| HL listing (2026-10-05 snapshot, incl. 56 delisted; X→XUSDT, kX→1000XUSDT) | HL `info` `meta` | `data/raw/web/itsm/hl_meta_raw.json` |
| 15m klines, months M and M−1 for every member, 2021-12..2026-03 | data.binance.vision `futures/um/monthly/klines/<SYM>/15m` | `data/raw/web/itsm/k15/` |

- The download was 241 MB, with 0 missing and 0 errors.
- No zips were kept. The cache is 114 MB.
- Scripts: `scripts/research/itsm_fetch.py` and `scripts/research/itsm_sim.py`.

## Method (as pre-registered)

- **Signal.** r_sig is the coin's return over the signal window. With k > 0, a trade needs |r_sig| ≥ k·σ, where σ is
  the standard deviation of the same window over the prior 30 days (at least 20 observations).
- **Trade.** Trade in the sign of r_sig. Enter at the open of the first 15m bar of the trade window and exit at the
  close of its last bar, taker on both sides.
- **Costs.** 4.5 bp taker + 2 bp slippage per side, so 13 bp per round trip. The Binance sensitivity uses 14 bp.
  No funding print falls inside a held window.

## Train (trade days 2022-01-01 .. 2025-06-30)

Means are in bp per trade. Net sum and net ex-top-3 are sums of fractions of notional, in %.

| config | signal → trade window (UTC) | n | gross | net | net BN | PF | net sum % | ex-top3 % | daily t | 2022 | 2023 | 2024 | 2025H1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F30_L30_k0 | 00:00–00:30 → 23:30–24:00 | 37,835 | +1.8 | −11.2 | −12.2 | 0.61 | −4248 | −4285 | −10.2 | −10.3 | −13.6 | −10.5 | −9.8 |
| F30_L30_k1 | same, \|r\| ≥ 1σ | 9,112 | +4.3 | −8.8 | −9.8 | 0.71 | −797 | −816 | −3.6 | −5.8 | −13.2 | −9.2 | −3.5 |
| F60_L60_k0 | 00:00–01:00 → 23:00–24:00 | 37,936 | 0.0 | −13.0 | −14.0 | 0.68 | −4930 | −4965 | −7.9 | −13.9 | −15.2 | −12.4 | −8.1 |
| **F60_L60_k1** (selected) | same, 1σ | 9,338 | +1.8 | −11.2 | −12.2 | 0.74 | −1047 | −1081 | −2.9 | −13.9 | −18.2 | −6.8 | +0.5 |
| PF_k0 | 00:15–01:15 (post-funding) → 23:00–24:00 | 37,907 | +0.4 | −12.6 | −13.6 | 0.68 | −4770 | −4805 | −7.7 | −13.2 | −13.8 | −10.9 | −12.5 |
| PF_k1 | same, 1σ | 9,043 | −0.4 | −13.4 | −14.4 | 0.71 | −1212 | −1246 | −3.6 | −15.7 | −17.3 | −6.7 | −14.1 |
| PL_k0 | 23:00–23:30 → 23:30–24:00 (previous-to-last) | 37,695 | −3.5 | −16.5 | −17.5 | 0.48 | −6205 | −6246 | −14.0 | −16.9 | −13.9 | −16.2 | −21.1 |
| PL_k1 | same, 1σ | 8,990 | −5.7 | −18.7 | −19.7 | 0.54 | −1678 | −1719 | −5.6 | −15.5 | −14.2 | −18.3 | −36.2 |
| BOTH_k0 | r1 and r12 same sign → 23:30–24:00 | 19,151 | −1.6 | −14.6 | −15.6 | 0.52 | −2803 | −2831 | −9.5 | −14.0 | −14.6 | −13.7 | −18.1 |
| BOTH_k1 | same, both ≥ 1σ | 1,331 | −1.7 | −14.7 | −15.7 | 0.63 | −196 | −212 | −3.1 | −14.6 | −23.2 | −7.4 | −9.2 |
| US_k0 | NY 09:30–10:00 → 15:30–16:00 (DST-aware) | 37,776 | +1.0 | −12.0 | −13.0 | 0.63 | −4520 | −4546 | −8.2 | −15.0 | −8.7 | −12.8 | −10.6 |
| US_k1 | same, 1σ | 9,311 | −0.7 | −13.7 | −14.7 | 0.62 | −1274 | −1296 | −4.4 | −20.2 | −7.1 | −14.9 | −10.7 |

Win rates are 34–43%. Long and short legs both lose in every config: long legs −7 to −14 bp, short legs −10 to −27 bp.

## Validation (2025-07-01 .. 2026-03-31, run once, F60_L60_k1, information only)

| n | days | gross | net | net BN | PF | net sum % | ex-top3 % | daily t | pos days | 2025H2 | 2026Q1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1,756 | 244 | −11.8 | −24.8 | −25.8 | 0.46 | −436 | −453 | −3.9 | 36% | −25.0 | −24.3 |

## Reading

- **The published effect is tiny on our sample.** Diagnostic only, not a config: for BTCUSDT under F30_L30_k0 on
  train, the gross is +0.7 bp per trade (t 0.7, n = 1,277), and for ETH it is +0.8 bp. The sign is consistent with Shen et al.
  (first half-hour → last half-hour), but the size is two orders of magnitude below the 13 bp cost.
- **The previous-to-last half-hour predicts reversal on alts, not momentum** (PL gross −3.5 to −5.7 bp). This is
  the opposite of Gao et al.'s r12 result for equities.
- **Thresholding on the first window's size (k = 1) adds 1–2 bp of gross at best.** The highest-volatility first
  sessions are where Shen et al. report the strongest effect, but here that still leaves the strategy about 9 bp
  short of costs.
- **This matches the costs story of H-XSREV, H-FUNDCLOCK and H-MOMENTUM.** Intraday clock effects in liquid perps
  are worth 0–4 bp gross, against 13–14 bp of taker round-trip cost. A maker execution is not modelled here, because
  15m bars cannot show non-fills honestly.
- **Effective n is days, not trades.** Same-day trades across about 30 coins are one correlated bet. We therefore
  report the t-statistic on daily sums, and it is strongly negative everywhere.

## Caveats

- HL listing is a 2026 snapshot that includes delisted coins, so it is not point in time. HL perps did not exist in 2022.
- The 15m resolution means each fill is at a bar's open or close price. The 300 ms delay and spread are covered only
  by the 2 bp slippage assumption.
- "Session" here is a fixed clock window, not Shen et al.'s volume-defined session.
- The literature figures quoted come from the round-6 lead file and were not re-verified here.
