# TWAP data notes (H-TWAPRIDE / H-TWAPFADE): recorder, coverage, lag, plan

Status 2026-10-05. Recorder: `scripts/research/twap_recorder.py` (its README is at the top of the file). Output:
`data/raw/web/twap/` (hourly parquet chunks + `recorder.log`; `data/raw/` is gitignored). No strategy has been
backtested and nothing has been traded. Only public, unauthenticated read endpoints are used.

## What is recorded

| Table | Source | Content |
|---|---|---|
| `twaps_<hour>` | Hypurrscan `GET /twap/*`, every 15 s | One row per TWAP placement: our first-seen time, block time, user, asset, coin, side, size, minutes, reduce-only, randomize, block, hash, error. `source = hs`, or `hist` if found only in a user's `twapHistory`. `initial = True` for the TWAPs already listed when the recorder started; their lag is meaningless. |
| `events_<hour>` | HL info `twapHistory`, per user | twapId, status (activated / finished / terminated / error / stopped / waitingForTrigger) and the status-event time, executedSz, executedNtl, trigger. Polled at first sight, every 30 min while active, and at expected end + 2 min. Rate-limited to at most 1 call per 5 s. |
| `ctx_<hour>` | HL info `metaAndAssetCtxs`, every minute | mark, mid, oracle, 24 h notional volume, open interest, funding for every main-dex perp, plus builder dexes that have a running tracked TWAP. This gives the 1-min mid and the point-in-time 24 h volume for participation p. |

- **Not used: HL websocket.** Its TWAP channels are per user, capped at 10 users per IP, and there is no global TWAP channel.
- **Not used: `allMids`.** It is superseded by the per-minute ctx poll.
- **Disk:** about 0.55 MB for the first 45 min, so roughly 15–20 MB/day. The budget is under 200 MB/day.

## What the Hypurrscan feed is (checked 2026-10-05)

- **It lists running TWAPs, not a 24 h log.**
  - Two calls a few minutes apart showed that TWAPs drop out once they end. The dropped records were 45, 30 and 420 min TWAPs placed long enough ago to have finished.
  - The list holds about 500–530 records.
  - So the round-6 snapshot comparison ("Hypurrscan ≈ 25–30% of the twapId increase") undercounted. That snapshot missed every short TWAP that had already finished.
  - Snapshot evidence: of 1,100 placements in the same 23.6 h window, taken from `twapHistory` of the 182 users that appeared in the snapshot, Hypurrscan showed 504. The missing ones had a median duration of 30 min; the shown ones had a median of 1,470 min.
- **Polling every 15 s catches TWAPs while they run.** The HL minimum duration is 5 min.

## Coverage and lag, first 0.66 h of live recording (06:07–06:50 UTC, 2026-10-05)

From `python scripts/research/twap_recorder.py coverage`; the initial snapshot is excluded.

| Metric | Value |
|---|---|
| Placements recorded | 78 (71 via Hypurrscan, 7 only via `twapHistory`) |
| Hypurrscan share of placements we know of | 0.91 |
| `hist` rows found > 60 s after placement (real Hypurrscan misses) | 1 (a BTC TWAP found 1,116 s late) |
| Other 6 `hist` rows | Found within about 2 s of placement: a race with the next Hypurrscan poll, not a miss |
| Rate: Hypurrscan placements per hour vs twapId increase per hour | 108 vs 191 |
| Distinct twapIds recorded / twapId span | 78 / 125 = **0.62** |
| Lag, first-seen − block time (Hypurrscan rows) | p10 4.6 s, p50 9.8 s, p90 20.6 s, p99 29.9 s, max 30.4 s |
| Share with lag ≤ 60 s (the pre-registered cut-off) | 1.00 |
| Asset mix of Hypurrscan rows | 40 main-dex perps, 22 spot, 9 builder-dex perps |

**Reading the numbers.**
- **Lag.** Lag is bounded by the 15 s poll plus Hypurrscan's own delay. About 12% of Hypurrscan polls fail through the container's proxy (ProxyError or connection reset; 21 in about 45 min). A failed poll pushes some lags to about 30 s.
- **Clock skew.** A few `hist` lags are slightly negative (down to −1.4 s), which shows about 1 s of skew between this container and HL block time.
- **Unexplained twapId gap.** About 38% of twapIds in the span are not in our data. We cannot yet tell whether they are:
  - TWAPs Hypurrscan never lists, for example trigger TWAPs waiting for their trigger, or placements that fail at once;
  - ids used by other objects;
  - TWAPs of users we never poll.
  This is a 40-min window, so the 0.62 is noisy. Re-run `coverage` after 24 h.
- **The miss check is biased.** It only looks at users who placed some other TWAP that Hypurrscan showed, so it underestimates misses.

## Plan

1. **Recording.** Run 48 h from 2026-10-05 06:07 UTC (`--hours 48`, pid 25141). Restart for day 3, and keep it running for the forward test.
2. **Train: recording days 1–2** (2026-10-05 06:07 → 2026-10-07 06:07 UTC).
   - Count qualifying TWAPs and compute p from `ctx`.
   - Settle the open coverage questions: the twapId gap, `waitingForTrigger` TWAPs, and the share of completions with `executedSz/size ≥ 0.9`.
   - Choose within the pre-registered grids only.
3. **Validation: day 3.** Score the chosen configs once.
4. **Freeze.** Write `reports/hypotheses/twaptride_preregistration.json` and `twapfade_preregistration.json` with the rule, grid, costs and a hash of the scoring code. Then forward-test on later recorded days only. No re-tuning after the freeze.
5. **Before freezing.** Read Barone and Lillo in full (decay half-life, impact vs participation), as listed in round 6 §4. Get an ethics and legal read on trading ahead of disclosed orders before anything goes beyond paper.

## Operations

- Check it is alive:
  - `ps -p 25141 -o pid,etime,cmd`
  - `tail data/raw/web/twap/recorder.log`; the log prints a `summary:` line every hour.
- Coverage and lag: `python scripts/research/twap_recorder.py coverage`.
- Restart after a container restart or stop:
  `nohup python scripts/research/twap_recorder.py record --hours 48 >> data/raw/web/twap/recorder.log 2>&1 &`.
  - On restart it reloads the last 48 chunk files and does not re-record those placements or events. TWAPs placed while it was down appear with `initial=True`.
- Gaps: the recorder does not survive a container shutdown. Any gap in the hourly chunks is a gap in the data, so record it rather than fill it.
