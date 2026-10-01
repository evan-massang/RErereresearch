"""The structured trader dataset: tokens, narratives, decisions, metric readings.

A decision is one observed choice (BUY / SKIP / SELL / ...) by one trader at
one moment of one source. Everything the trader could see is recorded as
*metric readings* attached to the decision, each with its provenance (read
off a frame, said aloud, from chain data, or derived). A metric that was not
visible has no reading, so the wide view shows NULL; values are never guessed.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from . import db
from .ids import new_id, stable_id

DECISIONS = {"BUY", "ADD", "SKIP", "WATCH", "HOLD", "PARTIAL_SELL", "SELL", "MISSED"}
OBSERVED_VIA = {"screen", "said", "onchain", "derived"}
TOKEN_IDENTIFICATION = {"ca_visible", "ticker_visible", "spoken", "onchain_match", "other"}
NARRATIVE_RELATIONS = {"canonical", "copycat", "derivative", "unclear"}
WALLCLOCK_BASES = {"onchain_tx", "stream_start_offset", "on_screen_clock"}
RESULT_BASES = {"shown", "said", "onchain", "computed"}
SIZE_UNITS = {"SOL", "USD", "pct_of_wallet", "tokens"}
STATUSES = {"draft", "reviewed", "rejected"}

# Canonical metric vocabulary -> default unit. Tool-specific fields that do not
# fit go in as "x_<tool>_<field>" so nothing is forced into the wrong column.
METRICS: dict[str, str] = {
    "market_cap_usd": "USD", "market_cap_sol": "SOL",
    "liquidity_usd": "USD", "liquidity_sol": "SOL",
    "price_usd": "USD", "price_sol": "SOL",
    "token_age_s": "s",
    "txns": "count", "buys": "count", "sells": "count",
    "unique_buyers": "count", "unique_sellers": "count",
    "volume_usd": "USD", "volume_sol": "SOL",
    "holders": "count", "top10_pct": "pct", "dev_pct": "pct",
    "snipers_pct": "pct", "snipers_count": "count",
    "insiders_pct": "pct", "bundles_pct": "pct",
    "pro_traders": "count", "kols": "count", "viewers": "count",
    "bonding_curve_pct": "pct",
    "social_posts_per_min": "per_min", "author_followers": "count",
    "position_pnl_pct": "pct", "position_value_usd": "USD",
}


# ------------------------------------------------------------------ display parsing

_NUM_RE = re.compile(r"^\s*\$?\s*([-+]?\d[\d,]*(?:\.\d+)?)\s*([kKmMbB]?)\s*%?\s*$")
_MULT = {"": 1, "k": 1e3, "m": 1e6, "b": 1e9}
_DUR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|s|m|h|d|w|mo|y)\b")
_DUR_S = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "mo": 2592000, "y": 31536000}


def parse_display_number(text: str | None) -> float | None:
    """'$12.4K' -> 12400, '1.2M' -> 1.2e6, '45%' -> 45, '1,234' -> 1234; unparseable -> None."""
    if text is None:
        return None
    m = _NUM_RE.match(text)
    if not m:
        return None
    return float(m.group(1).replace(",", "")) * _MULT[m.group(2).lower()]


def parse_display_duration(text: str | None) -> float | None:
    """Age labels like '12s', '3m', '1h 5m', '2d' -> seconds; unparseable -> None.

    'm' is read as minutes (as on trading terminals); 'mo' is months.
    """
    if not text:
        return None
    parts = _DUR_RE.findall(text.strip().lower())
    if not parts or _DUR_RE.sub("", text.strip().lower()).strip():
        return None
    return sum(float(v) * _DUR_S[u] for v, u in parts)


# ------------------------------------------------------------------ tokens & narratives

def add_token(con: duckdb.DuckDBPyConnection, *, identification: str, ticker: str | None = None,
              name: str | None = None, mint: str | None = None, identification_confidence: float | None = None,
              launchpad: str | None = None, created_onchain_at: datetime | None = None,
              image_description: str | None = None, notes: str | None = None,
              is_synthetic: bool = False) -> str:
    """Register a token as identified in evidence. Same mint -> same token_id."""
    if not (ticker or name or mint):
        raise ValueError("need at least one of ticker, name, mint")
    if identification not in TOKEN_IDENTIFICATION:
        raise ValueError(f"identification must be one of {sorted(TOKEN_IDENTIFICATION)}")
    if identification_confidence is not None and not 0 <= identification_confidence <= 1:
        raise ValueError("identification_confidence must be in [0, 1]")
    if mint:
        existing = con.execute("SELECT token_id FROM tokens WHERE mint = ?", [mint]).fetchone()
        if existing:
            return existing[0]
    token_id = stable_id("tok", "solana", mint) if mint else new_id("tok")
    db.upsert(con, "tokens", {
        "token_id": token_id, "chain": "solana", "mint": mint, "ticker": ticker, "name": name,
        "launchpad": launchpad, "created_onchain_at": created_onchain_at,
        "image_description": image_description, "identification": identification,
        "identification_confidence": identification_confidence, "notes": notes,
        "created_at": db.now(), "is_synthetic": is_synthetic,
    })
    return token_id


def set_token_mint(con: duckdb.DuckDBPyConnection, token_id: str, mint: str, *,
                   identification: str = "onchain_match", confidence: float | None = None,
                   note: str | None = None) -> None:
    """Record a mint recovered later (e.g. by matching the trader's wallet transactions)."""
    db.require(con, "tokens", "token_id", token_id)
    other = con.execute("SELECT token_id FROM tokens WHERE mint = ? AND token_id <> ?", [mint, token_id]).fetchone()
    if other:
        raise ValueError(f"mint already belongs to {other[0]}; merge the two tokens instead")
    if identification not in TOKEN_IDENTIFICATION:
        raise ValueError(f"identification must be one of {sorted(TOKEN_IDENTIFICATION)}")
    con.execute(
        "UPDATE tokens SET mint = ?, identification = ?, identification_confidence = ?, "
        "notes = concat_ws(' | ', notes, ?) WHERE token_id = ?",
        [mint, identification, confidence, note, token_id])


def add_narrative(con: duckdb.DuckDBPyConnection, title: str, *, description: str | None = None,
                  origin_description: str | None = None, origin_source_id: str | None = None,
                  first_seen_at: datetime | None = None, category: str | None = None,
                  notes: str | None = None, is_synthetic: bool = False) -> str:
    if not title.strip():
        raise ValueError("title is required")
    db.require(con, "sources", "source_id", origin_source_id)
    narrative_id = new_id("nar")
    db.upsert(con, "narratives", {
        "narrative_id": narrative_id, "title": title.strip(), "description": description,
        "origin_description": origin_description, "origin_source_id": origin_source_id,
        "first_seen_at": first_seen_at, "category": category, "notes": notes,
        "created_at": db.now(), "is_synthetic": is_synthetic,
    })
    return narrative_id


def link_token_narrative(con: duckdb.DuckDBPyConnection, token_id: str, narrative_id: str, relation: str,
                         observation_id: str | None = None) -> None:
    db.require(con, "tokens", "token_id", token_id)
    db.require(con, "narratives", "narrative_id", narrative_id)
    db.require(con, "observations", "observation_id", observation_id)
    if relation not in NARRATIVE_RELATIONS:
        raise ValueError(f"relation must be one of {sorted(NARRATIVE_RELATIONS)}")
    db.upsert(con, "token_narratives", {"token_id": token_id, "narrative_id": narrative_id,
                                        "relation": relation, "observation_id": observation_id})


# ------------------------------------------------------------------ decisions

def add_decision(
    con: duckdb.DuckDBPyConnection,
    *,
    trader_id: str,
    source_id: str,
    decision: str,
    extraction_confidence: float,
    extractor: str,
    video_ts_s: float | None = None,
    decision_wallclock: datetime | None = None,
    wallclock_basis: str | None = None,
    token_id: str | None = None,
    trade_id: str | None = None,
    discovery_channel: str | None = None,
    stated_reason: str | None = None,
    observed_context: str | None = None,
    inferred_reason: str | None = None,
    reason_codes: list[str] | None = None,
    chart_state: str | None = None,
    narrative_id: str | None = None,
    position_size: float | None = None,
    position_size_unit: str | None = None,
    result_pct: float | None = None,
    result_sol: float | None = None,
    result_basis: str | None = None,
    extractor_version: str | None = None,
    status: str = "draft",
    notes: str | None = None,
    is_synthetic: bool = False,
    decision_id: str | None = None,
) -> str:
    db.require(con, "traders", "trader_id", trader_id)
    db.require(con, "sources", "source_id", source_id)
    db.require(con, "tokens", "token_id", token_id)
    db.require(con, "trades", "trade_id", trade_id)
    db.require(con, "narratives", "narrative_id", narrative_id)
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {sorted(DECISIONS)}")
    if not 0 <= extraction_confidence <= 1:
        raise ValueError("extraction_confidence must be in [0, 1]")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    if decision_wallclock is not None and wallclock_basis not in WALLCLOCK_BASES:
        raise ValueError(f"decision_wallclock needs wallclock_basis in {sorted(WALLCLOCK_BASES)}")
    if position_size is not None and position_size_unit not in SIZE_UNITS:
        raise ValueError(f"position_size needs position_size_unit in {sorted(SIZE_UNITS)}")
    if (result_pct is not None or result_sol is not None) and result_basis not in RESULT_BASES:
        raise ValueError(f"a result needs result_basis in {sorted(RESULT_BASES)}")
    if video_ts_s is not None:
        dur = con.execute("SELECT duration_s FROM videos WHERE source_id = ?", [source_id]).fetchone()
        if video_ts_s < 0 or (dur and dur[0] is not None and video_ts_s > dur[0] + 1):
            raise ValueError(f"video_ts_s {video_ts_s} outside the video")
    decision_id = decision_id or new_id("dec")
    db.upsert(con, "decisions", {
        "decision_id": decision_id, "trader_id": trader_id, "source_id": source_id,
        "video_ts_s": video_ts_s, "decision_wallclock": decision_wallclock,
        "wallclock_basis": wallclock_basis, "decision": decision, "token_id": token_id,
        "trade_id": trade_id, "discovery_channel": discovery_channel, "stated_reason": stated_reason,
        "observed_context": observed_context, "inferred_reason": inferred_reason,
        "reason_codes": reason_codes or [], "chart_state": chart_state, "narrative_id": narrative_id,
        "position_size": position_size, "position_size_unit": position_size_unit,
        "result_pct": result_pct, "result_sol": result_sol, "result_basis": result_basis,
        "extraction_confidence": extraction_confidence, "extractor": extractor,
        "extractor_version": extractor_version, "status": status, "notes": notes,
        "created_at": db.now(), "is_synthetic": is_synthetic,
    })
    return decision_id


def add_reading(
    con: duckdb.DuckDBPyConnection,
    decision_id: str,
    metric: str,
    *,
    observed_via: str,
    value_num: float | None = None,
    value_text: str | None = None,
    unit: str | None = None,
    metric_window: str | None = None,
    frame_id: str | None = None,
    observation_id: str | None = None,
    as_of_offset_s: float | None = None,
    confidence: float | None = None,
    notes: str | None = None,
) -> str:
    """Attach one metric reading (with provenance) to a decision."""
    row = con.execute("SELECT source_id, video_ts_s FROM decisions WHERE decision_id = ?", [decision_id]).fetchone()
    if row is None:
        raise ValueError(f"unknown decision_id {decision_id!r}")
    source_id, video_ts = row
    if metric not in METRICS and not metric.startswith("x_"):
        raise ValueError(f"unknown metric {metric!r}; use the vocabulary in decisions.METRICS or an x_ prefix")
    if observed_via not in OBSERVED_VIA:
        raise ValueError(f"observed_via must be one of {sorted(OBSERVED_VIA)}")
    if value_num is None and value_text is not None:
        value_num = parse_display_duration(value_text) if metric == "token_age_s" else parse_display_number(value_text)
    if value_num is None and value_text is None:
        raise ValueError("a reading needs value_num or value_text (omit the reading if nothing was visible)")
    if confidence is not None and not 0 <= confidence <= 1:
        raise ValueError("confidence must be in [0, 1]")
    if observed_via == "screen":
        if not frame_id:
            raise ValueError("a screen reading must cite the frame it was read from")
        frame = con.execute("SELECT source_id, timestamp_s FROM frames WHERE frame_id = ?", [frame_id]).fetchone()
        if frame is None:
            raise ValueError(f"unknown frame_id {frame_id!r}")
        if frame[0] != source_id:
            raise ValueError("frame belongs to a different source than the decision")
        if as_of_offset_s is None and video_ts is not None:
            as_of_offset_s = round(frame[1] - video_ts, 3)
    if observed_via == "said" and not observation_id:
        raise ValueError("a 'said' reading must cite the observation holding the quote")
    db.require(con, "observations", "observation_id", observation_id)
    reading_id = new_id("rd")
    db.upsert(con, "decision_metrics", {
        "reading_id": reading_id, "decision_id": decision_id, "metric": metric,
        "value_num": value_num, "value_text": value_text, "unit": unit or METRICS.get(metric),
        "metric_window": metric_window, "observed_via": observed_via, "frame_id": frame_id,
        "observation_id": observation_id, "as_of_offset_s": as_of_offset_s,
        "confidence": confidence, "notes": notes,
    })
    return reading_id


def set_decision_status(con: duckdb.DuckDBPyConnection, decision_id: str, status: str) -> None:
    db.require(con, "decisions", "decision_id", decision_id)
    if status not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    con.execute("UPDATE decisions SET status = ? WHERE decision_id = ?", [status, decision_id])


def import_decisions_jsonl(con: duckdb.DuckDBPyConnection, path: Path | str, *,
                           is_synthetic: bool | None = None) -> list[str]:
    """Bulk import, all-or-nothing. One JSON object per line:

        {"decision": {...add_decision kwargs...},
         "readings": [{...add_reading kwargs without decision_id...}, ...]}
    """
    lines = [l for l in Path(path).read_text().splitlines() if l.strip()]
    ids: list[str] = []
    con.execute("BEGIN TRANSACTION")
    try:
        for n, line in enumerate(lines, 1):
            rec: dict[str, Any] = json.loads(line)
            d = dict(rec["decision"])
            if is_synthetic is not None:
                d["is_synthetic"] = is_synthetic
            if isinstance(d.get("decision_wallclock"), str):
                d["decision_wallclock"] = datetime.fromisoformat(d["decision_wallclock"])
            try:
                did = add_decision(con, **d)
                for r in rec.get("readings", []):
                    add_reading(con, did, **r)
            except (TypeError, ValueError) as e:
                raise ValueError(f"line {n}: {e}") from e
            ids.append(did)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return ids
