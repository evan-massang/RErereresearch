# Research archive (human-readable)

Mostly generated from the database by `python -m pipeline export-all`; hand-written
notes go in `traders/<slug>/notes.md` and `narratives/`.

| path | contents | generated? |
|---|---|---|
| `traders/<slug>/identity.md` | account/wallet leads with sources, doubts, ambiguities, content queue | yes |
| `information_environment.md` | what trading tools display; protocol mechanics (search-derived leads) | yes, from `sources/leads/info_environment.json` |
| `videos/<source_id>.md` | per-video worksheet: transcripts, candidate moments, coded decisions | yes |
| `transcripts/<trader>/*.txt` | `[HH:MM:SS]` transcripts for `rg` | yes |
| `frames/<source_id>/` | frames cited as evidence | copied |
| `trades/trades.csv`, `rejected_tokens/skips.csv`, `observations/*.csv` | dataset exports (non-synthetic only) | yes |
| `narratives/` | narrative notes | hand-written |
