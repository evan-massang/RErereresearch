# H-PROPCARRY: long Solana meme spot (prop-AMM-routed) + 1x short perp, weekly episodes. Verdict: FAIL (validation n = 41 < 50)

Family: `sources/leads/documented_edges_round10.md` idea 1. It iterates on H-FUNDCARRY (`agent_fundcarry.md`: validation
n 6–13, spot leg 0.5%/side) and H-SPOTCARRY-WIDE (`agent_spotcarry.md`: the incidence of carry collapsed and decayed).

**Bar** (per split, primary cost case, per-episode return on capital): n ≥ 50, net > 0, PF > 1.2, net > 0 with the 3 best removed.

**Result.**
- **Train:** 2 of 12 configs pass. The selection rule picked L24_F12_Z7, and the kill test passed (margin 43.8 bp per episode).
- **Validation** (run once, Hyperliquid): **n = 41**. Net, PF and ex-top-3 are all positive, but n is below 50, so the bar
  is not met.
- **Cost stress:** at ×4 spot cost the result turns negative.
- **Binance replicate:** fails train (net negative) and gives n = 34 on validation.
- **Holdout:** never touched. It was never downloaded, and cached rows ≥ 2026-04-01 were dropped at load.

## Pre-registration
`reports/hypotheses/propcarry_preregistration.json`, frozen 2026-10-05T09:55Z. That was before any new download and before
any episode outcome was computed.
- **Disclosure:** the HL funding and CEX spot caches for these coins came from H-FUNDCARRY, which had already scored
  them at higher thresholds.

**Rules.**
- **Decision:** every Monday 00:00 UTC, enter when the trailing L-hour mean HL funding (point in time) is ≥ F.
- **Position:** buy spot and short equal units of the perp at 1x.
- **Exit:** after Z days, or on whichever of these comes first:
  - collateral stop: the perp hourly high reaches 1.6× entry;
  - basis-blowout stop: the basis widens by 3 pp or more over entry basis;
  - a data gap of more than 6 h;
  - split end.
- **Grid:** L ∈ {24, 168} h × F ∈ {12, 20, 35}%/yr × Z ∈ {7, 14} d = 12 configs.
- **Splits:** train = decisions ≤ 2025-06-30. Validation = 2025-07-01 to 2026-03-31. Holdout = 2026-04-01 onward, never touched.

## Data (7.6 MB new, under `data/raw/web/propcarry/`; free disk stayed about 4.3 GB)

| item | source | notes |
|---|---|---|
| HL hourly funding + premium | cached `data/raw/web/hyperliquid/funding_*.json` (HL `info` `fundingHistory`) | kBONK from 2023-11, PENGU and FARTCOIN from 2024-12, TRUMP from 2025-01, PUMP from 2025-07. USELESS has **no HL history before 2026-09**, so it is out of the HL venue. |
| Binance funding + 1h perp klines | `data.binance.vision` monthly archive, months ≤ 2026-03 | `binance_funding.json`, `binance_perp_1h.json`, manifest |
| Lighter hourly funding | `mainnet.zklighter.elliot.ai/api/v1/fundings` (public, paged) | History starts 2025-01/02 (BONK, TRUMP, FARTCOIN) or 2025-07/08 (PENGU, PUMP, USELESS). **Units verified** against docs.lighter.xyz/trading/funding: the floor is InterestRate 0.01%/8 h, so the API `rate` is **percent per hour** (0.0012 = 0.12 bp/h). Reading `direction` "long" as "longs pay" is an inference from the docs' sign convention. |
| Spot 1h (proxy for Solana spot) | Binance (PENGU, TRUMP), MEXC (BONK, FARTCOIN, PUMP; cached), MEXC USELESSUSDT (new) | GeckoTerminal is unusable for this test: its public history covers 180 days, which is holdout only. Binance spot does not list FARTCOIN, PUMP or USELESS (archive returns 404). |
| Jupiter quotes | `lite-api.jup.ag/swap/v1/quote`, **quotes only, no swap sent** | `research/observations/evidence_propcarry_costs.json` |

**Basis risk (not modelled).** The spot leg is a CEX hourly close. The gap between Solana DEX spot and CEX spot is not
observed historically.
- **HL venue:** the perp is spot × (1 + HL premium). Fundcarry validated this proxy (median absolute error 0.07%).
- **Binance venue:** the perp is the real Binance perp close. Its basis to CEX spot is therefore modelled.

