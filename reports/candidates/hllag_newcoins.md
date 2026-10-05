# H-HLLAG on new coins: cross-sectional out-of-sample test (agent, 2026-10-05)

**Verdict: PASSES the pre-registered bar on train and on validation, pooled over the new coins.
But only 2 new coins (TRUMP, SPX) could be tested, and the result depends on ~300 ms latency
exactly as on the development coins. This supports adding TRUMP and SPX to the forward paper test;
it is not a validated edge.** The holdout (2026-04-01 onward) was not downloaded.

Pre-registration: `reports/hypotheses/hllag_newcoins_preregistration.json`, written before any download
of test data. The rule is the frozen `hlanchor_lib.sim_lag` (sha256 `98166e5f…c3ad`, unchanged):
θ = 40 bp, L = 300 ms, H = 30 s, cooldown 10 s, no gap-close exit, info latency 300 ms,
4.5 bp taker fee per side, $1k units. No parameters were changed.

## Coin selection (mechanical, set before results)
- **Candidates.** 17 Hyperliquid meme perps with a Binance USDT-M perp, minus the 4 development coins.
- **Liquidity rule.** HL 24h notional volume ≥ $1M at the 2026-10-05 05:37Z snapshot. Seven passed, in rank
  order: DOGE, kPEPE, TRUMP, USELESS, PENGU, SPX, kSHIB.
- **Size gate.** A coin was excluded if its Binance `book_ticker` file for 2025-10-01 was over 60 MB.
  - DOGE: 103.8 MB, excluded.
  - kPEPE: 68.8 MB, excluded.
- **Download budget.** The cap was 1.45 GB, with coins processed in rank order.
  - PENGU was cut. Its expected size was 820 MB.
  - kSHIB was cut. Its expected size was 393 MB, against 277 MB remaining.
- **No data.** USELESS returned HTTP 400 from Tardis for HL `quotes` on all 17 days, so it was not tested.
- **Tested coins.** TRUMP and SPX, both listed from 2025-02-01.
- **Total downloaded.** ≈1.16 GB, including 0.12 GB of sizing probes. Free disk stayed at about 4.0–4.2 GB.

## Results (bar: n ≥ 50, net > 0, PF > 1.2, net ex top-3 > 0; mean in bp per $1k round trip)

| split | coin-days | n | net $ | mean bp | PF | net ex top-3 | days + | pass |
|---|---|---|---|---|---|---|---|---|
| train (2025-02..06) | 10 | 329 | +286.4 | +8.7 | 1.74 | +231.6 | 5/5 | **yes** |
| validation (2025-07..2026-03) | 18 | 243 | +136.4 | +5.6 | 1.39 | +63.9 | 6/9 | **yes** |

Per coin, which is not the test:

| coin | split | n | net $ | PF | net ex top-3 |
|---|---|---|---|---|---|
| TRUMP | train | 151 | +238.8 | 2.37 | +183.9 |
| SPX | train | 178 | +47.7 | 1.22 | +15.2 |
| TRUMP | valid | 47 | +65.6 | 2.17 | +9.1 |
| SPX | valid | 196 | +70.8 | 1.24 | +17.4 |

Robustness (informational only):

| variant | train n / net / PF | valid n / net / PF |
|---|---|---|
| +0.5 bp cost | 329 / +270.0 / 1.68 | 243 / +124.3 / 1.35 |
| L = 800 ms | 329 / −189.0 / 0.69 | 243 / −218.1 / 0.57 |
| without the best coin-day | 240 / +118.3 / 1.43 (drops TRUMP 2025-02-01) | 211 / +87.8 / 1.28 (drops SPX 2025-10-01) |

Mean entry markout before fees was +13.4/+17.9/+20.2 bp at 1/5/30 s on train and +12.2/+17.7/+19.1 bp on
validation. The development coins showed a similar profile.

