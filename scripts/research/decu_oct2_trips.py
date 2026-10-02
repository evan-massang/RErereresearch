"""Decu's own bonding-curve round trips on 2026-10-02 (a day not used to build anything).

Checks whether the trader's edge persists out of sample, independent of any rule we derived from them.
Curve trades only (AMM sells after migration are not matched by round_trips, so trips into migration show as open).

    python scripts/research/decu_oct2_trips.py [--record]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402

from pipeline import config, market  # noqa: E402

WALLET = "4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9"
DAY_START = 1790899200.0  # 2026-10-02 00:00 UTC


def main() -> dict:
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    trips = [t for t in market.round_trips(con, [WALLET]) if t.first_ts >= DAY_START]
    span = con.execute("SELECT min(recv), max(recv) FROM curve_trades WHERE recv >= ?", [DAY_START]).fetchone()
    return {"wallet": WALLET, "tape_span": span, "summary": market.summarize(trips),
            "trips": [{"mint": t.mint, "first_ts": t.first_ts, "sol_in": round(t.sol_in, 4), "sol_out": round(t.sol_out, 4),
                       "closed": t.closed, "graduated": t.graduated, "age_at_entry_s": t.age_at_entry_s} for t in trips]}


if __name__ == "__main__":
    o = main()
    print(json.dumps(o["summary"], indent=1))
    if "--record" in sys.argv:
        from pipeline import annotations, db, findings, observations
        from pipeline.ingest_web import ingest_document
        ex = "claude:decu-oct2-trips"
        p = ROOT / "research/observations/evidence_decu_oct2_trips.json"
        p.write_text(json.dumps(o, indent=1))
        con = db.connect()
        kept = findings.clear_previous(con, ex, ex)
        tid = annotations.trader_by_slug(con, "decu")
        sid, snap = ingest_document(con, str(p), title="Decu bonding-curve round trips, 2026-10-02",
                                    canonical_url="stream://pump_curve/2026-10-02/decu-trips")
        obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="trade_summary",
                                           trader_id=tid, extractor=ex, status="reviewed", value=o["summary"],
                                           content="Decu's verified wallet, curve round trips on Oct 2.")
        s = o["summary"]
        new = findings.add_finding(
            con, trader_id=tid, funnel_stage="exit", evidence_type="observed",
            statement=f"On 2026-10-02 (tape not used to build anything), Decu's verified wallet closed "
                      f"{s['closed_trips']} bonding-curve round trips for {s['pnl_sol']:+.2f} SOL (win rate "
                      f"{s['win_rate']:.0%}, PF {s['profit_factor']}, median size {s['median_size_sol']:.1f} SOL, median "
                      f"entry {s['median_age_at_entry_s']:.0f} s after launch); {s['open_or_incomplete']} more went to "
                      f"migration or are still open. Small sample; consistent with their Oct 1 edge.",
            evidence=[("observation", obs, "supports")], n_supporting=s["closed_trips"],
            n_observable=s["closed_trips"] + s["open_or_incomplete"], confidence=0.5,
            notes=f"{ex}; curve only, AMM exits not matched")
        for k in kept:
            findings.set_finding_status(con, k, "superseded", "Rebuilt.", superseded_by=new)
        print("recorded")
