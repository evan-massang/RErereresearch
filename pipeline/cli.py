"""Command-line entry point: ``python -m pipeline <command> ...``

Every command prints JSON so its output can be piped into jq or read by an agent.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import annotations, config, db, frames, observations
from .ingest_transcript import TRANSCRIBERS, ingest_caption_file, transcribe
from .ingest_video import ingest_video
from .ingest_web import ingest_document, ingest_web
from .provenance import SourceUnavailable, classify_error, tool_versions
from .sources import VIDEO_ADAPTERS, WEB_ADAPTERS, get_video_adapter, get_web_adapter

DEFAULT_PROBES = [
    "https://www.youtube.com",
    "https://i.ytimg.com",
    "https://huggingface.co",
    "https://pypi.org/simple/",
    "https://example.com",
]


def out(obj) -> None:
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))


def _video_adapter(args):
    kwargs = {"cookies_file": args.cookies} if args.adapter == "ytdlp" and args.cookies else {}
    return get_video_adapter(args.adapter, **kwargs)


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _jsonish(s: str):
    try:
        return json.loads(s)
    except ValueError:
        return s


# ------------------------------------------------------------------ commands

def cmd_init(args, con):
    out({"archive_root": str(config.archive_root()), "db": str(args.db or config.db_path()),
         "tables": db.TABLES})


def cmd_status(args, con):
    out({"archive_root": str(config.archive_root()), "tables": db.table_counts(con),
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


def cmd_add_observation(args, con):
    oid = observations.add_observation(
        con, source_id=args.source_id, kind=args.kind, content=args.content, extractor=args.extractor,
        quote=args.quote, value=_jsonish(args.value) if args.value else None, trader_id=args.trader_id,
        trade_id=args.trade_id, transcript_id=args.transcript_id, segment_seq=args.segment,
        start_s=args.start, end_s=args.end, frame_id=args.frame_id, snapshot_id=args.snapshot_id,
        char_start=args.char_start, char_end=args.char_end, confidence=args.confidence,
        status=args.status, is_synthetic=args.synthetic)
    row = con.execute("SELECT quote_verified FROM observations WHERE observation_id = ?", [oid]).fetchone()
    out({"observation_id": oid, "quote_verified": row[0]})


def cmd_import_observations(args, con):
    ids = observations.import_jsonl(con, args.file, extractor=args.extractor,
                                    is_synthetic=True if args.synthetic else None)
    out({"imported": len(ids), "observation_ids": ids})


def cmd_set_observation_status(args, con):
    observations.set_status(con, args.observation_id, args.status)
    out({"observation_id": args.observation_id, "status": args.status})


def cmd_add_trader(args, con):
    out({"trader_id": annotations.add_trader(con, args.name, aliases=args.alias, notes=args.notes,
                                             is_synthetic=args.synthetic)})


def cmd_add_identity(args, con):
    out({"identity_id": annotations.add_trader_identity(
        con, args.trader_id, args.platform, handle=args.handle, url=args.url,
        evidence_source_id=args.evidence_source, is_synthetic=args.synthetic)})


def cmd_add_trade(args, con):
    evidence = []
    for e in args.evidence or []:
        oid, _, role = e.partition(":")
        evidence.append((oid, role or None))
    tid = annotations.add_trade(
        con, trader_id=args.trader_id, instrument=args.instrument, asset_class=args.asset_class,
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


def cmd_export_parquet(args, con):
    out({"written": [str(p) for p in db.export_parquet(con, args.out)]})


def cmd_import_parquet(args, con):
    out({"rows_added": db.import_parquet(con, args.input)})


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
    p = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__)
    p.add_argument("--db", help="database file (default: <archive>/db/research.duckdb)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_, description=help_)
        sp.set_defaults(fn=fn)
        return sp

    def synthetic(sp):
        sp.add_argument("--synthetic", action="store_true",
                        help="mark as synthetic test data (removed by purge-synthetic)")

    add("init", cmd_init, "create the archive layout and database")
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
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("ingest-captions", cmd_ingest_captions, "import a VTT/SRT/JSON/TXT transcript for a source")
    sp.add_argument("source_id")
    sp.add_argument("file")
    sp.add_argument("--lang")
    sp.add_argument("--method", default="imported",
                    choices=["imported", "platform_manual", "platform_auto"])

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

    sp = add("extract-clip", cmd_extract_clip, "cut a clip from a source's media")
    sp.add_argument("source_id")
    sp.add_argument("start", type=float)
    sp.add_argument("end", type=float)
    sp.add_argument("--media-path")

    sp = add("ingest-web", cmd_ingest_web, "snapshot a page and extract its main text")
    sp.add_argument("uri")
    sp.add_argument("--adapter", default="http", choices=sorted(WEB_ADAPTERS))
    sp.add_argument("--canonical-url", help="file a saved copy under its original URL")
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("ingest-doc", cmd_ingest_doc, "archive a local file (HTML, PDF, CSV, TXT) as a source")
    sp.add_argument("path")
    sp.add_argument("--title")
    sp.add_argument("--canonical-url")
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("add-observation", cmd_add_observation, "record one evidence-linked observation")
    sp.add_argument("--source-id", required=True)
    sp.add_argument("--kind", required=True)
    sp.add_argument("--content", required=True)
    sp.add_argument("--extractor", required=True, help="human | claude | script:<name>")
    sp.add_argument("--quote")
    sp.add_argument("--value", help="JSON payload")
    sp.add_argument("--trader-id")
    sp.add_argument("--trade-id")
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

    sp = add("add-trader", cmd_add_trader, "create a trader record")
    sp.add_argument("name")
    sp.add_argument("--alias", action="append")
    sp.add_argument("--notes")
    synthetic(sp)

    sp = add("add-identity", cmd_add_identity, "attach a platform handle/URL to a trader")
    sp.add_argument("trader_id")
    sp.add_argument("platform")
    sp.add_argument("--handle")
    sp.add_argument("--url")
    sp.add_argument("--evidence-source")
    synthetic(sp)

    sp = add("add-trade", cmd_add_trade, "create a trade-level record")
    sp.add_argument("--trader-id")
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

    sp = add("export-parquet", cmd_export_parquet, "write every table to Parquet")
    sp.add_argument("--out")
    sp = add("import-parquet", cmd_import_parquet, "load tables from Parquet (upsert)")
    sp.add_argument("--in", dest="input")

    sp = add("purge-synthetic", cmd_purge_synthetic, "delete all synthetic test rows")
    sp.add_argument("--yes", action="store_true")

    sp = add("query", cmd_query, "run SQL against the archive and print JSON")
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