## Costs (per episode, per unit notional)
Spot round trip comes from today's Jupiter quotes (SOL → token → SOL), in bp:

| coin | 0.5 SOL | 2 SOL | 5 SOL |
|---|---|---|---|
| PENGU | 1.9 | 1.3 | 4.1 |
| PUMP | 2.9 | 1.3 | 0.9 |
| TRUMP | 5.5 | 3.2 | 3.5 |
| BONK | 5.2 | 1.4 | 8.4 |
| FARTCOIN | 8.6 | 10.6 | 12.6 |
| USELESS | 10.6 | 7.4 | 9.3 |

- **SOL↔USDC hop:** about 0 bp measured. 2 bp is charged anyway.
- **Tips:** 1 bp.
- **Perp:** HL 4.5 bp taker + 1.7 bp half spread per side (12.4 bp round trip). Binance 5 + 1 bp per side (12 bp; the
  spread is assumed because the `fapi` REST API returns 451).
- **Stress:** the primary case is spot ×2; ×1 and ×4 are reported as sensitivities. How long these coins have been
  routed through prop AMMs is unknown. In 2024 and early 2025 the real BONK and FARTCOIN costs were probably well above
  ×4 (fundcarry charged 50 bp/side).

## Train (HL, 12 configs, primary ×2) — `research/observations/evidence_propcarry_train.json`

| config | n | net | PF | ex top 3 | net ×1 | net ×4 | passes |
|---|---|---|---|---|---|---|---|
| **L24_F12_Z7** (selected) | 55 | +0.082 | 2.59 | +0.054 | +0.107 | +0.031 | yes |
| L24_F12_Z14 | 36 | +0.121 | 3.64 | +0.077 | +0.138 | +0.088 | no (n) |
| L24_F20_Z7 | 41 | +0.072 | 2.54 | +0.044 | +0.091 | +0.034 | no (n) |
| L24_F20_Z14 | 29 | +0.098 | 2.97 | +0.048 | +0.111 | +0.071 | no (n) |
| L24_F35_Z7 | 27 | +0.060 | 2.35 | +0.033 | +0.073 | +0.036 | no (n) |
| L24_F35_Z14 | 18 | +0.074 | 2.48 | +0.024 | +0.082 | +0.057 | no (n) |
| L168_F12_Z7 | 73 | −0.010 | 0.93 | −0.038 | +0.024 | −0.078 | no |
| L168_F12_Z14 | 43 | +0.029 | 1.20 | −0.015 | +0.049 | −0.010 | no |
| L168_F20_Z7 | 56 | +0.029 | 1.27 | +0.001 | +0.055 | −0.023 | yes (barely) |
| L168_F20_Z14 | 34 | +0.068 | 1.68 | +0.024 | +0.084 | +0.037 | no (n) |
| L168_F35_Z7 | 34 | +0.010 | 1.11 | −0.016 | +0.026 | −0.021 | no |
| L168_F35_Z14 | 22 | +0.036 | 1.38 | −0.010 | +0.046 | +0.016 | no |

**L24_F12_Z7 on train.**
- Mean +14.9 bp per weekly episode on capital.
- Per unit notional: funding 77.6 bp, cost 33.8 bp, basis −14 bp.
- **Kill test:** funding minus cost = 43.8 bp, above the 5 bp threshold, so it passed.

**By year:**

| year | n | net |
|---|---|---|
| 2023 | 1 | +0.009 |
| 2024 | 31 | +0.051 |
| 2025 H1 | 23 | +0.022 |

**By quarter:** 2024Q1 is +0.064 (n 12), 78% of the whole-train net of +0.082. 2024Q4 is −0.023: the BONK squeeze collateral
stop of 2024-11-13 cost −0.043.

**Coins:** BONK 36, FARTCOIN 15, PENGU 3, TRUMP 1.

## Validation (run once, L24_F12_Z7) — `research/observations/evidence_propcarry_validation.json`

| venue | cost | n | net | PF | ex top 3 | mean bp/ep | funding (unit) | basis (unit) | cost (unit) |
|---|---|---|---|---|---|---|---|---|---|
| **HL** | **×2** | **41** | **+0.028** | **3.01** | **+0.014** | **+6.8** | +0.169 | +0.012 | 0.125 |
| HL | ×1 | 41 | +0.043 | 5.89 | +0.028 | +10.5 | | | |
| HL | ×4 | 41 | −0.003 | 0.90 | −0.015 | −0.8 | | | |
| Binance | ×2 | 34 | +0.010 | 2.26 | +0.001 | +3.0 | +0.124 | +0.007 | 0.111 |
| Binance | ×4 | 34 | −0.020 | 0.34 | −0.028 | −5.8 | | | |

