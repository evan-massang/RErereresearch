# H-LPSELL (passive PumpSwap LP) and H-CLOCK (clock-time bursts): both FAIL on train (agent lpsell_clock, 2026-10-05)

**Verdicts.**
- **H-LPSELL: FAIL on train.** None of the 18 pre-declared configs passed the bar. Every config loses at both tips. Validation was **not examined**.
- **H-CLOCK: FAIL at step 0 (descriptive).** Second 0–5 and the quarter-hour marks carry no more flow than their neighbours on either train day. So, under the pre-declared rule, no trading rule was tested and validation was not examined.

The holdout (1790882100–1790899200) and anything at or after 1791072000 were never loaded. The database was opened read-only.

**Files.**
- **Scripts:** `scripts/research/lpsell_sim.py` and `scripts/research/clock_describe.py`.
- **Evidence:** `research/observations/evidence_lpsell_train.json` and `research/observations/evidence_clock_describe_train.json`.

Source idea: `sources/leads/documented_edges_round3.md`, ideas 2 and 4.

## H-LPSELL

### Facts verified on train data
1. **True quote reserve = `pool_sol_logged` + a per-pool offset.**
   - The exact sell identity `sol = R_s*tok/(R_t+tok)` gives an offset of 17.5845 SOL for migrated pools. A few odd pools seeded with a few SOL have an offset of 0, so the offset is measured per pool.
   - **The offset is real SOL:** `amm_pools.quote_in` is 84.990 SOL at creation, while the first logged reserve is 67.406.
2. **The LP fee rate is measured on-chain from reserve chaining, not assumed.** For consecutive sells whose token reserve chains exactly, the next pre-trade quote reserve equals `R_s - sol + lp*sol`.
   - **lp = 20.0 bps** in every `fee_bps` tier from 30 to 120.
   - **lp = 2.0 bps** in the 125-bps tier (97% of 256k sells). That is the lowest-market-cap tier, so early pools pay LPs only 0.02%.
