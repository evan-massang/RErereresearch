# H-HLANCHOR / H-HLLAG: HL meme perps vs Binance-futures (agent_hlanchor, 2026-10-05)

**Verdict: H-HLANCHOR FAILS (kill test). One H-HLLAG config formally passes the bar on train and on
validation, but it is a FRAGILE, MARGINAL candidate, not a validated edge.** The holdout (2026-04-01 onward)
was not downloaded or examined. It still needs a forward paper test with measured real latency.

## Data
Tardis.dev free first-of-month samples (public, no key). Sources: HL `quotes` (≈0.5 s top-of-book
snapshots) and `trades`, and Binance-futures `book_ticker`. The extracted columns are saved as parquet in
`data/raw/web/tardis/parquet/` (≈0.5 GB) and the raw csv.gz files were deleted.
- Train: 8 days (2024-11-01 to 2025-06-01), 22 coin-days. WIF and kBONK on every day; FARTCOIN from 2025-01.
- Validation: 9 days (2025-07-01 to 2026-03-01), 35 coin-days. WIF, kBONK and FARTCOIN, plus PUMP from 2025-08.
- PUMP and FARTCOIN were missing on the early days (HTTP 400, not yet listed).

## Fill model (conservative)
- **Clocks.** Decisions use Tardis `local_timestamp`. Our order reaches HL at decision + latency, and that
  arrival is compared with HL *exchange* timestamps. The exchange clock runs ≈175 ms behind local, which adds
  latency on top of the stated value.
- **Maker fills.** A maker order fills only on an HL print strictly through its price while the order is live.
  Prints at our price never fill it, so we are effectively behind all visible size.
- **Maker orders.** Orders are post-only. Cancels take 300 ms, and a stale quote can still be hit in that window.
- **Taker fills.** A taker order fills at the first HL top-of-book snapshot at or after arrival. Size above the
  displayed top fills one full spread worse.
- **Fees.** HL tier 0 is 1.5 bp maker and 4.5 bp taker
  ([HL fee docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)).
- **Size and inventory.** Units are $1k, with at most 2 units per coin. Positions are flattened by taker at
  day end. Funding is ignored because holds last seconds.
- **Bar unit.** A trade is one round trip.

## Configs (16; 14 pre-registered per the leads file, 2 added on train with a stated reason)

**H-HLANCHOR** (k ∈ {10, 15, 20} bp, T ∈ {10, 30} s; fair = Binance mid × (1 + trailing 10-min median basis)):
- All 6 configs lose, with PF 0.24–0.38 and 0 or 1 of 8 days positive.
- **Kill test fails.** The fill markout is +0.1 to +2.7 bp at 1 s, then −1.5 to −2.1 bp at 5 s and −2.5 to
  −4.4 bp at 30 s, before fees. This is adverse selection, as the leads file warned: fills arrive when
  Binance is about to move through us.

**H-HLLAG**, the pre-registered grid (θ ∈ {15, 25}, L ∈ {300, 800} ms, H ∈ {5, 30} s, plus a gap-close exit):
- All 8 configs lose, with PF 0.07–0.54.
- The gap-close exit fired within about 1 s on about 95% of trades, which cut the trades short. Yet the gross
  markout kept rising out to 30 s: at L = 300 it was +3.3 bp for θ = 15 and +8.2 bp for θ = 25.
- So configs 15–16 use a pure 30-s time exit: θ = 25, and θ = 40.

| config | split | n | net $ | mean bp | PF | net ex top-3 | days + | pass |
|---|---|---|---|---|---|---|---|---|
| lag θ25 L300 H30 timeonly | train | 2579 | −914 | −3.5 | 0.80 | −1011 | 3/8 | no |
| **lag θ40 L300 H30 timeonly** | train | 721 | +295 | +4.1 | **1.204** | +209 | 8/8 | yes (barely) |
| **lag θ40 L300 H30 timeonly** | **valid** | 721 | +363 | +5.0 | 1.358 | +302 | 5/9 | yes |

## Why it is still only marginal (skeptical reading)
- **Selection.** It is the best of 16 configs and was added after seeing the train results.
- **Train PF sits on the threshold.** It is 1.204, and +0.5 bp more cost per round trip gives PF 1.18, a fail.
- **Train is concentrated in time.** 464 of 721 train trades come from one coin-day, FARTCOIN on 2025-02-01,
  between 19:00 and 24:00 UTC. Without that day the train result is n = 257 with PF 1.59.
- **Validation is concentrated in one day.** 2025-08-01 contributes +$303 of the +$363. Without it the result
  is n = 555, net +$60, PF 1.07, which **fails** the bar.
- **Latency.** The same train config at L = 800 ms loses (PF 0.79, net −$355). The edge exists only if the
  real end-to-end latency, from seeing Binance to resting on HL, is about 300 ms or less, plus the snapshot
  cadence.
- **Fill model limits.**
  - HL quotes are 0.5-s snapshots and there is no L2 depth, so the slippage proxy is crude.
  - Size is $1k. Thin coins (WIF, kBONK) produced few trades.
- **What it is.** The trade is crowded momentum and catch-up in volatile bursts. Its gross is about 13–14 bp
  against a cost of about 9 bp in fees plus the spread.

## Next step (do not trade)
Run a forward paper recording with live HL WS `l2Book`/`trades` and Binance at the real latency, scored
against the same bar. Run the untouched holdout once only after that.

## Files
- `scripts/research/hlanchor_fetch.py`, `hlanchor_lib.py`, `hlanchor_run.py`
- `research/observations/evidence_hlanchor_train_20261005.json`, `evidence_hlanchor_valid_20261005.json`
- Per-trade results: `data/raw/web/tardis/results/` (parquet)