## Skeptical reading
- **Few coins.** Only 2 coins were tested, so this is a weak cross-sectional check. Four of the seven
  liquid coins were dropped for size, budget or missing data, and none of those reasons depend on the results.
- **Latency.** The edge disappears at 800 ms on both coins and both splits, as it does on the development
  coins. Every result here depends on end-to-end latency of about 300 ms.
- **Concentration.**
  - Train: TRUMP on 2025-02-01, about two weeks after its launch, gives +$168 of the +$286.
  - Validation: net ex top-3 is only +$64. TRUMP alone has 47 trades in validation, which is below 50.
- **Possible decay.** Validation per-day net was +44, +47, +5, +49, +50, then −8, +13, −33 and −30. The last
  four months (2025-12 to 2026-03) sum to −$58. That is too few trades to call it decay, but the forward
  test should watch for it.
- **Fill model.** The fill-model limits from `reports/candidates/hlanchor.md` still apply: 0.5-s HL
  snapshots, no depth data, and no queue model.

## Next step
Add TRUMP and SPX to the forward paper test, pre-declared before scoring, under the same frozen
parameters. Score them with the dev coins pooled and also on their own. To finish this cross-section, test
PENGU and kSHIB under the same pre-registration if disk allows.

## Files
- `reports/hypotheses/hllag_newcoins_preregistration.json`
- `scripts/research/hllag_newcoins.py`
- `research/observations/evidence_hllag_newcoins_20261005.json`
- Per-trade results, fetch log and HL volume snapshot: `data/raw/web/tardis/results/newcoins/` (gitignored)

## Addendum: PENGU, kSHIB, DOGE and kPEPE (agent, 2026-10-05)

**Result.**
- The primary addendum test is PENGU and kSHIB pooled. It **passes on train and on validation**.
- DOGE and kPEPE pooled **fails**.
- On its own, only **PENGU** passes both splits, and only narrowly.
- kSHIB, DOGE and kPEPE each fail on their own.
- Every coin loses money at L = 800 ms.

**Pre-registration.** `reports/hypotheses/hllag_newcoins_addendum.json` was saved at 06:02:23Z, before
any result for these coins was computed. The first result file was written at 06:04:11Z.
- **Known in advance.** The TRUMP and SPX results above were already known, and the addendum says so.
- **Unchanged.** The frozen rule (`hlanchor_lib` sha256 asserted), the params, the days and the bar.
- **Declared deviations.** These change only which coins are tested:
  - The 1.45 GB budget was lifted for PENGU and kSHIB.
  - The 60 MB size gate was lifted for DOGE and kPEPE.
- **Disk handling.** Data was processed one coin-day at a time. Each raw csv.gz was read in 2M-row
  chunks, with the dedup carried across chunk boundaries. This gives output identical to
  `hllag_newcoins.extract`, which was checked on a synthetic file. Raw files were deleted after each day.
  - Downloaded: 4.66 GB.
  - Lowest free disk: 3.27 GB, above the 2.5 GB limit.
  - 66 coin-days were processed.
  - PENGU has no Tardis HL quotes before 2025-01-01 (HTTP 400), so it is missing 2 train days.
- **Script.** `scripts/research/hllag_newcoins_addendum.py`

Columns are n / net $ / PF / net ex top-3. A split passes only if n ≥ 50, net > 0, PF > 1.2 and
net ex top-3 > 0.

| coin or group | train | pass | validation | pass | both |
|---|---|---|---|---|---|
| PENGU | 155 / +62.8 / 1.30 / +28.3 | yes | 83 / +34.7 / 1.39 / +14.9 | yes | **yes** |
| kSHIB | 63 / +23.5 / 1.31 / −7.7 | no | 7 / +3.2 / 1.77 / −4.0 | no | no |
| DOGE | 7 / −15.2 / 0.00 / −13.7 | no | 15 / +9.0 / 1.40 / −13.2 | no | no |
| kPEPE | 36 / +56.7 / 4.40 / +36.4 | no (n) | 25 / −13.5 / 0.68 / −28.9 | no | no |
| **A: PENGU+kSHIB (primary)** | 218 / +86.3 / 1.30 / +50.6 | **yes** | 90 / +37.9 / 1.40 / +18.2 | **yes** | **yes** |
| B: DOGE+kPEPE | 43 / +41.5 / 2.31 / +21.3 | no (n) | 40 / −4.5 / 0.93 / −27.3 | no | no |
| All 6 new coins (informational) | 590 / +414.3 / 1.59 / +359.5 | yes | 373 / +169.9 / 1.33 / +97.4 | yes | yes |

