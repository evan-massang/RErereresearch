"""Who makes money on the bonding curve (train data so far): wallet types by realized PnL."""
import json, sys
from collections import defaultdict
from pathlib import Path
import duckdb
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import config, db, findings, market, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402
EX = "claude:market-structure-2026-10-01"
src = market.connect(); market.load(src); src.close()
mc = duckdb.connect(); mc.execute(f"ATTACH '{config.path('data') / 'market.duckdb'}' AS s (READ_ONLY)")
for t in ["curve_trades", "curve_creates", "curve_completes", "kol_wallets"]:
    mc.execute(f"CREATE TABLE {t} AS SELECT * FROM s.{t}")
window = mc.execute("SELECT min(recv), max(recv) FROM curve_trades").fetchone()
SPECIAL = {"BwWK17cbHxwWBKZkUYvzxLcNQ1YVyaFezduWbtm2de6s"}   # excluded by kolscan's own client code; not a person
active = [r[0] for r in mc.execute("SELECT usr FROM curve_trades GROUP BY usr HAVING count(*) >= 10").fetchall()]
creators = {r[0] for r in mc.execute("SELECT DISTINCT creator FROM curve_creates").fetchall()}
by = defaultdict(list)
for t in market.round_trips(mc, active):
    if t.closed and t.wallet not in SPECIAL:
        by[t.wallet].append(t)
groups = defaultdict(lambda: {"wallets": 0, "profitable": 0, "pnl_sol": 0.0})
for w, ts in by.items():
    if len(ts) < 5:
        continue
    s = market.summarize(ts)
    cb = s["share_entries_creation_block"] or 0
    if cb >= 0.5:
        kind = "creation_block_creator" if w in creators else "creation_block_non_creator"
    elif s["median_hold_s"] < 5:
        kind = "sub5s_flipper"
    else:
        kind = "human_paced"
    g = groups[kind]
    g["wallets"] += 1
    g["profitable"] += s["pnl_sol"] > 0
    g["pnl_sol"] = round(g["pnl_sol"] + s["pnl_sol"], 3)
ev = {"window_recv": window, "min_closed_trips": 5, "excluded_special_accounts": sorted(SPECIAL), "groups": groups,
      "definitions": {"creation_block": ">=50% of entries in the token's creation slot",
                      "sub5s_flipper": "median hold < 5 s", "human_paced": "everything else"},
      "caveat": "bonding-curve trades only; positions that migrate are excluded; fees 1.25% included, priority fees not"}
p = ROOT / "research/observations/evidence_market_structure_2026-10-01.json"
p.write_text(json.dumps(ev, indent=1, default=float))
con = db.connect()
con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
sid, snap = ingest_document(con, str(p), title="Who profits on the bonding curve: wallet types by realized PnL",
                            canonical_url="stream://pump_curve/2026-10-01/market-structure")
o = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="market_structure",
                                 content=json.dumps(groups, default=float), value=ev, extractor=EX, status="reviewed")
hp = groups["human_paced"]
findings.add_finding(con, trader_id=None, funnel_stage="meta", evidence_type="observed",
    statement="On the pump.fun bonding curve, realized profit concentrates in creation-block entries (mostly token "
              "creators buying their own launch and selling within seconds) and sub-5-second flippers; human-paced "
              f"wallets are net negative in aggregate ({hp['pnl_sol']} SOL), with {hp['profitable']} of "
              f"{hp['wallets']} profitable.",
    evidence=[("observation", o, "supports")], n_supporting=hp["wallets"] - hp["profitable"],
    n_observable=hp["wallets"], confidence=0.7,
    notes=f"{EX}; n_supporting = unprofitable human-paced wallets; one hour of data so far, re-run on full train")
print(json.dumps(groups, default=float))
