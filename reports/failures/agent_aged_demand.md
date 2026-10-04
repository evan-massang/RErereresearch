# Aged-wallet organic demand (agent aged_demand, 2026-10-04): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## Hypothesis

Activity-based entries (unique buyers, net flow, the 24-feature ML model) count every wallet equally, so fresh bot-farm wallets and wash trading inflate them. Demand from wallets that were already active in our tape hours earlier ("aged", likely real traders) and that are not round-tripping should predict continuation better than raw activity does.

## Method

Scripts: `scripts/research/aged_demand_build.py` (features), `scripts/research/aged_demand_eval.py` (36-config grid), `scripts/research/aged_demand_followup.py` (4 more configs). `data/market.duckdb` was opened read-only. The holdout (1790882100–1790899200) and anything from 1791072000 on were never queried.

**Wallet age.** `first_seen` is a wallet's earliest curve trade in the allowed data. A buyer is aged at time t when `first_seen <= t − 3 h`. That condition only refers to the past, so it is point in time. A 6 h version was computed as a diagnostic only. Wallets first seen in the holdout are not in the queried data, so holdout activity never makes a wallet aged.

**Limitation.** The tape starts on Oct 1 at about 12:17 UTC, so Oct 1 has no earlier day. There, "aged" can only mean seen at least 3 h earlier in the same session, and Oct 1 triggers start around 15:17. Only 32 of the 208 train trades of the best config are from Oct 1.

**Other features.** All are computed only from trades received at or before t.
- **Round-trip (wash) flag:** within a token, the wallet bought and sold within 10 s of each other.
- **Wash share:** the share of window buys made by flagged wallets.
- **Aged share:** aged non-wash buyers divided by all distinct buyers in the window.
- **Human aged:** an aged buyer that had touched at most 100 distinct mints before this one.
- **Distinct aged buyers since launch:** computed but not used in the grid.

**Trigger.** The first aged-buy print where the condition holds, on a token that:
- is 10–600 s old;
- is still on the curve, at a clean state (|vsol − rsol − 30| < 0.01);
- is not in Mayhem Mode (PumpPortal flag False; tokens with an unknown flag are excluded);
- has its trade history from creation to t + 1 + 1800 s inside one gap-free recording segment (no gap over 60 s) within its split.

There is one trade per token per config.

**Fills.** The `event_studies.rt()` model on clean states:
- 0.5 SOL per trade, 1.25% fee per side, 1 s latency;
- take-profit / stop-loss exits that fill 1 s after the trigger print;
- the completion cut;
- tips of 0.001 SOL (main case) and 0.01 SOL per transaction.

**Grid (36 selectable configs).**

| parameter | values |
|---|---|
| window W | 30, 60 s |
| K (distinct aged non-wash buyers in W) | 10, 25 |
| filter | none; share (aged share ≥ 0.5 and wash share ≤ 0.2); human (count human-aged buyers, plus the share filter) |
| exit | TP30/SL15 300 s; TP50/SL20 300 s; TP100/SL30 1800 s |

K was first drafted as 3/5. Before any outcome was computed, it was changed to roughly the 75th and 90th percentile of the per-token maximum aged-buyer count on train, because aged buyers turned out to be ubiquitous (see below).

**Baseline (not selectable).** Raw distinct buyers ≥ 2K in W, with no age requirement.

**Follow-up (4 configs, 40 in total).** On train, results improved with K and with the filters. One stated step tested K = 40 at W = 30 s with the share or human filter, under the TP30/SL15 and TP50/SL20 exits.

## Result: FAIL on train. No config passes, so validation was not looked at.

Evidence: `research/observations/evidence_aged_demand_train_20261004.json`, `research/observations/evidence_aged_demand_followup_train_20261004.json`.

Train results at a 0.001 SOL tip:

| config | n | net SOL | per trade | PF | net without best 3 |
|---|---|---|---|---|---|
| **best:** W30 K25 human, TP50/SL20 300 s | 208 | −1.28 | −0.006 | 0.93 | −2.38 |
| W60 K25 human, TP30/SL15 300 s | 263 | −2.49 | −0.010 | 0.86 | −3.47 |
| W30 K25 share, TP50/SL20 300 s | 354 | −3.72 | −0.011 | 0.88 | −4.92 |
| W30 K25 none (aged only), TP50/SL20 | 658 | −14.5 | −0.022 | 0.77 | −16.5 |
| baseline: raw ≥ 50 buyers in 30 s, TP50/SL20 | 780 | −29.4 | −0.038 | 0.64 | −31.3 |
| follow-up: W30 K40 human, TP50/SL20 | 86 | −1.13 | −0.013 | 0.85 | −2.56 |
| follow-up: W30 K40 share, TP50/SL20 | 148 | −1.83 | −0.012 | 0.86 | −3.06 |

At a 0.01 SOL tip, the best config is −0.024 SOL per trade (PF 0.75).

TP100/SL30 1800 s was the worst exit in every cell, at −0.02 to −0.06 SOL per trade.

## What this says

- **Aged is not "real".** 69% of all buys in the allowed tape come from wallets first seen at least 3 h earlier. Bots and volume farms are long-lived wallets, so age alone barely separates them from people. The median count of aged non-wash buyers in 30 s at an aged buy print is 21.
- **The filters help, but not enough.** Aged buyers, the share and wash filters and the human (≤ 100 prior mints) filter each lose less than the raw-buyer baseline at similar selectivity: −0.006 to −0.011 against −0.03 to −0.04 SOL per trade. That relative ordering is an observed train result. It never reaches break-even after fees and tips.
- **The improvement stops.** Raising K from 25 to 40 did not continue the trend, so the gain looks like noise around a slightly-less-negative mean rather than an edge.
- **Not tested:** wallet age from data before our tape (on-chain history), a longer warm-up than one session on Oct 1, and aged *sellers* (distribution) as an exit or a filter.
