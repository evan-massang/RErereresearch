"""Evidence: Decu on stream, second segment 14:43:19-16:11:39 UTC (2026-10-01).

Footage: data/raw/video/live/twitch_decu/20261001T141139Z_720p.mp4, the finished 720p capture (14:11:39-16:11:39;
chart clock = 14:11:39 + video t; frames here are read and registered from this same file).
Chain: curve trades from the tape; trades after migration (Pump AMM) from kolscan's relay of the wallet's swaps.

Re-runnable: removes its own earlier rows (extractor tag).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402

from pipeline import annotations, config, db, decisions, findings, frames, observations  # noqa: E402
from pipeline.ingest_video import ingest_video  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402
from pipeline.sources import get_video_adapter  # noqa: E402

import os
SEG = os.environ.get("DECU_SEGMENT", "2")          # "2": 14:43-16:11 (720p capture 1); "3": 16:15-21:20 (capture 2)
EX = f"claude:decu-stream-{SEG}-2026-10-01"
WALLET = "4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9"
if SEG == "3":
    VIDEO = ROOT / "data/raw/video/live/twitch_decu/20261001T161519Z.mp4"
    T0 = datetime(2026, 10, 1, 16, 15, 19, tzinfo=timezone.utc)
    A, B = T0.timestamp(), T0.timestamp() + 18314
else:
    VIDEO = ROOT / "data/raw/video/live/twitch_decu/20261001T141139Z_720p.mp4"
    T0 = datetime(2026, 10, 1, 14, 11, 39, tzinfo=timezone.utc)
    A, B = T0.timestamp() + 1900, T0.timestamp() + 7200
LAG_S = 3.0
utc = lambda x: datetime.fromtimestamp(x, timezone.utc)

con = db.connect()
con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
con.execute("DELETE FROM decision_metrics WHERE decision_id IN (SELECT decision_id FROM decisions WHERE extractor = ?)", [EX])
con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
con.execute("DELETE FROM decisions WHERE extractor = ?", [EX])
tid = annotations.trader_by_slug(con, "decu")

res = ingest_video(con, str(VIDEO), get_video_adapter("local"), captions=False,
                   notes=f"Finished live capture of twitch.tv/decu at 720p; video t=0 is {T0.isoformat()}; the stream "
                         "continued (next capture starts 16:15:19)")
vid = res.source_id
con.execute("UPDATE sources SET title = ?, author = ?, published_at = ? WHERE source_id = ?",
            [f"Decu live stream (Twitch) 720p, {T0:%H:%M:%S}-{datetime.fromtimestamp(B, timezone.utc):%H:%M:%S} UTC "
             f"(capture {SEG})", "Decu", T0, vid])
for (fid, lp) in con.execute("SELECT frame_id, local_path FROM frames WHERE source_id = ?", [vid]).fetchall():
    con.execute("DELETE FROM frames WHERE frame_id = ?", [fid])
    (ROOT / lp if not Path(lp).is_absolute() else Path(lp)).unlink(missing_ok=True)

m = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
curve = m.execute("""SELECT t.sig, t.recv, t.mint, c.symbol, c.name, c.recv, t.buy, t.sol, t.tok, t.vsol, t.vtok
                     FROM curve_trades t LEFT JOIN curve_creates c USING (mint)
                     WHERE t.usr = ? AND t.recv >= ? AND t.recv < ? ORDER BY t.recv""", [WALLET, A, B]).fetchall()
cols = ["sig", "recv", "mint", "symbol", "name", "created", "buy", "sol", "tok", "vsol", "vtok"]
curve = [dict(zip(cols, r)) for r in curve]
mints = sorted({t["mint"] for t in curve})
amm = m.execute(f"""SELECT signature, ts, recv, coalesce(nullif(in_token, ''), nullif(out_token, '')) AS mint, direction, dex,
                           sol_change, in_amount, out_amount
                    FROM kolscan_msgs WHERE wallet = ? AND dex = 'Pump AMM' AND recv >= ? AND recv < ? + 1800
                      AND (in_token IN ({','.join('?' for _ in mints)}) OR out_token IN ({','.join('?' for _ in mints)}))
                    ORDER BY recv""", [WALLET, A, B, *mints, *mints]).fetchall() if mints else []
amm = [dict(zip(["sig", "ts", "recv", "mint", "direction", "dex", "sol", "in_amount", "out_amount"], r)) for r in amm]
ev = {"note": "Decu's wallet 14:43:19-16:11:39 UTC: curve trades from the tape; Pump AMM trades (after migration) "
              "from kolscan's relay of the wallet's swaps, up to 30 min after the window.",
      "curve_trades": [{**t, "recv_utc": utc(t["recv"]).isoformat()} for t in curve], "amm_trades": amm}
ev_path = ROOT / "research/observations/evidence_decu_stream_2_2026-10-01.json"
ev_path.write_text(json.dumps(ev, indent=1, default=str))
doc_sid, snap = ingest_document(con, str(ev_path), title="Decu's on-stream trades, second segment (curve + AMM)",
                                canonical_url="stream://pump_curve/2026-10-01/decu-stream-2")

tokens, held, dec = {}, {}, {}
for t in curve:
    mt = t["mint"]
    if mt not in tokens:
        tokens[mt] = decisions.add_token(con, identification="onchain_match", mint=mt, ticker=t["symbol"], name=t["name"],
                                         launchpad="pump.fun", identification_confidence=0.99,
                                         created_onchain_at=utc(t["created"]) if t["created"] else None)
    if t["buy"]:
        kind = "ADD" if held.get(mt, 0) > 0 else "BUY"
        held[mt] = held.get(mt, 0) + t["tok"]
    else:
        held[mt] = held.get(mt, 0) - t["tok"]
        kind = "SELL" if held[mt] <= 1e-3 * t["tok"] else "PARTIAL_SELL"
        if kind == "SELL":
            held[mt] = 0.0
    vt = round(t["recv"] - 1.2 - T0.timestamp() - LAG_S, 1)
    d = decisions.add_decision(
        con, trader_id=tid, source_id=vid, decision=kind, token_id=tokens[mt], extractor=EX, extraction_confidence=0.95,
        video_ts_s=vt if 0 <= vt <= 7200 else None, decision_wallclock=utc(t["recv"] - 1.2), wallclock_basis="onchain_tx",
        position_size=round(t["sol"], 4), position_size_unit="SOL",
        observed_context=f"{'Bought' if t['buy'] else 'Sold'} {t['sol']:.3f} SOL on the bonding curve"
                         + (f"; token age {t['recv'] - t['created']:.0f} s" if t["created"] else ""))
    dec.setdefault(mt, []).append((t, d))
    decisions.add_reading(con, d, "market_cap_sol", observed_via="onchain", value_num=round(t["vsol"] / t["vtok"] * 1e9, 2),
                          as_of_offset_s=0, notes="vsol/vtok x 1e9 after the trade (tape)")
for a_ in amm:
    if a_["mint"] not in tokens or a_["direction"] != "Sell":
        continue
    held[a_["mint"]] = held.get(a_["mint"], 0) - (a_["in_amount"] or 0)
    kind = "SELL" if held[a_["mint"]] <= 1e5 else "PARTIAL_SELL"
    decisions.add_decision(
        con, trader_id=tid, source_id=doc_sid, decision=kind, token_id=tokens[a_["mint"]], extractor=EX,
        extraction_confidence=0.85, decision_wallclock=utc(a_["ts"] or a_["recv"]), wallclock_basis="onchain_tx",
        result_sol=round(a_["sol"], 4), result_basis="onchain",
        observed_context=f"Sold {a_['in_amount'] / 1e6:.2f}M tokens for {a_['sol']:.3f} SOL on Pump AMM after the token "
                         "migrated (kolscan relay)")

if SEG == "3":
    print("ok", vid, len(curve), "curve trades,", sum(1 for a_ in amm if a_["direction"] == "Sell"), "AMM sells (on-chain only)")
    raise SystemExit
first = lambda pre: next(d for t, d in dec[next(k for k in dec if k.startswith(pre))] if t["buy"])
obs = lambda **kw: observations.add_observation(con, trader_id=tid, extractor=EX, status="reviewed", source_id=vid,
                                                modality="screen", **kw)
f2549, f3076, f3620, f5089 = frames.extract_frames(con, vid, timestamps=[2549.0, 3076.0, 3620.0, 5089.0],
                                                   media_path=VIDEO)
o_pro = obs(kind="tweet_preview", frame_id=f2549, start_s=2549.0, decision_id=first("B3K5qb"),
            content="Hovering the X link of the 1-s-old 'PROHUMAN  Pro Human' card (V $3K, MC $6.43K, counter '58/5412') "
                    "shows a post by @Narra_Creator ('Meme Creator', verified badge, Joined Nov 2014, 871 followers): "
                    "'BIGGEST ANTI AI NARRATIVE?? The Pro Human Assembly brought together lawmakers, researchers, artists, "
                    "labor leaders and figures like Bernie Sanders and Steve Bannon around one idea: AI should serve "
                    "humans, not replace them. They've built it around the Pro Human AI Declaration and the message "
                    "\"keep the future…'. Decu's 2-SOL buy lands ~3 s later.")
decisions.add_reading(con, first("B3K5qb"), "author_followers", observed_via="screen", value_num=871, frame_id=f2549,
                      observation_id=o_pro, as_of_offset_s=-3, notes="followers of the X account linked on the card")
o_q1 = obs(kind="token_page", frame_id=f3076, start_s=3076.0, decision_id=first("AUN5zK"),
           content="QRCAT token page at chart clock 10:02:55 (UTC-5): age 32s, MC $18.6K, liquidity $16.8K, B.Curve "
                   "78.46%, holders 25, Top10 33.42%, Dev H 0%, Snipers H 7.29%, Insiders 0%, Bundlers 32.22%, 'Dev Tokens "
                   "(88)'; chart shows a 'DS' marker. Tracker rows include wallets labelled 'Cupsey'/'cupsey' buying "
                   "'AI'. A PROHUMAN tab is also open.")
for metric, val in (("market_cap_usd", 18600), ("liquidity_usd", 16800), ("token_age_s", 32), ("bonding_curve_pct", 78.46),
                    ("holders", 25), ("top10_pct", 33.42), ("dev_pct", 0), ("snipers_pct", 7.29), ("insiders_pct", 0),
                    ("bundles_pct", 32.22), ("x_axiom_dev_tokens", 88)):
    decisions.add_reading(con, first("AUN5zK"), metric, observed_via="screen", value_num=val, frame_id=f3076,
                          observation_id=o_q1, as_of_offset_s=-3, unit="count" if metric.startswith("x_") else None)
o_q2 = obs(kind="pulse", frame_id=f3620, start_s=3620.0, decision_id=first("D1K3bB"),
           content="Pulse at 15:11:59: Final Stretch top 'QRCAT', 21s, V $10K, MC $7.53K; the Migrated column shows "
                   "another 'QRCAT  qrcat' (migrated 3:54 ago, V $195K, MC $40.1K). Tracker: 'Dali' QRCAT 1.3671, "
                   "'beanz' QRCAT 0.5703. Decu's 3-SOL buy of the new QRCAT lands ~5 s later.")
o_tok = obs(kind="token_page", frame_id=f5089, start_s=5089.0, decision_id=first("5PuMW1"),
            content="'token' page at chart clock 10:36:28: age 26s, MC $26K, liquidity $19.8K, B.Curve 87.34%, ATH $30K, "
                    "holders 89, Top10 22.17%, Dev H 0%, Snipers H 1.03%, Insiders 3.03%, Bundlers 59.02%, 'Dev Tokens "
                    "(872)'; linked 'OPENAI +5'.")
for metric, val in (("market_cap_usd", 26000), ("liquidity_usd", 19800), ("token_age_s", 26), ("bonding_curve_pct", 87.34),
                    ("holders", 89), ("top10_pct", 22.17), ("dev_pct", 0), ("snipers_pct", 1.03), ("insiders_pct", 3.03),
                    ("bundles_pct", 59.02), ("x_axiom_dev_tokens", 872)):
    decisions.add_reading(con, first("5PuMW1"), metric, observed_via="screen", value_num=val, frame_id=f5089,
                          observation_id=o_tok, as_of_offset_s=-3, unit="count" if metric.startswith("x_") else None)
o_chain = observations.add_observation(
    con, trader_id=tid, extractor=EX, status="reviewed", source_id=doc_sid, snapshot_id=snap, modality="onchain",
    kind="wallet_trades", value={"curve_trades": len(curve), "amm_sells": sum(1 for a_ in amm if a_["direction"] == "Sell")},
    content="Decu's wallet in the segment: first QRCAT (AUN5zK…) bought 4.89 SOL at age 36 s and sold 74 s later for "
            "4.93 SOL (a loss after fees); that token was not seen to migrate in the tape, but Pulse shows a migrated "
            "'QRCAT' at $40.1K. 9 min later Decu bought a second QRCAT (D1K3bB…) at age 27 s, added small buys, and "
            "sold it on Pump AMM after its 15:16:23 migration for 17.2 SOL in 5 sells.")
findings.add_finding(
    con, trader_id=tid, funnel_stage="narrative", evidence_type="observed",
    statement="A third case of Decu reading the linked X post before buying: on PROHUMAN they hovered a post by an "
              "871-follower account framing the token as the 'biggest anti-AI narrative', and bought ~3 s later.",
    evidence=[("observation", o_pro, "supports")], n_supporting=1, n_observable=1, confidence=0.8, notes=EX)
findings.add_finding(
    con, trader_id=tid, funnel_stage="exit", evidence_type="observed",
    statement="Decu cut a flat QRCAT position after 74 s (about break-even before fees), then bought a newer QRCAT "
              "copy 9 minutes later and held it through migration, selling on Pump AMM for ~17.2 SOL against ~4.8 SOL in.",
    evidence=[("observation", o_chain, "supports"), ("observation", o_q2, "supports"),
              ("observation", o_q1, "supports")], n_supporting=1, n_observable=1, confidence=0.75, notes=EX)
print("ok", vid, len(curve), "curve trades,", sum(1 for a_ in amm if a_["direction"] == "Sell"), "AMM sells")
