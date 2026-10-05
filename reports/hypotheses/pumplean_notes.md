# pumplean: lean forward tape for pump.fun tests (loader notes and split plan)

**Recorder:** `scripts/research/pumplean_recorder.py`. It writes to `data/raw/web/pumplean/`.
- **Launched:** 2026-10-05 10:43:17Z, `--hours 72`, PID 5427. Log: `recorder.log`. Gap log: `events.jsonl`.
- **Source:** public Solana RPC only. It uses websocket `logsSubscribe` at `confirmed` commitment, with one
  connection for the pump.fun curve program and one for PumpSwap. `getMultipleAccounts` resolves pools. There is
  no trading and no API keys.
- **Decoders:** imported from `pipeline/recorder.py` (`decode_pump_event`) and `pipeline/market.py` (`decode_amm`).
- **Why it exists:** the full recorder has gaps and costs about 2 GB/day. See
  `reports/failures/agent_cleanmig.md`: train had only about 14.6 covered hours. This recorder targets ≤ 250 MB/day.

## Files

- **Data:** `<table>_<YYYY-MM-DD-HH>.parquet`. The hour is the UTC hour of `recv_us`. Compression is zstd.
- **Parts:** the recorder writes part files every 2 min to `parts/`. When the hour is over, it merges them into the
  hourly file. A part file can belong to the current hour, or to an hour whose merge was cut by a crash; include
  `parts/` when reading.
- **Units:** all amounts are raw integers. SOL is in lamports (÷1e9). pump tokens are in base units (÷1e6).
- **Clock:** `recv_us` is our receive time on the container clock. In the 5-min test it ran about 3.3 s behind
  on-chain `ts` (the container clock runs slow; see `reports/paper/hllag_forward_audit.md`). Score latency against
  `recv_us` only, and use `slot`/`ts` for on-chain order.
- **No signatures.** `tx_seq` is a per-process counter of log notifications (one per transaction). Rows from the same
  process with the same `tx_seq` come from the same transaction. `pid` is not a column. A recorder restart restarts
  the counter, so look up restarts in `events.jsonl` (`start` events) before grouping by `tx_seq`.

| table | rows | key fields |
|---|---|---|
| `curve_trades` | every bonding-curve TradeEvent (SOL-quoted) | mint, user, creator, is_buy, sol, tok, vsol, vtok, `vsol_less_rsol`, `vtok_less_rtok`, fee_bps, `fee_resid`, cfee_bps, `cfee_resid`, ts, slot |
| `curve_creates` | every CreateEvent | mint, curve, user, creator, name, symbol, uri, vtok, vsol, rtok, supply, is_mayhem |
| `curve_completes` | every CompleteEvent (curve finished) | mint, user |
| `amm_pools` | every PumpSwap CreatePoolEvent | pool, mint (base), quote_mint, creator, coin_creator, base_in, quote_in |
| `amm_swaps` | every swap in a **young SOL-quoted pool** of at least 0.001 SOL | pool, user, is_buy, base, quote, `uq_less_q`, pool_base, pool_quote (pre-trade, as logged), lp_bps, proto_bps, cc_bps, ev_len |
| `amm_bars` | all other PumpSwap swaps, aggregated | kind, n, n_buy, n_users, base/quote buy/sell sums, open/last pool reserves, last swap |
| `pool_map` | pool → base mint | src: `create_event`, `seed_market_duckdb`, `seed_raw_pumpswap`, `rpc_account` (`rpc_missing`) |

### What reaches `amm_swaps` and what goes to bars

**Young pool:** a SOL-quoted pool whose CreatePoolEvent is on file and is less than 7 days old. Pools enter the young
set from three places:
- the seed at start: `data/market.duckdb` `amm_pools` (created up to 2026-10-05 03:40Z, with the old recorder's
  gaps);
- `seed_pools.parquet`, built from the raw `pumpswap_raw` files of Oct 5 03h–05h;
- every CreatePoolEvent seen live.

