# DexScreener community takeover (CTO) on migrated tokens: NOT TESTABLE, 0 events (agent cto, 2026-10-05)

**Verdict: FAIL for lack of data.** Among all 1,124 recorded migrations (Oct 1 12:19 to Oct 3 08:21 UTC) there is
**one** CTO order, and it was paid 5.6 h *before* that token migrated, so it does not fit the hypothesis (an
abandoned, already-migrated token). That leaves **0 CTOs in train and 0 in validation**, against the about 50 needed.
No backtest was run, and no return was computed or looked at. Validation was not examined. Nothing here is a
statement about whether CTOs work. They simply do not occur often enough, soon enough after migration, for our
2.5-day universe.

## Data

- **Backfill.** `GET api.dexscreener.com/orders/v1/solana/{mint}` (public, no key) for every recorded migrated mint.
  The fetch ran on 2026-10-05 between about 02:24 and 03:05 UTC: 1,014 queried directly, and 110 taken read-only from
  agent dex_paid's cache (`data/raw/web/dexscreener_orders/`). There were 0 errors.
  - The order types found were `tokenProfile` (224 approved, 1 cancelled, 1 on-hold), `tokenAd` (2 approved) and
    `communityTakeover` (1 approved). 52 mints had boosts.
  - The single CTO: mint `5C7JRjLw…ngKH`, paid 2026-10-01 13:28:34 UTC, migrated 19:03:39 UTC. Its tokenProfile dates
    from Aug 2025, so this is an old token that completed the curve late, not a fresh one.
  - The fetch ran 2 to 3.5 days after each migration. A CTO later than that would fall after 1791072000 and outside
    the splits anyway.
- **Visibility lag.** For the 10 CTOs in the public feed `/community-takeovers/latest/v1`, `claimDate` minus
  `paymentTimestamp` was:
  40 s, 53 s, 80 s, 3.1 min, 3.3 min, 5.5 min, 10.8 min, 24.4 min, 26.9 min and 89.2 min.
  The planned +15 min lag covers 7 of 10, and +60 min covers 9 of 10. Use `claimDate`, or our own poll time, live.
- **Pre-declared grid (18 configs, never run).**
  - Lag +15 min, crossed with:
    - hold 4 h or 24 h;
    - exit: none, SL 40%, TP 50% / SL 25%, or TP 100% / SL 40%;
    - liquidity proxy: none, or at least $10k.
  - Plus lag +60 min with hold 4 h or 24 h and no TP/SL.
  - Costs are 2% per side, with a robustness variant of max(2%, 1.25% fee + 0.5 SOL ÷ quote reserve).
  - The controls are matched non-CTO tokens at the same bar, with age within ×1.5 and drawdown within ±15 pp, and the
    same token one hold earlier. All of this is in `scripts/research/cto_sim.py`.

## Why so rare, and recommendation

- **Rate.** The public feed had 10 CTOs in 13.3 h (Oct 4 08:18 to 21:37 UTC), across all chains. 8 were on Solana and
  6 were pump-suffix mints. Of the 5 on PumpSwap, only 1 pair was under a day old. The others were 9 days to
  17 months old.
- **Not from our recorder.** CTOs happen mostly on tokens that are weeks old, not on the last 2–3 days of graduates.
  From our recorder's universe the expected count is about 0–1 a day, so 50 trades would take months.
- **A live collector is worth running only in a changed design.** That design would poll `/community-takeovers/latest/v1`
  every 2–5 minutes for every Solana pump mint, of any age. The feed holds only 10 entries, so a 2–5 minute poll is
  safe.
  - On each new CTO it would stamp the receive time and the `claimDate`, then pull GeckoTerminal 15-min bars for the
    pool after 24 h and 48 h.
  - The expected rate is about 8–12 pump-mint CTOs a day, so reaching 50 train trades plus a validation set takes
    about **2–3 weeks**.
  - This is a different universe (old, mostly dead tokens), and the controls have to come from bars of non-CTO old
    tokens. That means sampling a random set of old PumpSwap pools as well.
- **Prior.** Iteration 8 found universal decay in migrated tokens, and CTO tokens are by definition ones that already
  failed once. Without new evidence a revival edge is a low prior.

## Files

- `scripts/research/cto_backfill.py` does the orders backfill and the feed-lag sample.
- `scripts/research/cto_fetch_ohlcv.py` refetches OHLCV with `before_timestamp=1791072000`. It ran partly, to
  `data/raw/web/ohlcv15_cto/` (177 pools), and was stopped when the count came back 0. It is not needed.
- `scripts/research/cto_sim.py` holds the declared grid and the simulator. Only `counts` was run.
- `research/observations/evidence_cto_orders_backfill.json` holds the raw orders per mint.
- `research/observations/evidence_cto_visibility_lag.json` and `evidence_cto_counts.json` hold the lag sample and the
  counts summary.
