# DexScreener paid orders ("DEX paid" profile and boosts): FAIL on train (agent dex_paid, 2026-10-05)

**Verdict: FAIL.** None of the 24 pre-declared configs passes the bar on train (at least 50 trades, net > 0 after
all costs, PF > 1.2, net > 0 without the best 3 trades). This holds at all three assumed visibility lags. As the rules
require, validation (Oct 3) was **not examined**: `dex_paid_validate.py` exits before loading it when nothing passes.

- **Evidence:** `research/observations/evidence_dex_paid_train_20261005.json` (full grid, both tips, all lags, control).
- **Scripts:** `scripts/research/dex_paid_fetch.py` (backfill), `dex_paid_sim.py` (rule and fills),
  `dex_paid_validate.py` (gate).
- **Raw data:** `data/raw/web/dexscreener_orders/{mint}.json`, the verbatim responses with fetch time. 2,887 mints are
  cached: all 2,727 train-sample mints, plus about 160 validation mints. The fetch was stopped once train failed.

## Sample and paid orders

- **Frame:** every mint whose trusted curve state (|vsol − rsol − 30| < 0.01) first reached real SOL ≥ 20 inside the
  train window. That is 2,727 mints; 2,331 were created inside the recording, and 3 are Mayhem.
  - The frame is a point-in-time milestone, not an outcome.
  - Each mint was queried once at `api.dexscreener.com/orders/v1/solana/{mint}`, at about 55 requests a minute.
- **Paid rate (approved `tokenProfile`):** 200 of 2,331 mints (8.6%). It is 23.8% among mints that completed the curve
  and 4.0% among those that did not.
  - 30 mints had any boost.
  - Among payers that completed, 32% paid before completion.
  - Only 3% paid before reaching 20 SOL.
- **Caveat:** the endpoint shows orders as they are *now*. Whether DexScreener drops orders or tokens (for example
  rugged ones) is unknown, so the frame could carry survivorship bias.

## Rule (point in time)

- **Trigger:** T = max(P + LAG, t20).
  - P is the payment time of the first approved `tokenProfile` order. In variant PB, it is the first boost if that
    comes earlier.
  - LAG is the assumed visibility lag: 120 s in the main run, with 30 s and 600 s as sensitivity checks.
  - t20 is the time of the 20-SOL milestone.
- **Filters:** token age at T is at least 60 s; no Mayhem tokens; P and T fall in the same allowed segment; the exit
  horizon ends before that segment ends.
- **Entry:** 0.5 SOL at T + 1 s.
  - **Curve:** an exact curve fill with a 1.25% fee per side, only when real SOL ≤ 75.
  - **PumpSwap** (if the token has migrated): an exact constant-product fill using the conservative `amm_flow_lib`
    states. The reserve is the logged value + 17.585, and the fee is `fee_bps`.
- **Exits:**
  - take-profit / stop-loss of 30/15, 50/20 or 100/30, checked on every later print and filled 1 s later;
  - otherwise at the maximum hold of 300 s or 1,800 s.
  - A curve position still open at migration continues on PumpSwap. It is not sold at the last curve price.
- **Tips:** 0.001 and 0.01 SOL per transaction, two transactions.
- **Grid: 24 configs.**
  - Profile trigger: 3 universes (all, curve, amm) × 3 exits × 2 holds = 18.
  - Profile-or-boost trigger: the "all" universe only = 6.

## Results (train, lag 120 s, 185 events: 93 on the curve, 92 on PumpSwap)

| config | n | net SOL (0.001 tip) | PF | net without best 3 | net at 0.01 tip |
|---|---|---|---|---|---|
| curve tp30/sl15, 300 s (best) | 93 | −0.56 | 0.89 | −1.32 | −2.23 |
| curve tp30/sl15, 1,800 s | 88 | −1.37 | 0.76 | −2.14 | −2.95 |
| curve tp50/sl20, 300 s | 93 | −1.95 | 0.71 | −2.89 | −3.62 |
| amm (best: tp100/sl30, 1,800 s) | 91 | −4.47 | 0.63 | −6.02 | −6.10 |
| all (best: tp30/sl15, 300 s) | 185 | −7.19 | 0.47 | −7.95 | −10.52 |

- **Lag sensitivity** (best curve config at each lag, 0.001 SOL tip):
  - 30 s: tp50/sl20, 300 s, n 100, −0.42 SOL, PF 0.94, −1.36 without the best 3;
  - 600 s: tp100/sl30, 300 s, n 81, −0.80 SOL, PF 0.82.
  - All 24 configs lose money at every lag.
- **PumpSwap entries after a payment are strongly negative:** PF 0.2–0.6 and a median of −9% to −16% per trade. The
  payment does not stop the usual post-migration bleed.
- **Curve entries are roughly break-even before costs:** about −0.8% per trade after about 2.5% in fees. Even if the lag
  were zero, the edge would not cover the fees and tips.
- **Descriptive control:** all sample tokens entered at the 20-SOL milestone (age ≥ 60 s, n ≈ 370) also lose,
  PF 0.55–0.65.

## Reading

Paying for a DexScreener profile is a selection marker. Payers graduate far more often (24% vs 4%). But this is
known almost entirely *after* the price move: a median payment comes once the token has already run. Once the order
is public, the excess return is gone or negative.

**Not measured:** the real visibility lag, and whether the per-mint endpoint shows pending orders before approval. A
live lag measurement would be needed before any freeze. Even the optimistic 30 s lag fails on train, though, so this
family is closed unless a different trigger (for example the pending-order state) is shown to lead the payment
publicly.
