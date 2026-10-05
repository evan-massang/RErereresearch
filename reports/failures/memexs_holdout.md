# H-MEMEXS VOLG_high_long_LS holdout: FAIL

_Agent: memexs, 2026-10-05. The rule was frozen in `reports/candidates/memexs.md`. A plan with the code's sha256 was
written before the run: `reports/hypotheses/memexs_holdout_plan.json`. Script: `scripts/research/memexs_holdout.py`,
run once. Evidence: `research/observations/evidence_memexs_holdout.json`. Leg and weekly parquet:
`data/raw/web/memexs/{legs,weekly}_holdout_VOLG_high_long_LS.parquet`._

**Window**
- Rebalances 2026-04-06 to 2026-09-21: 25 weeks, all traded. Positions closed at 2026-09-28 00:00 UTC.
- It ends there because fundingRate exists only as monthly files, published through 2026-09.

**Data**
- Downloaded: data.binance.vision monthly 1d klines and fundingRate for 2026-04..2026-09, for the 74 frozen meme
  symbols (2.1 MB, in `data/raw/web/memexs/holdout/`).
- History before April came from the read-only momentum cache.

**Universe:** the frozen 74-symbol CoinGecko meme-token list, with no additions. On average 31.6 memes were eligible
each week.

| | legs | net | PF | net ex top-3 | weekly Sharpe | pass |
|---|---|---|---|---|---|---|
| **VOLG_high_long_LS (frozen)** | 296 | **−0.327** | **0.865** | **−0.717** | −0.85 | **no** (fails net, PF and ex-top-3) |
| pre-declared diagnostic: identity-doubtful coins excluded | 256 | −0.732 | 0.706 | −1.116 | −1.96 | no |

**Other statistics:**
- 25 independent weeks, mean −131 bp a week, mean −11 bp per leg.
- Max drawdown −0.68 additive.
- Price P&L −0.28; funding received +0.03; costs 0.07; turnover 1.22 a week.
- **The legs split by side:**
  - Long legs (rising volume) made **+0.34**.
  - Short legs (fading volume) lost **−0.67**.
  - The short side, which carried validation, reversed.

**By month:**

| Apr | May | Jun | Jul | Aug | Sep |
|---|---|---|---|---|---|
| +0.29 | +0.01 | −0.22 | +0.11 | −0.42 | −0.09 |

**Concentration:** 50 coins were traded.
- **Best:** 币安人生 +0.25, B +0.10, M +0.08. Two of these three (B and M) are identity-doubtful members.
- **Worst:** SIREN −0.20, BULLA −0.18, 龙虾 −0.12, MUBARAK −0.07, PIPPIN −0.05.
- **Single worst leg:** a BULLA short squeezed +31% in the week of 2026-08-31.

**Reading**
- The validation pass did not carry over: it was 75% PIPPIN, and train was the small-universe 2024 season.
- With the doubtful coins removed, the holdout is worse (−0.73). So the core-meme cross-section has no
  volume-growth spread at this horizon, after costs.
- This matches the earlier findings:
  - weekly momentum and reversal among memes failed on train;
  - broad-perp XS_L7_LO failed its holdout.

**What happens next**
- Nothing is changed. The rule is not tuned.
- A forward paper test of the same frozen rule runs anyway (`scripts/research/memexs_forward.py`,
  `reports/paper/memexs_volg.json`). Its purpose is to record fresh-data evidence; it is not a rescue.
