"""Evidence: SolanaSwaggy's on-stream wallet and its role in token launches (2026-10-01).

Footage: data/raw/video/live/kick_solanaswaggy/20261001T122548Z.mp4 (recording started 12:25:48 UTC).
Tape:    pump.fun bonding-curve TradeEvents/CreateEvents recorded live (data/raw/streams/pump_curve).

Re-runnable: removes its own earlier rows (extractor tag) before writing.
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
from pipeline.sources import get_video_adapter  # noqa: E402

EX = "claude:swaggy-evidence-2026-10-01"
VIDEO = ROOT / "data/raw/video/live/kick_solanaswaggy/20261001T122548Z.mp4"
REC_START = datetime(2026, 10, 1, 12, 25, 48, tzinfo=timezone.utc)
SWORD = "EQapXTyWU3BmissyKpENaxjjMHuytAkeA3qzSerLc4YW"
BOY_COPY = "A7wg9GFwen"            # prefix; resolved below
WALLET = "AnrXEnftJMZRXQMrDGgHUuUvxujC6JPmAFy3x1SnXbDc"
TWIN = "BVzaGiRDDysGh4zwm6tmbeXKPomCuWSVAuThWXwXqnbJ"
DEV = "DbwyGZ5DdLXBC39rFgX58BSPuLpqVwZDAtCYt12BiT5m"

con = db.connect()
for t in ("finding_evidence",):
    con.execute(f"DELETE FROM {t} WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
con.execute("DELETE FROM decision_metrics WHERE decision_id IN (SELECT decision_id FROM decisions WHERE extractor = ?)", [EX])
con.execute("DELETE FROM decisions WHERE extractor = ?", [EX])
con.execute("DELETE FROM observations WHERE extractor = ?", [EX])

# --- trader + identities -------------------------------------------------------
tid = annotations.trader_by_slug(con, "solanaswaggy") or annotations.add_trader(
    con, "SolanaSwaggy", slug="solanaswaggy",
    notes="Live-trading streamer found while recording (kick.com/solanaswaggy); named in Leck lead file as a Kick trader.")

# --- the footage as a source --------------------------------------------------
res = ingest_video(con, str(VIDEO), get_video_adapter("local"), captions=False,
                   notes=f"Live recording of kick.com/solanaswaggy; video t=0 is {REC_START.isoformat()} "
                         "(stream latency ~7 s measured from the on-screen chart clock)")
vid = res.source_id
con.execute("UPDATE sources SET title = ?, author = ?, published_at = ? WHERE source_id = ?",
            ["SolanaSwaggy live stream (Kick) — recorded segment 12:25:48–12:34 UTC", "SolanaSwaggy", REC_START, vid])
annotations.add_trader_identity(con, tid, "kick", handle="solanaswaggy", url="https://kick.com/solanaswaggy",
                                evidence_source_id=vid, verification_status="verified",
                                verification_notes="Recorded from the channel itself; stream title "
                                                   "'$300k+ PNL ~ Live Trading Memecoins on Axiom'.")
f200 = frames.extract_frames(con, vid, timestamps=[200.0], media_path=VIDEO)[0]
f430 = frames.extract_frames(con, vid, timestamps=[430.0], media_path=VIDEO)[0]

# --- the tape excerpt as a source (exact on-chain events) ---------------------
mcon = market.connect()
market.load(mcon)
boy = mcon.execute("SELECT mint FROM curve_creates WHERE mint LIKE ? AND creator = ?", [BOY_COPY + "%", DEV]).fetchone()[0]
rows = mcon.execute("""SELECT mint, sig, recv, ts, usr, buy, sol, tok, vsol, vtok FROM curve_trades
                       WHERE mint IN (?, ?) AND usr IN (?, ?, ?) ORDER BY recv""", [SWORD, boy, WALLET, TWIN, DEV]).fetchall()
creates = mcon.execute("SELECT mint, symbol, name, creator, recv, sig FROM curve_creates WHERE mint IN (?, ?)",
                       [SWORD, boy]).fetchall()
ev_path = ROOT / "research/observations/evidence_swaggy_tape_2026-10-01.json"
ev_path.write_text(json.dumps({
    "note": "pump.fun bonding-curve events decoded from Solana RPC logs (recorder), 2026-10-01. tok = token units "
            "(6 decimals applied); sol excludes the 1.25% fee.",
    "creates": [dict(zip(["mint", "symbol", "name", "creator", "recv", "sig"], c)) for c in creates],
    "trades": [dict(zip(["mint", "sig", "recv", "ts", "user", "buy", "sol", "tok", "vsol", "vtok"], r)) for r in rows]},
    indent=1))
tape_sid, tape_snap = ingest_document(con, str(ev_path), title="Tape excerpt: swordbunny + copycat Boy launches",
                                      canonical_url="stream://pump_curve/2026-10-01/swaggy-evidence")

# --- observations: SCREEN, ONCHAIN, kept separate -----------------------------
o_screen = observations.add_observation(
    con, source_id=vid, modality="screen", kind="holders_row", frame_id=f200, trader_id=tid,
    content="Axiom holders tab for swordbunny shows the viewer's own row 'YOU (Diddy!)': bought $175.3 (41.6M tokens, "
            "avg $4.21K MC), sold $69.87 (12.5M), remaining $206 = 2.912% of supply, held 36s, funding: Binance.",
    value={"bought_tokens_display": "41.6M", "sold_tokens_display": "12.5M", "remaining_pct": 2.912},
    extractor=EX, confidence=0.85, status="reviewed")
o_chain = observations.add_observation(
    con, source_id=tape_sid, snapshot_id=tape_snap, modality="onchain", kind="wallet_trades", trader_id=tid,
    content=f"Wallet {WALLET} bought 41,599,019 swordbunny in the creation second (12:28:32 UTC, 1.47 SOL) and sold "
            f"12,479,706 at 12:28:40, leaving 29,119,313 = 2.912% of the 1B supply — the exact figures in the 'YOU' row.",
    quote=WALLET, extractor=EX, confidence=0.95, status="reviewed")
o_launch = observations.add_observation(
    con, source_id=tape_sid, snapshot_id=tape_snap, modality="onchain", kind="launch_pattern", trader_id=tid,
    content=f"Both tokens created by {DEV} in the window (swordbunny 12:28:32, 'Boy'/apeandhold 12:33:21) were bought "
            f"in their creation second by {WALLET} (1.47 SOL, 41,599,019 tokens) and {TWIN} (1.53 SOL, 39,688,860 "
            "tokens) — identical sizes on both launches — and both wallets sold at the same moments.",
    quote=DEV, extractor=EX, confidence=0.95, status="reviewed")
o_copycat = observations.add_observation(
    con, source_id=vid, modality="screen", kind="narrative_context", frame_id=f430, trader_id=tid,
    content="At 12:32:58 UTC Swaggy's screen shows a different 'Boy' (Return To Monke, created 12:30:29 by another "
            "wallet) in Axiom's Final Stretch column with a browser tab open on it; 23 s later the deployer above "
            "launched its own 'Boy'.", extractor=EX, confidence=0.7, status="reviewed")

annotations.add_trader_identity(con, tid, "wallet", handle=WALLET, evidence_source_id=tape_sid,
                                verification_status="probable",
                                verification_notes="Axiom 'YOU' holders row on stream (frame t=200 s) matches this "
                                                   "wallet's on-chain token amounts exactly (41.6M bought, 12.5M sold, "
                                                   "2.912% left). Probable rather than verified: the match is to one "
                                                   "frame and the trader has not publicly claimed the wallet.")

# --- decisions: what they DID (from chain), with what the SCREEN showed -------
tok = decisions.add_token(con, identification="onchain_match", mint=SWORD, ticker="swordbunny",
                          name="bunny wif sword", launchpad="pump.fun", identification_confidence=0.99)
d_buy = decisions.add_decision(
    con, trader_id=tid, source_id=vid, decision="BUY", token_id=tok, extraction_confidence=0.9, extractor=EX,
    decision_wallclock=datetime(2026, 10, 1, 12, 28, 32, tzinfo=timezone.utc), wallclock_basis="onchain_tx",
    position_size=1.47, position_size_unit="SOL", discovery_channel="own launch (inferred, see findings)",
    observed_context="Bought in the token's creation second together with the creator's 3 SOL and a twin wallet",
    inferred_reason="Bundled buy alongside the deploy; not a discretionary pick from Pulse (inference)")
decisions.add_reading(con, d_buy, "market_cap_sol", observed_via="onchain", value_num=36.9, as_of_offset_s=0,
                      observation_id=o_chain, notes="vsol/vtok x 1e9 after their buy")
decisions.add_decision(
    con, trader_id=tid, source_id=vid, decision="PARTIAL_SELL", token_id=tok, extraction_confidence=0.9,
    extractor=EX, decision_wallclock=datetime(2026, 10, 1, 12, 28, 40, tzinfo=timezone.utc),
    wallclock_basis="onchain_tx", result_sol=0.602, result_basis="onchain",
    observed_context="Sold 30% of the position 8 s after launch at ~47.5 SOL market cap")

# --- findings: OBSERVED and INFERRED, never merged ----------------------------
f_obs = findings.add_finding(
    con, trader_id=tid, funnel_stage="discovery", evidence_type="observed",
    statement="The wallet shown as 'YOU' on SolanaSwaggy's stream bought in the creation second of every token "
              "launched by deployer DbwyGZ5D… in the recorded window, with a fixed size and a twin wallet.",
    evidence=[("observation", o_chain, "supports"), ("observation", o_launch, "supports"),
              ("observation", o_screen, "supports"), ("decision", d_buy, "supports")],
    n_supporting=2, n_observable=2, confidence=0.9, notes=f"{EX}; window 12:25–12:34 UTC only")
findings.add_finding(
    con, trader_id=tid, funnel_stage="discovery", evidence_type="inferred",
    statement="SolanaSwaggy (or someone coordinating with them) launches tokens — including copycats of names "
              "trending on their Pulse screen — and buys the launch in the same block with fixed-size wallets, "
              "selling into the first seconds of bot demand. On this evidence their on-stream profit is at least "
              "partly launch-and-snipe, not discretionary selection.",
    evidence=[("finding", f_obs, "derived_from"), ("observation", o_copycat, "supports")],
    confidence=0.6, notes=f"{EX}; alternative: their wallet is a paid sniper attached to someone else's deploys "
                          "(J7's deploy API supports sniper wallets) — distinguish by checking more launches")
print("ok", vid, tid)
