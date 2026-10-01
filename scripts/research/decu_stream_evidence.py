"""Evidence: Decu trading live on Twitch with their verified wallet (2026-10-01).

Footage (fixed segments cut from the live captures, so frame timestamps stay valid):
  data/raw/video/live/twitch_decu/20261001T133837Z_seg0000-2000.mp4        360p, t=0 at 13:38:37 UTC
  data/raw/video/live/twitch_decu/20261001T141139Z_720p_seg0000-1900.mp4   720p, t=0 at 14:11:39 UTC
Clock: Axiom's chart clock on the 720p frames reads exactly 14:11:39 + t (UTC-5 shown), so for the 720p
segment video t = wall-clock - 14:11:39. On-chain buys land ~3 s after the frame where the quick-buy panel
is still empty (Sow: frame t=573 shows 14:21:12, buy in block at ~14:21:15).
Tape: pump.fun bonding-curve events recorded live (data/raw/streams/pump_curve).

Every value below is read from a frame (screen), from the chain (onchain), or computed from chain data.
Nothing that was not visible is filled in. Re-runnable: removes its own earlier rows (extractor tag).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import annotations, db, decisions, findings, frames, market, observations  # noqa: E402
from pipeline.ingest_video import ingest_video  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402
from pipeline.onchain import Rpc  # noqa: E402
from pipeline.sources import get_video_adapter  # noqa: E402

EX = "claude:decu-stream-2026-10-01"
WALLET = "4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9"
D = ROOT / "data/raw/video/live/twitch_decu"
SEG360 = (D / "20261001T133837Z_seg0000-2000.mp4", datetime(2026, 10, 1, 13, 38, 37, tzinfo=timezone.utc), 2000)
SEG720 = (D / "20261001T141139Z_720p_seg0000-1900.mp4", datetime(2026, 10, 1, 14, 11, 39, tzinfo=timezone.utc), 1900)
LAG_S = 3.0                  # frame showing the pre-click screen ~3 s before the block time (see docstring)
SOW_BUY_SIG = "3fwuUNKySjxbdTogsshHJ8C6SyziTitEMqn52foQM2mnhCN1ZzVrf2XSLHxAPDmCgZJGFtrAM2bp5aevLeJPy2Fq"
DECUSLOP = "GQyqQaQ3PTF4wc1UDkyFM8Cd4NA28ygQVLrWGfczECLS"
utc = lambda x: datetime.fromtimestamp(x, timezone.utc)

con = db.connect()
# H3 is kept across re-runs (findings.reregister_hypothesis), so its basis links go first
con.execute("DELETE FROM hypothesis_basis WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
con.execute("DELETE FROM decision_metrics WHERE decision_id IN (SELECT decision_id FROM decisions WHERE extractor = ?)", [EX])
con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
con.execute("DELETE FROM decisions WHERE extractor = ?", [EX])

tid = annotations.trader_by_slug(con, "decu")
assert tid, "trader 'decu' missing (run verify_identities.py first)"

# --- footage ------------------------------------------------------------------
vids = {}
for key, (path, start, dur) in (("360", SEG360), ("720", SEG720)):
    r = ingest_video(con, str(path), get_video_adapter("local"), captions=False,
                     notes=f"Live capture of twitch.tv/decu, first {dur} s; video t=0 is {start.isoformat()}")
    vids[key] = r.source_id
    con.execute("UPDATE sources SET title = ?, author = ?, published_at = ? WHERE source_id = ?",
                [f"Decu live stream (Twitch) {key}p, {start:%H:%M:%S}+{dur}s UTC", "Decu", start, r.source_id])
annotations.add_trader_identity(con, tid, "twitch", handle="decu", url="https://www.twitch.tv/decu",
                                evidence_source_id=vids["720"], verification_status="verified",
                                verification_notes="Recorded from the channel; the wallet trading on screen is the "
                                                   "one Decu published on X (4vw54…).")


def where(t: float):
    """(source_id, video t, media path) of the best capture covering wall-clock t (pre-click frame)."""
    for key, (path, start, dur) in (("720", SEG720), ("360", SEG360)):
        v = t - start.timestamp() - LAG_S
        if 0 <= v <= dur:
            return vids[key], round(v, 1), path
    return None, None, None


# --- the tape ------------------------------------------------------------------
mcon = market.connect()
market.load(mcon)
stream_start, stream_end = SEG360[1].timestamp(), SEG720[1].timestamp() + SEG720[2]
trades = mcon.execute("""SELECT t.sig, t.recv, t.mint, c.symbol, c.name, c.creator, c.recv, t.buy, t.sol, t.tok, t.vsol, t.vtok
                         FROM curve_trades t LEFT JOIN curve_creates c USING (mint)
                         WHERE t.usr = ? AND t.recv >= ? AND t.recv < ? ORDER BY t.recv""",
                      [WALLET, stream_start, stream_end]).fetchall()
cols = ["sig", "recv", "mint", "symbol", "name", "creator", "created_recv", "buy", "sol", "tok", "vsol", "vtok"]
trades = [dict(zip(cols, r)) for r in trades]


def others_net(mint, a, b):
    return mcon.execute("SELECT coalesce(sum(CASE WHEN buy THEN sol ELSE -sol END), 0) FROM curve_trades "
                        "WHERE mint = ? AND usr <> ? AND recv >= ? AND recv < ?", [mint, WALLET, a, b]).fetchone()[0]


# creator activity before each first entry >= 1 SOL
entries, seen = [], set()
for t in trades:
    if t["buy"] and t["sol"] >= 1 and t["mint"] not in seen:
        seen.add(t["mint"])
        dev = mcon.execute("""SELECT coalesce(sum(CASE WHEN buy THEN sol END), 0), coalesce(sum(CASE WHEN NOT buy THEN sol END), 0),
                                     min(CASE WHEN NOT buy THEN recv END)
                              FROM curve_trades WHERE mint = ? AND usr = ? AND recv < ?""",
                           [t["mint"], t["creator"], t["recv"]]).fetchone()
        entries.append({"symbol": t["symbol"], "mint": t["mint"], "at": utc(t["recv"]).isoformat(), "sol": t["sol"],
                        "age_s": round(t["recv"] - t["created_recv"], 1) if t["created_recv"] else None,
                        "mcap_sol_after": round(t["vsol"] / t["vtok"] * 1e9, 1), "creator": t["creator"],
                        "creator_bought_sol": round(dev[0], 3), "creator_sold_sol": round(dev[1], 3),
                        "s_since_creator_first_sell": round(t["recv"] - dev[2], 1) if dev[2] else None})

# small buys vs >=1 SOL buys: does others' net buying change in the 5 s after?
def flow_stats(sel):
    rows = []
    for t in sel:
        before, after = others_net(t["mint"], t["recv"] - 5, t["recv"]), others_net(t["mint"], t["recv"], t["recv"] + 5)
        sold20 = any(not u["buy"] and u["mint"] == t["mint"] and 0 < u["recv"] - t["recv"] <= 20 for u in trades)
        rows.append((before, after, sold20))
    n = len(rows)
    return {"n": n, "mean_others_net_sol_5s_before": round(sum(r[0] for r in rows) / n, 3) if n else None,
            "mean_others_net_sol_5s_after": round(sum(r[1] for r in rows) / n, 3) if n else None,
            "after_gt_before": sum(r[1] > r[0] for r in rows), "decu_sold_within_20s": sum(r[2] for r in rows)}


# base rate over every token created in the window: how unusual is "big creator buy, already dumped at a profit"?
BASE_Q = """WITH c AS (SELECT mint, creator, recv AS t0 FROM curve_creates WHERE recv >= ? AND recv < ?),
x AS (SELECT c.mint,
             sum(CASE WHEN t.usr = c.creator AND t.buy THEN t.sol ELSE 0 END) AS db,
             sum(CASE WHEN t.usr = c.creator AND NOT t.buy THEN t.sol ELSE 0 END) AS ds
      FROM c LEFT JOIN curve_trades t ON t.mint = c.mint AND t.recv <= c.t0 + 25 GROUP BY c.mint)
