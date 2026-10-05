# Candidate (conditional): delta-hedged PumpSwap PUMP/USDC LP, Lighter short, 5% band, 1 h check (H-LPHEDGE-2)

_Agent: lphedge, 2026-10-05. Pre-registration: `reports/hypotheses/lphedge2_preregistration.json`, written before the
validation window was examined. Its two amendments are crash fixes. Neither showed an outcome, and neither changed the
config or a rule. Parent: H-LPHEDGE (`reports/failures/agent_lphedge.md`), which failed train on n under a wrong coverage rule.
Scripts: `scripts/research/lphedge2_coverage.py` and `scripts/research/lphedge2_sim.py`. The second imports
`scripts/research/lphedge_sim.py`.
Evidence:
- `research/observations/evidence_lphedge2_coverage.json`
- `research/observations/evidence_lphedge2_validation.json`
- `research/observations/evidence_lphedge_fees.json`
- `research/observations/evidence_lphedge_train.json`

No trading. Public data only._

> **Update 2026-10-05 (post-hoc, informational, not the bar): honest capital top-ups break the pass.** The frozen rule
> restores the short's 1x collateral each day without modelling where the money comes from. Moving it out of the LP
> (and selling the withdrawn PUMP half at 30 bp) gives net **+$9.88**, PF **1.10**, net ex top-3 **−$47.55** on the
> same 72 validation days. That **would fail** the bar. See `reports/paper/lphedge2_addendum.json`.
> Frozen forward paper track: `reports/paper/lphedge2.json` (frozen 2026-10-05T12:28:49Z). Score it with
> `python scripts/research/lphedge2_forward.py score`. It reaches n = 50 on about 2026-11-24.

**Verdict: PASS on the single validation run** (2026-07-25 to 2026-10-05, 72 days, never examined before).

| n pool-days | net $ (after setup) | PF | net ex top-3 $ | mean bp/day of LP value | win days | hedge trades | liquidations |
|---|---|---|---|---|---|---|---|
| 72 (0 unscored) | **+175.65** | **1.57** | **+93.66** | +3.15 | 44/72 | 25 | 0 |

It passes the letter of the bar: n ≥ 50, net > 0, PF > 1.2 and net ex top-3 > 0. **Read it as a weak, regime-dependent lead, not an edge.** The caveats are below.

## How this iteration was set up
1. **Coverage check, before any new outcome.**
   - **Sample:** 25 train days in May–June (11 full days), 2,116 bars. Pool signatures were paged back from LP events.
   - **Result:** 345 of 347 bars missing from GeckoTerminal had no transaction that moved a pool vault.
   - **The two exceptions:** one is an LP withdrawal. The other is a single transaction that was not identified, so at most one swap was missed.
   - **Present bars:** every bar GeckoTerminal does show has successful pool transactions (median 30).
   - **Conclusion:** a missing bar means zero volume. The rule is now: a missing bar is zero volume and the price is carried forward. A day is scored if Lighter has ≥ 90/96 candles and the pool has ≥ 1 bar.
2. **One config, fixed in advance:** PUMP/USDC only, 5% band, 1 h check.
   - This is the a-priori neutral central case.
   - It is **not** the best post-hoc config. Iteration 1's train had already been seen. In its all-days train diagnostic, this config did *not* pass (+$52.04, PF 1.17, ex-top-3 −$7.05), and P1 b10 60m was best.
3. **Margin model:** a 1x Lighter short. Collateral is reset to 1x notional at 00:00 UTC each day.
   - **Liquidation:** if equity at the 15m candle high falls below the 6% maintenance margin (Lighter orderBookDetails), all remaining collateral is lost.
   - **Result:** no liquidation occurred.

## Components (validation, $ and mean bp/day of day-start LP value)
| component | $ | bp/day |
|---|---|---|
| LP fee share (25 bp × GeckoTerminal volume × our share) | +395.42 | +7.54 |
| funding received on the short | +94.17 | +1.80 |
| LVR: LP value change + hedge marked at pool prices | −290.91 | −5.93 |
| basis: hedge at Lighter prices minus at pool prices | +2.44 | −0.10 |
| hedge spread (half of the 3.75 bp round trip) | −0.95 | −0.02 |
| gas (2 tx/day) | −6.83 | −0.14 |
| liquidation losses | 0 | 0 |
| setup (pool buy/sell of the token half, short open/close) | −17.70 | — |

- **Pool:** median TVL $21.2M. Volume/TVL averaged 0.30 a day, against 0.12 on train (all-days).
- **Our share:** $5k is about 0.02% of the pool.
- **Basis:** the pool-vs-perp basis averaged +4.8 bp. Its drift was negligible in P&L.

## Caveats (read before acting)
- **Thin and regime-dependent.**
  - Fees beat LVR here because volume/TVL was high: 0.30 a day, against about 0.12–0.20 on train.
  - By thirds of the validation window, P&L was −$16, +$82 and +$128.
  - On train under the same config the result was +$52, which does not pass. The edge is fee income minus LVR, and it scales with volume, which is not under our control.
- **PUMP rose about 3.4× in the validation window.**
  - The LP gained $4,428 and the short lost $4,717.
  - Keeping 1x collateral needs about **$4.6k of top-ups**, financed by removing LP value. That transfer cost is inside the gas allowance, but the size reduction from it is not modelled.
  - **Return on capital:** about **+2.3% in 72 days on the initial $7.5k** (≈ 12%/yr), or about **+1.5% (≈ 7%/yr) on peak capital** (≈ $12.1k).
- **Fee model:** checked forward against exact on-chain fee growth (ratio 1.03 over 1.5 h on Oct 5). That is short; the full 24 h forward-train segment of pumplean is still to come.
- **Not modelled:** hedge price impact above the measured $1k depth (the median rebalance is about $100–250), fee compounding, Lighter downtime and venue risk. Lighter funding direction is inferred from its docs.
- **Selection history:** the config was chosen without using train P&L, but this is the second iteration of the idea. The coverage rule was corrected after iteration 1's train had been seen; the reason is documented and was checked on-chain.

## Next step (not done here)
A forward paper track of the frozen rule on pumplean plus Lighter. The 24 h train and validation segments give 1 pool-day each, so this is a fee-accounting confirmation and a running tally, not a pass/fail test. A longer forward window (≥ 50 pool-days) is needed before any real capital.
