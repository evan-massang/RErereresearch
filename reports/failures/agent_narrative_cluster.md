# Narrative-cluster heat (agent narrative_cluster, 2026-10-05): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## Idea

When several NEW launches by different creators share a distinctive keyword within a short window, a narrative is heating up. Buy the cluster's early leader at the moment the cluster forms, before any member has pumped. This differs from the failed sympathy test (`agent_sympathy.md`), which bought older, cheaper same-narrative tokens after a leader had already reached 150–300 SOL.

## Rule (fixed before any outcome was computed; `scripts/research/narrative_cluster_build.py`)

- **Keywords:** lowercase alphanumeric words of at least 4 characters from name + symbol (`curve_creates`), not all digits, not in the `sympathy_plays.GENERIC` stoplist.
- **Launches:** first create per mint, outside the off-limits ranges; Mayhem tokens (`mayhem_flags.is_mayhem == True`) excluded.
- **Cluster forms** at the create time *t* of a launch carrying keyword *w* when launches carrying *w* created in [*t* − 600 s, *t*] come from at least **K** distinct creators (K = 3 or 4). A keyword cannot re-fire for 1800 s.
- **Leader candidates** (all at or before *t*): cluster members not completed, last curve state trusted (|vsol − rsol − 30| < 0.01), market cap ≤ 80 SOL.
- **Leader choice:** `first` = earliest created; `buyers` = most distinct non-creator buyers; `inflow` = largest non-creator net SOL inflow. Ties go to the earliest created.
- **Fills:** `event_studies.outcomes()` (exact curve fills, 0.5 SOL, 1.25% fee per side, 1 s latency, TP/SL on later prints, completion handling). Tips 0.001 and 0.01 SOL per transaction.
- **Exits:** TP30/SL15 and TP50/SL20 with 300 s max hold; TP100/SL30 and TP200/SL50 with 1800 s max hold.
- **Re-entry:** same token not re-entered within 1800 s per (K, selection).
- **Grid:** 2 K × 3 selections × 4 exits = **24 configs**.
- **Hygiene:** gap-free segments (no trade gap > 60 s; the holdout boundary splits). [*t* − 600, *t* + 1802] must lie in one segment, so the cluster window and outcome window are fully recorded. Trades whose leader turned untrusted inside the outcome window are excluded (1 train trade).
- **Split:** train = Oct 1 before 19:15 UTC + Oct 2; validation = Oct 3.

## Result: FAIL on train, so validation was not looked at

`research/observations/evidence_narrative_cluster_train_20261005.json` holds the results.

- All 24 configs lose at both tips. Profit factor ranges from 0.28 to 0.44.
- Every config also loses on each train day separately.

| config (0.001 tip) | trades | SOL total | SOL per trade | PF | without best 3 |
|---|---|---|---|---|---|
| K3, first, TP30/SL15 300 s (best mean) | 884 | −31.69 | −0.036 | 0.35 | −37.78 |
| K3, buyers, TP30/SL15 300 s | 878 | −31.88 | −0.036 | 0.40 | −37.97 |
| K4, first, TP30/SL15 300 s | 539 | −21.42 | −0.040 | 0.28 | −23.24 |
| K4, first, TP200/SL50 1800 s (best PF) | 539 | −24.57 | −0.046 | 0.44 | −31.33 |

**Best config per day** (K3, first, TP30/SL15, 0.001 tip):
- Oct 1: 532 trades, −0.033 SOL per trade, PF 0.42.
- Oct 2: 352 trades, −0.040 SOL per trade, PF 0.24.

**First vs most-bought:** no meaningful difference. `buyers` and `inflow` hit the +30% take-profit a little more often (10–12% vs 8%) but lose about the same per trade.

## Diagnostics (after the fact; not used for selection)

These are in `evidence_narrative_cluster_diagnostics_20261005.json`.

- **Leaders migrate less often than an average launch:** 1.1–1.5% of cluster leaders migrate, against 2.5% of all non-Mayhem train launches.
- **Clusters form fast and are mostly copy bursts.** The median cluster has 3 members. The median leader is only 50–73 s old, at about 29–31 SOL market cap, so it has not left the starting price.
- **Top train keywords** are news and meme words (intelligence, justice, trump, elon, jane, fomo, grok, uptober). Clusters are a burst of copy launches around a headline, not a sign of demand.

## Reading

Several new launches sharing a keyword within 10 minutes is supply, not demand. Launch bots and copy-launchers flood a headline word, and the first or most-bought copy is no more likely to run than any other launch. It is in fact less likely. Combined with the sympathy failure, the bonding-curve tape shows no tradable narrative-rotation edge in either direction:
- buying at cluster formation loses;
- buying laggards after a leader has pumped loses.

The family is closed.
