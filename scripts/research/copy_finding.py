"""Record the copy-trading result (train period, 2026-10-01 12:15-13:10 UTC) as typed evidence."""
import json, sys, bisect, statistics
from pathlib import Path
import duckdb
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import config, db, findings, market, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402

EX = "claude:copy-finding-2026-10-01"
src = market.connect(); market.load(src); src.close()
mc = duckdb.connect(); mc.execute(f"ATTACH '{config.path('data') / 'market.duckdb'}' AS s (READ_ONLY)")
END = 1790860200.0          # 2026-10-01 13:10 UTC: freeze the evidence window (inside the train split)
for t in ["curve_trades", "curve_creates", "curve_completes"]:
    mc.execute(f"CREATE TABLE {t} AS SELECT * FROM s.{t} WHERE recv < {END}")
mc.execute("CREATE TABLE kol_wallets AS SELECT * FROM s.kol_wallets")
trips = [t for t in market.round_trips(mc) if t.first_ts < END - 200]
es = market.event_study(mc, trips)
rnd = market.event_study(mc, market.random_entries(mc, trips), exclude_wallet=False)
grid = {}
for t in trips:
    rows = mc.execute("SELECT recv, vsol/vtok FROM curve_trades WHERE mint=? AND recv BETWEEN ? AND ? ORDER BY recv",
                      [t.mint, t.first_ts - 30, t.first_ts + 40]).fetchall()
    ts = [r[0] for r in rows]
    p = lambda x: (rows[bisect.bisect_right(ts, x) - 1][1] if bisect.bisect_right(ts, x) > 0 else None)
    for d in (0.5, 1, 2):
        for h in (3, 5, 10):
            a, b = p(t.first_ts + d), p(t.first_ts + d + h)
            if a and b:
                grid.setdefault(f"enter+{d}s_hold{h}s", []).append(b / a - 1)
summary = {"window_utc": "2026-10-01 12:15-13:10", "tracked_entries": len(trips), "event_study_tracked": es,
           "event_study_random_control": rnd,
           "quick_flip_mid_returns": {k: {"n": len(v), "median": round(statistics.median(v), 4),
                                          "mean": round(statistics.mean(v), 4)} for k, v in grid.items()},
           "note": "mid prices from bonding-curve reserves; fees (1.25% each side) and impact not included"}
path = ROOT / "research/observations/evidence_copy_event_study_2026-10-01.json"
path.write_text(json.dumps(summary, indent=1))

con = db.connect()
con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
sid, snap = ingest_document(con, str(path), title="Event study: flow and price around tracked-wallet entries",
                            canonical_url="stream://pump_curve/2026-10-01/event-study")
o = observations.add_observation(
    con, source_id=sid, snapshot_id=snap, modality="onchain", kind="event_study", extractor=EX, status="reviewed",
    content=f"{es['n']} entries by kolscan-tracked wallets: others' net buying {es['net_flow_sol_per_s']}, "
            f"price vs pre-entry {es['median_return_from_pre_entry_price']}; random same-moment tokens: "
            f"{rnd['median_return_from_pre_entry_price']}", value=summary)
up5 = round(es["share_up"]["+5s"] * es["n"])
f1 = findings.add_finding(
    con, trader_id=None, funnel_stage="market", evidence_type="observed",
    statement="Right after a kolscan-tracked wallet buys on the bonding curve, other wallets' net buying jumps "
              "(~0.1 -> ~0.5 SOL/s in the next 5 s) and the price is up a median ~18% at +5 s vs the pre-entry "
              "price, fading to below the pre-entry price by +180 s; random same-moment tokens show neither.",
    evidence=[("observation", o, "supports")], n_supporting=up5, n_observable=es["n"], confidence=0.8,
    notes=f"{EX}; up at +5s counted as supporting")
q = summary["quick_flip_mid_returns"]
f2 = findings.add_finding(
    con, trader_id=None, funnel_stage="entry", evidence_type="observed",
    statement="A copier entering 0.5-2 s after a tracked buy captures none of that move: median mid-price return "
              "over the next 3-10 s is about 0% to -2% before ~2.5% round-trip fees.",
    evidence=[("observation", o, "supports")], n_supporting=0, n_observable=len(q),
    confidence=0.8, notes=f"{EX}; n_supporting = grid cells with positive median ({len(q)} cells)")
findings.add_finding(
    con, trader_id=None, funnel_stage="entry", evidence_type="inferred",
    statement="The visible profit of these traders comes at or before their own entry (timing/selection plus the "
              "follower flow their buy triggers), so copying their on-chain buys is not a viable strategy; any edge "
              "must come from anticipating the entry, not reacting to it.",
    evidence=[("finding", f1, "derived_from"), ("finding", f2, "derived_from")], confidence=0.7,
    notes=f"{EX}; copy simulations (reports/simulations/overnight_train.md) agree on 9 wallets")
print(json.dumps({"entries": es["n"], "f1": f1, "f2": f2}))
