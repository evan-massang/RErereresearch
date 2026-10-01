# Archive root

Created by `python -m pipeline init` (or `scripts/setup.sh`). Override the
location with `RR_ARCHIVE=/some/path`. Paths stored in the database are
relative to this directory.

```
archive/
├── db/research.duckdb          live database (git-ignored)
├── parquet/<table>.parquet     portable snapshot (committed; restored by setup.sh)
├── raw/
│   ├── video/<platform>/<external_id>/   media + info.json as fetched
│   ├── subtitles/<source_id>/            caption files as fetched/imported
│   ├── web/<source_id>/                  HTML/PDF/JSON snapshots, named by content hash
│   └── documents/                        files you drop in by hand
├── derived/
│   ├── audio/<source_id>/                16 kHz mono WAV for ASR
│   ├── transcripts/<source_id>/          ASR output JSON
│   ├── frames/<source_id>/               stills, t<ms>_<method>.jpg
│   └── clips/<source_id>/                cut clips
└── exports/                              ad-hoc analysis outputs
```

Everything under `raw/` and `derived/` is git-ignored: it is large and may be
third-party content. Only `parquet/` is committed. The cloud container is
deleted after inactivity, so run `python -m pipeline export-parquet` and commit
before you stop, or point `RR_ARCHIVE` at persistent storage.
