"""Command-line entry point: ``python -m pipeline <command> ...``

Every command prints JSON so its output can be piped into jq or read by an agent.
Run ``python -m pipeline <command> -h`` for the arguments of each command.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import (annotations, candidates, config, db, decisions, exports, findings, frames, moments,
               observations)
from .ingest_transcript import TRANSCRIBERS, ingest_caption_file, transcribe
from .ingest_video import ingest_video
from .ingest_web import ingest_document, ingest_web
from .provenance import SourceUnavailable, classify_error, tool_versions
from .sources import VIDEO_ADAPTERS, WEB_ADAPTERS, get_video_adapter, get_web_adapter

DEFAULT_PROBES = [
    "https://www.youtube.com", "https://i.ytimg.com", "https://www.twitch.tv", "https://kick.com",
    "https://huggingface.co", "https://x.com", "https://api.dexscreener.com", "https://api.geckoterminal.com",
    "https://api.mainnet-beta.solana.com", "https://pypi.org/simple/",
]


def out(obj) -> None:
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))


def _video_adapter(args):
    kwargs = {"cookies_file": args.cookies} if args.adapter == "ytdlp" and args.cookies else {}
    return get_video_adapter(args.adapter, **kwargs)


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        raise ValueError(f"timestamp {s!r} needs a timezone, e.g. 2026-01-02T03:04:05+00:00")
    return d


def _jsonish(s: str | None):
    if s is None:
        return None
    try:
        return json.loads(s)
    except ValueError:
        return s


# ------------------------------------------------------------------ core / ingestion

def cmd_init(args, con):
    out({"root": str(config.root()), "db": str(args.db or config.db_path()), "tables": db.TABLES})


def cmd_status(args, con):
    out({"root": str(config.root()), "tables": db.table_counts(con),
         "synthetic_rows": db.synthetic_counts(con),
         "fetch_status": dict(con.execute(
             "SELECT stage || ':' || status, count(*) FROM fetch_events GROUP BY 1 ORDER BY 1").fetchall()),
         "tool_versions": tool_versions(),
         "adapters": {"video": sorted(VIDEO_ADAPTERS), "web": sorted(WEB_ADAPTERS),
                      "transcribers": sorted(TRANSCRIBERS)}})


def cmd_check_network(args, con):
    import httpx

    from .sources.http_adapter import _verify

    results = {}
    for url in args.url or DEFAULT_PROBES:
        try:
            with httpx.Client(timeout=args.timeout, verify=_verify(), follow_redirects=True) as c:
                r = c.head(url)
            results[url] = {"status": "reachable", "http_status": r.status_code}
        except Exception as e:  # noqa: BLE001 — report any failure
            results[url] = {"status": classify_error(e), "error": f"{type(e).__name__}: {e}"[:300]}
    out(results)


def cmd_list_entries(args, con):
    out(_video_adapter(args).list_entries(args.uri, args.limit))


def cmd_ingest_video(args, con):
    res = ingest_video(con, args.uri, _video_adapter(args), media=args.media,
                       captions=not args.no_captions, languages=args.lang,
                       is_synthetic=args.synthetic, notes=args.notes)
    if res.source_id and args.candidate_id:
        candidates.set_candidate_status(con, args.candidate_id, "ingested", "ingest-video", source_id=res.source_id)
    out(res.__dict__)
    return 0 if res.stages.get("video_metadata") == "ok" else 2


def cmd_ingest_captions(args, con):
    out({"transcript_id": ingest_caption_file(con, args.source_id, args.file,
                                              method=args.method, language=args.lang)})


def cmd_transcribe(args, con):
    t = TRANSCRIBERS[args.engine](model=args.model, device=args.device, compute_type=args.compute_type)
    out({"transcript_id": transcribe(con, args.source_id, transcriber=t,
                                     media_path=args.media_path, language=args.language)})


def cmd_extract_frames(args, con):
    ts = [float(x) for x in args.at.split(",")] if args.at else None
    ids = frames.extract_frames(con, args.source_id, timestamps=ts, every_s=args.every,
                                scene_threshold=args.scene, start_s=args.start, end_s=args.end,
                                max_frames=args.max, width=args.width, media_path=args.media_path)
    out({"frame_ids": ids})


def cmd_extract_window(args, con):
    ids = frames.extract_decision_window(
        con, args.source_id, args.anchor, before=args.before, after=args.after, step=args.step,
        dense_radius=args.dense_radius, dense_step=args.dense_step, adaptive=not args.no_adaptive,
        change_threshold=args.threshold, max_frames=args.max, width=args.width, media_path=args.media_path)
    rows = con.execute(f"SELECT frame_id, timestamp_s, scene_score, local_path FROM frames WHERE frame_id IN "
                       f"({', '.join('?' for _ in ids)}) ORDER BY timestamp_s", ids).fetchall() if ids else []
    out({"anchor_s": args.anchor, "frames": [dict(zip(["frame_id", "t", "scene_score", "path"], r)) for r in rows]})


def cmd_extract_clip(args, con):
    out({"artifact_id": frames.extract_clip(con, args.source_id, args.start, args.end, args.media_path)})


def cmd_ingest_web(args, con):
    sid, snap = ingest_web(con, args.uri, get_web_adapter(args.adapter), canonical_url=args.canonical_url,
                           is_synthetic=args.synthetic, notes=args.notes)
    out({"source_id": sid, "snapshot_id": snap})


def cmd_ingest_doc(args, con):
    sid, snap = ingest_document(con, args.path, title=args.title, canonical_url=args.canonical_url,
                                is_synthetic=args.synthetic, notes=args.notes)
    out({"source_id": sid, "snapshot_id": snap})


# ------------------------------------------------------------------ discovery queue

def cmd_import_leads(args, con):
    out({f: candidates.import_leads(con, f, is_synthetic=args.synthetic) for f in args.files})


def cmd_add_candidate(args, con):
    trader = annotations.trader_by_slug(con, args.trader) if args.trader else None
    if args.trader and trader is None:
        raise ValueError(f"unknown trader slug {args.trader!r}")
    out({"candidate_id": candidates.add_candidate(
        con, args.url, discovered_via=args.discovered_via, platform=args.platform, title=args.title,
        published_text=args.published, duration_text=args.duration, content_type=args.content_type,
        trader_id=trader, priority=args.priority, is_synthetic=args.synthetic)})


def cmd_candidates(args, con):
    where, params = ["NOT c.is_synthetic"], []
    if args.trader:
        where.append("t.slug = ?")
        params.append(args.trader)
    if args.status:
        where.append("c.status = ?")
        params.append(args.status)
    rows = con.execute(f"""SELECT c.candidate_id, t.slug, c.priority, c.content_type, c.status, c.title, c.url,
                                  c.duration_text, c.published_text
                           FROM source_candidates c LEFT JOIN traders t USING (trader_id)
                           WHERE {' AND '.join(where)}
                           ORDER BY t.slug, CASE c.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END""",
                       params).fetchall()
    out([dict(zip(["candidate_id", "trader", "priority", "content_type", "status", "title", "url", "duration",
                   "published"], r)) for r in rows])


def cmd_set_candidate_status(args, con):
    candidates.set_candidate_status(con, args.candidate_id, args.status, args.reason, source_id=args.source_id)
    out({"candidate_id": args.candidate_id, "status": args.status})


# ------------------------------------------------------------------ traders / identities / tokens / narratives

def cmd_add_trader(args, con):
    out({"trader_id": annotations.add_trader(con, args.name, slug=args.slug, aliases=args.alias,
                                             notes=args.notes, is_synthetic=args.synthetic)})


def cmd_add_identity(args, con):
    out({"identity_id": annotations.add_trader_identity(
        con, args.trader_id, args.platform, handle=args.handle, url=args.url,
        evidence_source_id=args.evidence_source, verification_status=args.status,
        verification_notes=args.notes, is_synthetic=args.synthetic)})


def cmd_set_identity_status(args, con):
    annotations.set_identity_status(con, args.identity_id, args.status, args.notes,
                                    evidence_source_id=args.evidence_source)
    out({"identity_id": args.identity_id, "status": args.status})


def cmd_add_token(args, con):
    out({"token_id": decisions.add_token(
        con, identification=args.identification, ticker=args.ticker, name=args.name, mint=args.mint,
        identification_confidence=args.confidence, launchpad=args.launchpad,
        image_description=args.image, notes=args.notes, is_synthetic=args.synthetic)})


def cmd_set_token_mint(args, con):
    decisions.set_token_mint(con, args.token_id, args.mint, identification=args.identification,
                             confidence=args.confidence, note=args.note)
    out({"token_id": args.token_id, "mint": args.mint})


def cmd_add_narrative(args, con):
    out({"narrative_id": decisions.add_narrative(
        con, args.title, description=args.description, origin_description=args.origin,
        origin_source_id=args.origin_source, first_seen_at=_dt(args.first_seen), category=args.category,
        notes=args.notes, is_synthetic=args.synthetic)})


def cmd_link_token_narrative(args, con):
    decisions.link_token_narrative(con, args.token_id, args.narrative_id, args.relation, args.observation_id)
    out({"token_id": args.token_id, "narrative_id": args.narrative_id, "relation": args.relation})


# ------------------------------------------------------------------ decisions & observations

def cmd_add_decision(args, con):
    out({"decision_id": decisions.add_decision(
        con, trader_id=args.trader_id, source_id=args.source_id, decision=args.decision,
        extraction_confidence=args.confidence, extractor=args.extractor, video_ts_s=args.at,
        decision_wallclock=_dt(args.wallclock), wallclock_basis=args.wallclock_basis, token_id=args.token_id,
        trade_id=args.trade_id, discovery_channel=args.discovery, stated_reason=args.stated_reason,
        observed_context=args.observed_context, inferred_reason=args.inferred_reason,
        reason_codes=args.reason_code, chart_state=args.chart_state, narrative_id=args.narrative_id,
        position_size=args.size, position_size_unit=args.size_unit, result_pct=args.result_pct,
        result_sol=args.result_sol, result_basis=args.result_basis, notes=args.notes,
        is_synthetic=args.synthetic)})


def cmd_add_reading(args, con):
    out({"reading_id": decisions.add_reading(
        con, args.decision_id, args.metric, observed_via=args.via, value_num=args.value,
        value_text=args.text, unit=args.unit, metric_window=args.window, frame_id=args.frame_id,
        observation_id=args.observation_id, as_of_offset_s=args.offset, confidence=args.confidence,
        notes=args.notes)})


def cmd_import_decisions(args, con):
    ids = decisions.import_decisions_jsonl(con, args.file, is_synthetic=True if args.synthetic else None)
    out({"imported": len(ids), "decision_ids": ids})


def cmd_set_decision_status(args, con):
    decisions.set_decision_status(con, args.decision_id, args.status)
    out({"decision_id": args.decision_id, "status": args.status})


def cmd_add_observation(args, con):
    oid = observations.add_observation(
        con, source_id=args.source_id, modality=args.modality, kind=args.kind, content=args.content,
        extractor=args.extractor, quote=args.quote, value=_jsonish(args.value), trader_id=args.trader_id,
        trade_id=args.trade_id, decision_id=args.decision_id, token_id=args.token_id,
        transcript_id=args.transcript_id, segment_seq=args.segment, start_s=args.start, end_s=args.end,
        frame_id=args.frame_id, snapshot_id=args.snapshot_id, char_start=args.char_start,
        char_end=args.char_end, confidence=args.confidence, status=args.status, is_synthetic=args.synthetic)
    row = con.execute("SELECT quote_verified FROM observations WHERE observation_id = ?", [oid]).fetchone()
    out({"observation_id": oid, "quote_verified": row[0]})


def cmd_import_observations(args, con):
    ids = observations.import_jsonl(con, args.file, extractor=args.extractor,
                                    is_synthetic=True if args.synthetic else None)
    out({"imported": len(ids), "observation_ids": ids})


def cmd_set_observation_status(args, con):
    observations.set_status(con, args.observation_id, args.status)
    out({"observation_id": args.observation_id, "status": args.status})


def cmd_reverify_quotes(args, con):
    out(observations.reverify_quotes(con))


def cmd_find_moments(args, con):
    found = moments.find_moments(con, args.transcript_id)
    by_cat: dict[str, int] = {}
    for m in found:
        by_cat[m["category"]] = by_cat.get(m["category"], 0) + 1
    out({"moments": len(found), "by_category": by_cat,
         "busiest_windows": moments.busiest_windows(con, args.transcript_id, window_s=args.window, top=args.top)})


def cmd_review_moment(args, con):
    moments.review_moment(con, args.moment_id, args.status, args.decision_id)
    out({"moment_id": args.moment_id, "status": args.status})


# ------------------------------------------------------------------ trades & annotations

def cmd_add_trade(args, con):
    evidence = []
    for e in args.evidence or []:
        oid, _, role = e.partition(":")
        evidence.append((oid, role or None))
    tid = annotations.add_trade(
        con, trader_id=args.trader_id, token_id=args.token_id, source_id=args.source_id,
        observed_via=args.observed_via, instrument=args.instrument, asset_class=args.asset_class,
        direction=args.direction, entry_time=_dt(args.entry_time), entry_price=args.entry_price,
        exit_time=_dt(args.exit_time), exit_price=args.exit_price, stop_price=args.stop_price,
        target_price=args.target_price, size=args.size, size_unit=args.size_unit, currency=args.currency,
        timeframe=args.timeframe, outcome=args.outcome, pnl=args.pnl, pnl_unit=args.pnl_unit,
        status=args.status, confidence=args.confidence, notes=args.notes, evidence=evidence,
        is_synthetic=args.synthetic)
    out({"trade_id": tid})


def cmd_link_evidence(args, con):
    annotations.link_evidence(con, args.trade_id, args.observation_id, args.role)
    out({"trade_id": args.trade_id, "observation_id": args.observation_id})


def cmd_annotate(args, con):
    out({"annotation_id": annotations.annotate(con, args.target_type, args.target_id, args.key,
                                               _jsonish(args.value), annotator=args.annotator,
                                               is_synthetic=args.synthetic)})


# ------------------------------------------------------------------ findings & hypotheses

def _evidence_specs(specs: list[str] | None) -> list[tuple]:
    out_ = []
    for s in specs or []:
        parts = s.split(":", 3)
        if len(parts) < 3:
            raise ValueError(f"evidence {s!r} must be kind:id:relation[:note]")
        out_.append(tuple(parts))
    return out_


def cmd_add_finding(args, con):
    out({"finding_id": findings.add_finding(
        con, trader_id=args.trader_id, funnel_stage=args.stage, evidence_type=args.type,
        statement=args.statement, evidence=_evidence_specs(args.evidence), n_supporting=args.n_supporting,
        n_observable=args.n_observable, n_contradicting=args.n_contradicting, confidence=args.confidence,
        notes=args.notes, is_synthetic=args.synthetic)})


def cmd_link_finding(args, con):
    findings.link_evidence(con, args.finding_id, args.kind, args.evidence_id, args.relation, args.note)
    out({"finding_id": args.finding_id})


def cmd_set_finding_status(args, con):
    findings.set_finding_status(con, args.finding_id, args.status, args.note, args.superseded_by)
    out({"finding_id": args.finding_id, "status": args.status})


def cmd_check_findings(args, con):
    problems = findings.check_integrity(con)
    out({"ok": not problems, "problems": problems})
    return 0 if not problems else 1


def cmd_add_hypothesis(args, con):
    out({"hypothesis_id": findings.add_hypothesis(
        con, statement=args.statement, measurable_definition=args.definition, rationale=args.rationale,
        basis_finding_ids=args.basis, parent_id=args.parent, motivated_by_run_id=args.motivated_by_run,
        trader_scope=args.scope, is_synthetic=args.synthetic)})


def cmd_lineage(args, con):
    out(findings.hypothesis_lineage(con, args.hypothesis_id))


def cmd_define_splits(args, con):
    from .sim.splits import define_splits

    periods = {name: (_dt(getattr(args, f"{name}_start")), _dt(getattr(args, f"{name}_end")))
               for name in ("train", "validation", "holdout")}
    define_splits(con, args.split_set, periods, notes=args.notes, is_synthetic=args.synthetic)
    out({"split_set": args.split_set, "periods": periods})


# ------------------------------------------------------------------ exports

def cmd_export_parquet(args, con):
    out({"written": [str(p) for p in db.export_parquet(con, args.out)]})


def cmd_import_parquet(args, con):
    out({"rows_added": db.import_parquet(con, args.input)})


def cmd_export_all(args, con):
    out(exports.export_all(con))


def cmd_worksheet(args, con):
    out({"path": str(exports.render_worksheet(con, args.source_id))})


def cmd_purge_synthetic(args, con):
    if not args.yes:
        out({"would_delete_synthetic": db.synthetic_counts(con), "hint": "re-run with --yes"})
        return 1
    out({"deleted": db.purge_synthetic(con)})


def cmd_query(args, con):
    df = con.execute(args.sql).df()
    print(df.to_json(orient="records", indent=2, date_format="iso", default_handler=str))


# ------------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", help="database file (default: <root>/data/research.duckdb)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_, description=help_)
        sp.set_defaults(fn=fn)
        return sp

    def synthetic(sp):
        sp.add_argument("--synthetic", action="store_true",
                        help="mark as synthetic test data (removed by purge-synthetic)")

    add("init", cmd_init, "create the project layout and database")
    add("status", cmd_status, "row counts, fetch outcomes, tool versions, adapters")
    sp = add("check-network", cmd_check_network, "probe which hosts this environment can reach")
    sp.add_argument("--url", action="append", help="URL to probe (repeatable; default: built-in list)")
    sp.add_argument("--timeout", type=float, default=10)

    def video_opts(sp):
        sp.add_argument("--adapter", default="ytdlp", choices=sorted(VIDEO_ADAPTERS))
        sp.add_argument("--cookies", help="Netscape cookies.txt for yt-dlp")

    sp = add("list-entries", cmd_list_entries, "expand a channel/playlist/search/dir into video URIs")
    sp.add_argument("uri")
    sp.add_argument("--limit", type=int)
    video_opts(sp)

    sp = add("ingest-video", cmd_ingest_video, "store video metadata (+ optional media and captions)")
    sp.add_argument("uri")
    video_opts(sp)
    sp.add_argument("--media", choices=["video", "audio"], help="also download media")
    sp.add_argument("--no-captions", action="store_true")
    sp.add_argument("--lang", action="append", help="caption language (repeatable; default en, en-*)")
    sp.add_argument("--candidate-id", help="mark this queued candidate as ingested")
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("ingest-captions", cmd_ingest_captions, "import a VTT/SRT/JSON/TXT transcript for a source")
    sp.add_argument("source_id")
    sp.add_argument("file")
    sp.add_argument("--lang")
    sp.add_argument("--method", default="imported", choices=["imported", "platform_manual", "platform_auto"])

    sp = add("transcribe", cmd_transcribe, "speech-to-text on a source's media")
    sp.add_argument("source_id")
    sp.add_argument("--engine", default="faster-whisper", choices=sorted(TRANSCRIBERS))
    sp.add_argument("--model", default="small")
    sp.add_argument("--language")
    sp.add_argument("--device", default="auto")
    sp.add_argument("--compute-type", default="int8")
    sp.add_argument("--media-path")

    sp = add("extract-frames", cmd_extract_frames, "extract stills from a source's video")
    sp.add_argument("source_id")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--at", help="comma-separated timestamps in seconds")
    g.add_argument("--every", type=float, help="interval in seconds")
    g.add_argument("--scene", type=float, help="scene-change threshold 0-1 (e.g. 0.3)")
    sp.add_argument("--start", type=float, default=0.0)
    sp.add_argument("--end", type=float)
    sp.add_argument("--max", type=int)
    sp.add_argument("--width", type=int)
    sp.add_argument("--media-path")

    sp = add("extract-window", cmd_extract_window,
             "frames before/at/after a decision, densified where the screen changes fast")
    sp.add_argument("source_id")
    sp.add_argument("anchor", type=float, help="decision time in seconds")
    sp.add_argument("--before", type=float, default=12.0)
    sp.add_argument("--after", type=float, default=18.0)
    sp.add_argument("--step", type=float, default=2.0)
    sp.add_argument("--dense-radius", type=float, default=4.0)
    sp.add_argument("--dense-step", type=float, default=0.5)
    sp.add_argument("--no-adaptive", action="store_true")
    sp.add_argument("--threshold", type=float, default=0.03, help="visual change score that adds a frame")
    sp.add_argument("--max", type=int, default=150)
    sp.add_argument("--width", type=int)
    sp.add_argument("--media-path")

    sp = add("extract-clip", cmd_extract_clip, "cut a clip from a source's media")
    sp.add_argument("source_id")
    sp.add_argument("start", type=float)
    sp.add_argument("end", type=float)
    sp.add_argument("--media-path")

    sp = add("ingest-web", cmd_ingest_web, "snapshot a page and extract its main text")
    sp.add_argument("uri")
    sp.add_argument("--adapter", default="http", choices=sorted(WEB_ADAPTERS))
    sp.add_argument("--canonical-url", help="file a saved copy (or a cited URL) under this URL")
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("ingest-doc", cmd_ingest_doc, "archive a local file (HTML, PDF, CSV, TXT) as a source")
    sp.add_argument("path")
    sp.add_argument("--title")
    sp.add_argument("--canonical-url")
    sp.add_argument("--notes")
    synthetic(sp)

    # discovery queue
    sp = add("import-leads", cmd_import_leads, "load search-agent lead files (identities, candidates, claims)")
    sp.add_argument("files", nargs="+")
    synthetic(sp)

    sp = add("add-candidate", cmd_add_candidate, "queue a source for ingestion")
    sp.add_argument("url")
    sp.add_argument("--discovered-via", required=True, help="websearch:<query> | link_from:<source_id> | manual")
    sp.add_argument("--trader", help="trader slug")
    sp.add_argument("--platform")
    sp.add_argument("--title")
    sp.add_argument("--published")
    sp.add_argument("--duration")
    sp.add_argument("--content-type", choices=sorted(candidates.CONTENT_TYPES))
    sp.add_argument("--priority", choices=sorted(candidates.PRIORITIES))
    synthetic(sp)

    sp = add("candidates", cmd_candidates, "list the source queue")
    sp.add_argument("--trader", help="trader slug")
    sp.add_argument("--status", choices=sorted(candidates.CANDIDATE_STATUSES))

    sp = add("set-candidate-status", cmd_set_candidate_status, "update a queued source")
    sp.add_argument("candidate_id")
    sp.add_argument("status", choices=sorted(candidates.CANDIDATE_STATUSES))
    sp.add_argument("--reason", required=True)
    sp.add_argument("--source-id")

    # traders etc.
    sp = add("add-trader", cmd_add_trader, "create a trader record")
    sp.add_argument("name")
    sp.add_argument("--slug")
    sp.add_argument("--alias", action="append")
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("add-identity", cmd_add_identity, "attach a handle/URL/wallet to a trader")
    sp.add_argument("trader_id")
    sp.add_argument("platform", choices=sorted(annotations.IDENTITY_PLATFORMS))
    sp.add_argument("--handle")
    sp.add_argument("--url")
    sp.add_argument("--evidence-source")
    sp.add_argument("--status", default="lead", choices=sorted(annotations.IDENTITY_STATUSES))
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("set-identity-status", cmd_set_identity_status, "promote/demote an identity, with reasons")
    sp.add_argument("identity_id")
    sp.add_argument("status", choices=sorted(annotations.IDENTITY_STATUSES))
    sp.add_argument("--notes", required=True)
    sp.add_argument("--evidence-source")

    sp = add("add-token", cmd_add_token, "register a token as identified in evidence")
    sp.add_argument("--identification", required=True, choices=sorted(decisions.TOKEN_IDENTIFICATION))
    sp.add_argument("--ticker")
    sp.add_argument("--name")
    sp.add_argument("--mint")
    sp.add_argument("--confidence", type=float)
    sp.add_argument("--launchpad")
    sp.add_argument("--image", help="description of the token image")
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("set-token-mint", cmd_set_token_mint, "record a recovered mint address")
    sp.add_argument("token_id")
    sp.add_argument("mint")
    sp.add_argument("--identification", default="onchain_match", choices=sorted(decisions.TOKEN_IDENTIFICATION))
    sp.add_argument("--confidence", type=float)
    sp.add_argument("--note")

    sp = add("add-narrative", cmd_add_narrative, "record a narrative/story")
    sp.add_argument("title")
    sp.add_argument("--description")
    sp.add_argument("--origin", help="who/what originated it, as evidenced")
    sp.add_argument("--origin-source")
    sp.add_argument("--first-seen", help="ISO timestamp with timezone")
    sp.add_argument("--category")
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("link-token-narrative", cmd_link_token_narrative, "relate a token to a narrative")
    sp.add_argument("token_id")
    sp.add_argument("narrative_id")
    sp.add_argument("relation", choices=sorted(decisions.NARRATIVE_RELATIONS))
    sp.add_argument("--observation-id")

    # decisions
    sp = add("add-decision", cmd_add_decision, "record one observed decision (BUY/SKIP/SELL/...)")
    sp.add_argument("--trader-id", required=True)
    sp.add_argument("--source-id", required=True)
    sp.add_argument("--decision", required=True, choices=sorted(decisions.DECISIONS))
    sp.add_argument("--confidence", type=float, required=True, help="extraction confidence 0-1")
    sp.add_argument("--extractor", required=True)
    sp.add_argument("--at", type=float, help="video time in seconds")
    sp.add_argument("--wallclock", help="ISO timestamp with timezone")
    sp.add_argument("--wallclock-basis", choices=sorted(decisions.WALLCLOCK_BASES))
    sp.add_argument("--token-id")
    sp.add_argument("--trade-id")
    sp.add_argument("--discovery")
    sp.add_argument("--stated-reason", help="what the trader said")
    sp.add_argument("--observed-context", help="what the screen showed")
    sp.add_argument("--inferred-reason", help="our inference (kept separate)")
    sp.add_argument("--reason-code", action="append")
    sp.add_argument("--chart-state")
    sp.add_argument("--narrative-id")
    sp.add_argument("--size", type=float)
    sp.add_argument("--size-unit", choices=sorted(decisions.SIZE_UNITS))
    sp.add_argument("--result-pct", type=float)
    sp.add_argument("--result-sol", type=float)
    sp.add_argument("--result-basis", choices=sorted(decisions.RESULT_BASES))
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("add-reading", cmd_add_reading, "attach a metric reading (with provenance) to a decision")
    sp.add_argument("decision_id")
    sp.add_argument("metric", help="see pipeline/decisions.py METRICS, or x_<tool>_<field>")
    sp.add_argument("--via", required=True, choices=sorted(decisions.OBSERVED_VIA))
    sp.add_argument("--value", type=float)
    sp.add_argument("--text", help="value exactly as displayed, e.g. 12.4K")
    sp.add_argument("--unit")
    sp.add_argument("--window", help="e.g. 5m | 1h | lifetime | unknown")
    sp.add_argument("--frame-id")
    sp.add_argument("--observation-id")
    sp.add_argument("--offset", type=float, help="reading time minus decision time, seconds")
    sp.add_argument("--confidence", type=float)
    sp.add_argument("--notes")

    sp = add("import-decisions", cmd_import_decisions, "bulk-add decisions + readings from JSONL (all-or-nothing)")
    sp.add_argument("file")
    synthetic(sp)

    sp = add("set-decision-status", cmd_set_decision_status, "mark a decision reviewed/rejected")
    sp.add_argument("decision_id")
    sp.add_argument("status", choices=sorted(decisions.STATUSES))

    sp = add("add-observation", cmd_add_observation, "record one evidence-linked observation")
    sp.add_argument("--source-id", required=True)
    sp.add_argument("--modality", required=True, choices=sorted(observations.MODALITIES))
    sp.add_argument("--kind", required=True)
    sp.add_argument("--content", required=True)
    sp.add_argument("--extractor", required=True, help="human | claude | script:<name>")
    sp.add_argument("--quote")
    sp.add_argument("--value", help="JSON payload")
    sp.add_argument("--trader-id")
    sp.add_argument("--trade-id")
    sp.add_argument("--decision-id")
    sp.add_argument("--token-id")
    sp.add_argument("--transcript-id")
    sp.add_argument("--segment", type=int)
    sp.add_argument("--start", type=float)
    sp.add_argument("--end", type=float)
    sp.add_argument("--frame-id")
    sp.add_argument("--snapshot-id")
    sp.add_argument("--char-start", type=int)
    sp.add_argument("--char-end", type=int)
    sp.add_argument("--confidence", type=float)
    sp.add_argument("--status", default="draft", choices=sorted(observations.STATUSES))
    synthetic(sp)

    sp = add("import-observations", cmd_import_observations, "bulk-add observations from JSONL (all-or-nothing)")
    sp.add_argument("file")
    sp.add_argument("--extractor")
    synthetic(sp)

    sp = add("set-observation-status", cmd_set_observation_status, "mark an observation reviewed/rejected")
    sp.add_argument("observation_id")
    sp.add_argument("status", choices=sorted(observations.STATUSES))

    add("reverify-quotes", cmd_reverify_quotes, "re-check every quote against now-available transcripts/pages")

    sp = add("find-moments", cmd_find_moments, "flag candidate decision moments in a transcript")
    sp.add_argument("transcript_id")
    sp.add_argument("--window", type=float, default=120.0)
    sp.add_argument("--top", type=int, default=20)

    sp = add("review-moment", cmd_review_moment, "mark a candidate moment confirmed / false positive")
    sp.add_argument("moment_id")
    sp.add_argument("status", choices=["unreviewed", "confirmed", "false_positive"])
    sp.add_argument("--decision-id")

    # trades & annotations
    sp = add("add-trade", cmd_add_trade, "create a trade episode record")
    sp.add_argument("--trader-id")
    sp.add_argument("--token-id")
    sp.add_argument("--source-id")
    sp.add_argument("--observed-via", choices=sorted(annotations.OBSERVED_VIA))
    sp.add_argument("--instrument")
    sp.add_argument("--asset-class")
    sp.add_argument("--direction", default="unknown", choices=sorted(annotations.DIRECTIONS))
    sp.add_argument("--entry-time")
    sp.add_argument("--entry-price", type=float)
    sp.add_argument("--exit-time")
    sp.add_argument("--exit-price", type=float)
    sp.add_argument("--stop-price", type=float)
    sp.add_argument("--target-price", type=float)
    sp.add_argument("--size", type=float)
    sp.add_argument("--size-unit")
    sp.add_argument("--currency")
    sp.add_argument("--timeframe")
    sp.add_argument("--outcome", default="unknown", choices=sorted(annotations.OUTCOMES))
    sp.add_argument("--pnl", type=float)
    sp.add_argument("--pnl-unit")
    sp.add_argument("--status", default="reported", choices=sorted(annotations.TRADE_STATUSES))
    sp.add_argument("--confidence", type=float)
    sp.add_argument("--notes")
    sp.add_argument("--evidence", action="append", help="OBSERVATION_ID[:role] (repeatable)")
    synthetic(sp)

    sp = add("link-evidence", cmd_link_evidence, "link an observation to a trade")
    sp.add_argument("trade_id")
    sp.add_argument("observation_id")
    sp.add_argument("--role")

    sp = add("annotate", cmd_annotate, "attach a key/value annotation to any record")
    sp.add_argument("target_type", choices=sorted(annotations.TARGETS))
    sp.add_argument("target_id")
    sp.add_argument("key")
    sp.add_argument("value", help="JSON or plain string")
    sp.add_argument("--annotator", required=True)
    synthetic(sp)

    # findings & hypotheses
    sp = add("add-finding", cmd_add_finding, "record a rule-level finding (stated/observed/inferred/validated)")
    sp.add_argument("--trader-id")
    sp.add_argument("--stage", required=True, choices=sorted(findings.FUNNEL_STAGES))
    sp.add_argument("--type", required=True, choices=sorted(findings.EVIDENCE_TYPES))
    sp.add_argument("--statement", required=True)
    sp.add_argument("--evidence", action="append",
                    help="kind:id:relation[:note], kind in observation|decision|finding|sim_run")
    sp.add_argument("--n-supporting", type=int)
    sp.add_argument("--n-observable", type=int)
    sp.add_argument("--n-contradicting", type=int)
    sp.add_argument("--confidence", type=float)
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("link-finding", cmd_link_finding, "add evidence (incl. contradicting) to a finding")
    sp.add_argument("finding_id")
    sp.add_argument("kind", choices=sorted(findings.EVIDENCE_KINDS))
    sp.add_argument("evidence_id")
    sp.add_argument("relation", choices=sorted(findings.RELATIONS))
    sp.add_argument("--note")

    sp = add("set-finding-status", cmd_set_finding_status, "change a finding's status, with a reason")
    sp.add_argument("finding_id")
    sp.add_argument("status", choices=sorted(findings.FINDING_STATUSES))
    sp.add_argument("--note", required=True)
    sp.add_argument("--superseded-by")

    add("check-findings", cmd_check_findings, "re-check every finding against its evidence-type rules")

    sp = add("add-hypothesis", cmd_add_hypothesis, "record a measurable hypothesis and why it exists")
    sp.add_argument("--statement", required=True)
    sp.add_argument("--definition", required=True, help="measurable definition")
    sp.add_argument("--rationale", required=True)
    sp.add_argument("--basis", action="append", help="finding_id (repeatable)")
    sp.add_argument("--parent")
    sp.add_argument("--motivated-by-run")
    sp.add_argument("--scope", help="trader_id or 'cross'")
    synthetic(sp)

    sp = add("lineage", cmd_lineage, "show a hypothesis and the chain of reasons behind it")
    sp.add_argument("hypothesis_id")

    sp = add("define-splits", cmd_define_splits, "define chronological train/validation/holdout periods")
    sp.add_argument("split_set")
    for name in ("train", "validation", "holdout"):
        sp.add_argument(f"--{name}-start", required=True)
        sp.add_argument(f"--{name}-end", required=True)
    sp.add_argument("--notes")
    synthetic(sp)

    # exports
    sp = add("export-parquet", cmd_export_parquet, "write every table to Parquet")
    sp.add_argument("--out")
    sp = add("import-parquet", cmd_import_parquet, "load tables from Parquet (upsert)")
    sp.add_argument("--in", dest="input")
    add("export-all", cmd_export_all, "regenerate parquet, ledger, transcripts, worksheets, CSVs, identity pages")
    sp = add("worksheet", cmd_worksheet, "regenerate one video's worksheet")
    sp.add_argument("source_id")

    sp = add("purge-synthetic", cmd_purge_synthetic, "delete all synthetic test rows")
    sp.add_argument("--yes", action="store_true")

    sp = add("query", cmd_query, "run SQL against the database and print JSON")
    sp.add_argument("sql")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    con = db.connect(Path(args.db) if args.db else None)
    try:
        rc = args.fn(args, con)
    except SourceUnavailable as e:
        out({"error": str(e), "status": e.status})
        return 2
    except ValueError as e:
        out({"error": str(e)})
        return 1
    finally:
        con.close()
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
