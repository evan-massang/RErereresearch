"""Source discovery queue, search-result citations, lead import, and the source ledger.

Search results are leads, not evidence about behavior. A URL cited by a search
result is registered as a source with ``last_fetched_at = NULL`` (cited, not
read); claims taken from the search tool are stored as 'document' observations
with ``quote_verified = NULL`` until the page itself is fetched and the quote
re-checked (``observations.reverify_quotes``).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import duckdb

from . import annotations, config, db, observations
from .ids import stable_id

CANDIDATE_STATUSES = {"candidate", "queued", "ingested", "rejected", "unavailable"}
CONTENT_TYPES = {"live_trading_session", "recorded_trading_session", "trade_recap", "tutorial", "interview",
                 "podcast", "short_clip", "profile", "other", "unknown"}
PRIORITIES = {"high": 0, "medium": 1, "low": 2}


def normalize_url(url: str) -> str:
    """Stable key for a URL: lowercase scheme/host, no fragment, no trailing slash."""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/") or ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower().removeprefix("www."), path, parts.query, ""))


def web_source_id(url: str) -> str:
    """Same id ingest_web assigns when the page is later fetched with canonical_url=url."""
    return stable_id("src", "web", url)


def register_citation(con: duckdb.DuckDBPyConnection, url: str, *, title: str | None = None,
                      cited_via: str, notes: str | None = None, is_synthetic: bool = False) -> str:
    """Register a URL that a search result pointed to, without fetching it."""
    source_id = web_source_id(url)
    if db.exists(con, "sources", "source_id", source_id):
        return source_id
    db.upsert(con, "sources", {
        "source_id": source_id, "source_kind": "search_citation", "platform": urlsplit(url).netloc.lower(),
        "external_id": None, "uri": url, "canonical_url": url, "title": title, "author": None,
        "published_at": None, "first_seen_at": db.now(), "last_fetched_at": None, "adapter": "websearch",
        "metadata": {"cited_via": cited_via}, "is_synthetic": is_synthetic, "notes": notes,
    })
    return source_id


def add_candidate(
    con: duckdb.DuckDBPyConnection,
    url: str,
    *,
    discovered_via: str,
    platform: str | None = None,
    title: str | None = None,
    published_text: str | None = None,
    duration_text: str | None = None,
    content_type: str | None = None,
    trader_id: str | None = None,
    priority: str | None = None,
    discovery_evidence: Any = None,
    is_synthetic: bool = False,
) -> str:
    """Queue a source for ingestion. Re-adding the same URL merges evidence and keeps the higher priority."""
    if content_type is not None and content_type not in CONTENT_TYPES:
        raise ValueError(f"content_type must be one of {sorted(CONTENT_TYPES)}")
    if priority is not None and priority not in PRIORITIES:
        raise ValueError(f"priority must be one of {sorted(PRIORITIES)}")
    db.require(con, "traders", "trader_id", trader_id)
    candidate_id = stable_id("cand", normalize_url(url))
    prev = con.execute("SELECT priority, discovery_evidence, status, source_id, created_at, title, "
                       "published_text, duration_text, content_type, trader_id "
                       "FROM source_candidates WHERE candidate_id = ?", [candidate_id]).fetchone()
    evidence = [discovery_evidence] if discovery_evidence is not None else []
    status, source_id, created = "candidate", None, db.now()
    if prev:
        old_pri, old_ev, status, source_id, created = prev[0], prev[1], prev[2], prev[3], prev[4]
        evidence = (json.loads(old_ev) if old_ev else []) + evidence
        if old_pri and (priority is None or PRIORITIES[old_pri] < PRIORITIES[priority]):
            priority = old_pri
        title = title or prev[5]
        published_text = published_text or prev[6]
        duration_text = duration_text or prev[7]
        content_type = content_type or prev[8]
        trader_id = trader_id or prev[9]
    db.upsert(con, "source_candidates", {
        "candidate_id": candidate_id, "url": url, "platform": platform, "title": title,
        "published_text": published_text, "duration_text": duration_text, "content_type": content_type,
        "trader_id": trader_id, "discovered_via": discovered_via, "discovery_evidence": evidence or None,
        "priority": priority, "status": status, "status_reason": None, "source_id": source_id,
        "created_at": created, "updated_at": db.now(), "is_synthetic": is_synthetic,
    })
    return candidate_id


def set_candidate_status(con: duckdb.DuckDBPyConnection, candidate_id: str, status: str, reason: str,
                         source_id: str | None = None) -> None:
    db.require(con, "source_candidates", "candidate_id", candidate_id)
    db.require(con, "sources", "source_id", source_id)
    if status not in CANDIDATE_STATUSES:
        raise ValueError(f"status must be one of {sorted(CANDIDATE_STATUSES)}")
    if status == "ingested" and not source_id:
        raise ValueError("ingested needs the resulting source_id")
    con.execute("UPDATE source_candidates SET status = ?, status_reason = ?, source_id = coalesce(?, source_id), "
                "updated_at = ? WHERE candidate_id = ?", [status, reason, source_id, db.now(), candidate_id])


# ------------------------------------------------------------------ lead import

_CONFIDENCE = {"high": 0.7, "medium": 0.45, "low": 0.2}   # confidence in a *lead*, never > 0.7


def _domain(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def _cite(con, ev: dict, is_synthetic: bool) -> str | None:
    url = ev.get("source_url")
    if not url:
        return None
    return register_citation(con, url, title=ev.get("source_title"),
                             cited_via=f"websearch:{ev.get('query', '')}", is_synthetic=is_synthetic)


def _claim_obs(con, ev: dict, *, trader_id: str, kind: str, content: str, confidence: float | None,
               is_synthetic: bool) -> str | None:
    sid = _cite(con, ev, is_synthetic)
    if sid is None or not (ev.get("text") or "").strip():
        return None
    return observations.add_observation(
        con, source_id=sid, modality="document", kind=kind, content=content, quote=ev["text"].strip(),
        value={"claim_origin": ev.get("claim_origin"), "query": ev.get("query"),
               "note": "text came through a web-search tool; the page itself was not fetched"},
        trader_id=trader_id, extractor="claude:websearch-agent", confidence=confidence,
        is_synthetic=is_synthetic)


def import_leads(con: duckdb.DuckDBPyConnection, path: Path | str, *, is_synthetic: bool = False) -> dict[str, int]:
    """Load a leads JSON file produced by a search agent (see docs/DATA_MODEL.md)."""
    data = json.loads(Path(path).read_text())
    seed = data["trader_seed"].strip()
    slug = annotations.slugify(seed)
    trader_id = annotations.trader_by_slug(con, slug) or annotations.add_trader(
        con, seed, slug=slug, notes="seed trader from research brief", is_synthetic=is_synthetic)
    counts = {"identities": 0, "observations": 0, "candidates": 0, "ambiguities": 0, "open_questions": 0}

    for cand in data.get("identity_candidates", []):
        evs = cand.get("evidence") or []
        conf = _CONFIDENCE.get(cand.get("same_person_confidence"), 0.2)
        handle = cand.get("handle_or_address")
        platform = cand.get("platform") if cand.get("platform") in annotations.IDENTITY_PLATFORMS else "other"
        first_source = None
        for ev in evs:
            oid = _claim_obs(con, ev, trader_id=trader_id, kind="identity_link",
                             content=f"Search result associates {platform} '{handle}' with {seed}",
                             confidence=conf, is_synthetic=is_synthetic)
            if oid:
                counts["observations"] += 1
                first_source = first_source or con.execute(
                    "SELECT source_id FROM observations WHERE observation_id = ?", [oid]).fetchone()[0]
        if not cand.get("url") and (not handle or handle.strip().lower().startswith("unknown")):
            # An account is said to exist but nothing identifies it: record the gap, not an identity.
            annotations.annotate(con, "trader", trader_id, "identity_gap",
                                 {"platform": platform, "description": handle, "reasoning": cand.get("reasoning")},
                                 annotator="claude:websearch-agent", is_synthetic=is_synthetic)
            continue
        domains = {_domain(ev["source_url"]) for ev in evs if ev.get("source_url")}
        status = "probable" if cand.get("same_person_confidence") == "high" and len(domains) >= 2 else "lead"
        notes = " | ".join(x for x in [
            f"agent confidence: {cand.get('same_person_confidence')}",
            f"reasoning: {cand.get('reasoning')}" if cand.get("reasoning") else None,
            f"doubts: {cand.get('conflicts_or_doubts')}" if cand.get("conflicts_or_doubts") else None,
            f"independent domains: {len(domains)}",
        ] if x)
        annotations.add_trader_identity(con, trader_id, platform, handle=handle, url=cand.get("url"),
                                        evidence_source_id=first_source, verification_status=status,
                                        verification_notes=notes, is_synthetic=is_synthetic)
        counts["identities"] += 1

    for amb in data.get("ambiguity", []):
        for ev in amb.get("evidence") or []:
            if _claim_obs(con, ev, trader_id=trader_id, kind="ambiguity", content=amb["description"],
                          confidence=None, is_synthetic=is_synthetic):
                counts["observations"] += 1
        annotations.annotate(con, "trader", trader_id, "ambiguity", amb["description"],
                             annotator="claude:websearch-agent", is_synthetic=is_synthetic)
        counts["ambiguities"] += 1

    for c in data.get("content_candidates", []):
        if not c.get("url"):
            continue
        evs = c.get("evidence") or []
        ctype = c.get("content_type") if c.get("content_type") in CONTENT_TYPES else "unknown"
        add_candidate(con, c["url"], discovered_via=f"websearch:{evs[0].get('query', '') if evs else ''}",
                      platform=c.get("platform"), title=c.get("title"), published_text=c.get("published"),
                      duration_text=c.get("duration"), content_type=ctype, trader_id=trader_id,
                      priority=c.get("priority") if c.get("priority") in PRIORITIES else None,
                      discovery_evidence={"attributed_because": c.get("attributed_to_trader_because"),
                                          "evidence": evs},
                      is_synthetic=is_synthetic)
        counts["candidates"] += 1

    for key, kind in (("tools_and_workflow_leads", "workflow_lead"), ("secondary_claims", "secondary_claim")):
        for item in data.get(key, []):
            text = item.get("lead") or item.get("claim") or ""
            for ev in item.get("evidence") or []:
                if _claim_obs(con, ev, trader_id=trader_id, kind=kind, content=text, confidence=None,
                              is_synthetic=is_synthetic):
                    counts["observations"] += 1

    for other in data.get("other_traders_mentioned", []):
        annotations.annotate(con, "trader", trader_id, "other_trader_lead",
                             {"name": other.get("name"), "why": other.get("why_interesting"),
                              "evidence": other.get("evidence")},
                             annotator="claude:websearch-agent", is_synthetic=is_synthetic)

    for q in data.get("open_questions", []):
        annotations.annotate(con, "trader", trader_id, "open_question", q,
                             annotator="claude:websearch-agent", is_synthetic=is_synthetic)
        counts["open_questions"] += 1

    annotations.annotate(con, "trader", trader_id, "lead_import",
                         {"file": Path(path).name, "searched_at": data.get("searched_at"),
                          "n_searches": len(data.get("searches", []))},
                         annotator="claude:websearch-agent", is_synthetic=is_synthetic)
    return counts


# ------------------------------------------------------------------ ledger

LEDGER_COLUMNS = ["ledger_kind", "id", "url", "platform", "title", "author", "published", "traders",
                  "content_type", "status", "fetched", "adapter", "discovered_via", "priority", "notes"]


def ledger_rows(con: duckdb.DuckDBPyConnection, include_synthetic: bool = False) -> list[dict]:
    syn = "" if include_synthetic else "WHERE NOT s.is_synthetic"
    sources = con.execute(f"""
        SELECT 'source', s.source_id, COALESCE(s.canonical_url, s.uri), s.platform, s.title, s.author,
               CAST(s.published_at AS VARCHAR),
               (SELECT string_agg(DISTINCT t.slug, ';') FROM (
                    SELECT trader_id FROM observations o WHERE o.source_id = s.source_id
                    UNION SELECT trader_id FROM decisions d WHERE d.source_id = s.source_id
                    UNION SELECT trader_id FROM source_candidates c WHERE c.source_id = s.source_id) x
                JOIN traders t USING (trader_id)),
               (SELECT c.content_type FROM source_candidates c WHERE c.source_id = s.source_id LIMIT 1),
               s.source_kind, s.last_fetched_at IS NOT NULL, s.adapter,
               s.metadata->>'cited_via', NULL, s.notes
        FROM sources s {syn} ORDER BY s.first_seen_at""").fetchall()
    syn_c = "" if include_synthetic else "AND NOT c.is_synthetic"
    cands = con.execute(f"""
        SELECT 'candidate', c.candidate_id, c.url, c.platform, c.title, NULL, c.published_text, t.slug,
               c.content_type, c.status, FALSE, NULL, c.discovered_via, c.priority, c.status_reason
        FROM source_candidates c LEFT JOIN traders t USING (trader_id)
        WHERE c.source_id IS NULL {syn_c}
        ORDER BY t.slug, CASE c.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, c.created_at
    """).fetchall()
    return [dict(zip(LEDGER_COLUMNS, r)) for r in [*sources, *cands]]


def export_ledger(con: duckdb.DuckDBPyConnection, out: Path | str | None = None) -> Path:
    out = Path(out) if out else config.path("ledger") / "source_ledger.csv"
    rows = ledger_rows(con)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return out
