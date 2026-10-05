# Creator funding source (agent dev_funding, 2026-10-05): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

**Verdict: FAIL.** The hypothesis is wrong at the first step: on train, CEX-funded or aged creators do **not**
launch tokens that migrate more often. None of the 30 pre-declared configs passed on train (all 30 lose at both tip
levels), so validation outcomes were **not examined**. The holdout and anything from 1791072000 on were never queried.

- **Scripts:** `scripts/research/dev_funding_fetch.py` (sample + RPC), `dev_funding_build.py` (features, outcomes),
  `dev_funding_eval.py` (lift, grid).
- **Evidence:** `research/observations/evidence_dev_funding_lift_train_20261005.json`,
  `research/observations/evidence_dev_funding_train_20261005.json`.
- **Raw RPC cache:** `data/raw/web/rpc_funding/` (`creators/`, `tx/`, `funders/`, the sample parquet, and the
  CEX list). About 390 MB, so check its size before committing it.

## Hypothesis

Launches whose creator wallet was funded from an exchange hot wallet, or which is old (a real person), produce better
tokens than launches from fresh wallets funded by a farm. The funding source is not in our tape. It comes from the
public Solana RPC.

## Data and point in time

**Sample.** The sample was drawn with seed 20261005 and fixed before any outcome was computed:
- uniform random launches from `curve_creates`;
- not Mayhem Mode: flag False in `data/processed/mayhem_flags.parquet`, with unknown flags excluded;
- create time + 1 s + 1800 s inside one gap-free segment (no gap over 60 s) and inside the launch's split.

That gives **2,500 train launches** (1,322 from Oct 1 before the holdout, 1,178 from Oct 2) and **1,200 validation
launches**. Together they come from 2,317 distinct creators. Migrations were not oversampled and nothing is reweighted.

**RPC.** Calls went to `api.mainnet-beta.solana.com` through the proxy.
- **Pace:** at most 4 requests/s, with backoff on 429 and -32019 responses.
- **Concurrency:** the endpoint answered each call in 5–12 s, so 10 threads shared that global pace.
- **Result:** all 2,317 creators were fetched, and the 17 transient errors were retried.

**Point in time.**
- `getSignaturesForAddress(creator, before=<create signature>)` was paged back to the wallet's first signature, capped
  at 5,000 signatures. For each launch, only signatures with slot < create slot are used.
- The earliest successful transaction is fetched with `getTransaction` (up to 3 of the oldest are tried). The funder
  is the source of the largest system transfer or createAccount into the creator.
- `getSignaturesForAddress(funder, before=<funding tx>, limit=1000)` gives the funder's earlier activity.
- The in-sample funder graph counts only fundings dated before the launch.

## Funder classes (declared before outcomes; first match wins)

| class | definition | train launches |
|---|---|---|
| cex | funder in the Dune spellbook `cex_solana_addresses` list | 219 (157 Binance, 22 Coinbase, 20 KuCoin, …) |
| whale | funder held ≥ 1,000 SOL just before the funding tx (unlabelled exchange or custodial) | 239 |
| farm | funder funded ≥ 2 other sampled creators before the launch, or had ≥ 500 signatures in the prior 24 h | 359 |
| fresh | funder's first signature ≤ 7 days before the funding | 502 |
| other | an aged, low-activity funder | 486 |
| unknown | creator has ≥ 5,000 prior signatures (613) or no transfer was found | 695 |

**CEX source.** Dune Analytics spellbook,
`dbt_subprojects/hourly_spellbook/models/_sector/cex/addresses/chains/solana/cex_solana_addresses.sql`, at commit
`5f54fcf41b34b199c4c4ed1775059ab2d273f466`. Of its 166 entries, the 130 that decode as 32-byte Solana keys were
kept; 36 malformed or non-Solana entries were dropped. The copy is `data/raw/web/rpc_funding/cex_hot_wallets_dune.json`.

**Limitation.** The list misses current hot wallets. For example, a 40,900 SOL durable-nonce withdrawal wallet,
`iGdF…dwu`, is not in it. The `whale` class is the fallback for those.

**Creator classes:**

