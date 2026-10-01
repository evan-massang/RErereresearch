"""Trader- and trade-level records, plus free-form annotations on any record."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import duckdb

from . import db
from .ids import new_id

DIRECTIONS = {"long", "short", "unknown"}
TRADE_STATUSES = {"reported", "corroborated", "verified", "disputed", "retracted"}
OUTCOMES = {"win", "loss", "breakeven", "open", "unknown"}

TARGETS = {
    "source": ("sources", "source_id"),
    "trader": ("traders", "trader_id"),
    "trade": ("trades", "trade_id"),
    "observation": ("observations", "observation_id"),
    "frame": ("frames", "frame_id"),
    "transcript": ("transcripts", "transcript_id"),
    "snapshot": ("web_snapshots", "snapshot_id"),
}


def _need(con, table: str, col: str, key: str | None) -> None:
    if key and not db.exists(con, table, col, key):
        raise ValueError(f"unknown {col} {key!r}")


def add_trader(con: duckdb.DuckDBPyConnection, display_name: str, *, aliases: list[str] | None = None,
               notes: str | None = None, is_synthetic: bool = False, trader_id: str | None = None) -> str:
    if not display_name.strip():
        raise ValueError("display_name is required")
    trader_id = trader_id or new_id("trd")
    db.upsert(con, "traders", {
        "trader_id": trader_id, "display_name": display_name.strip(), "aliases": aliases or [],
        "notes": notes, "created_at": db.now(), "is_synthetic": is_synthetic,
    })
    return trader_id


def add_trader_identity(con: duckdb.DuckDBPyConnection, trader_id: str, platform: str, *,
                        handle: str | None = None, url: str | None = None,
                        evidence_source_id: str | None = None, is_synthetic: bool = False) -> str:
    _need(con, "traders", "trader_id", trader_id)
    _need(con, "sources", "source_id", evidence_source_id)
    if not (handle or url):
        raise ValueError("handle or url is required")
    identity_id = new_id("tid")
    db.upsert(con, "trader_identities", {
        "identity_id": identity_id, "trader_id": trader_id, "platform": platform, "handle": handle,
        "url": url, "evidence_source_id": evidence_source_id, "created_at": db.now(),
        "is_synthetic": is_synthetic,
    })
    return identity_id


def add_trade(
    con: duckdb.DuckDBPyConnection,
    *,
    trader_id: str | None,
    instrument: str | None = None,
    asset_class: str | None = None,
    direction: str | None = "unknown",
    entry_time: datetime | None = None,
    entry_price: float | None = None,
    exit_time: datetime | None = None,
    exit_price: float | None = None,
    stop_price: float | None = None,
    target_price: float | None = None,
    size: float | None = None,
    size_unit: str | None = None,
    currency: str | None = None,
    timeframe: str | None = None,
    outcome: str | None = "unknown",
    pnl: float | None = None,
    pnl_unit: str | None = None,
    status: str = "reported",
    confidence: float | None = None,
    notes: str | None = None,
    evidence: list[tuple[str, str | None]] | None = None,   # [(observation_id, role), ...]
    is_synthetic: bool = False,
    trade_id: str | None = None,
) -> str:
    _need(con, "traders", "trader_id", trader_id)
    if direction is not None and direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {sorted(DIRECTIONS)}")
    if status not in TRADE_STATUSES:
        raise ValueError(f"status must be one of {sorted(TRADE_STATUSES)}")
    if outcome is not None and outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(OUTCOMES)}")
    if confidence is not None and not 0 <= confidence <= 1:
        raise ValueError("confidence must be in [0, 1]")
    if entry_time and exit_time and exit_time < entry_time:
        raise ValueError("exit_time before entry_time")
    if status in {"corroborated", "verified"} and not evidence:
        raise ValueError(f"status {status!r} requires at least one evidence observation")
    for obs_id, _ in evidence or []:
        _need(con, "observations", "observation_id", obs_id)

    trade_id = trade_id or new_id("trade")
    db.upsert(con, "trades", {
        "trade_id": trade_id, "trader_id": trader_id, "instrument": instrument,
        "asset_class": asset_class, "direction": direction, "entry_time": entry_time,
        "entry_price": entry_price, "exit_time": exit_time, "exit_price": exit_price,
        "stop_price": stop_price, "target_price": target_price, "size": size, "size_unit": size_unit,
        "currency": currency, "timeframe": timeframe, "outcome": outcome, "pnl": pnl,
        "pnl_unit": pnl_unit, "status": status, "confidence": confidence, "notes": notes,
        "created_at": db.now(), "is_synthetic": is_synthetic,
    })
    for obs_id, role in evidence or []:
        link_evidence(con, trade_id, obs_id, role)
    return trade_id


def link_evidence(con: duckdb.DuckDBPyConnection, trade_id: str, observation_id: str,
                  role: str | None = None) -> None:
    _need(con, "trades", "trade_id", trade_id)
    _need(con, "observations", "observation_id", observation_id)
    db.upsert(con, "trade_evidence", {"trade_id": trade_id, "observation_id": observation_id, "role": role})


def annotate(con: duckdb.DuckDBPyConnection, target_type: str, target_id: str, key: str, value: Any, *,
             annotator: str, is_synthetic: bool = False) -> str:
    if target_type not in TARGETS:
        raise ValueError(f"target_type must be one of {sorted(TARGETS)}")
    table, col = TARGETS[target_type]
    _need(con, table, col, target_id)
    annotation_id = new_id("ann")
    db.upsert(con, "annotations", {
        "annotation_id": annotation_id, "target_type": target_type, "target_id": target_id,
        "key": key, "value": value, "annotator": annotator, "created_at": db.now(),
        "is_synthetic": is_synthetic,
    })
    return annotation_id
