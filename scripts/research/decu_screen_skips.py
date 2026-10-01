"""Token pages Decu opened on stream, from the browser's URL bar, and which of them they did not buy (SKIPs).

The Axiom token page URL holds the token's pump.fun bonding-curve address (axiom.trade/meme/<curve>), the PDA
of ["bonding-curve", mint] under the pump program, so OCR of the URL bar identifies the token exactly once
matched against the PDAs of tokens on the tape. Frames: the fixed 720p segment, 1 per second (60-s chunks;
a single pass over the whole file drops frames).

    python scripts/research/decu_screen_skips.py

OCR text is cached in data/processed/ocr/<source>/ (re-runs are fast). Writes
research/observations/evidence_decu_screen_visits_2026-10-01.json and records SKIP decisions with a
screen observation (frame at the visit's midpoint) plus on-chain context. Re-runnable (extractor tag).
"""
import difflib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
from solders.pubkey import Pubkey  # noqa: E402

from pipeline import annotations, config, db, decisions, frames, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402

EX = "claude:decu-screen-skips-2026-10-01"
WALLET = "4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9"
SEG = ROOT / "data/raw/video/live/twitch_decu/20261001T141139Z_720p_seg0000-1900.mp4"
T0 = datetime(2026, 10, 1, 14, 11, 39, tzinfo=timezone.utc).timestamp()   # chart clock = T0 + video t
DUR = 1900
PUMP = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
B58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{30,48}")
MIN_RATIO = 0.75            # fuzzy match of OCR'd address to a curve PDA
MIN_VISIT_S = 3             # a page shown for >= 3 s counts as a visit


def ocr_frames(source_id: str) -> dict[int, str]:
    out_dir = config.path("data") / "processed" / "ocr" / source_id
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = out_dir / "urlbar.json"
    if cache.exists():
        return {int(k): v for k, v in json.loads(cache.read_text()).items()}
    for c in range(0, DUR, 60):
        d = out_dir / f"c{c:04d}"
        d.mkdir(exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(c), "-t", "60", "-i", str(SEG), "-vf",
                        "fps=1,crop=700:20:60:46,scale=2800:80:flags=lanczos,format=gray", "-start_number", "0",
                        str(d / "u_%03d.png")], check=True)
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}

    def ocr(p: Path) -> tuple[int, str]:
        t = int(p.parent.name[1:]) + int(p.stem.split("_")[1])
        r = subprocess.run(["tesseract", str(p), "-", "--psm", "7"], capture_output=True, text=True, env=env)
        return t, r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""

    with ThreadPoolExecutor(6) as ex:
        res = dict(ex.map(ocr, sorted(out_dir.glob("c*/u_*.png"))))
    cache.write_text(json.dumps(res))
    return res


