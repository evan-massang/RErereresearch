# Notes for Claude

- Setup: `scripts/setup.sh` (idempotent; runs automatically in cloud sessions via the SessionStart hook).
- Tests: `python -m pytest`. Live-network tests: `RR_NETWORK_TESTS=1 python -m pytest tests/test_live_network.py`.
- Check what the network allows before fetching: `python -m pipeline check-network`.
- Never fabricate research data. Test data must be created with `is_synthetic=True` / `--synthetic`
  and must say SYNTHETIC in its text. Real observations must cite a source and a locator.
- Prefer quoting verbatim with `--quote` so `quote_verified` is set; don't present paraphrase as a quote.
- New sources go behind an adapter in `pipeline/sources/` (see README "Modularity"); stages
  must not import a specific site's adapter.
- Before ending a session with new data: `python -m pipeline export-parquet` and commit `archive/parquet/`.
