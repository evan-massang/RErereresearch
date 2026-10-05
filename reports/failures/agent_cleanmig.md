# H-CLEANMIG (structural filter at migration, then one delayed PumpSwap buy): FAIL at the train kill test (agent cleanmig, 2026-10-05)

**Verdict: FAIL.** Every train config with at least 10 trades lost between 29% and 43% of the stake per trade on
average. The pre-registered kill threshold was a mean above −2% for at least one config. Under the pre-registration,
no config was selected and **validation (Oct 3) was not examined**. Holdout rows (1790882100–1790899200) were never
loaded: every SQL query excludes them, and asserts check this.

- **Pre-registration:** `reports/hypotheses/cleanmig_preregistration.json`. It was written after the gap list and the
  eligible-trade counts were known, and before any price or P&L was computed.
- **Scripts:** `scripts/research/cleanmig_lib.py` (segments, point-in-time filters, fills) and
  `scripts/research/cleanmig_sim.py`.
- **Evidence:** `research/observations/evidence_cleanmig_train_20261005.json` and the per-trade file
  `research/observations/evidence_cleanmig_train_trades_20261005.csv`.
- **Source idea:** `sources/leads/documented_edges_round10.md`, idea 2.

## Step 1: tape gaps (declared before P&L)

A gap is more than 60 s with no market-wide trade in `amm_trades` or `curve_trades`. Both tapes have the same gaps,
so these are recorder outages, not quiet markets.

| gap (UTC) | length |
|---|---|
| Oct 1 12:34 → 12:41 | 7.5 min |
| Oct 1 19:15 → Oct 2 01:44 | 6.5 h (includes the 2 h holdout; the rest is a recorder gap) |
| Oct 2 07:41 → 16:55 | 9.2 h |
| Oct 2 18:49 → Oct 3 00:33 | 5.7 h |
| Oct 4 01:12 → 08:54 | 7.7 h |
| Oct 4 23:05 → 23:07 | 78 s |
| Oct 5 01:04 → 01:11 | 7.5 min |

- **Train has only about 14.6 covered hours:** Oct 1 12:19–19:15, Oct 2 01:44–07:41 and Oct 2 16:55–18:49.
- **Validation is covered from Oct 3 00:33 to Oct 4 01:12.**
- `loaded_amm_files` has 94 of 96 files complete. The 2 incomplete files are from Oct 5 03h, after the end of the
  data used here.

**Eligibility rules for each trade:**
- Token create, migration and entry must lie in one covered segment. Otherwise the curve history or the entry state
  would be incomplete.
- The exit must lie in a covered segment and before the data end.
- The whole lifecycle must not touch the holdout.
- Fixed-time holds may span a recorder gap, because only the entry and exit states are needed. The stop variant
  needs a continuous window.

**What these rules cost in sample size:**
- **Train n is at most 28 for any config,** so the n ≥ 50 train bar was unreachable. The pre-registration says so,
  and caps the best possible verdict at INCONCLUSIVE.
- The lead's "24 h with −40% stop" exit had 0 eligible train windows. It was replaced, before any P&L, by
  "4 h with −40% stop".

## Setup

- **Universe:** standard migrations (`quote_in` ≈ 84.99). Mayhem tokens are excluded: 0 on train, with 104 of 556
  flags unknown and kept.
- **Filters:** computed from `curve_trades` with recv ≤ migration only. Wallet balances are net curve buys minus
  sells; transfers are not visible.
  - **Base filter:** ≥ 20 curve trades, creator net balance < 0.1% of supply, top-10 wallets < 30%, and wallets whose
    first buy was in the create slot or the slot after still hold < 3%.
  - **Strict filter:** base, plus ≥ 150 holders.
  - **Train passers:** 59 base and 54 strict, out of 556 migrations. Of those 556, 326 (59%) are insider graduations
    with fewer than 20 curve trades.
- **Trade:** buy 0.5 SOL at migration + D + 1 s and sell everything at + D + H + 1 s.
  - **Fills:** exact constant product. The true reserve is the logged value + 17.585; this identity was re-checked on
    200k train sells, with a median relative error of 4e-6.
  - **Fees:** the pool's fee tier at fill time. The fill trade's `fee_bps` was 120–125 bps in every case on the
    filtered trades.
  - **Transaction costs:** a tip of 0.001 SOL per transaction (0.01 as a sensitivity) plus a 5,000-lamport base fee,
    on 2 transactions.
