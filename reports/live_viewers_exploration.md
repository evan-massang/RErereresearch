# Livestream viewers on bonding-curve coins: exploration (2026-10-04)

**Status: EXPLORATORY. Not a finding, not a frozen rule.** All data here was recorded after 2026-10-04 00:00 UTC,
which is reserved for forward tests. Using it is acceptable only because no strategy has been frozen on it and
this is a look at a new source. Any rule suggested here must be frozen first and then tested only on data
recorded **after** the freeze. These ~5.4 h must not be reused as validation for anything derived from them.

Scripts: `scripts/research/live_viewers_lib.py` (tolerant loader), `live_viewers_describe.py` (task 1),
`live_viewers_events.py` (tasks 2-3).
Evidence: `research/observations/evidence_live_viewers_describe_20261004.json` and
`evidence_live_viewers_events_20261004.json`.

## Hypothesis
When the viewer count rises on a coin still on its bonding curve, buy flow and price rise over the next
5-30 min, because viewers buy.

## Data
- 1,769 polls from 08:54 to 16:17 UTC (7.4 h). Polls are 15.0 s apart (p99 15.4 s, max 31.9 s). The files had
  0 error lines, 0 truncated lines and 5 empty polls. Two recorder files overlap in each restart hour, but no
  poll appears twice.
- About 53 live coins per poll (max 70): a median of 39 curve coins and 15 migrated coins. Live curve coins
  rose from about 34 per poll before noon to about 43 after 13:00.
- 304 distinct mints were seen; 280 of them were seen while still on the curve.
- **Viewers are mostly zero.** On curve rows the median is 0 viewers, p90 is 21 and the max is 86. The
  "$-family" (below) inflates these figures. Without it, the median is 0, p90 is 2, p99 is 6 and the max is 86.
- **A single-operator family.** Five curve coins look like one operator: `$M`, `$J`, `$O`, `$R` and `$mAjor`.
  - They were created on 2026-09-15 between 10:13 and 13:50 UTC.
  - They have no stream title.
  - Their market cap stays near the curve's starting value all day (28-29.6 SOL).
  - They are live in every poll with 11-51 median viewers, and they make up 97.5% of curve rows with 10 or
    more viewers.
  - They have different creator wallets.

  Their viewer counts are not tied to trading, so they are excluded from events and baselines.
- Other clustering:
  - 20 creators had 2 or more mints on the list (55 mints in all).
  - Repeated titles: "WE LIVE" ×3, two of them high-viewer coins (DOSR and KEY, about 70 min apart, with
    different creators), "hello" ×3 and "cat" ×3.
  - Repeated symbols: "SI" ×4 and "SOLANA" ×4.
  - No other large single-operator cluster was found.
- Distinct curve coins that ever reached each viewer count, excluding the family. The first figure is the
  count in 7.4 h; the figure in brackets is the rate of new mints per hour.

  | Viewers | Coins | New mints per hour |
  |---|---|---|
  | 5 | 18 | 2.4 |
  | 10 | 9 | 1.2 |
  | 20 | 4 | 0.5 |
  | 50 | 2 | — |

  Including the family, the counts are 23, 14, 9 and 4.
- Tape overlap: `curve_trades` ends at 14:49:51 UTC. Only 121 of the 280 curve mints have any trusted curve
  trades. Many streams are on coins that nobody trades.

## Events (point in time, using only polls received at or before t)
- `cross_V`: the first poll at which the coin shows V or more viewers. The coin must have been seen below V
  earlier, or must have first appeared after the recorder's first minute; this excludes coins that were
  already above V when the recorder started.
- `rise_V_X`: viewers ≥ V and ≥ (1+X) × the minimum viewers seen in polls 1-3 min earlier, with a 5-min
  cooldown per mint.
- Baselines:
  - `flat_same_mints`: the same coins at moments with flat viewers (≥1 viewer, within ±10% of 1-3 min earlier),
    sampled every 5 min.
  - `sample_other_mints(_active)`: all other live curve coins, sampled every 5 min.

Outcomes use trusted curve states only (|vsol−rsol−30|<0.01). The simulated trade is `event_studies.rt/outcomes`:
a 0.5 SOL round trip with exact constant-product fills, 1.25% fee per side, 1 s latency, take-profit /
stop-loss exits and max holds of 300 s or 1800 s. Only events at least 30 min before the end of the tape are
used, which leaves 5.4 h covered.

