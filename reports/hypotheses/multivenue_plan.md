# Multi-venue forward recording and pre-registration plan (H-LIGHTLAG, H-EQLAG; H-LIGHTFADE, H-T2LAG data)

Written 2026-10-05 by an agent session. Source hypotheses: `sources/leads/documented_edges_round7.md` (ideas 1, 2,
4, 6). None of them has history, so this is a forward-only test. No backtest is scored here, nothing is traded, and
no authenticated API or account is used.

## 1. What is recorded

`scripts/research/multivenue_recorder.py` (public websockets only, proxy-aware like `hllag_forward.py`). It runs
apart from the frozen H-HLLAG forward collector and does not import or touch `hllag_forward.py` or `hlanchor_lib.py`.

| Venue | Stream | Coins |
|---|---|---|
| Binance USDⓈ-M | `wss://fstream.binance.com` `<sym>@bookTicker` | SOL XRP HYPE ENA PUMP DOGE SUI; TSLA NVDA MU INTC COIN MSTR XAU XAG (all 8 equity/metal perps confirmed live on fstream 2026-10-05; Binance REST `fapi` returns HTTP 451 from here, so the check used the `!bookTicker` stream, which also lists AAPL, AMZN, GOOGL, META, HOOD, CRCL, SPY, QQQ and PAXG) |
| Lighter | `wss://mainnet.zklighter.elliot.ai/stream?readonly=true`, `ticker/<id>` (best bid/ask + size) and `trade/<id>` | the same 15 coins (market ids from `/api/v1/orderBooks`: SOL 2, DOGE 3, XRP 7, SUI 16, HYPE 24, ENA 29, PUMP 45, XAU 92, XAG 93, COIN 109, NVDA 110, TSLA 112, MSTR 122, INTC 137, MU 164) |
| Hyperliquid HIP-3 trade[XYZ] | `wss://api.hyperliquid.xyz/ws` `bbo` + `trades` | xyz:TSLA, NVDA, MU, INTC, COIN, MSTR, GOLD (=XAU), SILVER (=XAG) |
| Aster (control) | `wss://fstream.asterdex.com` `<sym>@bookTicker` | the 7 crypto coins |
| Metadata, hourly | HL `metaAndAssetCtxs` `dex:"xyz"` (growthMode, deployerFeeScale), Lighter `orderBooks` (taker/maker fee) | `meta_xyz.jsonl`, `meta_lighter.jsonl` |

**Files:** `data/raw/web/multivenue/<venue>_<bbo|trades>_<YYYY-MM-DD-HH>.parquet`, sorted by (coin, ts_us).
- `ts_us`: our receive time in microseconds (container clock). `exch_ts_ms`: venue time (Binance/Aster `T`, Lighter
  `last_updated_at` / `transaction_time`, HL `time`).
- bbo: `bid, ask, bid_sz, ask_sz`. trades: `px, sz, side` (+1 taker buy), plus `liq, trade_id` on Lighter.
- **Compaction (stated, affects fills):** a price change within 50 ms of the last written row is held and the
  latest state is written once 50 ms have passed (sub-50-ms flickers are dropped, recorded prices are at most
  ~60 ms stale). Size-only changes are written at most every 500 ms per coin, so a recorded top size can be up to
  ~0.5 s stale. Trades are complete except the history snapshot sent on (re)subscribe, which is skipped.
- **Clock:** the container clock ran about **2.77 s behind** the venue clocks in the test run (receive − venue time:
  Binance −2767 ms, Lighter −2773 ms, Aster −2730 ms, HL bbo −2531 ms). All decisions and fills use `ts_us` only, so
  this offset cancels. Venue times serve only for one-way-delay diagnostics.

**Run.** Launched 2026-10-05T07:19:14Z (container clock), PID **9984**, `--hours 48` (ends about
2026-10-07T07:19Z), logging to `data/raw/web/multivenue/recorder.log` (a `stats` line every minute; `start` line
holds `start_ts_us` = 1791184754884879). Recorder sha256 at launch:
`8d26e606c43acc3a84fbdbf538d4afe00fe76870e35234fcd71a32d9efab90d5`. A disk guard stops it below 1 GB free.
The disk had only ~3.6 GB free at launch.

