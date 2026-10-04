# Crash-bounce (capitulation rebound) on the bonding curve (agent crash_bounce, 2026-10-04): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## Hypothesis

Mechanical dumps (creator or launch-sniper exits, or cascades) overshoot, and the token's remaining organic demand produces a bounce. The bot buys **into** the crash, 1 s after the crash print and before any recovery. This differs from H3/H5 (the first creator sell within 20 s of launch) and from the `absorb` trigger in `agent_curve_flow.md`, which waits for a recovery above the pre-sell price.

## Rule (fixed before any outcome was computed)

`scripts/research/crash_bounce_build.py`. Every condition uses only trades received at or before the decision time.

**Crash.** A sell print whose price is at most (1 − D) times the highest print over the preceding W seconds.

**Gating:**
- at least 15 distinct non-creator buyers so far;
- token age at least 30 s;
- token not yet completed.

The trigger fires once per token and variant, on the first qualifying print.

| variant | D | W | extra condition |
|---|---|---|---|
| d40_w30 | 40% | 30 s | none |
| d60_w30 | 60% | 30 s | none |
| d40_w10 | 40% | 10 s | a fast crash: one big sell or a tight cascade |
| d40_w30_mech | 40% | 30 s | the largest seller (by SOL) between the window high and the crash print is the creator or a launch-block sniper (bought in slot ≤ create slot + 1) |
| d40_w30_dem | 40% | 30 s | at least 2 distinct non-creator buyers in the next 5 s; the decision moves to crash + 5 s |

**Exits:** take-profit/stop-loss pairs of 20/30, 30/15, 50/30 and 100/50%, each with a 60 s or 300 s maximum hold.

**Grid:** 5 variants × 8 exits = **40 configs**.

**Fills:** `event_studies.outcomes()` / `rt()`, which gives:
- exact constant-product fills;
- 0.5 SOL per trade;
- 1.25% fee per side;
- 1 s latency;
- completion handling.

**Tips:** 0.001 and 0.01 SOL per transaction (two transactions per trade).

**Data hygiene:**
- **Gaps:** the token's creation, the decision and the full 300 s window plus latency must lie in one recording segment with no gap over 60 s; 285 triggers were dropped for this.
- **Holdout:** never read.
- **Trade cut-offs:** Oct 1 tokens are capped at 19:15 UTC and Oct 2 tokens at Oct 3 00:00.

## A data-validity fix, applied before the final train run

The first train run (`evidence_crash_bounce_train_nokfilter_20261004.json`) showed a group of crashes "below the curve floor", at market caps of 0.03–30 SOL, losing 0.20 SOL per trade.

**Cause.** About 19% of tokens (4,044 of 21,055 on Oct 1) have curve states in which k = vsol·vtok is not constant. `vtok` chains correctly from trade to trade, but `vsol` jumps; for example, a 0.0245 SOL sell takes vsol from 22.7 to 10.3. Exact constant-product fills are not computable on such states.

**Rule added.** A token is eligible only while vsol·vtok has stayed within 1% of its first print (`K_TOL`). This is a point-in-time check a live bot can run, and it was not chosen on outcomes. With the rule in place, every event also keeps k valid through its outcome window.

**Note for other studies.** Other studies that use `rt()` on such tokens may have the same problem. The recorder's decoding of these curves is worth checking: they might be a different curve type.

## Result: FAIL on train, so validation (Oct 3) was not looked at

`research/observations/evidence_crash_bounce_train_20261004.json`, tip 0.001 SOL. All 40 configs have a negative mean, PF ≤ 0.44, and are negative on Oct 1 and on Oct 2 separately.

| variant | trades | best exit | SOL per trade | PF | without best 3 | win % |
|---|---|---|---|---|---|---|
| d40_w30_dem | 1,210 | TP20/SL30, 60 s | −0.040 | 0.44 | −50.1 | 32.5 |
| d40_w30_mech | 1,128 | TP30/SL15, 60 s | −0.042 | 0.25 | −50.1 | 10.0 |
| d60_w30 | 944 | TP30/SL15, 60 s | −0.042 | 0.30 | −42.9 | 12.4 |
| d40_w10 | 1,347 | TP30/SL15, 60 s | −0.044 | 0.34 | −64.0 | 15.4 |
| d40_w30 | 2,405 | TP30/SL15, 60 s | −0.044 | 0.31 | −110.1 | 14.8 |

**Best config:** d40_w30_dem with a TP20/SL30, 60 s exit.
- At a 0.001 SOL tip: 1,210 trades, −48.9 SOL in total (−0.040 per trade), PF 0.44, −50.1 SOL without the best 3.
- At a 0.01 SOL tip: −0.058 SOL per trade.

## Why: there is no bounce, the crash continues

`evidence_crash_bounce_train_diag_20261004.json` (d40_w30, 600 sampled train events):
- **Median price relative to the crash print:**

  | after | +1 s (entry) | +5 s | +30 s | +60 s | +300 s |
  |---|---|---|---|---|---|
  | median price | 0.993 | 0.974 | 0.919 | 0.900 | 0.818 |

- **Share of events above the crash print:** 15–22% at every horizon up to 60 s, and 10% at 300 s.
- **Largest gain from entry within 300 s:** the median is 0%; the 75th percentile is +15% and the 90th +54%.
- **Mean gross PnL before tips:** −0.038 to −0.063 SOL per trade. The immediate round-trip cost alone is −0.027, so the price drift after entry is negative even before costs.
- **Creator vs sniper as the top seller:** −0.044 vs −0.040 SOL per trade. "Mechanical" selling does not mean the dump overshoots.
- **Continued non-creator buying in the next 5 s:** this lifts the win rate from 15% to 33%, but the mean is not better than the base.
- **Splits by market cap or age:** no bucket is near zero; the best is the near-floor bucket at −0.024.

A 40–70% crash within seconds on the curve is information. Remaining holders follow the dumper out, and too little demand is left to lift the price by the 2.5%+ that fees need.
