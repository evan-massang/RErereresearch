"""Evidence-linked observations.

An observation is one atomic statement extracted from one source, pinned to
where in that source it comes from (time range, transcript segment, frame,
or character span of a page snapshot). Quotes are checked verbatim against
the linked transcript/snapshot so paraphrase can't masquerade as quotation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from . import db
from .ids import new_id

STATUSES = {"draft", "reviewed", "rejected"}

# What kind of evidence an observation is (kept separate on purpose):
#   said      the trader's own words (transcript, post, interview)
#   screen    what the trader's screen showed (frame of their UI)
#   action    what the trader actually did (clicked buy, sold, closed a tab)
#   onchain   a wallet transaction or on-chain state
#   document  third-party text (articles, wikis, tracker pages, search results)
MODALITIES = {"said", "screen", "action", "onchain", "document"}


def _norm(s: str) -> str:
    # JSON-sourced text keeps line breaks as literal "\n" escapes; treat them as whitespace.
    s = s.replace("\\n", " ").replace("\\t", " ").replace('\\"', '"')
    return re.sub(r"\s+", " ", s).strip().casefold()


def _check_belongs(con, table: str, key_col: str, key: str, source_id: str) -> tuple:
    row = con.execute(f"SELECT * FROM {table} WHERE {key_col} = ?", [key]).fetchone()
    if row is None:
        raise ValueError(f"unknown {key_col} {key!r}")
    owner = con.execute(f"SELECT source_id FROM {table} WHERE {key_col} = ?", [key]).fetchone()[0]
    if owner != source_id:
        raise ValueError(f"{key_col} {key!r} belongs to {owner}, not {source_id}")
    return row


def verify_quote(con, quote: str, *, transcript_id: str | None = None, segment_seq: int | None = None,
                 snapshot_id: str | None = None, window: int = 2) -> bool | None:
    """True/False if the quote is/isn't found verbatim (whitespace/case-insensitive); None if nothing to check."""
    haystack = None
    if transcript_id:
        if segment_seq is not None:
            rows = con.execute(
                "SELECT text FROM transcript_segments WHERE transcript_id = ? AND seq BETWEEN ? AND ? ORDER BY seq",
                [transcript_id, segment_seq - window, segment_seq + window]).fetchall()
        else:
            rows = con.execute("SELECT text FROM transcript_segments WHERE transcript_id = ? ORDER BY seq",
                               [transcript_id]).fetchall()
        haystack = " ".join(r[0] for r in rows)
    elif snapshot_id:
        row = con.execute("SELECT text FROM web_snapshots WHERE snapshot_id = ?", [snapshot_id]).fetchone()
        haystack = row[0] if row else None
    if haystack is None:
        return None
    return _norm(quote) in _norm(haystack)


def add_observation(
    con: duckdb.DuckDBPyConnection,
    *,
    source_id: str,
    modality: str,
    kind: str,
    content: str,
    extractor: str,
    quote: str | None = None,
    value: Any = None,
    trader_id: str | None = None,
    trade_id: str | None = None,
    decision_id: str | None = None,
    token_id: str | None = None,
    transcript_id: str | None = None,
    segment_seq: int | None = None,
    start_s: float | None = None,
    end_s: float | None = None,
    frame_id: str | None = None,
    snapshot_id: str | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
    extractor_version: str | None = None,
    confidence: float | None = None,
    status: str = "draft",
    is_synthetic: bool = False,
    observation_id: str | None = None,
) -> str:
    if not db.exists(con, "sources", "source_id", source_id):
        raise ValueError(f"unknown source_id {source_id!r}")
    if modality not in MODALITIES:
        raise ValueError(f"modality must be one of {sorted(MODALITIES)}")
    if not content or not content.strip():
        raise ValueError("content is required")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    if confidence is not None and not 0 <= confidence <= 1:
        raise ValueError("confidence must be in [0, 1]")
    if trader_id and not db.exists(con, "traders", "trader_id", trader_id):
        raise ValueError(f"unknown trader_id {trader_id!r}")
    if trade_id and not db.exists(con, "trades", "trade_id", trade_id):
        raise ValueError(f"unknown trade_id {trade_id!r}")
    db.require(con, "decisions", "decision_id", decision_id)
    db.require(con, "tokens", "token_id", token_id)

    if transcript_id:
        _check_belongs(con, "transcripts", "transcript_id", transcript_id, source_id)
        if segment_seq is not None:
            seg = con.execute("SELECT start_s, end_s FROM transcript_segments WHERE transcript_id = ? AND seq = ?",
                              [transcript_id, segment_seq]).fetchone()
            if seg is None:
                raise ValueError(f"no segment {segment_seq} in {transcript_id}")
            start_s = seg[0] if start_s is None else start_s
            end_s = seg[1] if end_s is None else end_s
    elif segment_seq is not None:
        raise ValueError("segment_seq requires transcript_id")
    if frame_id:
        _check_belongs(con, "frames", "frame_id", frame_id, source_id)
        if start_s is None:
            start_s = con.execute("SELECT timestamp_s FROM frames WHERE frame_id = ?", [frame_id]).fetchone()[0]
    if snapshot_id:
        _check_belongs(con, "web_snapshots", "snapshot_id", snapshot_id, source_id)
    if start_s is not None and end_s is not None and end_s < start_s:
        raise ValueError("end_s < start_s")

    quote_verified = None
    if quote:
        quote_verified = verify_quote(con, quote, transcript_id=transcript_id,
                                      segment_seq=segment_seq, snapshot_id=snapshot_id)

    observation_id = observation_id or new_id("obs")
    db.upsert(con, "observations", {
        "observation_id": observation_id, "source_id": source_id, "modality": modality,
        "kind": kind, "content": content,
        "quote": quote, "quote_verified": quote_verified, "value": value,
        "trader_id": trader_id, "trade_id": trade_id, "decision_id": decision_id,
        "token_id": token_id, "transcript_id": transcript_id,
        "segment_seq": segment_seq, "start_s": start_s, "end_s": end_s, "frame_id": frame_id,
        "snapshot_id": snapshot_id, "char_start": char_start, "char_end": char_end,
        "extractor": extractor, "extractor_version": extractor_version, "confidence": confidence,
        "status": status, "created_at": db.now(), "is_synthetic": is_synthetic,
    })
    return observation_id