**HL ×2 by quarter:**

| quarter | n | net |
|---|---|---|
| 2025Q3 | 29 | +0.037 |
| 2025Q4 | 9 | −0.010 |
| 2026Q1 | 3 | +0.0005 |

**By year:** 2025 is n 38, +0.027. 2026 is n 3, +0.0005.

**Coins:** FARTCOIN 17, PUMP 8, PENGU 7, BONK 6, TRUMP 3.

**Worst episodes:** all are the 2025-10-06 crash week, at −0.45% or better: TRUMP (negative funding), FARTCOIN and PUMP.

**Binance train replicate** (`evidence_propcarry_binance_train.json`, ×2): n 26, net −0.045, PF 0.48.
- 4 collateral stops cost −0.074, driven by BONK in 2024-11 and FARTCOIN in 2025-03.
- The stop fill is the pre-registered conservative one: spot sells at the bar close while the perp is bought back at
  1.6× entry. This creates basis losses that an execution of both legs at the same moment would mostly avoid. The fill
  rule was not changed.

## Lighter (descriptive only) — `evidence_propcarry_lighter_funding.json`

| | hours at the 0.12 bp/h floor | mean funding | HL mean, same hours | Binance mean |
|---|---|---|---|---|
| PENGU | 70% | 6.1%/yr | 1.2%/yr | |
| BONK | 76% | 8.0%/yr | 5.2%/yr | |
| PUMP | 66% | 19.8%/yr | 15.1%/yr | |
| FARTCOIN | 73% | 18.6%/yr | 17.6%/yr | |
| USELESS | 55% | 34.9%/yr | HL not listed | 18.5%/yr |
| TRUMP | 37% | −20.2%/yr | −17.5%/yr | −18.5%/yr |

Validation-period figures.
- Lighter pays shorts somewhat more than HL, with zero fees, which would save about 9 bp of the 12.4 bp perp cost per
  episode.
- That was not scored as a venue: there is no Lighter price history in this test, and n would still be about 41.

## Interpretation
- **The carry exists and is positive after today's quote-implied costs.** At ×2 it is about 7 bp per weekly episode on
  capital in validation, about 3.5%/yr while invested.
  - It is thin: ×4 spot cost erases it on both venues.
  - 2025Q3 alone (+0.037) exceeds the validation total (+0.028); 2025Q4–2026Q1 is net negative.
- **Incidence fell again.** Of eligible coin-Mondays, 37% qualified in train (55 of 148) but 22% in validation
  (41 of 190): 29 in 2025Q3, 9 in 2025Q4 and 3 in 2026Q1.
  - Funding sat at the floor about 66–76% of hours on Lighter in validation.
  - This is the same decay that killed SPOTCARRY. "Weekly episodes make n a function of time" fails because the
    threshold filter removes most weeks.
- **It needs more than six coins.** Reaching n ≥ 50 on validation would take more coins, which reopens the cost problem
  (WIF, POPCAT, SPX and MOODENG quote 40–60 bp round trips). Any such change would have to be pre-registered as a new
  iteration.
- **Train is a regime artefact again.** 2024Q1 BONK does most of the work, and the universe is chosen on 2026 routing
  (look-ahead in universe choice).

## Caveats
- Costs are quotes, not fills. Quote fade and minimum sizes are unverified, and historical prop-AMM costs are unknown.
- The spot leg is a CEX proxy, and the DEX–CEX basis is not modelled.
- HL perp prices are a premium-based proxy, so intrabar stops use spot high × (1 + premium).
- Funding paid into margin is not compounded. Capital opportunity cost is not charged.
- Train overlaps data that H-FUNDCARRY had already examined.

**Do not run the holdout:** no config passed validation.

## Files
- `reports/hypotheses/propcarry_preregistration.json`
- `scripts/research/propcarry_fetch.py`: the Jupiter (quotes only), Binance archive (≤ 2026-03) and USELESS MEXC fetches, with a disk guard below 2.5 GB
- `scripts/research/propcarry_lighter.py`: the Lighter funding history fetch
- `scripts/research/propcarry_sim.py`: `train | validation KEY | binance_train KEY | lighter`
- `research/observations/evidence_propcarry_{train,validation,binance_train,lighter_funding,costs}.json`
- `data/raw/web/propcarry/`: raw caches