def main() -> dict:
    con = db.connect()
    sid = con.execute("SELECT source_id FROM sources WHERE title LIKE 'Decu live stream (Twitch) 720p, 14:11:39%'"
                      ).fetchone()[0]                      # registered by decu_stream_evidence.py
    text = ocr_frames(sid)
    mcon = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    toks = mcon.execute("SELECT mint, symbol, recv FROM curve_creates WHERE recv >= ? AND recv < ?",
                        [T0 - 6 * 3600, T0 + DUR]).fetchall()
    pda = {str(Pubkey.find_program_address([b"bonding-curve", bytes(Pubkey.from_string(m))], PUMP)[0]): (m, s, r)
           for m, s, r in toks}
    by_prefix: dict[str, list[str]] = {}
    for a in pda:
        by_prefix.setdefault(a[:3], []).append(a)

    def match(addr: str):
        cands = by_prefix.get(addr[:3]) or list(pda)       # prefix first (fast); fall back to all
        best = max(cands, key=lambda a: difflib.SequenceMatcher(None, a, addr).ratio())
        ratio = difflib.SequenceMatcher(None, best, addr).ratio()
        if ratio < MIN_RATIO and cands is not pda:
            best = max(pda, key=lambda a: difflib.SequenceMatcher(None, a, addr).ratio())
            ratio = difflib.SequenceMatcher(None, best, addr).ratio()
        return (best, ratio) if ratio >= MIN_RATIO else (None, ratio)

    per_s = {}
    for t, s in sorted(text.items()):
        if "/meme/" not in s:
            per_s[t] = None
            continue
        raw = re.split(r"[?&]|chain", s.split("/meme/", 1)[1])[0]
        addr = re.sub(r"[^1-9A-HJ-NP-Za-km-z]", "", raw)     # OCR inserts spaces, '/', '|' inside the address
        per_s[t] = match(addr)[0] if 30 <= len(addr) <= 48 else None
    # visits: runs of the same token page, tolerating 2-s OCR gaps
    visits, cur = [], None
    for t in range(0, DUR):
        a = per_s.get(t)
        if a and cur and a == cur["curve"] and t - cur["end"] <= 3:
            cur["end"] = t
        elif a:
            if cur:
                visits.append(cur)
            cur = {"curve": a, "start": t, "end": t}
    if cur:
        visits.append(cur)
    visits = [v for v in visits if v["end"] - v["start"] + 1 >= MIN_VISIT_S]
    buys = mcon.execute("SELECT mint, recv, sol FROM curve_trades WHERE usr = ? AND buy AND recv >= ? AND recv < ?",
                        [WALLET, T0 - 3600, T0 + DUR + 120]).fetchall()
    rows = []
    for v in visits:
        mint, sym, created = pda[v["curve"]]
        a, b = T0 + v["start"], T0 + v["end"]
        bought_before = [x for x in buys if x[0] == mint and x[1] < a - 5]
        bought_during = [x for x in buys if x[0] == mint and a - 5 <= x[1] <= b + 60]
        st = mcon.execute("SELECT arg_max(vsol / vtok, recv) * 1e9 FROM curve_trades WHERE mint = ? AND recv <= ?",
                          [mint, a]).fetchone()[0]
        rows.append({"mint": mint, "symbol": sym, "video_start_s": v["start"], "video_end_s": v["end"],
                     "seconds_open": v["end"] - v["start"] + 1, "wall_start": datetime.fromtimestamp(a, timezone.utc).isoformat(),
                     "token_age_s_at_open": round(a - created, 1), "mcap_sol_at_open": round(st, 1) if st else None,
                     "decu_bought_before": len(bought_before), "decu_bought_during_or_60s_after": len(bought_during),
                     "decu_sol_during": round(sum(x[2] for x in bought_during), 3),
                     "outcome": "BUY" if bought_during else ("HELD_ALREADY" if bought_before else "SKIP")})
    out = {"source_id": sid, "frames_ocr": len(text), "frames_on_token_page": sum(1 for v in per_s.values() if v),
           "frames_url_unmatched": sum(1 for t, s in text.items() if "/meme/" in s and not per_s.get(t)),
           "visits": rows, "counts": {k: sum(1 for r in rows if r["outcome"] == k) for k in ("BUY", "HELD_ALREADY", "SKIP")},
           "method": "URL bar OCR (tesseract 5) at 1 fps; address fuzzy-matched (ratio >= 0.75) to bonding-curve "
                     "PDAs of tokens on the tape; visit = same page >= 3 s; BUY = any buy by Decu's wallet from 5 s "
                     "before the page opened to 60 s after it closed."}
    p = ROOT / "research/observations/evidence_decu_screen_visits_2026-10-01.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    record(con, out, sid, p)
    return out