**Disk rate (test runs, quiet Monday 07:0x UTC):** about 0.11 MB/min, which is **~160 MB/day**. US cash hours
will be busier, so expect up to ~2× that. The first version (no coalescing) ran ~490 MB/day and was cut down
before launch.

**Not recorded (gaps):** Lighter depth beyond the top level (the fill model caps size at the displayed top);
MEXC and Gate, so H-T2LAG's control arm is Aster only; HL crypto perps (the HLLAG collector already records its
coins); the extra round-7 universe coins (ZEC, NEAR, 1000PEPE, WLD, AAVE, TAO, LINK).

## 2. Split and procedure

- **T0 = 2026-10-05T07:19:14Z** (`start_ts_us` 1791184754884879). Test-run data before T0 sits in a scratch
  directory and is never scored.
- **Day 1, [T0, T0+24 h): exploratory/train.** Run every config of each grid and choose **one config per
  hypothesis** by the pre-registered selection rule. H-LIGHTLAG's kill test and H-EQLAG's leader map
  (pre-check 0) also run on day 1. Trigger counts are reported first.
- **Day 2, [T0+24 h, T0+48 h): validation, run once,** with the selected config only. Bar: n ≥ 50 round trips,
  net > 0, PF > 1.2, net without the top-3 trades > 0. If n < 50 the result is inconclusive, not a pass.
- **Then freeze and run forward.** Write a freeze file (sha256 of the scoring module, the params, frozen_at) and
  score only data received after the freeze. A day-2 failure is written to `reports/failures/`.
- No tuning after day 1. Any change needs a new hypothesis id with a rationale (parent + failing run).

