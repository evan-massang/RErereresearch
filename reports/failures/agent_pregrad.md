# Pre-graduation exit and launch-metadata socials (agent pregrad, 2026-10-04): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.
The bar must hold at both tips (0.001 and 0.01 SOL per transaction).

## Sources (leads, `document` modality)

- **B2, arXiv 2602.14860.** Liquidity is thinner just after migration, so sell on the curve before completion (about 85 real SOL).
- **B3, arXiv 2607.02823.** Tokens whose metadata lists a Telegram link graduate 8.9× more often. The paper reports graduation lift only; it makes no claim about profit.

## What was tested

The rules were fixed before any outcome was computed (`scripts/research/pregrad_build.py`). The grid has **34 configs**.

| idea | entry decision | exit | filter | configs |
|---|---|---|---|---|
| A | first trusted print with real SOL ≥ E, for E = 30, 40, 50 | X = 70, 75, 80; stop 30%; time stop 900 or 3600 s | all non-Mayhem tokens | 18 |
| B | E = 30 or 50 | X = 75; stop 30%; time stop 900 or 3600 s | Telegram link (`tg`), or at least 2 of Telegram, X and website (`soc2`) | 8 |
| C | launch + 2 s (allows the metadata fetch), or real SOL first ≥ 10 | X = 75; stop 30% or 50%; time stop 3600 s | `tg` or `soc2` | 8 |

The exit sells when a print shows real SOL ≥ X, or price at or below entry × (1 − stop), or when the time stop is reached.

**Fills:**
- exact constant product, 0.5 SOL, 1.25% fee per side;
- each fill is at the trusted curve state 1 s after the decision print;
- if the curve completes before the exit fill, the tokens are sold into the logged PumpSwap pool state (counted as `*_amm`);
- if the curve completes before the entry fill, there is no trade.

**Hygiene:**
- trusted states only (|vsol − rsol − 30| < 0.01);
- tokens confirmed non-Mayhem only (`is_mayhem == False`): 18,639 Mayhem and 12,432 unflagged tokens are dropped;
- the token's creation, the decision and the full window up to fill + time stop + 1 s must lie inside one gap-free recording segment (no gap over 60 s) and inside one allowed split;
- nothing in the off-limits windows is read.

## Metadata coverage (non-Mayhem creates)

| split | creates | metadata cached | Telegram | ≥2 socials |
|---|---|---|---|---|
| train | 18,112 | 12,228 (67.5%) | 494 | 5,795 |
| validation | 30,864 | **555 (1.8%)** | 3 | 43 |

Ideas B and C could not have been validated in any case: the validation day has almost no cached metadata.

## Result: FAIL on train (validation not looked at)

**No config passes on train.** Full numbers are in `research/observations/evidence_pregrad_train_20261004.json`.

The best configs at a 0.001 SOL tip:

| config | trades | net SOL | PF | without the best 3 |
|---|---|---|---|---|
| C, tg, real SOL ≥ 10, X75, stop 30% | 46 | +2.62 | 1.37 | **−5.27** |
| B, tg, E30, X75, 3600 s | 18 | +0.41 | 1.16 | −2.28 |
| A, all, E50, X70, 3600 s (best A) | 280 | −7.71 | 0.75 | −9.09 |
| A, all, E40, X70, 900 s | 483 | −10.56 | 0.84 | −12.81 |

The only positive config with a large sample is C, tg, real SOL ≥ 10:
- it has fewer than 50 trades;
- three trades (+2.85, +2.64 and +2.41 SOL) carry the whole result;
- 33 of its 46 trades are stopped out.

**All 18 A configs lose.**
- Stops dominate. A stopped trade averages about −0.20 SOL (−40%) after slippage on a falling curve, against about +0.18 SOL for a target exit from E50 to X70.
- From E50, 128 of 280 trades (46%) reach X70, and 40.7% of trades are winners. That is below breakeven.
- Going in earlier (E30) makes this worse: only 15–18% of trades reach the target.

**The socials filter selects poorly beyond Telegram.**
- `soc2` (mostly X plus website) loses more than the unfiltered set.
- `tg` tokens are too few for the bar.

## Interpretation

The pre-graduation exit removes migration risk, but the entry side carries no edge: the chance of reaching 70–80 real SOL from 30–50 is priced in. This agrees with B1's breakeven result, and with H8, which held positions through migration.

The Telegram lift (B3) may be real for graduation, but on our data it does not turn into enough profitable trades. The sample is 46 trades, and the result rests on 3 outliers.

## Files

- `scripts/research/pregrad_build.py`
- `scripts/research/pregrad_eval.py`
- `research/observations/evidence_pregrad_train_20261004.json`
