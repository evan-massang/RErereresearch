# Creator fee-claim events (H-CLAIM, idea 5): NOT TESTABLE in train/validation, 0 events (agent fee_claim, 2026-10-05)

**Verdict: FAIL for lack of data, not a statement about the edge.** Every claim event we can recover sits in the
forward window. Train and validation contain **0** decodable claim events. No backtest was run, no grid was
declared against data, and **no price or return after any claim was computed or looked at**. The Oct 5 files are
used for event counts only, as the split rules require.

## Discriminators (source: public pump.fun IDLs)

Source: `https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/idl/pump_amm.json` (program
`pAMMBay6…`) and `.../idl/pump.json` (program `6EF8rrec…`). Fetched 2026-10-05. The script recomputes
`sha256("event:<Name>")[:8]` and asserts that it equals the IDL bytes.

| Event | Program | Discriminator | Fields |
|---|---|---|---|
| `CollectCoinCreatorFeeEvent` | PumpSwap | `[232,245,194,238,234,218,58,89]` = `e8f5c2eeeada3a59` | ts i64, coin_creator, coin_creator_fee u64, vault_ata, dest token account |
| `CollectCreatorFeeEvent` | pump (curve) | `[122,2,127,1,14,191,12,175]` | ts, creator, creator_fee u64, quote_mint |
| `DistributeCreatorFeesEvent` | pump (fee sharing) | `[165,55,129,112,4,179,202,40]` | ts, mint, bonding_curve, sharing_config, admin, shareholders vec, distributed u64, quote_mint |

**Important for any future rule:** the PumpSwap claim event has **no pool or mint**. There is one creator vault per
creator, shared by all of that creator's pools. A claim is a *creator* event. It can be tied to a token only
through `coin_creator` in Buy/SellEvent (offset 312), and unambiguously only when the creator has one pool.
`DistributeCreatorFeesEvent` (fee-sharing tokens) does carry the mint.

## What data exists

- `pumpswap_raw` holds only three files: `20261005_01_420`, `20261005_01_833` and `20261005_02_833`. They cover
  recv 1791162000 to about 1791168793, which is Oct 5 01:00 to 02:53 UTC, with a gap of about 7.5 min at the
  recorder restart. That is **≥ 1791072000, all forward**. The Oct 1–4 raw files were deleted after the swaps
  were decoded, and `load_amm` kept only Buy/Sell/CreatePool. Claim events from Oct 1–4 are therefore lost.
- `pump_curve` is stored decoded. The recorder keeps only trade/create/complete and drops every other pump event
  (`decode=True` → `continue`), so **curve claims were never recorded**. We checked a file: it holds only `trade`,
  `create` and `complete`.
- `pump_live`, `pumpportal` and `launchlab_raw` carry no claim events.

## Descriptive counts (Oct 5, about 1.75 h of coverage, forward window, counts only)

From `research/observations/evidence_fee_claim_counts.json`, produced by `scripts/research/fee_claim_decode.py`.
The current file was still being written when this ran.

- **`CollectCoinCreatorFeeEvent`: 687** (347 in the 01:00 hour and 340 in the 02:00 hour, partial), by **370
  creators**. 85 creators claimed 2 or more times, and one claimed 21 times. That rate is roughly 9k a day.
  - 460 of the 687 use the WSOL vault ATA, a check we verified by deriving the PDA. The rest use other quote mints
    or token programs, so their amounts are not SOL.
  - Amount quantiles (raw u64 / 1e9, all claims): median 0.017, p75 1.2, p90 5.9.
  - 0 claims had the creator selling in the same transaction.
- **Pool age at claim:** 124 claims could be tied to a pool created while recording. Minimum pool age at the claim:
  8 under 10 min, 5 at 10–60 min, 22 at 1–6 h, 7 at 6–24 h, and 82 over 24 h (median about 28 h). Early claims
  right after migration are **rare**. Most claims come from creators of tokens that are a day or more old.
- **Curve `CollectCreatorFeeEvent` seen in PumpSwap-mentioning transactions:** 456 events from 272 creators, with
  a median of 0.059 SOL. 140 of them share a transaction with an AMM claim, which looks like a "claim all" action.
  This is a **partial view**: curve-only claims never mention PumpSwap.
- **`DistributeCreatorFeesEvent`:** 2,215 events over 689 mints. Of these, 691 distributed 0, with a median of
  0.0046 SOL. Repeats on one mint run every 0.5–1.5 min, which looks like a keeper bot, so they are **not a creator
  decision**. Shareholder counts were 1 (1,399), 2 (243), 3 (566) and 4 (7). For 61 mints that migrated while
  recording, the first distribution came a median of 25 h after the pool was created.

## Why the hypothesis is weak even with data

- Early-claim fee farmers are rare: 13 of the 124 attributable claims came in the first hour after migration.
- The pool cannot be attributed for creators with several pools.
- Distribution events are automated and periodic, not a signal.
- Most claims are tiny: half are below 0.02 SOL.

## Recommendation (forward-only data collection)

Do not edit `pipeline/recorder.py` from this agent. The proposed change is:

1. In `chain_logs` for the pump program, keep the `CollectCreatorFeeEvent` and `DistributeCreatorFeesEvent`
   discriminators (and `SetCreatorEvent` / `MigrateBondingCurveCreatorEvent`) as decoded rows instead of dropping
   them.
2. In `market.load_amm`, also decode `CollectCoinCreatorFeeEvent` (layout above) into an `amm_creator_claims`
   table **before** raw files are deleted. Alternatively, keep raw PumpSwap files.
3. Tie claims to tokens with `coin_creator` from Buy/SellEvent, or from the pool's `coin_creator`.

After about 2 weeks the split could hold enough early claims, roughly 13 per 1.75 h tied to the first hour after
migration among recorded pools, to test H-CLAIM-exit as an overlay. A historical RPC backfill (signatures per
creator wallet plus `getTransaction`) is possible in principle, but the public RPC rate limits make it
impractical. It would need a paid RPC.