def import_jsonl(con: duckdb.DuckDBPyConnection, path: Path | str, *, extractor: str | None = None,
                 is_synthetic: bool | None = None) -> list[str]:
    """Bulk-add observations, one JSON object per line (keys = add_observation args).

    All-or-nothing: if any line fails validation, nothing is written.
    """
    lines = [l for l in Path(path).read_text().splitlines() if l.strip()]
    ids = []
    con.execute("BEGIN TRANSACTION")
    try:
        for n, line in enumerate(lines, 1):
            rec = json.loads(line)
            if extractor and "extractor" not in rec:
                rec["extractor"] = extractor
            if is_synthetic is not None:
                rec["is_synthetic"] = is_synthetic
            try:
                ids.append(add_observation(con, **rec))
            except (TypeError, ValueError) as e:
                raise ValueError(f"line {n}: {e}") from e
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return ids


def set_status(con: duckdb.DuckDBPyConnection, observation_id: str, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    if not db.exists(con, "observations", "observation_id", observation_id):
        raise ValueError(f"unknown observation_id {observation_id!r}")
    con.execute("UPDATE observations SET status = ? WHERE observation_id = ?", [status, observation_id])


def list_observations(con: duckdb.DuckDBPyConnection, *, source_id: str | None = None,
                      trader_id: str | None = None, kind: str | None = None,
                      include_synthetic: bool = False) -> pd.DataFrame:
    where, params = [], []
    for col, val in (("source_id", source_id), ("kind", kind)):
        if val:
            where.append(f"{col} = ?")
            params.append(val)
    if trader_id:
        where.append("observation_id IN (SELECT observation_id FROM observations WHERE trader_id = ?)")
        params.append(trader_id)
    if not include_synthetic:
        where.append("NOT is_synthetic")
    sql = "SELECT * FROM v_observation_provenance"
    if where:
        sql += " WHERE " + " AND ".join(where)
    return con.execute(sql + " ORDER BY source_id, start_s NULLS LAST", params).df()


def reverify_quotes(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Recompute quote_verified for every quoted observation (e.g. after a cited page is finally fetched).

    Observations that cite a source without a snapshot are re-pointed at the
    source's latest snapshot when one now exists.
    """
    rows = con.execute(
        "SELECT observation_id, source_id, quote, transcript_id, segment_seq, snapshot_id "
        "FROM observations WHERE quote IS NOT NULL").fetchall()
    changed = {"checked": 0, "now_verified": 0, "now_unverified": 0}
    for oid, sid, quote, tid, seq, snap in rows:
        if not tid and not snap:
            latest = con.execute("SELECT snapshot_id FROM web_snapshots WHERE source_id = ? "
                                 "ORDER BY fetched_at DESC LIMIT 1", [sid]).fetchone()
            if latest:
                snap = latest[0]
                con.execute("UPDATE observations SET snapshot_id = ? WHERE observation_id = ?", [snap, oid])
        verified = verify_quote(con, quote, transcript_id=tid, segment_seq=seq, snapshot_id=snap)
        before = con.execute("SELECT quote_verified FROM observations WHERE observation_id = ?", [oid]).fetchone()[0]
        con.execute("UPDATE observations SET quote_verified = ? WHERE observation_id = ?", [verified, oid])
        changed["checked"] += 1
        if verified is True and before is not True:
            changed["now_verified"] += 1
        if verified is False and before is not False:
            changed["now_unverified"] += 1
    return changed