**Two kinds of bar** (nothing is dropped silently):
- **`young_dust_1m`:** swaps in young pools below 0.001 SOL, in 1-minute buckets.
- **`other_5m`:** all other swaps, in 5-minute buckets. These are older pools, non-SOL-quoted pools, and pools created
  while no recorder ran.

**Declared hole:** pools created between 2026-10-05 05:05Z, when the old recorder stopped, and 10:43Z, when this one
started, are in `other_5m` bars only. Their mint is resolved in `pool_map`.

**Effect on H-SURVIVOR:** for entries at pool age 24–48 h, every pool is covered from about Oct 6 10:43Z on (pools
created after the start). Before then, coverage is limited to the seeded pools.

## Reading in DuckDB

```sql
SET VARIABLE d = 'data/raw/web/pumplean';
CREATE VIEW curve_trades AS
SELECT recv_us / 1e6 AS recv, slot, tx_seq, ts, mint, "user" AS usr, creator, is_buy,
       sol / 1e9 AS sol, tok / 1e6 AS tok,
       vsol / 1e9 AS vsol, vtok / 1e6 AS vtok,
       (vsol - vsol_less_rsol) / 1e9 AS rsol, (vtok - vtok_less_rtok) / 1e6 AS rtok,
       fee_bps, (ceil(sol * fee_bps / 10000.0) + fee_resid) / 1e9 AS fee_sol,
       cfee_bps, (ceil(sol * cfee_bps / 10000.0) + cfee_resid) / 1e9 AS creator_fee_sol,
       vsol_less_rsol = 30000000000 AND vtok_less_rtok = 279900000000000 AS std_curve,
       vsol::DOUBLE / vtok * 1e-3 AS price_sol_per_token          -- (vsol/1e9)/(vtok/1e6)
FROM read_parquet(getvariable('d') || '/**/curve_trades_*.parquet')   -- ** = hourly files + parts/;

CREATE VIEW amm_swaps AS
SELECT s.recv_us / 1e6 AS recv, s.slot, s.tx_seq, s.ts, s.pool, m.mint, s."user" AS usr, s.is_buy,
       s.base / 1e6 AS tok, s.quote / 1e9 AS quote_sol, (s.quote + s.uq_less_q) / 1e9 AS user_quote_sol,
       s.pool_base / 1e6 AS pool_tok_pre, s.pool_quote / 1e9 AS pool_sol_pre_logged,
       (CASE WHEN s.is_buy THEN s.pool_base - s.base ELSE s.pool_base + s.base END) / 1e6 AS pool_tok_post,
       s.lp_bps, s.proto_bps, s.cc_bps, s.ev_len
FROM read_parquet(getvariable('d') || '/**/amm_swaps_*.parquet') s
LEFT JOIN (SELECT pool, any_value(mint) AS mint
           FROM read_parquet(getvariable('d') || '/**/pool_map_*.parquet')
           WHERE mint IS NOT NULL GROUP BY pool) m USING (pool);
```

The same pattern works for `curve_creates`, `curve_completes`, `amm_pools` and `amm_bars`.

### Caveats on the PumpSwap fields (checked in the 5-min test, 2026-10-05 10:34Z)

**`quote` vs `user_quote` depends on `ev_len`:**
- **504/507-byte BuyEvents:** `quote` is the gross SOL the user paid. `user_quote` is the net SOL into the pool.
- **489-byte BuyEvents and 441-byte SellEvents:** the reverse.
- Either way, `|quote − user_quote|` = lp + protocol + creator fee. On the 04h raw tape this held for 99.96% of sells.
  The fee amounts are not stored; split the total by the three bps fields.

**Execution price:** gross SOL ÷ `tok`, with gross SOL = `greatest(quote, user_quote)` for buys and `quote` for sells.

