# Parent-meme short at copycat-wave peak (H-NARRPEAK, agent narrpeak, 2026-10-05): BLOCKED on data, no P&L

**Bar (not reached):** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## Idea

Copycat pump.fun launches that reuse a parent meme's ticker (TRUMP, PEPE, DOGE, PENGU, POPCAT and others) would act as a
retail-attention gauge. When a parent's daily copycat count spikes and then turns down, short the parent's perp for
1-7 days (with an alt-basket-hedged variant). Source: `sources/leads/documented_edges_round12.md`, idea 3.

## Gate: a complete point-in-time history of daily copycat counts, 2024-2026

The brief's order was to check completeness first and stop if the history cannot be reached. **It cannot be reached.**
No pre-registration was written, and no prices, splits or outcomes were opened.

`research/observations/evidence_narrpeak_counts.json` holds the details. The raw responses are in
`data/raw/web/narrpeak/`: 69 files, about 6 MB, from about 75 requests spaced 3-4 s apart.

### What the public pump.fun API does

| endpoint | behaviour |
|---|---|
| `frontend-api-v3/coins?searchTerm=X&sort=created_timestamp` | Returns 200, but **ignores `searchTerm`**: it lists the newest coins on the site. The round-12 lead was right that this returns 200 with `created_timestamp`, but the path is not a search. |
| `frontend-api-v3/coins/search` | 404 |
| `frontend-api-v3/coins/search-v2?searchTerm=X&sort=created_timestamp&order=DESC` | Real search, but **fuzzy**: "PENGU" also matches "Penguin" and "P/ACC Penguin Acceleration". A few relevance hits are pinned at the top whatever their date. `limit` is capped at 50. **`offset` is clamped at 500**: offsets 500, 550, 600, 1000, 2000, 5000 and 10000 return the identical page. At most about 550 coins can be reached per term and sort order. |
| time parameters (`createdBefore`, `before`, `cursor`, `endTimestamp`, ...) | ignored |
| `frontend-api`, `frontend-api-v2`, `advanced-api-v2` | 530 / 403 / 530 |

`search-v2` also mixes in other launchpads and chains: `raydium_launchpad`, `meteora_dbc`, EVM addresses, and coins
with no program. Any pump-only count has to filter on `program == 'pump'`.

### How far back the newest ~550 results reach

| term | oldest reachable created time (excluding pinned hits) |
|---|---|
| TRUMP | 2026-10-04 03:39 UTC (about 1 day) |
| PENGU | 2026-09-30 21:17 UTC (about 4.6 days; most hits are fuzzy "Penguin" matches) |
| POPCAT | 2026-08-17 (about 7 weeks) |

The train window (up to 2025-06-30) and the validation window (2025-07-01 to 2026-03-31) are reachable for **no**
parent ticker. Sorting oldest-first only adds the oldest ~550 matches, which leaves the 2024-2026 middle out of
reach.

### Overlap with `curve_creates`

**Method:**
- Recorder span: 2026-10-01 12:17 to 2026-10-05 03:40 UTC.
- Match rule: the ticker as a whole word in the name or symbol.
- Compared window: the recorder span, clipped to how far back the API reaches.

| term | API word-matches in window (all launchpads) | recorder | in both | recorder-only | API-only with program = pump |
|---|---|---|---|---|---|
| PENGU | 74 | 19 | 19 | 0 | 12 |
| POPCAT | 19 | 5 | 5 | 0 | 1 |
| TRUMP (Oct 4-5 only) | 370 | 200 | 198 | 2 | 46 |

Per day, PENGU had 1/3/8/4/3 recorder copies on Oct 1-5, and every one of them is in the API. Most API-only pump coins
were created inside recorder gaps (more than 120 s with no recorded create).

**What the overlap shows:**
- **Recall is good.** Within the window the API can reach, its pump-program results cover the recorder's coins
  (24 of 24 for PENGU and POPCAT, 198 of 200 for TRUMP).
- **Depth is the failure.** Only about 550 results can be reached per query.

## Verdict

**Blocked: no complete point-in-time copycat-count history is reachable**, so the hypothesis cannot be tested
historically.

## Not tried

- **Dune, Bitquery or Flipside:** no keys in the environment.
- **A full Solana RPC scan** of pump-program create instructions since 2024: hundreds of millions of signatures, far
  beyond the 200 MB and politeness budget.

## What would unblock it

- **An indexed on-chain source**, for example a Dune query on pump.fun create events grouped by day and ticker. That
  would need the user to supply an API key.
- **Forward recording.** Keep `curve_creates` running and score the hypothesis prospectively. At about 2-6 events a
  week across about 13 parents, n = 50 takes roughly 3-6 months of recording.

Correction to round 12: the "`/coins?searchTerm` returns 200" lead does not search. Its exhaustiveness is now
**resolved as no** (`search-v2` is capped at about 550 results per query).