- **Grid:** filter {base, strict} × D {30 min, 2 h} × exit {hold 4 h, hold 24 h, hold 4 h with a −40% stop} = 12.

## Train results (tip 0.001 SOL, main fills)

| config | n | net SOL | mean | median | PF | net ex top-3 | win | rugs (≤ −90%) |
|---|---|---|---|---|---|---|---|---|
| base D30m H4 | 10 | −1.44 | −28.8% | −17.4% | 0.08 | −1.51 | 10% | 1 |
| base D30m H24 | 28 | −5.96 | −42.6% | −39.4% | 0.00 | −5.92 | 0% | 3 |
| base D30m H4 stop40 | 10 | −1.51 | −30.1% | −30.3% | 0.08 | −1.58 | 10% | 1 |
| base D2h H4 | 2 | +0.003 | +0.3% | — | 1.07 | — | — | 0 |
| base D2h H24 | 18 | −3.41 | −37.9% | −50.0% | 0.04 | −3.46 | 6% | 0 |
| base D2h H4 stop40 | 2 | +0.003 | +0.3% | — | 1.07 | — | — | 0 |
| strict D30m H4 / H4 stop40 | 10 / 10 | −1.44 / −1.51 | −28.8% / −30.1% | | 0.08 | | 10% | 1 |
| strict D30m H24 | 26 | −5.43 | −41.8% | −39.4% | 0.00 | −5.39 | 0% | 2 |
| strict D2h H4 / H4 stop40 | 2 / 2 | +0.003 | +0.3% | | | | | 0 |
| strict D2h H24 | 17 | −3.37 | −39.7% | −50.7% | 0.04 | −3.42 | 6% | 0 |

**Sensitivities:**
- **Tip 0.01 SOL:** every config loses more.
- **Conservative fills and zero-value stale exits:** they change net by less than 0.5 SOL in every config. One stale
  exit occurred in base D30m H24 and one in base D2h H24.
- **Gross before costs:** mid-to-mid returns are already −24% to −39% on average. Costs are not the problem.

**Distribution of base D30m H24 (net return per trade):**
- p5 −94%, p25 −69%, median −39%, p75 −9.5%, p95 −2.3%.
- 28 of 28 trades lost. The best trade was −2.0%.
- **Stops gap through.** In the stop variant, stopped trades exited at −96%, −48% and −48% (mid to mid).

**Why the trades start so badly:** 30 minutes after migration the true SOL reserve was already down to about
20–50 SOL from 85. So the entry pool is thin, and the round trip costs about 8% even when the price does not move.

**By entry hour (UTC), base D30m H24:** every hour is negative.

| hour | 02 | 03 | 04 | 05 | 06 | 07 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|
| mean net | −3% | −40% | −30% | −50% | −55% | −20% | −64% | −52% |

The 4 h configs only have Oct 1 13–14 h and Oct 2 02–03 h entries, all negative on average.

**Skip reasons (base D30m H24, of 59 passers):**
- 22: lifecycle crosses the holdout;
- 8: entry in a gap or in a different segment;
- 1: curve history crosses a gap.

## Descriptive references (not gates)

**The lead's kill idea.** It wanted the filter to lift the 4 h median by at least 5 pp over unfiltered migrations.
The filter did the opposite:

| D30m H4 | n | median |
|---|---|---|
| filtered (base) | 10 | −17.4% |
| unfiltered | 137 | −8.0% |

The filter is 9.4 pp **worse**.

**Insider graduations** (fewer than 20 curve trades):
- D30m H4: n 90, mean −23%, 23 rugs;
- D30m H24: n 150, mean −25%.

They are bad, but filtering them out does not leave a profitable group.

**One unregistered side observation, not promoted.** Organic migrations that *fail* the filter, at D30m H4: n 37,
mean +6.8%, PF 1.26, but net ex top-3 −4.70 SOL. That is tail-driven noise, below n 50, and not in the grid.

## Reading

Structural "clean" features at migration do not avoid post-migration decay. These pools lose most of their SOL
reserve within the first 30 minutes, and both the decay and the rugs continue through 24 h. This matches iteration 8
and the round-10 kill-risk note: the decay is mostly organic seller exhaustion, not insider dumps that a filter could
screen out.

**Limitations:**
- Train n is small (≤ 28) because of recorder gaps.
- The 24 h train exits fall on Oct 3, the validation calendar day; only those pools' prices were read.
- Creator and sniper balances ignore token transfers.

None of these could turn a gross mean of −24% to −39% into a profit. The idea is closed at these delays and holds.
