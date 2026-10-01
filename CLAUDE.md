# Notes for Claude

Read `docs/RESEARCH_BRIEF.md` (the governing brief) and `docs/RESEARCH_PLAN.md`
(current status, blocked items) before doing research work. `docs/WORKFLOW.md`
is the procedure; `docs/DATA_MODEL.md` the tables and rules.

## Evidence rules (the brief's, enforced in code where possible)
- Never fabricate research data. If a value is not visible or recoverable it is NULL: add no reading.
- Keep SAID / SCREEN / DID apart: observation `modality` said | screen | action | onchain | document;
  decisions keep `stated_reason`, `observed_context` and `inferred_reason` separate.
- Findings are typed stated | observed | inferred | validated and never silently merged or upgraded.
  Run `python -m pipeline check-findings` before committing.
- Search results and third-party pages are leads (`document` modality), not the trader's statements.
  Identities stay `lead`/`probable` until a primary source verifies them.
- Quote verbatim with `--quote` so `quote_verified` is set; never present paraphrase as a quote.
- Record skips, losses, rugs and mistakes, not just winners.
- Test data must be created with `is_synthetic=True` / `--synthetic` and say SYNTHETIC in its text.

## Simulation rules
- Strategies read only through `PointInTimeView`; no future data, labels or outcomes.
- Fees are explicit and sourced; no zero-impact fills.
- Iterations need a stated evidence-based reason (`add-hypothesis --rationale`, parent + failing run).
- Never tune against the holdout. `evaluate_holdout` runs once; a failure is documented in `reports/failures/`.

## Mechanics
- Setup: `scripts/setup.sh` (idempotent; SessionStart hook runs it in cloud sessions).
- Tests: `python -m pytest`. Live-network tests: `RR_NETWORK_TESTS=1 python -m pytest tests/test_live_network.py`.
- Check what the network allows before fetching: `python -m pipeline check-network`.
- New sources go behind an adapter in `pipeline/sources/`; stages must not import a site's adapter.
- Use they/them for traders in written research unless their pronouns are documented.
- Before ending a session with new data: `python -m pipeline export-all`, then commit
  `data/parquet research reports sources`.