3. **Public docs agree on the standard split.** Before dynamic fees the split was 0.20% LP, 0.05% protocol and 0.05% creator, and "protocol and LP fee allocations remain unchanged" under Dynamic Fees V1 ([madeonsol](https://madeonsol.com/blog/pumpfun-revenue-sharing-pumpswap-fees-creators), [medium/jump_bit](https://medium.com/@jump_bit/pumpswap-lp-fees-explained-how-to-earn-125-day-from-your-memecoin-pool-6cf6b2c2a918); `document` leads). The official tier table is an image (`pump-fun/pump-public-docs` `docs/FEE_PROGRAM_README.md`, `fees.png`) and was not readable as text. The 2 bps tier is our own measurement.

### Method
**Fee accounting.** It is exact and does not need LP-supply data.
- Per unit of liquidity, sqrt(k) grows only through swaps, by `sqrt(k_pre(i+1)/k_pre(i))` on exactly chained steps (median chain rate 99.9%).
- A broken chain step, from a liquidity event or a missed swap, is credited with no fee growth.
- **Check:** on 17 sampled positions this growth G matched an independent estimate, Σ lp·sol/(2R_s), with a correlation of 0.999999.

**Position.**
- **Entry:** 0.5 SOL in total. Part is swapped into the token with an exact fill and the fee on top, priced at the conservative higher-priced state. The rest is deposited balanced.
- **Value at exit:** `L·G·sqrt(P)` SOL plus `L·G/sqrt(P)` tokens.
- **Exit:** withdraw, then sell the tokens through the pool net of our withdrawal, paying the fee, at the conservative lower-priced state.
- **Stop:** exit when a post-trade mid falls to 0.6× the entry mid or lower.
- **Costs:** 4 transactions × (tip + 5,000 lamports).
- **Benchmarks:** cash (0), and buying and holding 0.5 SOL of the token over the same window.

**Grid (18 configs):** pool age at entry A ∈ {10 min, 1 h, 4 h} × hold H ∈ {1 h, 4 h} × trailing-1-h volume/TVL ≥ V ∈ {0, 2, 5}.
- **Eligibility:** true reserve ≥ 50 SOL at entry, and the pool traded within the last hour.
- **One position per pool.** Entry and exit must lie in the same train segment.

### Results (train, 0.001 SOL tip)

| config | n | net SOL | PF | net without best 3 | win | mean fee growth | median price ratio | stopped | hold-token net |
|---|---|---|---|---|---|---|---|---|---|
| A10m H1h V≥5 (best PF) | 90 | −5.15 | 0.55 | −8.34 | 18% | +1.10% | 0.58 | 79% | +1.52 |
| A10m H4h V≥5 | 72 | −6.06 | 0.40 | −9.45 | 10% | +1.46% | 0.58 | 85% | −1.26 |
| A1h H1h V≥0 | 127 | −9.30 | 0.14 | −10.28 | 23% | +0.24% | 1.00 | 28% | −11.32 |
| A10m H1h V≥0 (largest n) | 321 | −49.23 | 0.16 | −52.44 | 17% | +0.51% | 0.53 | 72% | −53.66 |

- **Configs passing the bar: 0 of 18.** At a 0.01 SOL tip every config loses more.
- Configs at A = 4 h have n ≤ 41, all losing.

### Reading
- **LP fee income is small.** Even in the highest-turnover pools (V ≥ 5) it averages +1.1% over 1 h and +1.5% over 4 h. The young pools that turn over most sit mostly in the 125-bps tier, which pays LPs only 2 bps.
- **Drift dominates.** Over the same window the median surviving pool trades at about 0.58× its entry price. A balanced LP loses about half of that move plus impermanent loss.
- **The LP gives up the upside.** In the best-PF config, the hold-token benchmark (+1.52 SOL, PF 1.08, no stop) did *better* than the LP (−5.15). Here the LP gave away the right tail that the lottery literature says buyers overpay for.
- In these pools the overpricing shows up as negative drift, not as fee income. A passive LP holds half its value in the token and so eats that drift.
- **The idea is closed for 1–4 h holds in post-migration pools.**

## H-CLOCK (step 0, train only)

**Clock and data.**
- The clock is the on-chain block time `ts`.
- **Curve:** trusted states only, with Mayhem mints excluded.
- **AMM:** all PumpSwap swaps.

**Metrics.** Buy count, buy SOL, distinct buyers, Σ|log price impact| and net signed impact, each by second-of-minute and by minute-of-hour.
- Each cell is normalised by its hour's mean.
- Only full-coverage hours are kept. The recorder has gaps: day 1 has 8 hours by second and 6 by minute; day 2 has 10 and 7.

**Pre-declared rule:** continue only if the mark exceeds 1.3× its neighbours on both days.

| ratio (mark / neighbours) | curve buy n d1 / d2 | curve buy SOL d1 / d2 | AMM buy n d1 / d2 | AMM buy SOL d1 / d2 |
|---|---|---|---|---|
| second 0–5 vs seconds 54–59 and 6–11 | 1.02 / 1.03 | 1.07 / 0.99 | 0.98 / 0.97 | 0.88 / 0.92 |
| quarter-hour minutes vs ±1–3 min | 1.03 / 0.99 | 1.01 / 0.97 | 0.91 / 1.03 | 0.79 / 0.93 |
| 5-min marks vs other minutes | 0.98 / 0.99 | 0.99 / 1.00 | 0.94 / 1.00 | 0.94 / 1.01 |

- **The peak positions are unstable across days.** For example, curve buy SOL peaks at second 25 on day 1 and second 21 on day 2.
- Creates (by `recv` second) give ratios of 0.95 and 1.00.
- **Top-of-hour flow is *lower* than average**, at 0.62–0.90 of the hourly mean for AMM buy SOL and curve buy SOL.
- Net signed impact by second shows no sign pattern that repeats across days.

**Conclusion.** The lead's mechanism (cron and call-channel bursts at clock marks) is not visible in this tape. No rule was built, and no validation data was examined.
