# Candidate (conditional, fragile): VOLG_high_long_LS, weekly volume-growth spread within Binance meme perps (H-MEMEXS)

_Agent: memexs, 2026-10-05. Pre-registration (frozen before any meme return, signal value or P&L was computed):
`reports/hypotheses/memexs_preregistration.json`. Script: `scripts/research/memexs_sim.py`.
Evidence: `research/observations/evidence_memexs_{train,validation,diag_train,diag_validation}.json`.
Leg and weekly parquet: `data/raw/web/memexs/`. The holdout (2026-04-01 onward) was never read. No new download was
needed: the momentum cache (`data/raw/web/momentum/{klines,funding}`, months up to 2026-03) was reused read-only._

**Verdict.**
- 1 of the 12 pre-registered configs passed the bar on train: `VOLG_high_long_LS`. It was the one selected, and it
  passed validation on its single run.
- **It passes the letter of the bar, but it is not robust.**
  - Train profit is almost all from 2024 Q1–Q2. At that time only about 8–17 memes were eligible, so the portfolio
    was 2 long and 2 short at 25% each. Two legs in that period (1000PEPE and PEOPLE longs) made +1.39 of the +1.71.
  - On validation, PIPPIN alone made +0.48 of the +0.64 (75%).
- Neither diagnostic below was used for selection:
  - Excluding the identity-doubtful coins fails on train.
  - Excluding the single best coin (a post-hoc check) fails on validation.
- The strategy is market-neutral within memes. On validation, most of the profit came from the short leg (low volume
  growth).
- Treat it as a weak lead that one clean holdout run can kill. Do not treat it as an edge.

## Universe (fixed, pre-declared)
- **Classification:** CoinGecko `meme-token` category, from the list cached on 2026-10-05
  (`data/raw/web/coingecko/listshort_meme_category.json`). The H-LISTSHORT rule and its identity overrides are reused
  unchanged (`scripts/research/listshort_classify.py`):
  - Symbols are matched after stripping the 1000, 1000000 and 1M prefixes.
  - When several CoinGecko coins share a symbol, the meme coin must be the largest by market cap.
- **Applied to:** all 900 USDT-M symbols in the data.binance.vision archive, delisted ones included. This gives 74 meme
  symbols, and 67 of them have klines up to 2026-03.
- **Look-ahead risk:** the classification is today's list.
  - Memes that died and left CoinGecko are missing, and coins that later became famous are included.
  - Mitigation: every archived perp of a classified coin is included, delisted ones too, with a 2% penalty on a
    delisting exit (none occurred).
  - Some survivorship toward coins that still exist remains.
- **Identity-doubtful members** are kept in the primary run, as the rule says: GHST, ORDI, M (MemeCore), B (BUILDon),
  PEOPLE, and the AI-agent tokens AIXBT, AI16Z, GRIFFAIN and ZEREBRO.
- **Eligibility, point in time, at each Monday 00:00 UTC:**
  - at least 35 daily bars, a bar for day t-1, and at least 25 of the last 30 days present;
  - 30-day mean daily quote volume of at least $5M;
  - the week is traded only if at least 8 memes are eligible. The first tradable week was in early 2024. Mean
    eligible was 14 in 2024, 46 in 2025 and 38 in 2026 Q1.

## Frozen rule (VOLG_high_long_LS)
- **Signal:** VOLG = quote volume over days t-7..t-1, divided by (quote volume over days t-35..t-8)/4.
- **Positions:** with n eligible and k = max(2, ⌊n/5⌋), go long the top k at +0.5/k each and short the bottom k at
  -0.5/k each. Fill at close(t-1) and hold 7 days.
- **Costs:**
  - Binance taker fee of 5 bp per side;
  - slippage tiers of 2/5/10/20 bp, set by 30-day ADV (≥$1B, $200M–1B, $50M–200M, below $50M);
  - funding prints in (t, t+7d].

## Train: all 12 configs (t < 2025-07-01; 79 traded weeks from 2024-01)
| config | legs | net | PF | net ex top-3 | weekly Sharpe | 2024 | 2025H1 | pass |
|---|---|---|---|---|---|---|---|---|
| R7_mom_LS | 736 | −0.45 | 0.94 | −2.19 | −0.49 | −0.35 | −0.10 | no |
| R7_mom_BASKET | 1946 | +0.31 | 1.05 | −1.05 | 0.29 | +0.35 | −0.04 | no |
| R7_rev_LS | 736 | +0.07 | 1.01 | −1.39 | 0.08 | +0.13 | −0.06 | no |
| R7_rev_BASKET | 1946 | +0.55 | 1.10 | −0.60 | 0.77 | +0.58 | −0.03 | no |
| R28_mom_LS | 736 | −0.06 | 0.99 | −1.81 | −0.05 | −0.34 | +0.28 | no |
| R28_mom_BASKET | 1946 | +0.44 | 1.08 | −0.93 | 0.42 | +0.52 | −0.08 | no |
| R28_rev_LS | 736 | −0.15 | 0.98 | −1.93 | −0.13 | +0.20 | −0.36 | no |
| R28_rev_BASKET | 1946 | +0.38 | 1.07 | −0.98 | 0.45 | +0.78 | −0.40 | no |
| FUND7_low_long_LS | 736 | +0.18 | 1.02 | −1.01 | 0.20 | +0.07 | +0.11 | no |
| FUND7_low_long_BASKET | 1946 | +0.60 | 1.11 | −0.34 | 1.16 | +0.45 | +0.15 | no |
| **VOLG_high_long_LS** | 736 | **+1.71** | **1.28** | **+0.10** | 1.38 | +1.64 | +0.07 | **yes** |
| VOLG_high_long_BASKET | 1946 | +0.74 | 1.13 | −0.50 | 0.93 | +0.92 | −0.18 | no |

