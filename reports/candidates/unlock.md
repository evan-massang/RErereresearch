# Candidate (conditional, beta-driven): H-UNLOCK k30_m3, short Binance USDT-M perps from 30 days before to 3 days after large vesting cliff unlocks

_Agent: unlock, 2026-10-05._

- **Pre-registration:** `reports/hypotheses/unlock_preregistration.json`, frozen before any return, P&L or funding sum was computed.
- **Scripts:** `scripts/research/unlock_map.py`, `unlock_events.py`, `unlock_sim.py` and `unlock_placebo.py`. The placebo script is a post-hoc diagnostic.
- **Evidence:**
  - `research/observations/evidence_unlock_train_20261005.json`
  - `research/observations/evidence_unlock_validation_20261005.json`
  - `research/observations/evidence_unlock_placebo_20261005.json`
- **Holdout:** unlocks on or after 2026-04-01 were never priced. The price archive used ends 2026-03-31.

## Verdict

**k30_m3 passes the letter of the bar on train and on validation.** It was the only one of the 12 pre-registered configs to pass on train. Validation was run once.

**There is no unlock-specific edge on validation.** The validation profit matches what an equal-weight short of every Binance perp earned over the same dates. Excess over that basket is **+7 bp per trade (t = 0.03)**. Shorting the same coins 60 days earlier earns a gross +591 bp per trade, against +702 bp in the unlock window. The 2025-H2 to 2026-Q1 alt bear market drives the pass.

On train the excess over the basket is +274 bp (t = 1.7). That too is mostly coin-specific drift: shorting the same coins 60 days earlier earns +243 bp gross. Coins with heavy vesting fall all the time, not just around the unlock.

**Recommendation.** Do not forward-paper this as an "unlock edge". If it is pursued, pre-register a new market-neutral version: short the unlock coin and long the alt basket or BTC. Its first untouched test must be a new period, because validation is used up.

## Data source (public, unauthenticated)

**Unlock schedules: DefiLlama's emissions dataset bucket.** The endpoints are:
- `https://defillama-datasets.llama.fi/emissionsIndex` (370 protocols);
- `/emissionsProtocolsList`;
- `/emissions/<protocol>`, of which 181 were downloaded (244 MB).

The cache is in `data/raw/web/unlock/`. The documented API `api.llama.fi/emissions` returns HTTP 402 (paywalled). Tokenomist has no public API.

**Mapping to Binance symbols.** Each gecko_id is turned into a ticker with `coins.llama.fi`. A Binance symbol is accepted only if its daily close and DefiLlama's historical price agree within ±15% (median of 3 dates). This compares price levels only.
- 182 protocols were mapped.
- 19 gecko ids with no current price got manual ticker fallbacks, which are then price-checked. Examples are OM, OMNI and CHESS. They are listed in `llama_symbols.json`.
- RAY was rejected for a price mismatch.

**Prices and funding.** Binance USDT-M daily klines and funding come from the data.binance.vision archive. They are read-only copies of the momentum agent's cache, put in `data/raw/web/unlock/{klines,funding}`. Nothing new was downloaded from Binance, and the Binance live API is geo-blocked (HTTP 451).

## Point-in-time handling (limitations stated, not corrected)

- **Schedule vintage.** Only today's snapshot exists.
  - DefiLlama adapter git history (when each schedule first appeared) was unreachable: GitHub access was refused and the Wayback Machine is blocked.
  - So the "enter when the unlock first appears on calendars" variant is **not testable**. The test uses a fixed T−k entry.
  - Past events show the realised schedule. If a project postponed an unlock, a trader at T−k may not have known the recorded date. This look-ahead favours the strategy.
- **Observed flows versus scheduled vesting.** Many DefiLlama "cliff" rows are on-chain observed flows, not scheduled unlocks: incentives, treasury outflows and rewards. Only cliff allocations in the categories insiders, privateSale, publicSale or airdrop count as events.
- **Survivorship.** DefiLlama's coverage is today's set of 370 protocols. The Binance universe includes delisted perps, and a delisted position exits at its last close with a 2% charge.
- **Denominator.** No public point-in-time circulating supply was available. Size is measured against the schedule-implied unlocked supply at the end of T−1, excluding the noncirculating and burned sections. This is knowable in advance but noisy. For example, ONDO's January 2025 unlock shows as 462% of circulating supply.

## Frozen rule (k30_m3)

- **Event:** total vesting-cliff tokens on UTC day T are at least 2% of schedule circulating supply at T−1.
- **Universe:** the coin's first Binance perp bar is at least 60 days before T.
- **Trade:** short at the open of T−30 and cover at the open of T+3.
  - Per symbol, an event is skipped if its entry falls inside an open trade.
  - Stop: 35% adverse move on the daily high; the stop fill pays an extra 1%.
- **Costs:**
  - 5 bp taker fee per side;
  - slippage per side by 30-day average daily quote volume: 3 / 8 / 15 / 30 bp for at least $200M / $50–200M / $10–50M / below $10M;
  - Binance funding paid or received.

## Results (bp per trade, net of all costs)

All 12 configs on train (unlock day on or before 2025-06-30):