**Post-trade reserves:**
- **Token side:** `pool_tok_post` = pre ∓ base, by definition. In the test, the next swap's logged pre-trade base
  matched this for 81–90% of rows. Same-slot ordering and dust swaps sent to bars explain the rest.
- **SOL side:** pool SOL moved by about `quote × (1 + lp_bps/1e4)` on 489-byte buys, by about
  `quote × (1 − (proto+cc)/1e4)` on 504-byte buys (median ratio 0.9926), and by about `−quote × (1 − lp_bps/1e4)` on
  sells.
- **Exact post state:** use the next swap's logged pre-trade reserves (`lead(...) OVER (PARTITION BY pool ORDER BY
  slot, tx_seq)`).
- **Level offset:** `pipeline/market.py` notes that the logged `pool_quote` level sits about 17.6 SOL below the reserve
  the swap math uses. Treat it "as logged".

### Caveats on the curve fields

**Standard curves:**
- 71% of test trades have `vsol − rsol` = exactly 30 SOL and `vtok − rtok` = exactly 279.9M tokens. These are standard
  curves.
- The rest are non-standard curves (small virtual SOL; one had absurd `vsol`). Filter on `std_curve` (in the view below) for standard pump.fun curves.

**Other checks from the test:**
- `fee_resid` = 0 on 99.9% of rows.
- Creates: standard reserves 1,073,000,000 virtual tokens / 30 SOL, 793.1M real tokens, 1B supply. 19 of 186 had
  `is_mayhem` = true.
- `creator` on trades is filled for 99.9% of rows.

## Gaps are declared in `events.jsonl`

| event | contents |
|---|---|
| `start`, `stop` | the seed counts and `market_duckdb_max_recv` are in `start` |
| `connect`, `disconnect` | stream, error, how long the connection lived, last slot, backoff |
| `minute` | per stream: notifications, failed transactions, rows per table, swaps sent to bars, last slot, `silent` (list of streams with 0 messages that minute) |
| `chunk` | an hourly merge, with its rows and bytes |
| `disk_guard` | the stop when free disk is below 1.5 GB |

**Reconnects:** a stream with no message for 45 s is reconnected. Backoff is 1, 2, 4 … 60 s, and resets after a
connection that lived ≥ 120 s.

**Gap rule for tests (fix it before scoring):** a covered minute is one where both streams have `msgs > 0` and no
`disconnect` event falls inside it. A gap is more than 60 s with no curve trade, or a non-covered minute. List the gaps
before any P&L, as `reports/failures/agent_cleanmig.md` did.

**Limit of the source:** the public RPC `logsSubscribe` can silently drop notifications under load. This shows up only
as a lower per-minute count, not as a disconnect. Compare the `minute` counts with a rolling median; treat a minute
below 30% of the median as suspect, and report it.

## Split plan for future forward pump.fun tests (declared 2026-10-05, before any of this tape is examined)

T0 is the first clean minute after launch. A clean minute is a covered minute as defined above, with no recorder
restart in the hour before it. For this run, T0 is expected at about 2026-10-05 10:44Z; confirm it from
`events.jsonl`.

| segment | window | use |
|---|---|---|
| **train** | the first 24 h of clean recording after T0 (covered minutes only, counted until 24 h of coverage is reached) | fit, select and kill tests |
| **validation** | the next 24 h of clean recording | examined once per pre-registered config set, only after the train kill test passes |
| **forward** | everything after that | out-of-sample confirmation and paper tracking. It is never used to tune |

- **Gaps:** when a gap falls inside a segment, the segment is extended until it holds 24 h of coverage. Lifecycles
  (create → migration → entry → exit) that cross a gap follow the eligibility rules in `agent_cleanmig.md`.
- **Fixing the boundaries:** the boundaries are fixed by writing the T0, train-end and validation-end timestamps into
  the first pre-registration that uses this tape. They are computed from `events.jsonl` only, never from price data.
- **Holdout:** the older holdout (`reports/hypotheses/holdout_plan.md`) is unaffected. This tape does not overlap it.