| class | definition | train launches |
|---|---|---|
| fresh | first signature < 1 day before launch (median age 11 min) | 900 |
| young | 1–30 days | 548 |
| aged | ≥ 30 days | 404 |
| heavy | ≥ 5,000 prior signatures (serial launchers) | 613 |
| unknown | no usable history | 35 |

## Step 1: migration lift (train)

**Correction found first.** 33 of the 57 train "migrations" complete **inside the create transaction** (time to
complete under 1 s): the creator buys the whole curve in a bundle. 32 of those 33 are fresh creators. These cannot be
traded, so the lift below uses the 24 tradable migrations (base rate 0.96%). Counting them would have shown a spurious
2× "fresh creator" lift.

| group | n | tradable migration | lift | 95% CI (creator bootstrap) |
|---|---|---|---|---|
| all | 2,500 | 0.96% | 1.00 | 0.58–1.36% |
| cex-funded | 219 | 0.91% | 0.95 | 0–2.3% |
| cex or whale | 458 | 0.66% | 0.68 | 0–1.6% |
| aged creator (≥ 30 d) | 404 | 0.50% | 0.52 | 0–1.3% |
| "real" (exch or aged, not farm) | 674 | 0.74% | 0.77 | 0.15–1.5% |
| not farm, not fresh, not fresh creator | 529 | 0.57% | 0.59 | 0–1.3% |
| farm-funded | 359 | 0% | 0 | — |
| heavy (≥ 5,000 prior sigs) | 613 | 1.96% | 2.04 | (not in the grid) |

**What this shows:**
- Exchange-funded and aged creators migrate no more often than the base. The "real person" hypothesis has no lift.
- Farm-funded launches never migrated in this sample. Excluding them raises the base only slightly.
- CEX-funded launches reach 2× peaks more often (25% vs about 15%), but they do not migrate more.
- The only group with a lift is the serial launchers. That is the H7 / good-dev signal, which already failed on costs.

## Step 2: trade grid (train)

**Grid: 30 configs**, declared in `dev_funding_eval.py` before any return was printed:
- **5 filters:** cex, exch, aged, real and notfarm (definitions above).
- **2 entries:**
  - L1: decision at create, fill at the first state at or after create + 1 s; the initial curve state counts when no
    trade has happened yet;
  - M2: the first clean print at 2× the initial price within 600 s, filled 1 s later.
- **3 exits:** TP50/SL20 with a 300 s maximum hold, TP100/SL30 with 1800 s, and TP200/SL50 with 1800 s.

**Fills.** The `event_studies.rt()` model:
- exact constant product;
- 0.5 SOL per trade, 1.25% fee per side, 1 s latency;
- completion cut;
- clean states only (|vsol − rsol − 30| < 0.01), and the entry state must be clean.

**Tips:** 0.001 SOL per transaction is the primary case and 0.01 the sensitivity. Each trade has two transactions.

**Result: all 30 configs lose at both tips.** 0 passed, so validation was not opened.

| config (0.001 tip) | n | net SOL | SOL per trade | PF | without best 3 |
|---|---|---|---|---|---|
| best per trade: real, L1, TP50/SL20 | 669 | −15.0 | −0.022 | 0.61 | −19.2 |
| best PF: cex, L1, TP50/SL20 | 216 | −5.6 | −0.026 | 0.63 | −7.1 |
| aged, L1, TP100/SL30 | 403 | −10.9 | −0.027 | 0.58 | −14.1 |
| cex, M2, TP50/SL20 | 51 | −5.1 | −0.100 | 0.30 | −6.1 |
| reference, unfiltered L1, TP50/SL20 | 2,467 | −81.9 | −0.033 | 0.43 | −86.1 |

**Why the filters do not help.** They improve the unfiltered launch entry by only about 0.01 SOL per trade. Even with
the tips and the 1.25% protocol fee (about 0.0125 SOL per round trip) added back, the best filtered config is still
about −0.008 SOL per trade.
The 2× milestone entry is worse, at −0.06 to −0.19 SOL per trade.

## Conclusion

The creator's funding source is real information that is absent from the tape, but it does not separate launch
quality. CEX-funded and aged creators are not better launchers here. Farm funding marks bad launches, but excluding
them leaves a universe that still loses. Instant bundle completions are a trap: they make fresh wallets look 2× better
if they are not separated out. The family is closed. A cleaner CEX list would not change the result, because cex and
whale together still show no lift.
