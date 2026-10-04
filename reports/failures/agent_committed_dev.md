# Committed dev (agent committed_dev, 2026-10-04): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## Hypothesis

A creator who buys a meaningful amount at launch and has not sold anything by token age T, while organic buyers arrive, is more often running a real project. Holding signals confidence. This had not been tested before:
- H3/H5 bought right after the creator dumps, the opposite trigger;
- H7 bought good devs at launch;
- H1/H2 used activity thresholds without a dev condition;
- the gradient-boosted model had dev_in/dev_out as features, but not this explicit rule.

## Method

The rules were fixed before any outcome was computed (`scripts/research/committed_dev_build.py`, `scripts/research/committed_dev_eval.py`).

**Decision.** The decision is made at exactly creation + T, using only trades received at or before that time. The trigger fires when:
- the creator's launch buy (slot ≤ create slot + 1) is at least D SOL;
- the creator has made **no** sell by then;
- at least B distinct organic buyers have bought (not the creator, not launch-block buyers);
- the token has not completed.

| variant | D | B | extra filters |
|---|---|---|---|
| A | 1 SOL | 10 | none |
| B | 1 SOL | 20 | none |
| C | 1 SOL | 10 | creator has 0 prior launches in allowed recorded data; not Mayhem Mode (PumpPortal `is_mayhem_mode`) |
| D | 2 SOL | 10 | as C, plus ≤ 3 launch-block non-creator buyers |

**Ages and exits.**
- T = 60, 120 or 300 s.
- Three exits:
  - TP50/SL20, 300 s maximum hold;
  - TP100/SL30, 1800 s maximum hold;
  - "devx": TP200/SL50, 1800 s maximum hold, or exit 1 s after the creator's first sell.

**Grid:** 4 × 3 × 3 = **36 configs**.

**Fills.** The `event_studies.rt()` constant-product model:
- 0.5 SOL per trade;
- 1.25% fee per side;
- entry 1 s after the decision;
- exit fills 1 s after the exit signal;
- completion cut.

**Data hygiene.**
- The price path uses only clean states (|vsol − rsol − 30| < 0.01), and the entry state must be clean.
- The window from token creation to trigger + 1801 s must lie in one gap-free recording segment (no gap over 60 s) and inside its split.
- Holdout and Oct 4 data are never queried.

**Tips:** 0.001 and 0.01 SOL per transaction (two per trade).

## Result: FAIL on train, so validation was not looked at

**All 36 configs lose on train at both tips** (`research/observations/evidence_committed_dev_train_20261004.json`). Train has 720 triggers: 265 at T = 60, 266 at T = 120 and 189 at T = 300.

| config (0.001 tip) | n | SOL per trade | PF | without best 3 |
|---|---|---|---|---|
| best with n ≥ 50: C, T300, TP50/SL20 300 s | 120 | −0.023 | 0.67 | −4.13 |
| B, T300, TP50/SL20 300 s | 123 | −0.027 | 0.61 | −4.18 |
| A, T300, TP50/SL20 300 s | 189 | −0.033 | 0.51 | −7.57 |
| A, T60, devx | 265 | −0.057 | 0.61 | −18.66 |
| D, T60, TP100/SL30 1800 s (n < 50) | 20 | +0.028 | 1.18 | −1.78 |

Variant D, the only non-negative cell, has 20 trades, a PF below 1.2, and loses without its best 3 trades. That is noise.

**The loss holds on both train days.** Variant A with the TP100/SL30 exit loses −0.079 SOL per trade on Oct 1 and −0.048 on Oct 2.

## Why it fails

- **The condition does select better tokens.** 3.6% of triggers migrate, against about 1% of all launches. The migrating 26 average +0.41 SOL (TP100/SL30).
- **The other 694 average −0.083 SOL.** Holding devs plus 10–20 organic buyers is visible to everyone, so it is already priced in by T. Entering after it means buying into the organic flow that created the signal.
- **Exiting on the dev's first sell does not help.** It is the worst exit for variants A and B.
- **The filters do not rescue it.** Restricting to first-time creators and excluding Mayhem Mode improves the mean only from −0.033 to −0.023.
- **Mayhem Mode is a non-factor here.** No train trigger was flagged Mayhem. 70 of 720 triggers had no PumpPortal create message and were kept.

The family is closed.
