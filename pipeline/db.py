"""DuckDB connection, schema management, and Parquet export/import."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb

from . import config

SCHEMA_VERSION = "1"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Base tables in dependency order (views are not exported).
TABLES = [
    "sources",
    "fetch_events",
    "artifacts",
    "videos",
    "transcripts",
    "transcript_segments",
    "frames",
    "web_snapshots",
    "traders",
    "trader_identities",
    "trades",
    "observations",
    "trade_evidence",
    "annotations",
]

JSON_COLUMNS = {
    "metadata", "tool_versions", "details", "chapters", "available_captions",
    "links", "page_metadata", "value",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def connect(db_file: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    """Open the archive database and make sure the schema exists."""
    if db_file is None:
        config.ensure_layout()
        db_file = config.db_path()
    con = duckdb.connect(str(db_file))
    apply_schema(con)
    return con


def apply_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(SCHEMA_PATH.read_text())
    con.execute(
        "INSERT OR REPLACE INTO schema_meta VALUES ('schema_version', ?)", [SCHEMA_VERSION]
    )


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


def exists(con: duckdb.DuckDBPyConnection, table: str, key_col: str, key: str) -> bool:
    return con.execute(f"SELECT 1 FROM {table} WHERE {key_col} = ? LIMIT 1", [key]).fetchone() is not None


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


def synthetic_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    out = {}
    for t in ("sources", "traders", "trader_identities", "trades", "observations", "annotations"):
        out[t] = con.execute(f"SELECT count(*) FROM {t} WHERE is_synthetic").fetchone()[0]
    return out


def purge_synthetic(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Delete every synthetic row and everything hanging off a synthetic source."""
    syn_src = "(SELECT source_id FROM sources WHERE is_synthetic)"
    syn_obs = f"(SELECT observation_id FROM observations WHERE is_synthetic OR source_id IN {syn_src})"
    syn_trades = "(SELECT trade_id FROM trades WHERE is_synthetic)"
    statements = [
        ("trade_evidence", f"DELETE FROM trade_evidence WHERE observation_id IN {syn_obs} OR trade_id IN {syn_trades}"),
        ("annotations", f"DELETE FROM annotations WHERE is_synthetic OR target_id IN {syn_src} OR target_id IN {syn_obs}"),
        ("observations", f"DELETE FROM observations WHERE is_synthetic OR source_id IN {syn_src}"),
        ("trades", "DELETE FROM trades WHERE is_synthetic"),
        ("trader_identities", "DELETE FROM trader_identities WHERE is_synthetic"),
        ("traders", "DELETE FROM traders WHERE is_synthetic"),
        ("transcript_segments", f"DELETE FROM transcript_segments WHERE transcript_id IN (SELECT transcript_id FROM transcripts WHERE source_id IN {syn_src})"),
        ("transcripts", f"DELETE FROM transcripts WHERE source_id IN {syn_src}"),
        ("frames", f"DELETE FROM frames WHERE source_id IN {syn_src}"),
        ("web_snapshots", f"DELETE FROM web_snapshots WHERE source_id IN {syn_src}"),
        ("videos", f"DELETE FROM videos WHERE source_id IN {syn_src}"),
        ("artifacts", f"DELETE FROM artifacts WHERE source_id IN {syn_src}"),
        ("fetch_events", f"DELETE FROM fetch_events WHERE source_id IN {syn_src}"),
        ("sources", "DELETE FROM sources WHERE is_synthetic"),
    ]
    counts = {}
    for table, sql in statements:
        before = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        con.execute(sql)
        counts[table] = before - con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    return counts
