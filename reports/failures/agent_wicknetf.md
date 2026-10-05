# H-WICKNET-F: filtered wick-catching with a fast exit (agent_wicknet, 2026-10-05). FAIL on validation

**Verdict: FAIL.** I ran validation once, on the config selected on train (f_d50_TK2). It fails the bar: n = 122, net −$32.20, PF 0.75, and net with the 3 best trades removed is −$45.21. The holdout was not touched.

## Pre-registration and disclosure
- The pre-registration is `reports/hypotheses/wicknetf_preregistration.json`, frozen before any WICKNET-F run.
- **This hypothesis was derived from the H-WICKNET train observations.** Filtered d = 50 fills had markouts of +22 bp at 1 s and +14 bp at 5 s. Train was therefore not a test: it was run only for information and to apply the selection rule.
- **Rule and fill model are the same as H-WICKNET** (`reports/failures/agent_wicknet.md`):
  - reference: the Binance-implied fair value F;
  - every place and cancel takes 300 ms;
  - fills happen only on a trade-through, or after the displayed queue at placement has traded;
  - hard stop at d against the entry;
  - fees: maker 1.5 bp, taker 4.5 bp;
  - size: $1k.
- The market-wide filter is always on, and the quotes refresh every 2 s.
- **Grid (6 configs):** d ∈ {30, 50} bp × exit ∈ {taker at 2 s, taker at 5 s, maker take-profit at F with a 5 s time stop}.
- **Selection rule:** the highest train PF among configs with n ≥ 20.

## Train (informational; 22 coin-days; PUMP has no train days)
| config | n | net $ | PF | net ex top-3 | markout 1/5/30 s (bp) | gross bp per trade | days positive |
|---|---|---|---|---|---|---|---|
| f_d30_TK2 | 166 | −48.8 | 0.57 | −56.8 | +10.0 / +4.1 / +3.7 | +3.1 | 3/8 |
| f_d30_TK5 | 164 | −64.0 | 0.56 | −75.6 | +9.9 / +4.2 / +3.9 | +2.1 | 4/8 |
| f_d30_MK5 | 165 | −52.6 | 0.62 | −62.3 | +10.0 / +4.1 / +3.9 | +2.7 | 4/8 |
| **f_d50_TK2** (selected) | 41 | +34.2 | 2.73 | +24.6 | +23.3 / +15.7 / +9.0 | +14.4 | 5/6 |
| f_d50_TK5 | 40 | +21.7 | 1.79 | +10.8 | +22.3 / +14.4 / +7.4 | +11.4 | 5/6 |
| f_d50_MK5 | 40 | +31.4 | 2.24 | +17.2 | +22.3 / +14.4 / +7.4 | +13.6 | 6/6 |

The d = 30 configs trade often enough, but their gross of 2–3 bp does not cover the 6 bp maker-plus-taker cost.

## Validation (one look; 35 coin-days; WIF, kBONK, FARTCOIN, PUMP)
| config | n | net $ | PF | net ex top-3 | win | markout 1/5/30 s (bp) | gross bp per trade | days positive |
|---|---|---|---|---|---|---|---|---|
| f_d50_TK2 | 122 | **−32.20** | **0.746** | −45.21 | 0.50 | +13.3 / +4.7 / +2.6 | +3.4 | 2/8 |

**Results by coin:**

| coin | n | gross bp per trade | net $ |
|---|---|---|---|
| FARTCOIN | 62 | +6.8 | +4.68 |
| PUMP | 49 | −4.2 | −49.85 |
| WIF | 4 | +22.8 | +6.73 |
| kBONK | 7 | +14.9 | +6.23 |

- **The decay is faster than on train.** The 5 s markout fell from +15.7 bp on train to +4.7 bp on validation.
- **The gross is too small.** At +3.4 bp per trade, it does not cover the 6 bp round-trip cost.
- **Order traffic.** The run placed about 181k orders. All 122 fills were trade-throughs, and only 2 orders were rejected as post-only.

**Post-hoc, not a test.** Dropping PUMP, the one coin with no train days, gives n = 73, net +$17.64, PF 1.33 and net ex top-3 +$4.63. I chose that exclusion after seeing validation, so it does not count. It is recorded here so that nobody rediscovers it later and calls it a pass.

## Reading
- The local-wick reversion seen on train (n ≈ 40, 3 coins) did not carry over to validation.
- The 1 s markout stays positive (+13 bp). But a 300 ms taker exit decided on 0.5 s snapshots cannot capture it, and the reversion has largely decayed by 5 s.
- Together with H-WICKNET, this family has now used 18 configs. **Do not iterate further on cached first-of-month Tardis days.** Any next step would need sub-second exit infrastructure and a forward recording across many coins, under a new pre-registration.

## Files
- `reports/hypotheses/wicknetf_preregistration.json`
- `scripts/research/wicknetf_run.py`
- `scripts/research/wicknet_sim.py`: the time stop is now a parameter, `H_s`; the WICKNET defaults are unchanged.
- `research/observations/evidence_wicknetf_train_20261005.json`
- `research/observations/evidence_wicknetf_valid_20261005.json`
- `data/raw/web/tardis/results/wicknetf/`: trades, fills and summaries.