| config | n | gross | funding | cost | net mean | net median | PF | net ex top-3 (sum) | passes |
|---|---|---|---|---|---|---|---|---|---|
| k30_m0 | 344 | 242 | +1 | 58 | 185 | 782 | 1.17 | +4.62 | no |
| **k30_m3** | 247 | 337 | −4 | 59 | **275** | 875 | **1.24** | +5.00 | **yes** |
| k30_m10 | 247 | 207 | +1 | 62 | 146 | 704 | 1.11 | +1.66 | no |
| k14_m0 | 345 | 78 | +6 | 46 | 38 | 467 | 1.05 | +0.01 | no |
| k14_m3 | 345 | 153 | +2 | 48 | 107 | 531 | 1.12 | +2.34 | no |
| k14_m10 | 345 | −27 | +8 | 54 | −73 | 391 | 0.93 | −4.02 | no |
| k7_m0 | 345 | 65 | +2 | 37 | 30 | 172 | 1.05 | −0.09 | no |
| k7_m3 | 345 | 112 | −3 | 40 | 69 | 190 | 1.10 | +1.01 | no |
| k7_m10 | 345 | −38 | +3 | 48 | −83 | 33 | 0.92 | −4.36 | no |
| k3_m0 | 345 | 34 | −2 | 32 | 0 | −11 | 1.00 | −0.92 | no |
| k3_m3 | 345 | 93 | −7 | 34 | 52 | 94 | 1.10 | +0.56 | no |
| k3_m10 | 344 | −81 | +1 | 41 | −121 | 5 | 0.86 | −5.36 | no |

Every k does worse with m = 10 than with m = 3: holding 10 days past the unlock gives back profit. That fits the leads' story of "selling before, relief after", but it was not tested as a rule.

k30_m3 by split and year:

| split / year | n | net mean | median | PF | ex top-3 | BTC short, same window | alt-basket short | excess vs basket (t) |
|---|---|---|---|---|---|---|---|---|
| train, all | 247 | +275 | +875 | 1.24 | +5.00 | −474 | +63 | +274 (1.73) |
| 2020 | 1 | −1798 | | | | | | |
| 2021 | 15 | −824 | −547 | 0.52 | −2.24 | −1205 | −2685 | +1816 (2.36) |
| 2022 | 29 | +225 | +791 | 1.20 | −0.61 | +773 | +989 | −704 (−1.45) |
| 2023 | 53 | −347 | +144 | 0.73 | −2.94 | −1091 | −632 | +331 (1.33) |
| 2024 | 87 | +371 | +936 | 1.34 | +1.72 | −544 | +174 | +173 (0.65) |
| 2025 H1 | 62 | +993 | +2198 | 2.03 | +4.41 | −258 | +767 | +453 (1.33) |
| **validation (run once)** | 114 | **+515** | +1149 | **1.49** | +3.98 | +515 | +695 | **+7 (0.03)** |
| 2025 H2 | 75 | +241 | +875 | 1.20 | −0.09 | +268 | +585 | −182 (−0.59) |
| 2026 Q1 | 39 | +1042 | +1724 | 2.43 | +2.67 | +991 | +907 | +370 (0.94) |

**Validation detail:**
- Gross +702 bp, funding −118 bp (shorts paid in the bear market), costs 69 bp.
- 62% of trades won; t on net = 1.86.
- 28 stops out of 114 trades.
- 56 events were skipped for overlap and 1 because its exit fell beyond the data.

**Sensitivities on validation (reported, not selected on):**

| subset | n | net mean (bp) | PF |
|---|---|---|---|
| HL-listed (current HL meta) | 87 | +267 | 1.24 |
| size ≥ 5% | 52 | −44 | 0.97 |
| team-majority unlocks | 52 | −4 | 1.00 |

On train, size ≥ 5% was +494 bp. On validation the "bigger unlocks and team unlocks hurt more" claim from the leads does **not** hold.

## Forward-test speed

- **Validation:** 171 qualifying events (≥ 2%) in 39 weeks, about **4.4 a week**.
- **Today's schedule, 2026-10-05 to 2027-03-31:** 99 events on 30 symbols, about **3.9 a week**.
- Many coins vest monthly, and a 33-day hold skips every other event. That gives about 2.5–3 trades a week.
- 50 trades would take about 4–5 months, plus 33 days for the last trades to close.

## Leads (document modality, unverified practitioner claims)

- [Keyrock, "From Locked to Liquidity: What 16,000+ Token Unlocks Teach Us"](https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/). Its claims, as summarised by search:
  - 90% of unlocks create negative pressure;
  - the effect starts about 30 days before the unlock;
  - team unlocks are worst, at about −25%.
- [BeInCrypto summary of the Keyrock study](https://beincrypto.com/keyrock-research-token-unlocks/).
- [Tokenomist, cliff-unlock glossary](https://www.tokenomist.ai/learn/glossary-term/cliff-unlock).
- [Crypto Briefing on Tokenomist's monthly unlock totals](https://cryptobriefing.com/2b-token-unlocks-august-tokenomist/).

Our data matches the leads' sign and their 30-day lead time. It does not show the effect beyond market and coin drift.
