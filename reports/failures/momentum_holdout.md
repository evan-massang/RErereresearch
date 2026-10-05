# XS_L7_LO holdout: FAIL

_Agent: momentum, 2026-10-05. Rule frozen in `reports/candidates/momentum.md`.
Plan with code sha256 values, written before the run: `reports/hypotheses/momentum_holdout_plan.json`.
Script: `scripts/research/momentum_holdout.py` (run once). Evidence: `research/observations/evidence_momentum_holdout.json`._

**Holdout window:** rebalances from 2026-04-06 to 2026-09-21 (25 weeks), with positions closed at 2026-09-28 00:00 UTC.
- The window ends there because that is the last week fully covered by the archive.
- Daily klines reach 2026-10-03, and fundingRate exists only as monthly files, through 2026-09.

**Data:** data.binance.vision monthly klines and funding for 2026-04 to 2026-09; 874 of the 901 listed symbols were fetched.

| | n | net | PF | net without top 3 | pass |
|---|---|---|---|---|---|
| XS_L7_LO (frozen) | 163 | +0.168 | 1.085 | **−0.619** | **no** (fails on PF and on net without the top 3) |
| funding excluded | 163 | −0.267 | 0.882 | −1.049 | no |
| settlement episodes excluded | 163 (none occurred) | +0.168 | 1.085 | −0.619 | no |
| equal-weight long benchmark, same universe and costs | 144 | +0.282 | 1.51 | +0.016 | (benchmark) |

**Other statistics:**
- Sharpe 0.35; max drawdown −0.47 additive, −41% compounded.
- Turnover 1.59 per week; costs 0.05.
- Price P&L was **−0.22**. Funding received was +0.44.
- The net of +0.17 depends entirely on funding received, and 3 coins (AKE, VELVET, LAB) account for 6 times the total net.

**By month:**

| Apr | May | Jun | Jul | Aug | Sep |
|---|---|---|---|---|---|
| −0.06 | −0.06 | +0.38 | −0.09 | −0.20 | +0.20 |

**Reading:** the validation-period caveats played out. In the holdout:
- the price component of the momentum tilt lost money;
- the strategy did worse than simply holding the universe equal-weight;
- what remained was funding collected on squeezed coins, concentrated in a few names.

No parameter will be changed. A forward paper test of the same frozen rule is set up, so the call can rest on fresh data rather than this one window: `reports/paper/momentum_xs_l7_lo.json`.
