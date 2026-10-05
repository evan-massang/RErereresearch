# Audit of the H-HLLAG forward paper test (hllag_theta40, hllag_theta40_newcoins), 2026-10-05

**Verdict: the official forward score is not comparable to the backtest, and a forward pass under it would
be misleading.** The container clock is about 1.6 to 2.8 s behind true time and keeps drifting. `sim_lag`
compares our local Binance signal time with HL *exchange* timestamps. As a result, every forward entry is
filled at an HL quote that we received **1.4 to 2.0 s before the signal fired**. That is better than zero
latency. The backtest's effective delay was **+0.6 to +1.2 s**. When the forward data are re-aligned to the
backtest's clock relation, all five forward trades so far lose. The data are an informational re-run in
scratch, n = 5, and are far too few to judge the edge. They are enough to show that the scoring is biased.

Scope: this was read-only analysis. `hlanchor_lib.py`, `hllag_forward.py` and the freeze records were not
modified, and the collector (pid 14093) was not touched. All re-runs used a byte-identical copy of
`hlanchor_lib.py` (sha256 `98166e5f…c3ad`) on copies of the chunks in the session scratchpad
(`…/scratchpad/audit/`: `resim.py`, `diag.py`, `wide.py`, `sweep.py`, `pertrade.py`, `lat.py`). Data
covers chunks through 2026-10-05 07:11 local-clock. The official ledgers (scored 07:00) were reproduced
exactly: dev n = 3, net +$20.39; new coins n = 2, net +$6.85. No trades were added between 07:00 and 07:11.

## 1. Data quality

**Clock offset (the main finding).** HL quote `local_timestamp − timestamp` is **negative** for every
coin and every message:
- It is about −1.6 s at 04:25 and about −2.5 s at 07:10. The 10-minute median falls linearly at about
  −0.33 s per hour, with no steps.
- In the Tardis backtest the same quantity is **+130 to +340 ms** (p1 to median, PUMP and FARTCOIN, 2025-08
  to 2026-03).

The local clock, not HL, is wrong:
- Binance bookTicker `local − E` measured live at 07:15 was −2.82 s, with a p10 to p90 spread of only
  15 ms. Binance's own event time is therefore about 2.8 s ahead of our clock, plus the one-way delivery
  time.
- The Cloudflare trace `ts` and the HTTP `Date` headers also put the container 2.1 to 2.9 s behind. The
  Cloudflare readings are noisy.

The container clock is not NTP-disciplined, so the scoring offset changes over time (see §2).

**Gaps and reconnects.**
- The current collector log (`hllag2.log`) is empty: there were no reconnect messages since 05:47. The
  first collector's log (`hllag1.log`) is also empty.
- **The one real outage is 05:47:13, a 35 s gap across all streams and coins.** It is the collector
  restart that added TRUMP and SPX. It falls after the dev-coin freeze (04:25:42), so it is inside the
  dev-coin scoring window. It falls before the new-coin freeze, so the new coins are not affected.
- Longer per-coin gaps have another cause. They are HL `bbo` quiet periods: `bbo` is event-driven, with up
  to 46 s between WIF updates and 62 gaps over 10 s on kBONK. Binance SPX also has quiet periods. None of
  them line up across streams.

**Event-loop stalls.**
- There are 29 all-stream silences of 0.5 to 1.2 s. Late in each hour they recur every 60 s, which matches
  `flusher()`. The flush reads, concatenates and rewrites the growing hourly parquet inside the asyncio
  loop.
- After each stall, up to 380 messages are stamped within 20 ms. 49% of PUMP Binance messages are stamped
  less than 50 µs after the previous one.
- Local timestamps therefore record processing time, not arrival time, and can be up to about 1 s late
  around flushes. None of the 5 forward signals fell within a few seconds of a stall.

**Message rates per coin** (04:25 to 07:11; TRUMP and SPX from 05:47):

| coin | Binance bookTicker /s | HL bbo /s | HL trades /s |
|---|---|---|---|
| PUMP | 63.6 | 5.2 | 1.9 |
| kBONK | 13.1 | 1.3 | 0.11 |
| WIF | 11.3 | 2.4 | 0.07 |
| FARTCOIN | 11.2 | 3.1 | 0.24 |
| TRUMP | 20.1 | 1.7 | 0.06 |
| SPX | 8.1 | 2.5 | 0.18 |