The grids were written **before any recorded data existed**. The preregistration JSONs were committed (by the
session's auto-commit) at 07:03 UTC, and the first test recording started at 07:04:40 UTC.

## 3. Pre-registered grids (full rules in the JSON files)

**H-LIGHTLAG** (`reports/hypotheses/lightlag_preregistration.json`), 12 configs:
- Universe SOL, XRP, HYPE, ENA, PUMP, DOGE, SUI.
- Trigger: the Binance mid moves ≥ θ in 2 s, and Lighter's mid has moved < θ/2 in that direction.
- Grid: θ ∈ {15, 25, 40} bp × L_total ∈ {600, 900} ms × H ∈ {5, 30} s. L_total is our ~300 ms (assumed, not
  measured) + Lighter's 300 ms taker speed bump, with 900 ms as the pessimistic case.
- Entry: Lighter taker at t + L, filled at the recorded opposite best. Exit at t_in + H + L.
- Size: min($1,000, displayed top notional); skip if under $100. Exit size beyond the displayed top fills one
  spread worse.
- Fee 0. Cooldown 10 s; one position per coin.
- Day-1 kill test (from the leads file): for θ = 25, the mean Lighter mid continuation from t+600 ms to t+30 s
  must be ≥ 3 bp.

**H-EQLAG** (`reports/hypotheses/eqlag_preregistration.json`), 12 configs:
- Names TSLA, NVDA, MU, INTC, COIN, MSTR, XAU/GOLD, XAG/SILVER.
- The leader per name × session (cash open is Mon–Fri 13:30–20:00 UTC) comes from day-1 cross-correlation of
  100 ms mid returns. Fallback leader: Binance.
- Grid: θ ∈ {5, 10, 20} bp × H ∈ {5, 30} s × follower/latency ∈ {xyz @ 300 ms, Lighter @ 600 ms}.
- Fees per side: Lighter 0; xyz 0.9 bp in growth mode; **9.0 bp for xyz:GOLD and xyz:MSTR, which are not in growth
  mode** (see §4). The rate follows the hourly metadata snapshot. The spread is paid through the fill model, with
  the same size cap as above.

**H-LIGHTFADE and H-T2LAG.** The same recording serves both, but neither is pre-registered here.
- LIGHTFADE's leads-file grid uses universes A/B, which are only partly recorded. Its 7-coin version must be
  written to a pre-registration file **before day-1 data is opened** for it, or it waits for the next recording.
- T2LAG is run only as the Aster diagnostic named in the LIGHTLAG file (same trigger, Aster follower, 3.5 bp
  taker unverified), and is not scored against the bar.

## 4. Fee and terms verification (leads from official docs, fetched 2026-10-05 ~07:0x UTC)

**Lighter, Standard account (default), 0 / 0, with a 300 ms taker delay.** DOC, `document` modality.
- [docs.lighter.xyz/trading/trading-fees](https://docs.lighter.xyz/trading/trading-fees.md):
  - "For both perpetual futures and spot markets, Lighter currently charges no maker or taker fees for Standard
    Accounts, allowing all participants to trade across all markets free of charge. Plus and Premium Accounts are
    subject to maker and taker fees."
  - Standard account: "Fees: 0 maker / 0 taker", "Taker latency: 300ms", "Maker latency: 0ms",
    "Cancel/Modify latency: 300ms".
- [apidocs.lighter.xyz/docs/account-types](https://apidocs.lighter.xyz/docs/account-types.md) (updatedAt
  2026-10-04), the API docs, apply the same table to API users:
  - "Lighter API users can operate under a Standard, Plus or Premium account."
  - Standard row: Maker Fee 0%, Taker Fee 0%, Taker Latency 300 ms, Cancel/Modify Latency 300 ms, Maker Latency 0ms.
  - "For standard accounts only, TWAP orders charge a 1bps fee."
  - Plus: 0.005% maker/taker, 300 ms taker. Premium: 0.0280% taker / 0.0040% maker at 0 staked LIT, 140 ms taker.
  - This resolves the round-7 gap: maker latency is 0 ms for Standard, and the 200 ms figure belongs to Plus.
- [apidocs.lighter.xyz/docs/rate-limits](https://apidocs.lighter.xyz/docs/rate-limits.md) (updatedAt 2026-09-30):
  - Standard accounts get "60 requests per rolling minute".
  - "Standard accounts are still bound to the 60 requests per minute limit" for sendTx/sendTxBatch.
  - So a strategy is capped at about 30 round trips a minute across all coins, which is not binding at the
    expected trigger rates.
- OWN check: `/api/v1/orderBooks` shows `taker_fee "0.0000"`, `maker_fee "0.0000"` on all 15 recorded markets. This
  is the public metadata, not account-specific, and it is snapshotted hourly.

**trade[XYZ] HIP-3: 0.9 bp taker in growth mode (tier 0 base rate); 9 bp standard.** DOC.
- [docs.trade.xyz/perpetuals/mechanics/fees](https://docs.trade.xyz/perpetuals/mechanics/fees.md):
  - "Standard fees for all HIP-3 assets are currently 2x the usual fees on validator-operated perp markets".
  - "With growth mode, all-in fees are reduced by ≥90% from the standard fee rate".
  - Growth-mode table, tier 0 base rate: Taker 0.0090%, Maker 0.0030%. Standard tier 0: 0.090% / 0.030%.
  - Not eligible: "Perps on vehicles or wrappers that hold primarily crypto assets (e.g. MSTR)" and "Perps tracking
    gold, because PAXG-USDC already tracks gold price (e.g. Gold)".
- OWN check (`metaAndAssetCtxs` dex xyz, 2026-10-05 07:0x):
  - `growthMode: "enabled"` on TSLA, NVDA, MU, INTC, COIN and SILVER;
  - **absent on GOLD and MSTR**, so those two pay 9 bp taker at tier 0;
  - `deployerFeeScale "1.0"` on all eight.
  - The round-7 claim that all of xyz is 0.9 bp is **wrong for GOLD and MSTR**.
- Staking discounts (Diamond to Wood) and volume tiers lower these rates. The tests use the tier-0 base rate.

These are DOC leads. Terms can change, and Lighter has changed account tiers before; the hourly metadata snapshots
record any change during the run.

## 5. Next steps (not done here)

- After T0+24 h: write the scoring module (e.g. `scripts/research/multivenue_score.py`). It must read only the
  recorded files, apply the JSON rules, and print day-1 trigger counts before any P&L. Its sha256 is frozen at
  selection.
- Check `recorder.log` for reconnects or gaps, and that the disk rate stays below 300 MB/day.
