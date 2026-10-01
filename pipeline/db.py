"""DuckDB connection, schema management, and Parquet export/import."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb

from . import config

SCHEMA_VERSION = 2
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Statements that upgrade a database from version N-1 to N (applied in order).
# Version 2 is the first schema to hold research data; version 1 was pre-release.
MIGRATIONS: dict[int, list[str]] = {}

# Base tables in dependency order (views are not exported).
TABLES = [
    "sources",
    "source_candidates",
    "fetch_events",
    "artifacts",
    "videos",
    "transcripts",
    "transcript_segments",
    "candidate_moments",
    "frames",
    "web_snapshots",
    "traders",
    "trader_identities",
    "tokens",
    "narratives",
    "token_narratives",
    "decisions",
    "decision_metrics",
    "trades",
    "observations",
    "trade_evidence",
    "findings",
    "finding_evidence",
    "hypotheses",
    "hypothesis_basis",
    "features",
    "data_splits",
    "sim_runs",
    "holdout_log",
    "annotations",
]

JSON_COLUMNS = {
    "metadata", "tool_versions", "details", "chapters", "available_captions",
    "links", "page_metadata", "value", "discovery_evidence", "strategy_spec",
    "execution_model", "metrics_imitation", "metrics_performance",
}


class SchemaVersionError(RuntimeError):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def connect(db_file: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    """Open the research database and make sure the schema is current."""
    if db_file is None:
        config.ensure_layout()
        db_file = config.db_path()
    con = duckdb.connect(str(db_file))
    apply_schema(con)
    return con


def _current_version(con) -> int | None:
    has_meta = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'schema_meta'").fetchone()[0]
    if not has_meta:
        return None
    row = con.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
    return int(row[0]) if row else None


def apply_schema(con: duckdb.DuckDBPyConnection) -> None:
    version = _current_version(con)
    if version is not None and version < 2:
        raise SchemaVersionError(
            f"database has pre-release schema v{version}, which never held research data; "
            "delete data/research.duckdb and re-run (or restore from data/parquet)")
    if version is not None and version > SCHEMA_VERSION:
        raise SchemaVersionError(f"database schema v{version} is newer than this code (v{SCHEMA_VERSION})")
    if version is not None:
        for v in range(version + 1, SCHEMA_VERSION + 1):
            for stmt in MIGRATIONS.get(v, []):
                con.execute(stmt)
    con.execute(SCHEMA_PATH.read_text())
    con.execute("INSERT OR REPLACE INTO schema_meta VALUES ('schema_version', ?)", [str(SCHEMA_VERSION)])


def _encode(col: str, value: Any) -> Any:
    if col in JSON_COLUMNS and value is not None:
        return json.dumps(value, default=str, ensure_ascii=False)
    return value


def upsert(con: duckdb.DuckDBPyConnection, table: str, row: dict[str, Any]) -> None:
    """INSERT OR REPLACE a single row (dict keys are column names)."""
    cols = list(row)
    sql = (
        f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)})"
    )
    con.execute(sql, [_encode(c, row[c]) for c in cols])


def insert_many(con: duckdb.DuckDBPyConnection, table: str, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    cols = list(rows[0])
    sql = (
        f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)})"
    )
    con.executemany(sql, [[_encode(c, r[c]) for c in cols] for r in rows])
    return len(rows)


def exists(con: duckdb.DuckDBPyConnection, table: str, key_col: str, key: str | None) -> bool:
    if key is None:
        return False
    return con.execute(f"SELECT 1 FROM {table} WHERE {key_col} = ? LIMIT 1", [key]).fetchone() is not None


def require(con: duckdb.DuckDBPyConnection, table: str, key_col: str, key: str | None) -> None:
    """Raise ValueError if a (non-None) key does not exist."""
    if key is not None and not exists(con, table, key_col, key):
        raise ValueError(f"unknown {key_col} {key!r}")


def export_parquet(con: duckdb.DuckDBPyConnection, out_dir: Path | str | None = None) -> list[Path]:
    """Write one Parquet file per table — a portable, diff-able snapshot."""
    out = Path(out_dir) if out_dir else config.path("parquet")
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for table in TABLES:
        target = out / f"{table}.parquet"
        con.execute(f"COPY {table} TO '{target.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
        written.append(target)
    return written


def import_parquet(con: duckdb.DuckDBPyConnection, in_dir: Path | str | None = None) -> dict[str, int]:
    """Load Parquet files written by export_parquet (upserting by primary key)."""
    src = Path(in_dir) if in_dir else config.path("parquet")
    counts = {}
    for table in TABLES:
        f = src / f"{table}.parquet"
        if not f.exists():
            continue
        before = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        con.execute(
            f"INSERT OR REPLACE INTO {table} BY NAME SELECT * FROM read_parquet('{f.as_posix()}')"
        )
        counts[table] = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] - before
    return counts


def table_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}


SYNTHETIC_FLAGGED = [
    "sources", "source_candidates", "traders", "trader_identities", "tokens", "narratives",
    "decisions", "trades", "observations", "findings", "hypotheses", "features",
    "data_splits", "sim_runs", "annotations",
]


def synthetic_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {t: con.execute(f"SELECT count(*) FROM {t} WHERE is_synthetic").fetchone()[0]
            for t in SYNTHETIC_FLAGGED}


def purge_synthetic(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Delete every synthetic row and everything hanging off a synthetic parent."""
    src = "(SELECT source_id FROM sources WHERE is_synthetic)"
    obs = f"(SELECT observation_id FROM observations WHERE is_synthetic OR source_id IN {src})"
    dec = f"(SELECT decision_id FROM decisions WHERE is_synthetic OR source_id IN {src})"
    trd = "(SELECT trade_id FROM trades WHERE is_synthetic)"
    tok = "(SELECT token_id FROM tokens WHERE is_synthetic)"
    nar = "(SELECT narrative_id FROM narratives WHERE is_synthetic)"
    fnd = "(SELECT finding_id FROM findings WHERE is_synthetic)"
    hyp = "(SELECT hypothesis_id FROM hypotheses WHERE is_synthetic)"
    tsc = f"(SELECT transcript_id FROM transcripts WHERE source_id IN {src})"
    splits = "(SELECT split_set FROM data_splits WHERE is_synthetic)"
    any_target = f"target_id IN {src} OR target_id IN {obs} OR target_id IN {dec} OR target_id IN {trd}"
    statements = [
        ("annotations", f"DELETE FROM annotations WHERE is_synthetic OR {any_target}"),
        ("finding_evidence", f"DELETE FROM finding_evidence WHERE finding_id IN {fnd} "
                             f"OR evidence_id IN {obs} OR evidence_id IN {dec}"),
        ("hypothesis_basis", f"DELETE FROM hypothesis_basis WHERE hypothesis_id IN {hyp} OR finding_id IN {fnd}"),
        ("trade_evidence", f"DELETE FROM trade_evidence WHERE observation_id IN {obs} OR trade_id IN {trd}"),
        ("token_narratives", f"DELETE FROM token_narratives WHERE token_id IN {tok} OR narrative_id IN {nar}"),
        ("decision_metrics", f"DELETE FROM decision_metrics WHERE decision_id IN {dec}"),
        ("candidate_moments", f"DELETE FROM candidate_moments WHERE transcript_id IN {tsc}"),
        ("observations", f"DELETE FROM observations WHERE is_synthetic OR source_id IN {src}"),
        ("decisions", f"DELETE FROM decisions WHERE is_synthetic OR source_id IN {src}"),
        ("trades", "DELETE FROM trades WHERE is_synthetic"),
        ("findings", "DELETE FROM findings WHERE is_synthetic"),
        ("hypotheses", "DELETE FROM hypotheses WHERE is_synthetic"),
        ("features", "DELETE FROM features WHERE is_synthetic"),
        ("sim_runs", "DELETE FROM sim_runs WHERE is_synthetic"),
        ("holdout_log", f"DELETE FROM holdout_log WHERE split_set IN {splits}"),
        ("data_splits", "DELETE FROM data_splits WHERE is_synthetic"),
        ("tokens", "DELETE FROM tokens WHERE is_synthetic"),
        ("narratives", "DELETE FROM narratives WHERE is_synthetic"),
        ("trader_identities", "DELETE FROM trader_identities WHERE is_synthetic"),
        ("traders", "DELETE FROM traders WHERE is_synthetic"),
        ("transcript_segments", f"DELETE FROM transcript_segments WHERE transcript_id IN {tsc}"),
        ("transcripts", f"DELETE FROM transcripts WHERE source_id IN {src}"),
        ("frames", f"DELETE FROM frames WHERE source_id IN {src}"),
        ("web_snapshots", f"DELETE FROM web_snapshots WHERE source_id IN {src}"),
        ("videos", f"DELETE FROM videos WHERE source_id IN {src}"),
        ("artifacts", f"DELETE FROM artifacts WHERE source_id IN {src}"),
        ("fetch_events", f"DELETE FROM fetch_events WHERE source_id IN {src}"),
        ("source_candidates", f"DELETE FROM source_candidates WHERE is_synthetic OR source_id IN {src}"),
        ("sources", "DELETE FROM sources WHERE is_synthetic"),
    ]
    counts = {}
    for table, sql in statements:
        before = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        con.execute(sql)
        counts[table] = before - con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    return counts