| event | n (mints) | ret 5m | ret 15m mean / median | ret 30m | net buy SOL, 15m before → 15m after | sim TP50/SL20/1800, tip 0.001 | tip 0.01 |
|---|---|---|---|---|---|---|---|
| cross_3 | 25 (25) | +3.3% | −6.6% / 0% | −10.8% | +2.9 → −2.1 | −0.026 | −0.044 |
| cross_5 | 11 (11) | −3.8% | −18.8% / −19.4% | −27.2% | +7.6 → −6.4 | −0.073 | −0.091 |
| cross_10 | 7 (7) | +20.2% | +3.7% / −23.4% | −9.6% | +12.4 → −0.5 | −0.053 | −0.071 |
| rise_5_50 | 35 (10) | −0.7% | −1.8% / −2.8% | +0.8% | +3.5 → −1.1 | −0.030 | −0.048 |
| rise_3_50 | 184 (26) | +0.6% | −0.2% / 0% | +0.6% | +0.8 → −0.1 | −0.021 | −0.039 |
| flat_same_mints | 585 (24) | −0.3% | +0.1% / 0% | +0.9% | +0.2 → −0.1 | −0.025 | −0.043 |
| sample_other_mints_active | 136 (65) | −0.6% | −1.0% / 0% | −1.7% | +0.3 → −0.2 | −0.033 | −0.051 |

All simulated exits lose money: across all 10 TP/SL/hold settings, the best mean at tip 0.001 is about −0.002
SOL for cross_3 and −0.015 SOL for rise_5_50. The only positive means are for TP20/SL10/300 s on cross_5 and
cross_10 (+0.012 and +0.051 SOL), from n = 11 and n = 7. Each is the best of 10 exit settings, so they are
noise.

The table below is a mint-cluster bootstrap of the event mean minus `flat_same_mints` (90% CI):

| Event | 15m return | Sim TP50/SL20/1800 |
|---|---|---|
| cross_5 | −18.9% [−31%, −6%] | −0.049 SOL [−0.099, +0.010] |
| cross_3 | −6.7% [−13%, −1.5%] | −0.002 SOL [−0.035, +0.035] |
| rise_5_50 | −1.9% [−21%, +17%] | −0.005 SOL [−0.061, +0.039] |

Lead and lag at the poll level (1,556 curve-coin samples with a tape; Spearman correlation):

| Correlation of viewer change with | ρ |
|---|---|
| net buy flow in the next 5 min | 0.05 |
| net buy flow in the previous 5 min | 0.05 |
| return over the next 15 min | −0.02 |

## Reading
- **The hypothesis is not supported.** Viewer jumps come after buy flow: in every event type, net buying is
  positive in the 15 min before and negative in the 15 min after. Viewers arrive with a pump already underway
  and appear around its top.
- cross_5 shows the opposite of the hypothesis: −19% over 15 min against flat. That rests on 11 mints from one
  morning-to-afternoon session, so it is a lead, not a finding.
- A long entry on viewer rises loses about the fee floor or worse, at both tips.
- Bonding-curve tokens cannot be shorted, so the only possible use is as an **avoid filter**: do not buy a
  curve coin in the 15-30 min after its viewers first cross about 5. Other strategies would use it that way.
- **Caveats:**
  - The window is about 5.4 h, on one day, ending at 14:49.
  - 37% of curve-live mints have no tape trades.
  - Events cluster by mint: rise_5_50 has 35 events from 10 mints.
  - The cross_5/10 sets overlap: the same coins and pumps appear in both.

## Decision and data needed
- **Drop the long-entry hypothesis.** Nothing here is worth pre-registering as an entry.
- **Keep the recorder running.** The data costs little, and the reversal after crossing 5 viewers is a
  candidate *negative filter*. It should be pre-registered only once the following is frozen:
  - the trigger: cross_5, excluding coins that never trade and always-on families like the $-family;
  - the outcome: the 15-min return and the TP50/SL20/1800 round trip against the flat baseline;
  - the decision rule.
- **Sample size.** Per-trade SD is about 0.12 SOL on 0.5 SOL. Detecting a 0.02 SOL difference at about 2 SE
  needs about 140 independent mints per split. cross_5 yields about 2.0 usable mints per hour, so that is about
  70 h per split, or **about 6 days of overlapping poll and tape data** for train plus validation.

  A filter-sized effect like the −19% seen here would need far less: about 30-40 mints per split, or 15-20 h
  each. Even so, recording should run at least 2-3 full days, so that the sample covers different times of day
  and is not dominated by a few operators.
- **Freeze order.** The train window must start no earlier than the freeze. Today's data is exploration only.
