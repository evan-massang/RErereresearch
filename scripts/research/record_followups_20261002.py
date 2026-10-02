"""Recompute and record three train-period follow-up studies of 2026-10-02 (none became a hypothesis):

1. X-handle dev tracking (x_handle_track.py): migration lift on Oct 1 train / validation.
2. Final stretch at later entries (final_stretch.py with entry_mcap 250-400): Oct 1 train.
3. Smart-money convergence (smart_convergence.py): smart set from 12:17-14:15, signals 14:15-16:15.

    python scripts/research/record_followups_20261002.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/research"))

import final_stretch as fs  # noqa: E402
import smart_convergence as sc  # noqa: E402
import x_handle_track as xh  # noqa: E402

KEEP = ("n_trades", "pnl_sol", "expectancy_sol", "median_sol", "profit_factor")


def compute() -> dict:
    o = {}
    lift = xh.lift(xh.build())
    o["x_handle"] = {w: lift[w] for w in ("train_oct1", "validation_oct1")}
    o["final_stretch_entry_levels"] = []
    for m in (250, 300, 330, 360, 380, 400):
        r = fs.evaluate(fs.hm("12:17"), fs.hm("16:15"), fs.hm("17:15"), fs.PARAMS | {"entry_mcap_sol": m, "exit_after_s": 300})
        o["final_stretch_entry_levels"].append({"entry_mcap_sol": m} | {k: r[k] for k in KEEP + ("expectancy_without_top3", "exits")})
    con = sc.con_()
    o["smart_convergence"] = []
    for s in (sc.SET, dict(min_trips=10, min_pnl_sol=2, min_win=0.6), dict(min_trips=8, min_pnl_sol=5, min_win=0.5)):
        sm = sc.smart_set(con, sc.U(12, 17), sc.U(14, 15), s)
        for k in (1, 2, 3, 5):
            p = sc.PARAMS | {"k": k, "stop_pct": 50, "exit_after_s": 300}
            r = sc.evaluate(con, sc.signals(con, sm, sc.U(14, 15), sc.U(16, 15), k, p["max_age_s"]), sc.U(17, 15), p)
            o["smart_convergence"].append({"set": s, "n_wallets": len(sm), "k": k} | {x: r[x] for x in KEEP + ("pnl_without_top3",)})
    return o


if __name__ == "__main__":
    from pipeline import db, findings, observations
    from pipeline.ingest_web import ingest_document
    o = compute()
    ex = "claude:followups-2026-10-02"
    p = ROOT / "research/observations/evidence_followups_2026-10-02.json"
    p.write_text(json.dumps(o, indent=1))
    con = db.connect()
    kept = findings.clear_previous(con, ex, ex)
    sid, snap = ingest_document(con, str(p), title="Follow-up studies: X-handle devs, late final-stretch entries, smart-money convergence",
                                canonical_url="stream://pump_curve/2026-10-01/followups-2026-10-02")
    obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="signal_study",
                                       extractor=ex, status="reviewed", value=o,
                                       content="Three train-period follow-up studies (2026-10-02).")
    xt, xv = o["x_handle"]["train_oct1"], o["x_handle"]["validation_oct1"]
    fsl = o["final_stretch_entry_levels"]
    sm = o["smart_convergence"]
    new = []
    new.append(findings.add_finding(
        con, trader_id=None, funnel_stage="discovery", evidence_type="observed",
        statement=f"Tracking devs by the X handle in launch metadata is weak: launches whose handle had an earlier "
                  f"migration migrated {xt['handle_prior_mig>=1']['migration_rate']:.1%} on train "
                  f"({xt['handle_prior_mig>=1']['lift']}x, n={xt['handle_prior_mig>=1']['n']}) and "
                  f"{xv['handle_prior_mig>=1']['lift']}x on validation, vs {xt['wallet good dev']['lift']}x for wallet-based good devs. "
                  f"Handles reused by 3+ launches with no migration: {xt['handle prior>=3, 0 mig']['lift']}x.",
        evidence=[("observation", obs, "supports")], n_supporting=xt["handle_prior_mig>=1"]["n"],
        n_observable=xt["all"]["n"], confidence=0.6, notes=ex))
    new.append(findings.add_finding(
        con, trader_id=None, funnel_stage="entry", evidence_type="observed",
        statement="Buying near the end of the curve does not remove the final-stretch dependence on a few runners: "
                  "on Oct 1 train every entry level from 250 to 400 SOL market cap is negative once its top 3 trades are "
                  "removed (" + ", ".join(f"{r['entry_mcap_sol']}: {r['expectancy_without_top3']:+.3f}" for r in fsl) + " SOL/trade).",
        evidence=[("observation", obs, "supports")], n_supporting=sum(1 for r in fsl if (r["expectancy_without_top3"] or 0) < 0),
        n_observable=len(fsl), confidence=0.6, notes=ex))
    new.append(findings.add_finding(
        con, trader_id=None, funnel_stage="entry", evidence_type="observed",
        statement=f"Buying 1 s after k proven wallets (defined on earlier data, snipers and creators excluded) have bought "
                  f"loses on train for every set and k tested: {sum(1 for r in sm if r['pnl_sol'] < 0)} of {len(sm)} "
                  f"configurations negative, best {max(r['pnl_sol'] for r in sm):+.1f} SOL. On-chain buys by winners are "
                  f"priced in before a follower can act; followers supply their exits.",
        evidence=[("observation", obs, "supports")], n_supporting=sum(1 for r in sm if r["pnl_sol"] < 0),
        n_observable=len(sm), confidence=0.65, notes=ex))
    for k in kept:
        findings.set_finding_status(con, k, "superseded", "Rebuilt.", superseded_by=new[0])
    print(json.dumps({"x_handle": o["x_handle"], "smart": [(r["n_wallets"], r["k"], r["pnl_sol"]) for r in sm]}, indent=1))
