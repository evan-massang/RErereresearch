"""Refreshed copy tests (full train period, deterministic simulator) -> findings; pre-registers H6 (copy Decu).

The copy findings of 13:25 UTC were computed on 1 h of tape with a sampled (non-deterministic) slot clock.
On the full train period, copying some wallets is positive in-sample, so the earlier inference is marked
weakened (not edited) and the new numbers are recorded as their own observed finding.

    python scripts/research/copy_refresh.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import annotations, db, findings, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402

EX = "claude:copy-refresh-2026-10-01"
OLD_INFERRED = "fnd_7805bdebf0e74ccb"


def main() -> None:
    o = json.loads((ROOT / "reports/simulations/overnight_train.json").read_text())

    def at(c, d):
        return next((s for s in (c or {}).get("sweep", []) if s["delay_s"] == d), None)

    rows = []
    for slug, v in o["seeds"].items():
        if v.get("copy"):
            rows.append({"who": f"seed:{slug}", "wallet": v["wallet"], "trips": v["summary"].get("closed_trips"),
                         "own_pnl_sol": v["summary"].get("pnl_sol"), **{f"copy_{d}s": at(v["copy"], d) for d in (0.5, 1, 2, 5)}})
    for x in o["leaders"]:
        if any(r["wallet"] == x["wallet"] for r in rows):
            continue                                       # a seed that is also a leader is counted once
        rows.append({"who": f"leader:{x['name']}", "wallet": x["wallet"], "trips": x["summary"]["closed_trips"],
                     "own_pnl_sol": x["summary"]["pnl_sol"], **{f"copy_{d}s": at(x["copy"], d) for d in (0.5, 1, 2, 5)}})
    ev = {"window": o["window"], "note": "Copy = MirrorWallet 0.5 SOL per entry, mirrored sells, 900-s time stop; "
                                         "fee 125 bps, 0.001 SOL priority, 20% slippage tolerance, 2% failure; curve "
                                         "only (exits on Pump AMM after migration are not seen). Leaders are the top "
                                         "8 tracked wallets by PnL in this same window (selection bias); seeds were "
                                         "chosen before any data.", "rows": rows}
    p = ROOT / "research/observations/evidence_copy_refresh_2026-10-01.json"
    p.write_text(json.dumps(ev, indent=1, default=str))

    con = db.connect()
    con.execute("DELETE FROM hypothesis_basis WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)",
                [f"%{EX}%"])
    con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)",
                [f"%{EX}%"])
    con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
    con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
    sid, snap = ingest_document(con, str(p), title="Copy tests, full train period (deterministic simulator)",
                                canonical_url="stream://pump_curve/2026-10-01/copy-refresh")
    obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="copy_sim",
                                       extractor=EX, status="reviewed", value=rows,
                                       content="Copy-trade simulation per wallet at 0.5-5 s delay, train period.")
    pos = [r for r in rows if r["copy_1s"] and r["copy_1s"]["realized_pnl_sol"] > 0]
    neg = [r for r in rows if r["copy_1s"] and r["copy_1s"]["realized_pnl_sol"] <= 0]
    fmt = lambda r: f"{r['who'].split(':')[1]} {r['copy_1s']['realized_pnl_sol']:+.2f} ({r['copy_1s']['n_trades']})"
    decu = next(r for r in rows if r["who"] == "seed:decu")
    f = findings.add_finding(
        con, trader_id=None, funnel_stage="meta", evidence_type="observed",
        statement=f"On the full train period (12:15-17:15 UTC) a 0.5-SOL copier with 1 s delay makes money on "
                  f"{len(pos)} of {len(pos) + len(neg)} tested wallets ({'; '.join(fmt(r) for r in pos)}) and loses "
                  f"on {len(neg)} ({'; '.join(fmt(r) for r in neg)}), SOL (trades). Copying Decu: "
                  f"{decu['copy_0.5s']['realized_pnl_sol']:+.2f} at 0.5 s, {decu['copy_1s']['realized_pnl_sol']:+.2f} at "
                  f"1 s, {decu['copy_5s']['realized_pnl_sol']:+.2f} at 5 s. Small samples; leaders were chosen by "
                  "their PnL in the same window.",
        evidence=[("observation", obs, "supports")], n_supporting=len(pos), n_observable=len(pos) + len(neg),
        confidence=0.5, notes=f"{EX}; supersedes the 13:25 copy simulations (sampled slot clock, 1 h of tape)")
    st = con.execute("SELECT status FROM findings WHERE finding_id = ?", [OLD_INFERRED]).fetchone()
    if st and st[0] == "open":
        findings.set_finding_status(
            con, OLD_INFERRED, "weakened",
            f"Its copy simulations used a sampled (non-deterministic) slot clock and 1 h of tape. On the full train "
            f"period with the fixed simulator, copying is positive for {len(pos)} of {len(pos) + len(neg)} tested "
            f"wallets in-sample (see {f}); the follower-spike observation itself still stands.")
    tid = annotations.trader_by_slug(con, "decu")
    choice = con.execute("SELECT finding_id FROM findings WHERE notes LIKE '%decu-choice-2026-10-01%' LIMIT 1").fetchone()
    pre = json.loads((ROOT / "reports/hypotheses/h6_preregistration.json").read_text())
    findings.reregister_hypothesis(con, "H6:", statement=pre["statement"],
                                   measurable_definition=pre["measurable_definition"],
                                   rationale=f"{EX}: {pre['rationale']} Frozen at {pre['frozen_at_utc']} in "
                                             "reports/hypotheses/h6_preregistration.json.",
                                   basis_finding_ids=[f] + ([choice[0]] if choice else []), trader_scope=tid)
    print(json.dumps({"positive_at_1s": [fmt(r) for r in pos], "negative_at_1s": [fmt(r) for r in neg]}, indent=1))


if __name__ == "__main__":
    main()
