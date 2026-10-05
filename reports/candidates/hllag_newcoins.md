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