SELECT count(*), sum((ds > db AND db > 0)::INT), sum((db >= 2.9)::INT), sum((ds > db AND db >= 2.9)::INT) FROM x"""
br = mcon.execute(BASE_Q, [stream_start, stream_end]).fetchone()
base_rate = {"tokens_created": br[0], "creator_sold_more_than_bought_by_25s": br[1],
             "creator_bought_ge_2.9_sol": br[2], "creator_bought_ge_2.9_and_sold_more_by_25s": br[3],
             "share_big_buy_and_dumped": round(br[3] / br[0], 4) if br[0] else None}

tiny = flow_stats([t for t in trades if t["buy"] and t["sol"] < 0.3])
big = flow_stats([t for t in trades if t["buy"] and t["sol"] >= 1])

# one buy transaction in full: what a 3-SOL quick-buy costs
tx = Rpc().call("getTransaction", [SOW_BUY_SIG, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
meta = tx["meta"]
keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
keys += meta.get("loadedAddresses", {}).get("writable", []) + meta.get("loadedAddresses", {}).get("readonly", [])
deltas = {k: round((b - a) / 1e9, 9) for k, a, b in zip(keys, meta["preBalances"], meta["postBalances"]) if b != a}
tx_summary = {"sig": SOW_BUY_SIG, "slot": tx["slot"], "block_time": tx["blockTime"], "network_fee_sol": meta["fee"] / 1e9,
              "compute_units": meta.get("computeUnitsConsumed"), "balance_deltas_sol": deltas,
              "debited_from_wallet_sol": -deltas[WALLET], "into_curve_sol": 2.933333333,
              "uses_durable_nonce": any((ix.get("parsed") or {}).get("type") == "advanceNonce"
                                        for ix in tx["transaction"]["message"]["instructions"]),
              "top_level_transfers": [ix["parsed"]["info"] for ix in tx["transaction"]["message"]["instructions"]
                                      if (ix.get("parsed") or {}).get("type") == "transfer"]}

ev = {"note": "pump.fun bonding-curve TradeEvents decoded from Solana RPC logs (recorder) for Decu's verified wallet "
              "during the recorded stream; sol excludes fees. One buy tx fetched in full via getTransaction.",
      "window_utc": [utc(stream_start).isoformat(), utc(stream_end).isoformat()],
      "trades": [{**t, "recv_utc": utc(t["recv"]).isoformat()} for t in trades],
      "entries_ge_1sol": entries, "flow_after_small_buys_lt_0.3sol": tiny, "flow_after_buys_ge_1sol": big, "base_rate": base_rate,
      "sow_buy_tx": tx_summary}
ev_path = ROOT / "research/observations/evidence_decu_stream_2026-10-01.json"
ev_path.write_text(json.dumps(ev, indent=1, default=str))
tape_sid, tape_snap = ingest_document(con, str(ev_path), title="Decu's on-stream trades (tape excerpt + one full tx)",
                                      canonical_url="stream://pump_curve/2026-10-01/decu-stream")


def obs(**kw):
    kw.setdefault("trader_id", tid)
    kw.setdefault("extractor", EX)
    kw.setdefault("status", "reviewed")
    return observations.add_observation(con, **kw)


# frames from earlier runs of this script (possibly at other timestamps) are removed with their files
for (fid, lp) in con.execute("SELECT frame_id, local_path FROM frames WHERE source_id IN (?, ?)",
                             [vids["360"], vids["720"]]).fetchall():
    con.execute("DELETE FROM frames WHERE frame_id = ?", [fid])
    (ROOT / lp if not Path(lp).is_absolute() else Path(lp)).unlink(missing_ok=True)


def frame(src, t, path):
    return frames.extract_frames(con, src, timestamps=[t], media_path=path)[0]


# --- decisions: every on-chain trade in the window (what they DID) ---------------
tokens, held, decision_ids = {}, {}, {}
for t in trades:
    m = t["mint"]
    if m not in tokens:
        tokens[m] = decisions.add_token(con, identification="onchain_match", mint=m, ticker=t["symbol"], name=t["name"],
                                        launchpad="pump.fun", identification_confidence=0.99,
                                        created_onchain_at=utc(t["created_recv"]) if t["created_recv"] else None)
    src, vt, _ = where(t["recv"] - 1.2)
    if t["buy"]:
        kind = "ADD" if held.get(m, 0) > 0 else "BUY"
        held[m] = held.get(m, 0) + t["tok"]
    else:
        held[m] = held.get(m, 0) - t["tok"]
        kind = "SELL" if held[m] <= 1e-3 * t["tok"] else "PARTIAL_SELL"
        if kind == "SELL":
            held[m] = 0.0                               # dust left by a 100% sell does not count as a position
    did = decisions.add_decision(
        con, trader_id=tid, source_id=src or vids["720"], decision=kind, token_id=tokens[m], extractor=EX,
        extraction_confidence=0.95, video_ts_s=vt, decision_wallclock=utc(t["recv"] - 1.2), wallclock_basis="onchain_tx",
        position_size=round(t["sol"], 4), position_size_unit="SOL",
        observed_context=f"{'Bought' if t['buy'] else 'Sold'} {t['sol']:.3f} SOL on the bonding curve; token age "
                         f"{(t['recv'] - t['created_recv']):.0f} s, market cap after {t['vsol'] / t['vtok'] * 1e9:.1f} SOL"
                         if t["created_recv"] else None)
    decision_ids[t["sig"]] = did
    decisions.add_reading(con, did, "market_cap_sol", observed_via="onchain", value_num=round(t["vsol"] / t["vtok"] * 1e9, 2),
                          as_of_offset_s=0, notes="vsol/vtok x 1e9 after the trade (tape)")
    if t["created_recv"]:
        decisions.add_reading(con, did, "token_age_s", observed_via="onchain", value_num=round(t["recv"] - t["created_recv"], 1),
                              as_of_offset_s=0, notes="receive time of trade minus receive time of CreateEvent")


MINTS = {"Sow": "3mBG1D", "ㅤㅤㅤ": "5dmQ6Y", "BLACK": "4ED62z", "かのくん": "DCquzH", "DIT": "HyDTgY", "TITCOIN": "AMP4vk"}


def first(key):
    """First buy of a token, by ticker (via MINTS) or mint."""
    pre = MINTS.get(key, key)
    return next(t for t in trades if t["mint"].startswith(pre) and t["buy"])


# --- SCREEN: what Axiom showed just before the coded entries (720p) -----------------
S7 = (vids["720"], SEG720[0])
coded = {}

# Sow: Pulse card at 0-1 s, X profile hover, then the token page 3 s before the buy
f569, f571, f573 = (frame(*S7[:1], t, S7[1]) for t in (569.25, 571.25, 573.0))
sow = decision_ids[first("Sow")["sig"]]
o_sow_card = obs(source_id=vids["720"], modality="screen", kind="pulse_card", frame_id=f569, decision_id=sow,
                 token_id=tokens[first("Sow")["mint"]], start_s=569.25,
                 content="Axiom Pulse, New Pairs top row: 'Sow  Sow Fun', age 0s, V $4K, MC $6.78K, linked X "
                         "@sowfunhq, card counter '16/225'.")
o_sow_hover = obs(source_id=vids["720"], modality="screen", kind="x_profile_hover", frame_id=f571, decision_id=sow,
                  start_s=571.25,
                  content="Cursor on the card's X link opens a preview of @sowfunhq ('sow.fun', 'launch a coin. Fund a "
                          "life. 45% of every trade funds a real Kiva borrower…', Joined Apr 2023, 3 Following, "
                          "7 Followers). Card now 1s old, MC $10.1K, 19 holders.")
o_sow_page = obs(source_id=vids["720"], modality="screen", kind="token_page", frame_id=f573, decision_id=sow, start_s=573.0,
                 content="Token page for Sow at chart clock 09:21:12 (UTC-5): age 3s, MC $13K, liquidity $14.1K, "
                         "B.Curve 67.32%, holders 16, Top10 29.86%, Dev H 0%, Snipers H 16.04%, Insiders 0%, Bundlers "
                         "30.07%, LP burned 100%, 'Dev Tokens (225)', chart shows 'DB' and 'DS' markers; Bought 0.")
for metric, val, unit in (("market_cap_usd", 13000, None), ("liquidity_usd", 14100, None), ("token_age_s", 3, None),
                          ("bonding_curve_pct", 67.32, None), ("holders", 16, None), ("top10_pct", 29.86, None),
                          ("dev_pct", 0, None), ("snipers_pct", 16.04, None), ("insiders_pct", 0, None),
                          ("bundles_pct", 30.07, None), ("x_axiom_dev_tokens", 225, "count")):
    decisions.add_reading(con, sow, metric, observed_via="screen", value_num=val, unit=unit, frame_id=f573,
                          observation_id=o_sow_page, as_of_offset_s=-3)
decisions.add_reading(con, sow, "author_followers", observed_via="screen", value_num=7, frame_id=f571,
                      observation_id=o_sow_hover, as_of_offset_s=-5, notes="followers of the X account linked on the card")
coded["Sow"] = [o_sow_card, o_sow_hover, o_sow_page]

# blank-name token (ㅤㅤㅤ = Hangul filler characters): token page before the first buy, linked tweet before the 5-SOL re-entry
f695, f733 = frame(*S7[:1], 695.25, S7[1]), frame(*S7[:1], 733.25, S7[1])
hhh = first("ㅤㅤㅤ")
d_hhh = decision_ids[hhh["sig"]]
o_hhh_page = obs(source_id=vids["720"], modality="screen", kind="token_page", frame_id=f695, decision_id=d_hhh, start_s=695.25,
                 token_id=tokens[hhh["mint"]],
                 content="Token page, name renders blank, chart clock 09:23:14: age 8s, MC $12.5K, liquidity $13.7K, "
                         "B.Curve 65.82%, holders 23, Top10 39.08%, Dev H 12.49%, Snipers H 39.84%, Insiders 0%, "
                         "Bundlers 36.62%, 'Dev Tokens (395)'; Bought 0.")
for metric, val in (("market_cap_usd", 12500), ("liquidity_usd", 13700), ("token_age_s", 8), ("bonding_curve_pct", 65.82),
                    ("holders", 23), ("top10_pct", 39.08), ("dev_pct", 12.49), ("snipers_pct", 39.84),
                    ("insiders_pct", 0), ("bundles_pct", 36.62), ("x_axiom_dev_tokens", 395)):
    decisions.add_reading(con, d_hhh, metric, observed_via="screen", value_num=val, frame_id=f695,
                          observation_id=o_hhh_page, as_of_offset_s=-3, unit="count" if metric.startswith("x_") else None)
add = next(t for t in trades if t["mint"] == hhh["mint"] and t["buy"] and t["sol"] > 4)
d_add = decision_ids[add["sig"]]
o_tweet = obs(source_id=vids["720"], modality="screen", kind="tweet_preview", frame_id=f733, decision_id=d_add, start_s=733.25,
              token_id=tokens[hhh["mint"]],
              content="Hovering the blank-name card (Final Stretch, 46s, V $37K, MC $13.1K) shows the linked post by "
                      "@theghostfunsol (Joined Jul 2026, 1 follower), visible text: '@phantom literally gave us an ideal "
                      "narrative for Halloween, especially since this holiday is coming up soon, through which phantom "
                      "posted a tweet some time ago saying \"can you tokenize a ghost\" x.com/phantom/status/207781… "
                      "I also noticed that in CT talking a lot about this, beca… Halloween is approaching and…'. "
                      "Decu's 5-SOL re-entry (they had sold out 11 s earlier) lands ~26 s later.")
decisions.add_reading(con, d_add, "market_cap_usd", observed_via="screen", value_num=13100, frame_id=f733,
                      observation_id=o_tweet, as_of_offset_s=-26)
decisions.add_reading(con, d_add, "author_followers", observed_via="screen", value_num=1, frame_id=f733,
                      observation_id=o_tweet, as_of_offset_s=-26, notes="followers of the linked X account")
coded["ㅤㅤㅤ"] = [o_hhh_page, o_tweet]

# BLACK: bought from the Pulse card at age ~0-1 s with the card's 2.5 SOL quick-buy
f337 = frame(*S7[:1], 337.25, S7[1])
black = first("BLACK")
o_black = obs(source_id=vids["720"], modality="screen", kind="pulse_card", frame_id=f337,
              decision_id=decision_ids[black["sig"]], start_s=337.25, token_id=tokens[black["mint"]],
              content="Pulse New Pairs top row 'BLACK  Jackdaw Black', 0s, V $24, MC $3.29K; column quick-buy "
                      "set to 2.5 SOL. The on-chain buy (2.444 SOL into the curve) lands in the same second; it is sold "
                      "1 s later for 5.094 SOL.")
decisions.add_reading(con, decision_ids[black["sig"]], "market_cap_usd", observed_via="screen", value_num=3290,
                      frame_id=f337, observation_id=o_black, as_of_offset_s=0)
coded["BLACK"] = [o_black]

# tracker feed: labelled wallets incl. 'decuslop' = creator of the かのくん copy Decu bought 6 s later
kano = first("かのくん")
o_tracker = obs(source_id=vids["720"], modality="screen", kind="tracker_feed", frame_id=f337,
                decision_id=decision_ids[kano["sig"]], start_s=337.25, token_id=tokens[kano["mint"]],
                content="Left 'Trades' tracker panel lists labelled wallets' trades: 'decuslop' Kano-k… 2.0647, "
                        "2.0553, 1.9369, 5.5688, 1.3323 SOL (0-2 s ago), plus 'bwam dev', 'daumen', 'drill', 'flames', "
                        "'korean', 'clowm'. Pulse New Pairs row 2: 'Kano-kun', 1s, V $4K, MC $6.76K, @thedevorr, card counter '8/206', "
                        "creator label 'decusl…'.")
o_slop_chain = obs(source_id=tape_sid, snapshot_id=tape_snap, modality="onchain", kind="wallet_match",
                   decision_id=decision_ids[kano["sig"]], token_id=tokens[kano["mint"]], quote=DECUSLOP,
                   content=f"Creator {DECUSLOP} of かのくん (DCquzH…, created 14:17:14) bought 5.5 SOL at creation and "
                           "sold 1.961, 1.349, 2.081, 2.091 SOL within 2 s; with the 1.25% fee these are 5.569 and "
                           "1.936, 1.332, 2.055, 2.065 — the 'decuslop' rows in Decu's tracker. It created no other "
                           "token in the tape (since 12:17). Decu's wallet bought 2 s-preset (1.956 SOL) 8 s after "
                           "creation and sold 23 s later for 2.768 SOL.")
coded["かのくん"] = [o_tracker, o_slop_chain]

# DIT and TITCOIN: Pulse context just before the entry
f437, f1782 = frame(*S7[:1], 437.0, S7[1]), frame(*S7[:1], 1782.5, S7[1])
dit, tit = first("DIT"), first("TITCOIN")
o_dit = obs(source_id=vids["720"], modality="screen", kind="pulse_card", frame_id=f437, decision_id=decision_ids[dit["sig"]],
            start_s=437.0, token_id=tokens[dit["mint"]],
            content="Final Stretch top: 'DIT  Dead Internet Theory', 17s, V $18K, MC $11.6K, card counter '43/1627', "
                    "creator label 'domy d…'; a second 'DIT' appears at 0s in New Pairs. Tracker rows: 'Truno' DIT "
                    "0.2475 x3 and 1.98, 'domy' DIT 1.8911, 'domy dev' DIT 4.7851.")
decisions.add_reading(con, decision_ids[dit["sig"]], "market_cap_usd", observed_via="screen", value_num=11600,
                      frame_id=f437, observation_id=o_dit, as_of_offset_s=-5)
decisions.add_reading(con, decision_ids[dit["sig"]], "token_age_s", observed_via="screen", value_num=17,
                      frame_id=f437, observation_id=o_dit, as_of_offset_s=-5)
o_tit = obs(source_id=vids["720"], modality="screen", kind="pulse_card", frame_id=f1782, decision_id=decision_ids[tit["sig"]],
            start_s=1782.5, token_id=tokens[tit["mint"]],
            content="New Pairs: 'TITCOIN  Titcoin', 5s, @sh4wty (2.49K), V $3K, MC $8.93K, card counter '6/17', 10 "
                    "holders. Tracker top row: 'chester' TITCOIN 1.3103 SOL, 0s ago.")
decisions.add_reading(con, decision_ids[tit["sig"]], "market_cap_usd", observed_via="screen", value_num=8930,
                      frame_id=f1782, observation_id=o_tit, as_of_offset_s=-2)
decisions.add_reading(con, decision_ids[tit["sig"]], "token_age_s", observed_via="screen", value_num=5,
                      frame_id=f1782, observation_id=o_tit, as_of_offset_s=-2)

# execution settings on screen + the measured tx
o_panel = obs(source_id=vids["720"], modality="screen", kind="execution_settings", frame_id=f573, start_s=573.0,
              content="Axiom quick-trade panel: buy presets 10, 7, 1.58, 2, 5, 0.25, 0.025, 3 SOL; buy settings "
                      "'90%' slippage, 0.005 priority, 0.01 tip, MEV 'Off'; sell presets 10/25/60/100/85/33/5/50%, "
                      "sell settings '50%', 0.005, 0.005, 'Off'. Pulse columns quick-buy 2.5 SOL.",
              value={"buy_presets_sol": [10, 7, 1.58, 2, 5, 0.25, 0.025, 3], "buy_slippage_pct": 90,
                     "buy_priority_sol": 0.005, "buy_tip_sol": 0.01, "sell_slippage_pct": 50,
                     "sell_priority_sol": 0.005, "sell_tip_sol": 0.005, "pulse_quick_buy_sol": 2.5})
o_tx = obs(source_id=tape_sid, snapshot_id=tape_snap, modality="onchain", kind="tx_cost", quote=SOW_BUY_SIG,
           decision_id=sow, value=tx_summary,
           content=f"Decu's 3-SOL Sow buy debited {tx_summary['debited_from_wallet_sol']:.6f} SOL: 2.933333 into the curve, "
                   "0.027867 + 0.0088 pump.fun fees (0.95% + 0.30%), 0.022125/0.00675/0.000675 to three other "
                   "recipients (1.0% in a 75/23/2 split), 0.01 tip (top-level transfer), 0.005005 network fee, "
                   "0.002 to accounts; durable-nonce transaction.")

# --- findings (OBSERVED; one INFERRED with alternatives) ----------------------------
n_ent = len(entries)
dumped = [e for e in entries if e["creator_sold_sol"] > e["creator_bought_sol"] > 0]
quick = [e for e in dumped if e["s_since_creator_first_sell"] is not None and e["s_since_creator_first_sell"] <= 30]
o_entries = obs(source_id=tape_sid, snapshot_id=tape_snap, modality="onchain", kind="entry_timing",
                value={"entries": entries, "base_rate": base_rate},
                content="Per entry >=1 SOL: token age, creator's buys/sells before the entry, seconds since the "
                        "creator's first sell; base rate of the same creator pattern over all tokens launched in the window.")
f_dump = findings.add_finding(
    con, trader_id=tid, funnel_stage="entry", evidence_type="observed",
    statement=f"On stream, Decu's {n_ent} entries of >=1 SOL were into tokens 1-25 s old (one at ~4 min); in "
              f"{len(dumped)} of them the creator had already sold more SOL than they put in before Decu bought, "
              f"{len(quick)} within 2-30 s of the creator's first sell; those creators had put in 3.0-5.5 SOL. Across all "
              f"{base_rate['tokens_created']:,} tokens launched in the window only "
              f"{base_rate['share_big_buy_and_dumped']:.1%} had a creator buy of >=2.9 SOL already sold at a profit "
              "by age 25 s. The exception (BLACK) was bought in its first second and sold 1 s later.",
    evidence=[("observation", o_entries, "supports")] + [("decision", decision_ids[first(e['mint'])['sig']], "supports")
                                                         for e in entries],
    n_supporting=len(dumped), n_observable=n_ent, confidence=0.9, notes=f"{EX}; window 13:38-14:43 UTC")
f_exec = findings.add_finding(
    con, trader_id=tid, funnel_stage="sizing", evidence_type="observed",
    statement="Decu sizes with fixed Axiom presets (on chain: 2.933 = 3 SOL, 1.956 = 2, 2.444 = 2.5, 4.889 = 5, "
              "0.244 = 0.25, 0.024 = 0.025 after ~2.25% fees) and buys with 90% slippage, 0.005 SOL priority and "
              "0.01 SOL tip; one 3-SOL buy cost 2.84% over the SOL that reached the curve.",
    evidence=[("observation", o_panel, "supports"), ("observation", o_tx, "supports")],
    n_supporting=1, n_observable=1, confidence=0.9, notes=f"{EX}; cost measured on one tx")
f_narr = findings.add_finding(
    con, trader_id=tid, funnel_stage="narrative", evidence_type="observed",
    statement="Before two of the coded entries Decu hovered the X link on the Axiom card: a 7-follower project "
              "profile (Sow) and a 1-follower account's post tying the token to a Phantom 'can you tokenize a ghost' "
              "tweet and Halloween (blank-name token, before a 5-SOL re-entry).",
    evidence=[("observation", o_sow_hover, "supports"), ("observation", o_tweet, "supports")],
    n_supporting=2, n_observable=6, confidence=0.8, notes=f"{EX}; 6 entries coded on 720p frames")
f_tracker = findings.add_finding(
    con, trader_id=tid, funnel_stage="discovery", evidence_type="observed",
    statement="Decu's Axiom tracker feed holds labelled wallets, many named as deployers ('bwam dev', 'good dev', "
              "'theo dev', 'realist dev', 'clwon dev', 'domy dev', 'dvdev'); one label ('decuslop') is the creator "
              "of the かのくん copy Decu bought 8 s after its launch.",
    evidence=[("observation", o_tracker, "supports"), ("observation", o_slop_chain, "supports"),
              ("observation", o_dit, "supports")],
    n_supporting=1, n_observable=1, confidence=0.8, notes=f"{EX}; label-to-wallet match by amounts for one label")
o_flow = obs(source_id=tape_sid, snapshot_id=tape_snap, modality="onchain", kind="follower_flow",
             value={"small_buys": tiny, "entries_ge_1sol": big},
             content="Other wallets' net SOL into the token in the 5 s before vs after Decu's buys.")
f_tiny = findings.add_finding(
    con, trader_id=tid, funnel_stage="hold", evidence_type="observed",
    statement=f"Decu also makes many 0.025/0.25 SOL buys into tokens they already hold ({tiny['n']} on stream). "
              f"Unlike their >=1 SOL entries (others' net flow {big['mean_others_net_sol_5s_before']:+.2f} -> "
              f"{big['mean_others_net_sol_5s_after']:+.2f} SOL in 5 s), the small buys are not followed by more "
              f"buying from others ({tiny['mean_others_net_sol_5s_before']:+.2f} -> "
              f"{tiny['mean_others_net_sol_5s_after']:+.2f}); their purpose is not visible in the data.",
    evidence=[("observation", o_flow, "supports")], n_supporting=tiny["n"] - tiny["after_gt_before"],
    n_observable=tiny["n"], confidence=0.7, notes=f"{EX}; a 'tiny buys pull in followers' reading is NOT supported")
f_inf = findings.add_finding(
    con, trader_id=tid, funnel_stage="entry", evidence_type="inferred",
    statement="Decu's main entry is buying the first seconds after a new token's creator takes profit, on tokens "
              "they have pre-screened by narrative (linked X post) and by who is involved (labelled deployer and "
              "trader wallets in the tracker), then exiting within ~1 minute.",
    evidence=[("finding", f_dump, "derived_from"), ("finding", f_narr, "derived_from"),
              ("finding", f_tracker, "derived_from")],
    confidence=0.5, notes=f"{EX}; alternatives: the trigger is the tracker feed (other labelled wallets buying) or "
                          "Pulse momentum, and the creator's sell is incidental because nearly every new token's "
                          "creator sells in its first seconds — test against a base rate before relying on this")
# --- H3: does the mechanical part of the pattern pay on its own? (pre-registered before 14:45 data is looked at)
h3 = findings.reregister_hypothesis(con, "H3:",
    statement="H3: buying a <=30 s old token within 20 s of its creator's first sell, when the creator put in >=2.9 SOL "
              "and has already taken out more than that, then holding ~20 s, has positive expectancy after costs — "
              "i.e. the visible, mechanical part of Decu's entry pattern pays without their narrative/wallet screening.",
    measurable_definition="DevDumpEntry(size_sol=1.0, max_age_s=30, min_dev_buy_sol=2.9, max_since_dump_s=20, "
                          "hold_s=20, stop_pct=20). Primary execution: 1 s end-to-end latency, 125 bps on-chain fee, "
                          "0.01 SOL priority+tip per tx, 20% slippage tolerance, 2% tx failure. First test: train data "
                          "14:45-17:15 UTC, after the stream segment it was derived from. Pass: expectancy > 0, PF > 1.2, "
                          ">=30 trades. Reported but not used to pass/fail: latency sweep 0.1-10 s; Decu's measured costs "
                          "(225 bps, 0.015 SOL/tx); size 3 SOL.",
    rationale=f"{EX}: on stream 8/9 of Decu's >=1 SOL entries followed a large creator buy already dumped at a profit, a "
              "pattern seen in only a few % of launches. Thresholds are round values covering Decu's examples "
              "(creator buys 3.0-5.5 SOL; 7/8 entries <=20 s after the creator's first sell; median hold ~20 s), "
              "fixed before any data after 14:45 was examined. A failure would mean Decu's edge lies in what the "
              "tape cannot see (narrative and wallet screening), not in the timing.",
    basis_finding_ids=[f_dump, f_inf], trader_scope="decu")

print(json.dumps({"trades": len(trades), "entries": entries, "small": tiny, "big": big,
                  "base_rate": base_rate, "h3": h3,
                  "findings": [f_dump, f_exec, f_narr, f_tracker, f_tiny, f_inf]}, indent=1, default=str))