- Net is a sum of fractions of capital (gross exposure 1). Legs are coin-weeks.
- Momentum and reversal at both horizons fail. The broad-perp long-short momentum failure repeats inside memes.

## Selected config by split
| | train | validation (run once) |
|---|---|---|
| coin-week legs | 736 | 686 |
| independent (traded) weeks | 79 | 39 |
| net | +1.71 | +0.64 |
| PF | 1.28 | 1.25 |
| net ex top-3 legs | +0.10 | +0.18 |
| mean per leg | 23.2 bp | 9.3 bp |
| mean per week | 217 bp | 164 bp |
| weekly Sharpe (×√52) | 1.38 | 1.90 |
| max DD (additive) | −0.49 | −0.18 |
| long legs / short legs | +1.74 / −0.03 | +0.12 / +0.52 |
| funding paid (− = received) | −0.01 | −0.06 |
| costs | 0.14 | 0.10 |
| turnover per week | 1.14 | 1.13 |
| best coins | 1000PEPE +1.07, PEOPLE +1.02, MEME +0.20 | PIPPIN +0.48, HIPPO +0.11, M +0.10 |
| worst coins | 1000BONK −0.52, BOME −0.23, 1000WHY −0.12 | ZEREBRO −0.10, MOODENG −0.06, BAN −0.06 |

**Net by period:**
- **By year:** 2024 +1.64; 2025 H1 +0.07; 2025 H2 +0.41; 2026 Q1 +0.23.
- **By quarter, train:** 2024 Q1 +1.58, Q2 +0.31, Q3 −0.26, Q4 +0.01; 2025 Q1 −0.18, Q2 +0.25.
- **By quarter, validation:** 2025 Q3 +0.08, Q4 +0.33; 2026 Q1 +0.23.

## Diagnostics (not used for selection)
| variant | train net / PF / ex-top-3 | validation net / PF / ex-top-3 |
|---|---|---|
| Lighter cost (0 bp fee, same slippage; Binance funding as proxy) | +1.76 / 1.29 / +0.15 | +0.66 / 1.26 / +0.20 |
| slippage ×2 | +1.62 / 1.26 / +0.01 | +0.56 / 1.22 / +0.10 |
| funding excluded | +1.70 / 1.27 / +0.08 | +0.58 / 1.23 / +0.13 |
| excluding identity-doubtful coins (pre-declared) | **+0.16 / 1.03 / −0.29 (fail)** | +0.71 / 1.28 / +0.21 |
| excluding the best coin (post-hoc: 1000PEPE on train, PIPPIN on validation) | +1.17 / 1.21 / +0.005 | **+0.14 / 1.05 / −0.17 (fail)** |

The Lighter variant is informational only. Lighter lists only a subset of these memes, and its depth was not checked.

## Reading and risks
- **Costs:** the edge is not a cost artefact. It survives 2× slippage and does not depend on funding, unlike
  XS_L7_LO.
- **Concentration, the main risk:**
  - Train is carried by the small-universe 2024 meme season, when k was 2. In 2025 H1, with about 46 eligible memes
    and k of about 9, it made only +0.07.
  - Validation is 75% one coin, PIPPIN, mostly long legs in its Nov–Dec 2025 run (+0.22 in one week).
- **The direction flipped between splits.**
  - On train, the long leg (rising volume) made the money.
  - On validation, the short leg (fading volume) made it.
  - A consistent mechanism ("attention fades, so coins with fading volume underperform") is not established.
- **Multiple testing:** 1 of 12 configs passed train, just barely (+0.10 net without the top 3 legs). A single
  survivor of this size is close to what chance would produce.
- **Universe:** today's CoinGecko list is a look-ahead. The identity-doubtful coins (PEOPLE in particular) carried
  2024.
- **Next step:** if the coordinator wants it, run the holdout (2026-04-01..2026-09) once with exactly this rule:
  - Write a holdout plan with the code's sha256 first, as momentum did.
  - Report a failure in `reports/failures/`.
  - Do not tune.