Tardis HL quotes ran at about 1.8/s (median interval 546 ms). HL exchange timestamps never decrease within
a stream. HL `trades` rows share the receive timestamp of their batch.

## 2. Comparability with the backtest (fill timing)

`sim_lag` fills the entry at the first HL quote whose **exchange** ts is at or after
`t_local_signal + 300 ms`. The table below gives the delay from the signal to the local receipt of the
quote that was actually used for the fill.

| data | fill quote received relative to signal (p10 / median / p90) |
|---|---|
| Backtest (Tardis, θ40, 716 entries) | **+637 / +888 / +1167 ms** |
| Forward, official scoring (θ40 entries) | **−2009 to −1366 ms** (median −1555) |
| Forward, re-aligned (HL ts := local − 175 ms), event-driven | median +527 ms |
| Forward, re-aligned + 0.5 s snapshots (backtest-like) | median +754 ms |

The official forward run therefore trades at HL prices from before Binance had even moved, by our own
clock. This bias favours a lag-catch-up strategy, and it grows by about 0.33 s per hour as the clock
drifts. The exit and the markouts compare exchange time with exchange time, so they are internally
consistent, but they are anchored to the early entry.

The re-run was informational and in scratch. The official score was not replaced.

| variant (θ40, frozen otherwise) | dev n / net | new coins n / net |
|---|---|---|
| official (event bbo, skewed clock) | 3 / **+20.39** | 2 / **+6.85** |
| 0.5 s snapshots, clock as-is | 3 / +20.32 | 2 / +6.46 |
| clock re-aligned, event bbo, first update after arrival (sim rule) | 3 / **−20.58** | 2 / **−3.23** |
| clock re-aligned, event bbo, quote standing at arrival | 3 / −5.36 | 2 / +1.25 |
| clock re-aligned + 0.5 s snapshots (closest to backtest) | 3 / **−23.12** | 2 / **−6.05** |

**Event-driven vs 0.5 s snapshots.** Once the clock is aligned, snapshotting moves the fill about 0.2 s
later and costs about 1 to 3 $ per trade here. On event data the sim's "first quote at or after arrival"
rule picks the *next change* of the book. In a lagging market that change is usually the reprice against
us, so it is more pessimistic than the quote a real order would meet, which is the one standing at
arrival. The difference is −$20.6 vs −$5.4 on the dev coins. That difference is second-order next to the
clock error.

**Larger informational sample.** The same re-run at lower θ gives more signals (all coins, forward data):

| θ | official net / mean bp / PF | re-aligned net / mean bp / PF |
|---|---|---|
| 15 (n = 120) | +44 / +3.7 / 1.74 | −162 / −13.5 / 0.16 |
| 25 (n = 24) | +48 / +19.8 / 6.5 | −37 / −15.3 / 0.21 |

The official forward scoring makes even θ15 profitable. The pre-registered backtest found θ15 at L = 300
lost badly (PF 0.07 to 0.54). This is independent evidence that the forward alignment is optimistic.

**Latency sweep.** Fills use the quote standing when we had received HL data up to the signal plus X ms.

| X | θ40 net | θ25 mean bp | θ15 mean bp |
|---|---|---|---|
| 0 ms | +26.8 | +18.1 | +2.4 |
| 300 ms | +25.4 | +13.3 | −1.0 |
| 475 ms | −4.1 | −5.4 | −9.3 |
| 800 ms | −19.2 | −17.1 | −16.0 |

The forward P&L flips somewhere between X = 300 and 475 ms. On θ40 the flip is almost entirely one kBONK
trade, where HL repriced by 250 bp between +300 and +475 ms.

## 3. Fill realism per forward trade

Signal times are on the local clock. The print window is HL prints received 0 to 2 s after a realistic
arrival (signal + 300 ms local). "bp worse" is relative to the official entry price; positive means a
real taker would have paid more than the ledger assumes.

| trade | official entry | top size at fill quote | same-side prints in window | best print bp worse | VWAP bp worse | standing at +475 ms, bp worse |
|---|---|---|---|---|---|---|
| kBONK buy 06:19:56 | 0.003986 | $4.4k | 98 prints, $252k | −2.5 (2 prints ≤ entry) | **+139** | **+251** |
| PUMP buy 04:55:39 | 0.006424 | $4.9k | 85 prints, $35k | +1.6 (0 ≤ entry) | +24 | +1.6 |
| PUMP buy 05:03:08 | 0.0064314 (blended) | **$211** | 14 prints, $1.2k | +2.5 (0) | +16 | +12 |
| SPX sell 06:32:47 | 0.44813 | $1.4k | 32 prints, $5.1k | +2.7 (0) | +22 | +23 |
| SPX sell 06:35:46 | 0.44518 (blended) | **$100** | 14 prints, $1.8k | +17.1 (0) | +39 | +1.1 |