Robustness (informational only), shown as n / net $ / PF:

| coin or group | +0.5 bp, train | +0.5 bp, validation | L = 800 ms, train | L = 800 ms, validation |
|---|---|---|---|---|
| PENGU | 155 / +55.1 / 1.26 | 83 / +30.5 / 1.33 | 155 / −132.4 / 0.53 | 83 / −131.3 / 0.27 |
| kSHIB | 63 / +20.4 / 1.26 | 7 / +2.9 / 1.66 | 63 / −6.9 / 0.92 | 7 / −5.5 / 0.46 |
| DOGE | 7 / −15.5 / 0.00 | 15 / +8.3 / 1.36 | 7 / −15.7 / 0.01 | 15 / −8.8 / 0.68 |
| kPEPE | 36 / +54.9 / 4.19 | 25 / −14.8 / 0.66 | 36 / +6.8 / 1.20 | 25 / −31.6 / 0.41 |
| A: PENGU+kSHIB | 218 / +75.4 / 1.26 | 90 / +33.4 / 1.35 | 218 / −139.2 / 0.63 | 90 / −136.8 / 0.28 |
| B: DOGE+kPEPE | 43 / +39.4 / 2.20 | 40 / −6.5 / 0.90 | 43 / −8.9 / 0.82 | 40 / −40.5 / 0.51 |
| All 6 | 590 / +384.8 / 1.54 | 373 / +151.2 / 1.29 | 590 / −337.1 / 0.67 | 373 / −395.4 / 0.49 |

### Skeptical reading
- **PENGU's pass is thin.**
  - Mean is about +4 bp per round trip, against the 9 bp of fees it pays.
  - Without its best coin-day, train drops to PF 1.16 with +$0.3 ex top-3.
  - Without its best coin-day, validation has ex top-3 of −$0.4.
  - Two of 6 train days and 2 of 7 validation days with trades lost money.
- **Group A rests on PENGU.**
  - kSHIB adds 63 train trades but only 7 validation trades.
  - Most of kSHIB's train net comes from one day, 2024-12-01 (+$22.4 of +$23.5).
- **The rule rarely fires on DOGE and kPEPE.** They are the most liquid coins and their HL books follow
  Binance closely. The 40 bp signal fired 7–36 times per split.
  - DOGE lost money on train, and its validation net comes from one day, 2026-01-01 (+$21.8).
  - kPEPE's train result is concentrated in 2024-12 and 2025-01. Its validation net is negative.
- **Latency.** At 800 ms every coin and group loses, except kPEPE train at +$6.8 with PF 1.20. This
  matches the parent test and the development coins.
- **Recent months are weak.** Across the addendum coins, 2025-12 to 2026-03 is mostly flat or negative
  (DOGE 2026-01 is the exception). This fits the decay noted above for TRUMP and SPX.
- **Selection.** The addendum was decided with the TRUMP and SPX pass already known. The rule, days and
  bar did not change, but choosing to extend the test was not blind.

### Next step
PENGU can join TRUMP and SPX as a candidate for the forward paper test, but only as a marginal one.
kSHIB, DOGE and kPEPE should not be added on this evidence. The 300 ms latency dependence is still the
main thing to verify live.

Evidence: `research/observations/evidence_hllag_newcoins_addendum_20261005.json`. Failures:
`reports/failures/agent_hllag_newcoins_addendum.md`.
