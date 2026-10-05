# H-FLUSH: buying after OI + price flushes on meme perps. FAIL on train (validation not examined)

_Agent run 2026-10-05. Lead: `sources/leads/documented_edges_round4.md`, idea 3 "H-FLUSH" (ranked #1 in
that file's table). All numbers below are OWN computations from the public Binance archive; nothing is fabricated.
The verdict is **FAIL**. None of the 21 pre-declared configs passes the bar on train, so, as the protocol requires,
the **validation window was never simulated**. No holdout data (2026-04-01 onward) was downloaded._

## Bar
A config passes only if all four hold:
- n ≥ 50 trades;
- net profit after all costs;
- profit factor (PF) > 1.2;
- net profit still > 0 with the 3 best trades removed.

Splits were fixed in advance:
- train: up to 2025-06-30;
- validation: 2025-07-01 to 2026-03-31;
- holdout: 2026-04-01 onward, never touched.

## Data
- **Source:** data.binance.vision (USDⓈ-M futures). The script fetches:
  - daily `metrics`, with open interest every 5 min;
  - monthly or daily 1-min `klines`;
  - monthly `fundingRate`.
- **Cache:** compact parquet files under `data/raw/web/binance_fut/{metrics,klines1m,funding}/`. Everything is capped at 2026-03-31.
- **Universe:** declared before any return was computed. It is fundcarry's 23 verified Solana-meme Hyperliquid (HL) perps (`data/raw/web/hyperliquid/universe_map.json`), mapped to their Binance symbols, plus DOGE and 1000PEPE, which the task named. That gives 25 candidates.
  - LAUNCHCOINUSDT and YZYUSDT have no archive data.
  - USELESSUSDT was listed only in 2025-08, so it has no train data.
  - **PUMPUSDT is a reused symbol.** Before a relisting gap on 2025-07-10 it traded a different asset: price 0.05–0.16, flat through June 2025. Only data after the gap is used. It therefore has no train data.
  - That leaves **21 coins in train**. The table below gives each coin's signal start; all coverage runs to 2025-06-30.

| Coin | Signal start |
|---|---|
| DOGE | 2021-12 |
| 1000PEPE | 2023-05 |
| 1000BONK | 2023-12 |
| WIF | 2024-02 |
| MYRO | 2024-03 |
| BOME | 2024-04 |
| MEW | 2024-07 |
| POPCAT | 2024-09 |
| GOAT, MOODENG | 2024-11 |
| PNUT, CHILLGUY | 2024-12 |
| FARTCOIN, PENGU, AI16Z, GRIFFAIN, ZEREBRO | 2025-01 |
| TRUMP, MELANIA, VINE | 2025-02 |
| JELLYJELLY | 2025-04 |

  - Every coin needs a 20-day warm-up before its signals start.
  - 1-min kline coverage is 100% for every coin except PUMP (99.9%).
  - Metrics coverage is at least 99.9% for every coin except MYRO (90%), PUMP (92%) and AI16Z (68%). Their gaps only remove signals.
- **Timestamp check** (`evidence_flush_alignment.json`):
  - The price implied by `oi_value / oi` in a metrics row stamped t matches the close of the 1-min bar that opens at t+4. The median error is 2 bp, on 5 coins in 2025H1.
  - So the OI snapshot is really taken at **t+5 min**. The signal is used only from then, plus 1 more minute of latency.

## Rule tested (point in time)
- **Signal, at snapshot time s:**
  - dOI = log(OI_s / OI_{s−5m});
  - r = log(P_s / P_{s−5m}).
  - Each is divided by its own trailing 30-day standard deviation, computed strictly before s.
  - **FLUSH:** z_OI ≤ −q and z_P ≤ −q.
  - **CONTROL:** z_P ≤ −q and z_OI ≥ 0, i.e. an equally large drop with no OI fall.
- **Entry:** T0 = s + 1 min, and P0 is the open of the bar at T0.
  - `mkt`: a taker buy at P0.
  - `lim j`: a bid at P0·(1−j) resting for 5 min. It fills only if a bar's low trades **strictly below** the bid.
- **Exit:** a taker order H minutes after the fill bar.
  - Stop at −3%. The stop is also checked inside the fill bar, which is conservative.
- **Position limit:** one position per coin at a time.
- **Costs (Hyperliquid tier 0, [fee docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)):**
  - maker 1.5 bp, taker 4.5 bp;
  - taker slippage 3 bp on each side where a taker order is used;
  - a 5 bp venue-mismatch haircut per round trip, because the Binance tape stands in for HL fills (the lead's own prescription);
  - HL hourly funding while the position is held. This comes from the cached `funding_<coin>.json`. DOGE and 1000PEPE have no HL funding cache, so they use Binance settlements instead.

**Configs (21, all declared before the first full run):**
- q ∈ {2.5, 3} × entry ∈ {mkt, lim 0.3%, lim 0.6%} × H ∈ {15, 60, 120}, which gives 18 FLUSH configs;
- plus 3 CONTROL configs: q = 2.5, H = 60, each entry type.

**Not tested:**
- the mirror rule (shorting after a short-squeeze flush);
- liquidation-print confirmation, because no history of liquidation prints is available.

## Train results (`research/observations/evidence_flush_train.json`)
**Event counts** (number of 5-min bars meeting the condition, before the one-position-per-coin rule):

| Coin | FLUSH, q = 2.5 | FLUSH, q = 3 | CONTROL, q = 2.5 |
|---|---|---|---|
| DOGE | 562 | 342 | 2206 |
| 1000PEPE | 387 | 224 | 1113 |
| BOME | 308 | 190 | 406 |
| WIF | 296 | 166 | 632 |
| 1000BONK | 281 | 148 | 757 |
| MYRO | 270 | 156 | 480 |
| PNUT | 186 | 117 | 161 |
| MOODENG | 185 | 121 | 213 |
| POPCAT | 179 | 89 | 347 |
| MEW | 170 | 97 | 358 |
| CHILLGUY | 167 | 93 | 161 |
| GOAT | 154 | 85 | 209 |
| TRUMP | 139 | 80 | 59 |
| PENGU | 128 | 80 | 183 |
| VINE | 103 | 59 | 67 |
| MELANIA | 102 | 65 | 115 |
| AI16Z | 101 | 56 | 109 |
| ZEREBRO | 102 | 65 | 134 |
| FARTCOIN | 91 | 36 | 187 |
| GRIFFAIN | 86 | 44 | 146 |
| JELLYJELLY | 44 | 33 | 54 |
| **Total** | **4,041** | **2,346** | **8,097** |

Train trade results for all 21 configs:

| config | n | days | fill | net sum % | mean bp | PF | net ex-top3 % | win | day-clustered t | pass |
|---|---|---|---|---|---|---|---|---|---|---|
| flush_q2.5_mkt_H15 | 3838 | 574 | 1.0 | -641.66 | -16.7 | 0.781 | -686.89 | 0.453 | -3.88 | no |
| flush_q2.5_mkt_H60 | 3633 | 573 | 1.0 | -647.1 | -17.8 | 0.848 | -747.73 | 0.44 | -2.66 | no |
| flush_q2.5_mkt_H120 | 3485 | 573 | 1.0 | -748.48 | -21.5 | 0.85 | -863.7 | 0.41 | -2.62 | no |
| flush_q2.5_lim0.3%_H15 | 2637 | 480 | 0.686 | -340.94 | -12.9 | 0.841 | -387.13 | 0.477 | -2.26 | no |
| flush_q2.5_lim0.3%_H60 | 2535 | 479 | 0.685 | -404.21 | -15.9 | 0.872 | -494.01 | 0.443 | -1.85 | no |
| flush_q2.5_lim0.3%_H120 | 2442 | 479 | 0.682 | -335.02 | -13.7 | 0.908 | -464.61 | 0.414 | -1.36 | no |
| flush_q2.5_lim0.6%_H15 | 1810 | 396 | 0.47 | -270.64 | -15.0 | 0.834 | -318.65 | 0.476 | -1.95 | no |
| flush_q2.5_lim0.6%_H60 | 1746 | 396 | 0.466 | -270.09 | -15.5 | 0.883 | -341.64 | 0.441 | -1.47 | no |
| flush_q2.5_lim0.6%_H120 | 1699 | 396 | 0.464 | -354.95 | -20.9 | 0.868 | -444.93 | 0.393 | -1.67 | no |
| flush_q3.0_mkt_H15 | 2254 | 461 | 1.0 | -365.61 | -16.2 | 0.803 | -408.54 | 0.457 | -2.8 | no |
| flush_q3.0_mkt_H60 | 2167 | 460 | 1.0 | -334.72 | -15.4 | 0.874 | -419.55 | 0.437 | -1.72 | no |
| flush_q3.0_mkt_H120 | 2101 | 459 | 1.0 | -326.84 | -15.6 | 0.894 | -419.96 | 0.409 | -1.36 | no |
| flush_q3.0_lim0.3%_H15 | 1588 | 387 | 0.702 | -273.12 | -17.2 | 0.807 | -311.77 | 0.467 | -2.32 | no |
| flush_q3.0_lim0.3%_H60 | 1543 | 386 | 0.702 | -333.05 | -21.6 | 0.838 | -402.18 | 0.428 | -1.92 | no |
| flush_q3.0_lim0.3%_H120 | 1505 | 385 | 0.701 | -276.36 | -18.4 | 0.881 | -365.25 | 0.407 | -1.32 | no |
| flush_q3.0_lim0.6%_H15 | 1125 | 314 | 0.498 | -234.2 | -20.8 | 0.791 | -273.88 | 0.472 | -2.19 | no |
| flush_q3.0_lim0.6%_H60 | 1093 | 314 | 0.495 | -255.27 | -23.4 | 0.835 | -325.51 | 0.42 | -1.73 | no |
| flush_q3.0_lim0.6%_H120 | 1074 | 313 | 0.494 | -228.04 | -21.2 | 0.87 | -318.11 | 0.387 | -1.31 | no |
| control_q2.5_mkt_H60 | 6644 | 924 | 1.0 | -938.45 | -14.1 | 0.867 | -1039.96 | 0.443 | -2.82 | no |
| control_q2.5_lim0.3%_H60 | 4405 | 750 | 0.634 | -458.92 | -10.4 | 0.909 | -560.57 | 0.457 | -1.58 | no |
| control_q2.5_lim0.6%_H60 | 2877 | 578 | 0.398 | -192.63 | -6.7 | 0.947 | -277.82 | 0.449 | -0.72 | no |

Notes on the table:
- "net sum %" is the sum of per-trade net returns at equal notional.
- The day-clustered t-statistic uses daily sums of net return.

**The losses are not just costs: there is no reversal even before costs.**
- The mean gross return per trade (after entry/exit slippage, before fees and haircut) is −1.3 to −12 bp in every FLUSH config. The CONTROL configs are at 0 to +4.5 bp gross.
- The all-in cost is about 12–20 bp per round trip.
- Bars with forced selling (the OI falling) do **no better** than equally large price drops without an OI fall. Their gross means are slightly *worse*. In this data, forced flow does not mark a bottom 15–120 min out.
- Medians at H = 60–120 are strongly negative: −19 to −158 bp gross. Most flushes keep falling, and a few large rebounds carry the mean. The top 3 trades of the best config are each +36% to +48%. The −3% stop fires on 25–45% of trades at H ≥ 60.

**Best train config by PF: flush_q2.5_lim0.3%_H120.** n = 2,442, PF 0.908, net −335%, −13.7 bp per trade.
- **Per coin:** 8 of 21 coins are net positive. The largest are 1000PEPE +74%, WIF +60% and TRUMP +46%. The largest losers are MOODENG −89%, PENGU −78%, ZEREBRO −71% and PNUT −69%.
- **Per quarter:** 8 of 14 quarters are positive. The positive quarters are small and early: in 2022–2024Q1 there were only 12–104 trades a quarter, mostly DOGE and PEPE. 2024Q2 was +108%. Then the losses arrived: 2024Q4 −20%, 2025Q1 −360% (n = 632) and 2025Q2 −106% (n = 844). As the meme-perp universe grew, the rule got worse.

**Robustness checks** (all on flush_q2.5_mkt_H60, train only):
- dropping DOGE: −19.6 bp per trade;
- 2024 onward only: −19.5 bp per trade;
- excluding the 10 busiest market-wide days (15% of trades): −21.4 bp per trade.

**Observation, not tested.** The busiest market-wide flush days were net positive: 2025-04-23 (+61% over 88 trades) and 2025-05-09 (+55% over 82 trades). The coin-specific flushes lost.
- This is an *inferred* lead only: idiosyncratic flushes behave as information, market-wide ones as liquidity.
- It was **not** turned into a config. It would be a post-hoc iteration found on train and needs its own pre-registration.

## Validation and holdout
- **Validation (2025-07-01 to 2026-03-31): not examined.** No config passed on train, and the protocol allows the one validation look only for configs that pass on train.
- **Holdout:** never downloaded.

## Verdict
**FAIL.** Every one of the 21 configs is decisively negative on train:
- PF is 0.78–0.95;
- day-clustered t is between −0.7 and −3.9;
- every config has n > 1,000, so the result is not a matter of too few trades.

Catching knives dominates, as the lead's own risk section warned. The OI-drop condition adds nothing over a plain price-shock reversal, and neither covers HL-level costs.

## Caveats
- **Fill tape:** fills are modelled on Binance 1-min bars, not HL trades. The 5 bp haircut is a stand-in, not a measurement.
  - A limit bid on HL might fill at different moments.
  - Even so, the result is negative before costs, so better fills would not rescue it.
- **Bar resolution:** with 1-min bars, the stop and the fill can fall in the same bar. Such cases are resolved conservatively, by treating the trade as stopped.
- **Pre-signal funding** is ignored; funding during the hold averages about 0.1–0.2 bp per trade.

## Files
Scripts:
- `scripts/research/flush_fetch.py`: archive fetch, universe, holdout guard;
- `scripts/research/flush_alignment.py`: metrics timestamp check;
- `scripts/research/flush_sim.py`: signal, fill model, costs, stats.

Evidence:
- `research/observations/evidence_flush_alignment.json`;
- `research/observations/evidence_flush_train.json`.

Data:
- trade lists: `data/raw/web/binance_fut/flush_trades/train_*_slip3.csv`;
- cache: `data/raw/web/binance_fut/{metrics,klines1m,funding}/*.parquet`.

---

## Follow-up: market-wide flush rule (H-FLUSH-MW). FAIL on train; validation not examined

This follow-up turns the untested lead above into a NEW rule. The rule was pre-registered **before** anything was computed for it, in
`reports/hypotheses/flush_marketwide_preregistration.json`.
- **The rule:** a coin's q = 2.5 flush at snapshot s is eligible only if at least K distinct universe coins flushed at snapshots in (s − 30 min, s]. The count includes the coin itself.
  - This is point in time: every counted snapshot is visible at the decision time, s + 1 min.
  - A coin whose flush came before the count reached K is not entered after the fact.
- **Execution, costs and the one-position-per-coin rule are unchanged.** `flush_sim.simulate` is reused as is.
- **Configs (8):** K ∈ {3, 5} × entry {limit 0.3% below, market} × hold H ∈ {60, 120} min, with the −3% stop.
- **Bias caveat:** the lead came from exploring train, so these train numbers are optimistic.

**Eligible flush bars in train:**
- K = 3: 1,410 bars on 146 distinct days;
- K = 5: 717 bars on 69 distinct days.

Train results (`research/observations/evidence_flush_marketwide_train.json`):

| config | n | days | net sum % | mean bp | gross mean bp | PF | net ex-top3 % | day-t | pass |
|---|---|---|---|---|---|---|---|---|---|
| K3_lim0.3%_H60 | 927 | 132 | -62.22 | -6.7 | 4.4 | 0.951 | -152.02 | -0.37 | no |
| K3_lim0.3%_H120 | 909 | 132 | -24.81 | -2.7 | 8.5 | 0.982 | -131.52 | -0.13 | no |
| K3_mkt_H60 | 1275 | 146 | -101.15 | -7.9 | 6.2 | 0.938 | -189.45 | -0.52 | no |
| K3_mkt_H120 | 1246 | 146 | -166.77 | -13.4 | 0.8 | 0.913 | -249.01 | -0.78 | no |
| K5_lim0.3%_H60 | 489 | 65 | -84.24 | -17.2 | -6.1 | 0.879 | -174.04 | -0.72 | no |
| K5_lim0.3%_H120 | 479 | 65 | -15.33 | -3.2 | 8.0 | 0.980 | -122.11 | -0.10 | no |
| K5_mkt_H60 | 646 | 69 | -92.94 | -14.4 | -0.3 | 0.893 | -176.33 | -0.68 | no |
| K5_mkt_H120 | 634 | 69 | -87.15 | -13.7 | 0.5 | 0.913 | -169.08 | -0.55 | no |

**What the table shows:**
- Requiring breadth does help gross returns: the best configs reach +8 bp gross, against −1 to −12 bp for all flushes.
- That gain is smaller than the roughly 11–20 bp of costs. No config reaches PF 1.0, let alone 1.2.

**Best config: K3_lim0.3%_H120.** PF 0.98, net −25%; with the 3 best trades removed, −132%.
- The 3 best trades are +45%, +36% and +25%.
- The 3 best days are 2025-04-23 (+71%), 2025-05-09 (+58%) and 2024-05-23 (+42%). These are exactly the days that prompted the lead, so the earlier observation was driven by a few days.
- **Per quarter:** 4 of 6 positive: 2024Q1 −13%, 2024Q2 +85%, 2024Q3 +26%, 2024Q4 +26%, 2025Q1 −209%, 2025Q2 +60%.
- **Per coin:** 8 of 21 positive. The best are TRUMP +59%, 1000BONK +43% and WIF +39%; the worst are PNUT −51%, MOODENG −46% and BOME −41%.

**Validation:** not examined, because no config passed the full bar on train. The holdout was never touched.

**Verdict: FAIL.** This adds 8 configs to the 21 above, for **29 configs in the family**.

Files for this follow-up:
- `scripts/research/flush_marketwide.py`;
- `reports/hypotheses/flush_marketwide_preregistration.json`;
- `research/observations/evidence_flush_marketwide_train.json`;
- trade lists in `data/raw/web/binance_fut/flush_trades/mw_train_*.csv`.
