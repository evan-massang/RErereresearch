"""Evidence: Setuh's on-stream wallet (2026-10-01).

Footage: data/raw/video/live/twitch_setuhh/20261001T161522Z_seg0000-0240.mp4 (first 240 s of the live capture
of twitch.tv/setuhh; t=0 at 16:15:22 UTC; on-screen trade toasts appear ~4 s after the block time).
Chain: the wallet's HARDCAT buy and sell transactions, fetched in full (getTransaction).

Re-runnable: removes its own earlier rows (extractor tag).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import annotations, db, decisions, findings, frames, observations  # noqa: E402
from pipeline.ingest_video import ingest_video  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402
from pipeline.onchain import Rpc  # noqa: E402
from pipeline.sources import get_video_adapter  # noqa: E402

EX = "claude:setuh-wallet-2026-10-01"
SEG = ROOT / "data/raw/video/live/twitch_setuhh/20261001T161522Z_seg0000-0240.mp4"
REC_START = datetime(2026, 10, 1, 16, 15, 22, tzinfo=timezone.utc)
WALLET = "62N1K57D37AUDGp68tnDYKPjGDsaAAtmo357nBtEtuR"
MINT = "9Z3LM2FXUWLBfXC8sgQxWPzaRvnHizAg18LL1Rz8UTbx"           # HARDCAT (Token-2022 metadata: hardcat / HARDCAT)
BUY_SIG = "PKGWM51Y84n2RbCnBu37jhct4CKqSyvsGydTZitQQHscJLKDLMWpA8eCp1Y5qDk88JJCi4ujzY1tQX3Ajm3qSdu"
SELL_SIG = "4pDK6aUPF9b5LqeTQ22uwRtJRwAZNp847KSzkeWRGWE5fkqKG9j1JjcFXKdKyYcoMDMS5yQBiZPJH1L4qskUATud"

con = db.connect()
con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
con.execute("DELETE FROM decision_metrics WHERE decision_id IN (SELECT decision_id FROM decisions WHERE extractor = ?)", [EX])
con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
con.execute("DELETE FROM decisions WHERE extractor = ?", [EX])

tid = annotations.trader_by_slug(con, "setuh")
assert tid, "trader 'setuh' missing"

res = ingest_video(con, str(SEG), get_video_adapter("local"), captions=False,
                   notes=f"Live capture of twitch.tv/setuhh, first 240 s; video t=0 is {REC_START.isoformat()}")
vid = res.source_id
con.execute("UPDATE sources SET title = ?, author = ?, published_at = ? WHERE source_id = ?",
            ["Setuh live stream (Twitch) 720p, 16:15:22+240s UTC", "Setuh", REC_START, vid])
annotations.add_trader_identity(con, tid, "twitch", handle="setuhh", url="https://www.twitch.tv/setuhh",
                                evidence_source_id=vid, verification_status="verified",
                                verification_notes="Recorded from the channel; the Padre 'Terminal' referral link on "
                                                   "screen is trade.padre.gg/rk/setuh.")

annotations.add_trader_identity(con, tid, "other", handle="Padre (Terminal) referral code 'setuh'",
                                evidence_source_id=vid, verification_status="verified",
                                verification_notes="Setuh trades on Padre Terminal on stream; its balance panel shows "
                                                   "the referral link trade.padre.gg/rk/setuh.")

# --- chain: both transactions in full -----------------------------------------
rpc = Rpc()
txs = {}
for side, sig in (("buy", BUY_SIG), ("sell", SELL_SIG)):
    tx = rpc.call("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
    m = tx["meta"]
    keys = [k["pubkey"] for k in tx["transaction"]["message"]["accountKeys"]]
    i = keys.index(WALLET)
    tok = lambda bals: sum(float(b["uiTokenAmount"]["uiAmount"] or 0) for b in bals
                           if b["owner"] == WALLET and b["mint"] == MINT)
    txs[side] = {"sig": sig, "slot": tx["slot"], "block_time": tx["blockTime"],
                 "block_time_utc": datetime.fromtimestamp(tx["blockTime"], timezone.utc).isoformat(),
                 "fee_payer_is_wallet": keys[0] == WALLET,
                 "wallet_sol_change": (m["postBalances"][i] - m["preBalances"][i]) / 1e9,
                 "wallet_sol_after": m["postBalances"][i] / 1e9,
                 "hardcat_before": tok(m["preTokenBalances"]), "hardcat_after": tok(m["postTokenBalances"])}
ev = {"note": "Setuh's wallet: HARDCAT buy and sell on Raydium Launchpad, fetched with getTransaction; the mint's "
              "Token-2022 metadata reads name 'hardcat', symbol 'HARDCAT'.", "wallet": WALLET, "mint": MINT, **txs}
ev_path = ROOT / "research/observations/evidence_setuh_wallet_2026-10-01.json"
ev_path.write_text(json.dumps(ev, indent=1))
doc_sid, snap = ingest_document(con, str(ev_path), title="Setuh's wallet: HARDCAT buy/sell transactions",
                                canonical_url="solana://tx/setuh-hardcat-2026-10-01")

f78, f84, f97 = frames.extract_frames(con, vid, timestamps=[78.0, 84.0, 97.0], media_path=SEG)
obs = lambda **kw: observations.add_observation(con, trader_id=tid, extractor=EX, status="reviewed", **kw)
o_buy = obs(source_id=vid, modality="screen", kind="trade_toast", frame_id=f78, start_s=78.0,
            content="Padre Terminal shows the confirmation 'Buy HARDCAT for 1 SOL' on the HARDCAT token page: age 18s, "
                    "MC $6.75K, liquidity $9.35K, total fees paid 2.28, B.Curve 33%.")
o_after = obs(source_id=vid, modality="screen", kind="token_page", frame_id=f84, start_s=84.0,
              content="HARDCAT token page 6 s later: age 24s, MC $11.1K, liquidity $12.9K, B.Curve 62%.")
o_sell = obs(source_id=vid, modality="screen", kind="trade_toast", frame_id=f97, start_s=97.0,
             content="Confirmation 'Sell 100% HARDCAT'; the tracker panel lists a wallet labelled 'setuh' selling "
                     "HARDCAT for 2.59 SOL 5 s earlier; the wallet selector shows 12.2 SOL.")
o_chain = obs(source_id=doc_sid, snapshot_id=snap, modality="onchain", kind="wallet_trades", quote=WALLET, value=txs,
              content=f"Wallet {WALLET} bought 18,252,293.81 HARDCAT at {txs['buy']['block_time_utc'][11:19]} UTC "
                      f"(SOL {txs['buy']['wallet_sol_change']:+.4f}) and sold all of it at "
                      f"{txs['sell']['block_time_utc'][11:19]} (SOL {txs['sell']['wallet_sol_change']:+.4f}), "
                      f"leaving {txs['sell']['wallet_sol_after']:.4f} SOL; it signed both transactions.")
annotations.add_trader_identity(
    con, tid, "wallet", handle=WALLET, evidence_source_id=vid, verification_status="verified",
    verification_notes="On Setuh's own stream (16:16-16:17 UTC) a 1-SOL HARDCAT buy and a 100% sell appear ~4 s after "
                       "this wallet's HARDCAT buy (16:16:34) and full sell (16:16:52); the stream's tracker labels the "
                       "selling wallet 'setuh' and the wallet selector shows 12.2 SOL vs 12.197 on chain after the sell. "
                       "kolscan lists it as 'set' with x.com/Setuhx.")

tok = decisions.add_token(con, identification="onchain_match", mint=MINT, ticker="HARDCAT", name="hardcat",
                          launchpad="raydium_launchpad", identification_confidence=0.99)
d_buy = decisions.add_decision(
    con, trader_id=tid, source_id=vid, decision="BUY", token_id=tok, extraction_confidence=0.95, extractor=EX,
    video_ts_s=74.0, decision_wallclock=datetime.fromtimestamp(txs["buy"]["block_time"], timezone.utc),
    wallclock_basis="onchain_tx", position_size=1.0, position_size_unit="SOL",
    observed_context="Bought with the 1-SOL quick-buy on the token page of an 18-s-old Raydium Launchpad token")
for metric, val, unit in (("market_cap_usd", 6750, None), ("liquidity_usd", 9350, None), ("token_age_s", 18, None),
                          ("bonding_curve_pct", 33, None)):
    decisions.add_reading(con, d_buy, metric, observed_via="screen", value_num=val, unit=unit, frame_id=f78,
                          observation_id=o_buy, as_of_offset_s=0)
d_sell = decisions.add_decision(
    con, trader_id=tid, source_id=vid, decision="SELL", token_id=tok, extraction_confidence=0.95, extractor=EX,
    video_ts_s=93.0, decision_wallclock=datetime.fromtimestamp(txs["sell"]["block_time"], timezone.utc),
    wallclock_basis="onchain_tx", result_sol=round(txs["buy"]["wallet_sol_change"] + txs["sell"]["wallet_sol_change"], 4),
    result_basis="onchain", observed_context="Sold 100% 18 s after buying, after the curve went from 33% to >60%")
findings.add_finding(
    con, trader_id=tid, funnel_stage="meta", evidence_type="observed",
    statement="The wallet 62N1K57D… trades on Setuh's own stream: its HARDCAT buy and 100% sell (16:16:34 / 16:16:52 "
              "UTC, +1.55 SOL) appear as Padre Terminal confirmations ~4 s later, the stream's tracker labels it "
              "'setuh', and the on-screen wallet balance matches the chain.",
    evidence=[("observation", o_buy, "supports"), ("observation", o_sell, "supports"),
              ("observation", o_chain, "supports"), ("decision", d_buy, "supports"), ("decision", d_sell, "supports")],
    n_supporting=2, n_observable=2, confidence=0.95, notes=f"{EX}; one round trip")
print("ok", vid, txs["sell"]["wallet_sol_after"])
