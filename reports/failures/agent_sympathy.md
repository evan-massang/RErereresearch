# Sympathy plays on the bonding curve (agent sympathy, 2026-10-04): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## Idea

When a "leader" token rips, buy a *different* token that already exists, is still on the curve, is cheaper, and shares the leader's narrative, before slower traders rotate into it. This is the opposite of the earlier copycat test (buying the original once copies appear, median further gain about 0%): here the copies are bought when the original rips. It had not been tested before.

## Rule (fixed before any outcome was computed; `scripts/research/sympathy_plays.py`)

**Leader triggers.** Each fires once per leader, the first time it happens, on the leader's own tape:

| trigger | fires when |
|---|---|
| `mc150` | market cap (vsol/vtok × 1e9) first reaches 150 SOL |
| `mc250` | market cap first reaches 250 SOL |
| `x3_5m` | price is at least 3× its minimum over the trailing 300 s |
| `migr` | the curve completes |

**Narrative match.** Uses name and symbol from `curve_creates`. A token matches if any of these holds:
- same normalised name (as in `solo_signals.norm`);
- same normalised symbol;
- a shared keyword: a word of at least 4 characters that is not in a fixed list of generic words.

**Sympathy candidate.** All checks are at trigger time *t*:
- created before *t*, and not the leader itself;
- standard curve (first recorded vsol at least 20);
- at least one trade in the current gap-free segment at or before *t*, and not completed at or before *t*;
- last market cap below the leader's market cap.

**Selection:**
- `largest`: the highest market cap among the candidates;
- `recent`: the candidate with the most recent trade.

A token is not re-entered within 1800 s.

**Fills:** `event_studies.outcomes()`, which gives:
- exact constant-product fills;
- 0.5 SOL per trade;
- 1.25% fee per side;
- 1 s latency;
- take-profit/stop-loss on later prints;
- completion handling.

**Exits:**
- TP30/SL15 and TP50/SL20, each with a 300 s maximum hold;
- TP100/SL30 and TP200/SL50, each with an 1800 s maximum hold.

**Tips:** 0.001 and 0.01 SOL per transaction.

**Grid:** 4 triggers × 2 selections × 4 exits = **32 configs**.

**Data hygiene:**
- Holdout `[1790882100, 1790899200)` and everything from 1791072000 on are excluded, including creates.
- Segments are gap-free: no gap between trades longer than 60 s, and the holdout boundary also splits a segment.
- The leader's creation, its trigger and trigger + 1801 s must all lie in one segment.

**Split:**
- Train: Oct 1 before 19:15 UTC, plus Oct 2 (14.7 h of recorded tape).
- Validation: Oct 3.

## Result: FAIL on train, so validation was not looked at

`research/observations/evidence_sympathy_train_20261004.json` holds the results.
- All 32 configs have a negative mean at both tips. The profit factor is at most 0.46.
- Train has 6,744 trades in total. Of the matches, 4,360 are on the same name, 899 on the same symbol and 1,485 on a keyword.

| trigger | trades (largest / recent) | best config (0.001 tip) | SOL per trade | PF | without the best 3 |
|---|---|---|---|---|---|
| `mc250` | 373 / 389 | largest, TP30/SL15, 300 s | −0.031 | 0.39 | −13.07 |
| `mc150` | 656 / 700 | largest, TP30/SL15, 300 s | −0.046 | 0.18 | −31.08 |
| `migr` | 216 / 219 | largest, TP50/SL20, 300 s | −0.069 | 0.22 | −16.06 |
| `x3_5m` | 2011 / 2180 | largest, TP30/SL15, 300 s | −0.073 | 0.08 | −148.28 |

**Best config: `mc250 | largest | TP30/SL15, 300 s`.**
- At a 0.001 SOL tip: 373 trades, −11.55 SOL in total, PF 0.39, 12.9% winners.
- At a 0.01 SOL tip: −18.26 SOL, PF 0.26.

**The loss holds on both train days.** At TP50/SL20 and a 0.001 tip, all configs pooled lose −0.084 SOL per trade on Oct 1 and −0.077 on Oct 2.

## Robustness: after-the-fact slices, used to diagnose and not to select

These are in `evidence_sympathy_robustness_20261004.json`.

**Odd curve states.** About 30% of entries are in tokens whose recorded vsol had fallen below 30, which a standard curve cannot reach; vsol ≠ rsol + 30 on about 23% of the tape. Dropping every entry below 27 SOL market cap improves the mean but leaves it negative everywhere. The best slice is `mc250 largest` at −0.025 SOL per trade with PF 0.45.

**Candidates traded in the last 30 s.** Adding this filter makes no slice better than −0.022 SOL per trade (PF at most 0.68).

**Take-profit hit rates.** Even for the best trigger, `mc250`, a +30% take-profit is hit before a −15% stop on only 13–30% of entries. The sympathy token drifts down after the leader's trigger. Same-name copies do worst; same-symbol and keyword matches are slightly less bad.

## Reading

There is no measurable rotation from a ripping leader into its existing namesakes within 5–30 min. This is consistent with the earlier finding that copycats migrate less often than originals. Copies sitting on the curve are mostly dead or being sold into, and a leader's pump does not revive them. The family is closed. The vsol/rsol inconsistency on about 23% of curve trades should be checked by whoever owns the recorder, because every exact-fill simulation in this repo relies on vsol/vtok.