def record(con, out: dict, sid: str, path: Path) -> None:
    con.execute("DELETE FROM decision_metrics WHERE decision_id IN (SELECT decision_id FROM decisions WHERE extractor = ?)", [EX])
    con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
    con.execute("DELETE FROM decisions WHERE extractor = ?", [EX])
    tid = annotations.trader_by_slug(con, "decu")
    doc_sid, snap = ingest_document(con, str(path), title="Token pages Decu opened on stream (URL-bar OCR)",
                                    canonical_url="stream://twitch_decu/2026-10-01/screen-visits")
    con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)",
                [f"%{EX}%"])
    con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
    o_all = observations.add_observation(con, source_id=doc_sid, snapshot_id=snap, modality="screen", kind="page_visits",
                                 trader_id=tid, extractor=EX, status="reviewed", value=out["counts"],
                                 content=f"{len(out['visits'])} token-page visits of >= 3 s in the 720p segment: "
                                         f"{out['counts']}.")
    for v in out["visits"]:
        if v["outcome"] != "SKIP":
            continue
        tok = decisions.add_token(con, identification="onchain_match", mint=v["mint"], ticker=v["symbol"],
                                  launchpad="pump.fun", identification_confidence=0.9,
                                  notes="identified from the Axiom URL (bonding-curve PDA) by OCR")
        mid = (v["video_start_s"] + v["video_end_s"]) / 2
        fid = frames.extract_frames(con, sid, timestamps=[float(mid)], media_path=SEG)[0]
        d = decisions.add_decision(
            con, trader_id=tid, source_id=sid, decision="SKIP", token_id=tok, extractor=EX, extraction_confidence=0.7,
            video_ts_s=float(v["video_start_s"]), decision_wallclock=datetime.fromisoformat(v["wall_start"]),
            wallclock_basis="on_screen_clock",
            observed_context=f"Token page open {v['seconds_open']} s (URL bar), no buy by the wallet then or within "
                             "60 s after",
            inferred_reason=None)
        o = observations.add_observation(
            con, source_id=sid, modality="screen", kind="token_page_visit", frame_id=fid, decision_id=d, token_id=tok,
            trader_id=tid, start_s=float(v["video_start_s"]), end_s=float(v["video_end_s"]), extractor=EX,
            confidence=0.7, status="draft",
            content=f"Browser URL shows the Axiom page of {v['symbol']!r} ({v['mint'][:8]}…) for {v['seconds_open']} s; "
                    "identified by OCR of the URL bar, matched to the token's bonding-curve address.")
        if v["mcap_sol_at_open"] is not None:
            decisions.add_reading(con, d, "market_cap_sol", observed_via="onchain", value_num=v["mcap_sol_at_open"],
                                  as_of_offset_s=0, notes="tape, at page open")
        decisions.add_reading(con, d, "token_age_s", observed_via="onchain", value_num=v["token_age_s_at_open"],
                              as_of_offset_s=0, notes="tape, at page open")
        _ = o
    from pipeline import findings
    v = out["visits"]
    c = out["counts"]
    tok = lambda k: len({x["mint"] for x in v if x["outcome"] == k})
    skips = sorted({str(x["symbol"]).strip() for x in v if x["outcome"] == "SKIP"})
    findings.add_finding(
        con, trader_id=tid, funnel_stage="matching", evidence_type="observed",
        statement=f"In 31 min of 720p footage Decu opened {len(v)} token pages for >= 3 s: {c['BUY']} visits on "
                  f"{tok('BUY')} tokens they bought, {c['HELD_ALREADY']} on tokens already held, {c['SKIP']} skips "
                  f"({', '.join(skips)}). Pages are opened almost only for tokens they then buy; most screening "
                  "happens on Pulse cards. Around their Kano-kun buy they opened another Kano-kun copy (GFG2cM94…) "
                  "twice, at ~94 and ~277 SOL market cap, and passed both times; the copy they bought (DCquzH…) was "
                  "at ~50 SOL.",
        evidence=[("observation", o_all, "supports")], n_supporting=c["BUY"], n_observable=len(v), confidence=0.7,
        notes=f"{EX}; URL-bar OCR; {out['frames_url_unmatched']} token-page frames could not be matched to a bonding "
              "curve (likely migrated pools)")


if __name__ == "__main__":
    o = main()
    print(json.dumps({k: o[k] for k in ("frames_ocr", "frames_on_token_page", "frames_url_unmatched", "counts")}, indent=1))
    for v in o["visits"]:
        print(v["wall_start"][11:19], f"{v['seconds_open']:>3}s", v["outcome"][:4], f"{str(v['symbol'])[:12]:12}",
              "age", v["token_age_s_at_open"], "mc", v["mcap_sol_at_open"], "sol", v["decu_sol_during"])