- **Entry prices.** In 4 of 5 trades, no HL print in the 2 s after a realistic arrival traded at or
  better than the assumed entry. For kBONK, 2 of 98 prints did. The market traded through the assumed
  price immediately, so the ledger entries are better than any price other takers actually got.
- **Size.** $1k was not available at the top on 2 of 5 entries ($211 and $100). For those the sim's
  one-spread-worse proxy was applied. SPX exits showed only $25 and $100 at the top. The collector
  records `bbo` only, with no depth, so the excess-fill price cannot be checked.
- **Exits.** Exits had 0 to 3 opposite-side prints in their 2 s windows, too few to verify. Their
  timing is exchange-vs-exchange and is not biased by the clock.

## 4. Network latency from this container

All traffic goes through the agent proxy. The Cloudflare egress colo is IAD, in the US.
- **HL WebSocket application ping to pong RTT:** min 182, median 190 to 202, p90 212 to 288, max 440 ms
  (2 × 40 samples).
- **HL REST `l2Book` RTT:** 188 to 347 ms.
- **HL bbo delivery.**
  - Measured against Binance-anchored time, about 0.2 to 0.3 s after the HL `time` stamp.
  - The absolute value cannot be pinned down because the local clock is unsynced.
- **Binance.**
  - REST is **geo-blocked (HTTP 451)** from this egress, and WebSocket ping frames time out through the
    proxy, so there is no direct RTT.
  - bookTicker arrival jitter is small (p10 to p90 of `local − E` within 15 ms).
  - Binance futures matching is in Tokyo and the egress is US-East, so one-way delivery is at least
    about 70 to 100 ms.
- **Implied latency for a real order.** Seeing Binance, sending to HL (about 95 ms one way) and that HL
  state reaching us (about 0.2 to 0.3 s) gives X ≈ 0.3 to 0.45 s in the sweep's terms, before any
  decision or signing time. That is exactly on the cliff above.
  - The frozen "L = 300 ms" in the backtest meant an effective X of about 0.9 s, so the parameter's
    meaning differs between backtest and forward.
  - A Tokyo-colocated competitor sees Binance about 80+ ms earlier and reaches HL in a few ms.
- **Practical access.** Binance REST is geo-blocked here (451). Placing HL orders from a US egress may
  also be restricted. This should be checked before any live use.

## Risks that would make a forward pass misleading
1. **Clock skew gives negative effective latency** (−1.4 to −2.0 s and growing). This is the dominant
   issue. A pass under the current scoring says nothing about whether the edge survives 300 ms. If the
   clock is ever stepped by NTP, the bias changes abruptly mid-test.
2. **The backtest is not the same test.** The backtest effective delay was +0.9 s median. The forward
   official delay is −1.5 s. The re-aligned forward trades so far are all losses.
3. **Fills at prices nobody traded at.** In 4 of 5 trades the assumed entry was better than every print in
   the next 2 s.
4. **Size.** Top-of-book was below $1k on 2 of 5 entries and on both SPX exits. There is no depth data to
   check the slippage proxy.
5. **Flush stalls.** These stamp messages up to about 1 s late every minute, late in each hour. The 05:47
   restart left a 35 s hole in the dev-coin window.
6. **Sample.** n = 5 against a bar of n ≥ 50. θ40 results are dominated by a single kBONK trade in every
   variant.

## Suggested remediation (not done; it needs a pre-declared decision because the freeze forbids edits)
- Declare a **companion score** before more trades accrue. Leave `sim_lag` untouched and only fix the data
  passed to it.
  - Put HL exchange timestamps onto the local clock, for example `timestamp := local_timestamp − 175 ms`
    to match the backtest relation. Alternatively, estimate the offset continuously from Binance `E`/`T`.
  - Optionally add 0.5 s snapshotting for strict comparability.
- Record Binance `E`/`T` and HL `l2Book` depth in the collector.
- Write chunks per minute, not by rewriting the hourly file inside the event loop.
- Run the collector on an NTP-synced host and log a periodic clock-offset probe.
- Treat the current official ledgers as uninformative about the edge.
