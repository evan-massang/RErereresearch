"""Human-readable exports of the database into research/, reports/ and sources/.

Everything written here is *generated* from the database (the source of truth)
and is safe to regenerate. Synthetic rows are excluded unless asked for.
Run ``python -m pipeline export-all`` before committing.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb

from . import candidates, config, db


def _hms(t: float | None) -> str:
    if t is None:
        return "--:--:--"
    t = int(t)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def source_traders(con, source_id: str) -> list[str]:
    rows = con.execute("""
        SELECT DISTINCT t.slug FROM traders t WHERE t.trader_id IN (
            SELECT trader_id FROM source_candidates WHERE source_id = ?
            UNION SELECT trader_id FROM decisions WHERE source_id = ?
            UNION SELECT trader_id FROM observations WHERE source_id = ?)
        ORDER BY 1""", [source_id] * 3).fetchall()
    return [r[0] for r in rows]


# ------------------------------------------------------------------ transcripts

def export_transcripts(con: duckdb.DuckDBPyConnection, include_synthetic: bool = False) -> list[Path]:
    """research/transcripts/<trader>/<source_id>__<method>_<lang>.txt with [HH:MM:SS] lines (rg-friendly)."""
    rows = con.execute(f"""
        SELECT t.transcript_id, t.source_id, t.method, t.language, t.model, s.title,
               COALESCE(s.canonical_url, s.uri), s.author, CAST(s.published_at AS VARCHAR)
        FROM transcripts t JOIN sources s USING (source_id)
        {'' if include_synthetic else 'WHERE NOT s.is_synthetic'}""").fetchall()
    written = []
    for tid, sid, method, lang, model, title, url, author, published in rows:
        traders = source_traders(con, sid) or ["unattributed"]
        segs = con.execute("SELECT start_s, text FROM transcript_segments WHERE transcript_id = ? ORDER BY seq",
                           [tid]).fetchall()
        header = [f"# {title or sid}", f"# url: {url}", f"# channel: {author}", f"# published: {published}",
                  f"# source_id: {sid}  transcript_id: {tid}  method: {method}  language: {lang}  model: {model}",
                  f"# traders: {', '.join(traders)}", ""]
        body = [f"[{_hms(s)}] {text}" for s, text in segs]
        for slug in traders:
            out = config.path("transcripts", slug) / f"{sid}__{method}_{lang or 'xx'}.txt"
            out.write_text("\n".join(header + body) + "\n")
            written.append(out)
    return written


# ------------------------------------------------------------------ worksheets

def render_worksheet(con: duckdb.DuckDBPyConnection, source_id: str) -> Path:
    s = con.execute("""SELECT s.title, COALESCE(s.canonical_url, s.uri), s.author, s.published_at, v.duration_s,
                              v.was_live, v.live_start_at
                       FROM sources s LEFT JOIN videos v USING (source_id) WHERE s.source_id = ?""",
                    [source_id]).fetchone()
    if s is None:
        raise ValueError(f"unknown source_id {source_id!r}")
    title, url, author, published, duration, was_live, live_start = s
    lines = [f"# {title or source_id}", "",
             "_Generated from the database by `python -m pipeline export-all`; edits here are overwritten._", "",
             f"- **URL:** {url}", f"- **Channel:** {author}", f"- **Published:** {published}",
             f"- **Duration:** {_hms(duration)}", f"- **Live recording:** {was_live}  (stream start: {live_start})",
             f"- **Traders:** {', '.join(source_traders(con, source_id)) or '—'}", f"- **source_id:** `{source_id}`", ""]
    trs = con.execute("SELECT transcript_id, method, language, segment_count FROM transcripts WHERE source_id = ?",
                      [source_id]).fetchall()
    lines += ["## Transcripts", ""] + ([f"- `{t}` — {m} ({l}), {n} segments" for t, m, l, n in trs] or ["- none"]) + [""]

    mom = con.execute("""SELECT m.start_s, m.category, m.matched_text, m.review_status, m.decision_id, ts.text
                         FROM candidate_moments m JOIN transcripts t USING (transcript_id)
                         JOIN transcript_segments ts ON ts.transcript_id = m.transcript_id AND ts.seq = m.seq
                         WHERE t.source_id = ? AND m.category IN ('entry','add','partial','exit','stop','rug','skip','missed')
                         ORDER BY m.start_s""", [source_id]).fetchall()
    reviewed = sum(1 for r in mom if r[3] != "unreviewed")
    lines += [f"## Candidate decision moments ({reviewed}/{len(mom)} reviewed)", "",
              "| time | category | status | transcript |", "|---|---|---|---|"]
    lines += [f"| {_hms(t)} | {c} | {st}{' → ' + d if d else ''} | {txt.replace('|', '/')[:140]} |"
              for t, c, _, st, d, txt in mom] or ["| — | — | — | — |"]
    lines.append("")

    decs = con.execute("""SELECT video_ts_s, decision, ticker, market_cap_usd, stated_reason, inferred_reason,
                                 extraction_confidence, status, decision_id
                          FROM v_decisions_wide WHERE source_id = ? ORDER BY video_ts_s""", [source_id]).fetchall()
    lines += [f"## Decisions ({len(decs)})", "",
              "| time | decision | token | mcap | stated reason | inferred reason (ours) | conf | status |",
              "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {_hms(t)} | {d} | {tk or '?'} | {mc if mc is not None else ''} | {(sr or '')[:80]} | "
              f"{(ir or '')[:80]} | {c} | {st} |" for t, d, tk, mc, sr, ir, c, st, _ in decs] or ["| — | | | | | | | |"]
    nframes = con.execute("SELECT count(*) FROM frames WHERE source_id = ?", [source_id]).fetchone()[0]
    lines += ["", f"Frames extracted: {nframes}", ""]
    out = config.path("videos") / f"{source_id}.md"
    out.write_text("\n".join(lines))
    return out


# ------------------------------------------------------------------ trader identity pages

def render_identity(con: duckdb.DuckDBPyConnection, trader_id: str) -> Path:
    slug, name, aliases = con.execute("SELECT slug, display_name, aliases FROM traders WHERE trader_id = ?",
                                      [trader_id]).fetchone()
    L = [f"# {name} — identity & sources", "",
         "_Generated from the database. Statuses: **lead** = a search result or third party says so; "
         "**probable** = independent leads agree; **verified** = a primary source links it (e.g. the trader's own "
         "profile); **rejected** = shown to be someone else. Nothing below 'verified' is established._", ""]
    if aliases:
        L += [f"Aliases: {', '.join(aliases)}", ""]
    for status in ("verified", "probable", "lead", "rejected"):
        rows = con.execute("""SELECT i.platform, i.handle, i.url, i.verification_notes, s.canonical_url
                              FROM trader_identities i LEFT JOIN sources s ON s.source_id = i.evidence_source_id
                              WHERE i.trader_id = ? AND i.verification_status = ? ORDER BY i.platform""",
                           [trader_id, status]).fetchall()
        if rows:
            L += [f"## Accounts — {status}", "", "| platform | handle | url | first evidence | notes |",
                  "|---|---|---|---|---|"]
            L += [f"| {p} | {h or ''} | {u or ''} | {e or ''} | {(n or '').replace('|', '/')} |" for p, h, u, n, e in rows]
            L.append("")
    for key, heading in (("identity_gap", "Accounts said to exist but not identified"),
                         ("ambiguity", "Ambiguities (people/tokens that could be confused)"),
                         ("open_question", "Open questions"), ("other_trader_lead", "Other traders mentioned (leads)")):
        rows = con.execute("SELECT value FROM annotations WHERE target_type='trader' AND target_id = ? AND key = ? "
                           "ORDER BY created_at", [trader_id, key]).fetchall()
        if rows:
            L += [f"## {heading}", ""]
            for (v,) in rows:
                val = json.loads(v)
                if isinstance(val, dict) and "name" in val:
                    L.append(f"- {val['name']}: {val.get('why') or ''}")
                elif isinstance(val, dict) and "platform" in val:
                    L.append(f"- {val['platform']}: {val.get('description') or ''}")
                else:
                    L.append(f"- {val}")
            L.append("")
    cands = con.execute("""SELECT priority, content_type, title, url, duration_text, published_text, status
                           FROM source_candidates WHERE trader_id = ? AND NOT is_synthetic
                           ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, content_type""",
                        [trader_id]).fetchall()
    if cands:
        L += ["## Content candidates (queue)", "", "| priority | type | title | duration | published | status |",
              "|---|---|---|---|---|---|"]
        L += [f"| {p or ''} | {c or ''} | [{(t or u).replace('|', '/')[:90]}]({u}) | {d or ''} | {pub or ''} | {st} |"
              for p, c, t, u, d, pub, st in cands]
        L.append("")
    claims = con.execute("""SELECT kind, content, quote, source_url FROM v_observation_provenance
                            WHERE trader_id = ? AND kind IN ('workflow_lead', 'secondary_claim') AND NOT is_synthetic
                            ORDER BY kind, content""", [trader_id]).fetchall()
    if claims:
        L += ["## Third-party claims (leads to verify — not stated, not observed)", ""]
        L += [f"- [{k}] {c} — “{(q or '').strip()[:200]}” ({u})" for k, c, q, u in claims]
        L.append("")
    out = config.path("traders", slug) / "identity.md"
    out.write_text("\n".join(L))
    return out


# ------------------------------------------------------------------ tables, frames, all

def export_tables(con: duckdb.DuckDBPyConnection, include_synthetic: bool = False) -> list[Path]:
    syn = "" if include_synthetic else "WHERE NOT is_synthetic"
    specs = [
        (config.path("trades") / "trades.csv", f"SELECT * FROM v_trade_summary {syn} ORDER BY entry_time"),
        (config.path("rejected_tokens") / "skips.csv",
         f"SELECT * FROM v_decisions_wide WHERE decision = 'SKIP' {'' if include_synthetic else 'AND NOT is_synthetic'} "
         "ORDER BY trader, source_id, video_ts_s"),
        (config.path("observations") / "decisions.csv",
         f"SELECT * FROM v_decisions_wide {syn} ORDER BY trader, source_id, video_ts_s"),
        (config.path("observations") / "observations.csv",
         f"SELECT * FROM v_observation_provenance {syn} ORDER BY trader, source_id, start_s"),
        (config.path("observations") / "findings.csv", f"SELECT * FROM v_findings {syn} ORDER BY trader, funnel_stage"),
        (config.path("hypothesis_reports") / "hypotheses.csv", f"SELECT * FROM hypotheses {syn} ORDER BY created_at"),
        (config.path("simulation_reports") / "sim_runs.csv", f"SELECT * FROM sim_runs {syn} ORDER BY created_at"),
    ]
    written = []
    for path, sql in specs:
        con.execute(f"COPY ({sql}) TO '{path.as_posix()}' (HEADER, DELIMITER ',')")
        written.append(path)
    return written


def copy_evidence_frames(con: duckdb.DuckDBPyConnection) -> list[Path]:
    """Copy frames cited by decisions/observations into research/frames (committed)."""
    rows = con.execute("""SELECT DISTINCT f.source_id, f.local_path FROM frames f JOIN sources s USING (source_id)
                          WHERE NOT s.is_synthetic AND f.frame_id IN (
                              SELECT frame_id FROM decision_metrics WHERE frame_id IS NOT NULL
                              UNION SELECT frame_id FROM observations WHERE frame_id IS NOT NULL)""").fetchall()
    out = []
    for sid, rel_path in rows:
        src = config.resolve(rel_path)
        if not src.exists():
            continue
        dst = config.path("evidence_frames", sid) / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        out.append(dst)
    return out


def export_all(con: duckdb.DuckDBPyConnection) -> dict:
    result = {
        "parquet": len(db.export_parquet(con)),
        "ledger": str(candidates.export_ledger(con)),
        "transcripts": len(export_transcripts(con)),
        "tables": len(export_tables(con)),
        "evidence_frames": len(copy_evidence_frames(con)),
    }
    sids = [r[0] for r in con.execute(
        "SELECT source_id FROM sources WHERE source_kind = 'video' AND NOT is_synthetic").fetchall()]
    result["worksheets"] = len([render_worksheet(con, s) for s in sids])
    tids = [r[0] for r in con.execute("SELECT trader_id FROM traders WHERE NOT is_synthetic").fetchall()]
    result["identity_pages"] = len([render_identity(con, t) for t in tids])
    return result


# ------------------------------------------------------------------ information environment

def render_info_environment(json_path: Path | str, out: Path | str | None = None) -> Path:
    """Render a search agent's tool/protocol leads file as a reference page for reading frames."""
    data = json.loads(Path(json_path).read_text())

    def srcs(evs: list[dict], k: int = 3) -> str:
        urls = []
        for e in evs or []:
            u = e.get("source_url")
            if u and u not in urls:
                urls.append(u)
        return ", ".join(urls[:k]) + (f" (+{len(urls) - k})" if len(urls) > k else "") if urls else "unattributed summary"

    def cell(x) -> str:
        return str(x or "").replace("|", "/").replace("\n", " ")

    L = ["# Information environment: tools and protocol mechanics", "",
         f"_Generated from `{Path(json_path).name}` (web-search leads collected {data.get('searched_at')}). "
         "Everything here came from search-result titles or model-written search summaries; pages were not fetched. "
         "Treat each line as a lead to confirm against video frames or official docs, never as fact._", ""]
    for t in data.get("tools", []):
        L += [f"## {t['tool']}", ""]
        for w in t.get("what_it_is", [])[:2]:
            L.append(f"> {cell(w.get('text'))[:400]} — {w.get('source_url') or 'unattributed'}")
        L.append("")
        fields = t.get("displayed_fields", [])
        if fields:
            L += ["| field | where in UI | definition given | sources |", "|---|---|---|---|"]
            L += [f"| {cell(f.get('field'))} | {cell(f.get('where_in_ui'))} | {cell(f.get('definition_if_given'))[:220]} | "
                  f"{srcs(f.get('evidence'))} |" for f in fields]
            L.append("")
        feats = t.get("features", [])
        if feats:
            L += ["Features:", ""] + [f"- {cell(f.get('feature'))[:240]} ({srcs(f.get('evidence'), 2)})" for f in feats] + [""]
        used = t.get("used_by_traders_evidence", [])
        if used:
            L += ["Used by traders (leads):", ""] + [f"- {cell(u.get('text'))[:240]} ({srcs(u.get('evidence'), 2)})"
                                                     for u in used] + [""]
    mech = data.get("protocol_mechanics", [])
    if mech:
        L += ["## Protocol mechanics (inputs to the execution model — verify before use)", "",
              "| topic | value / description | as of | conflicts | sources |", "|---|---|---|---|---|"]
        L += [f"| {cell(m.get('topic'))} | {cell(m.get('value_or_description'))[:400]} | {cell(m.get('as_of_date'))[:160]} | "
              f"{cell(m.get('conflicts'))[:200]} | {srcs(m.get('evidence'))} |" for m in mech]
        L.append("")
    if data.get("open_questions"):
        L += ["## Open questions (settle these from frames / primary sources)", ""]
        L += [f"- {cell(q)}" for q in data["open_questions"]]
        L.append("")
    out = Path(out) if out else config.root() / "research" / "information_environment.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L))
    return out
