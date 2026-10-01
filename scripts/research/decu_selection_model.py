"""Can tape features reproduce Decu's BUY/SKIP choice out of time? (exploratory)

Uses research/observations/evidence_decu_choice_set_2026-10-01.json (candidates 13:38-19:15, written by
decu_choice_set.py 19:15). Trains an L2 logistic regression on candidates before 17:00 and scores those after.

    python scripts/research/decu_selection_model.py
"""
import json
import statistics
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import annotations, db, findings, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402

EX = "claude:decu-selection-model-2026-10-01"
CUT = 1790874000.0          # 17:00 UTC
F = ["age_s", "uniq_buyers_10s", "uniq_buyers_30s", "net_flow_10s", "net_flow_30s", "vol_60s", "trades_60s", "mcap_sol",
     "holders", "top10_pct", "snipers_pct_now", "creation_block_buyers", "creation_block_sol", "largest_buy_30s",
     "dev_in", "dev_out", "s_since_dump", "creator_prev_launches_1h", "dev_pct_now", "drawdown_60s"]
LOG = {"uniq_buyers_30s", "net_flow_10s", "net_flow_30s", "vol_60s", "trades_60s", "mcap_sol", "creation_block_sol",
       "largest_buy_30s", "dev_in", "dev_out"}


def X(rs):
    a = np.array([[float(r.get(f) or 0.0) for f in F]
                  + [float(r.get("twitter_kind") == "profile"), float(r.get("meta_host") == "metadata.j7tracker.io")]
                  for r in rs])
    for i, f in enumerate(F):
        if f in LOG:
            a[:, i] = np.sign(a[:, i]) * np.log1p(np.abs(a[:, i]))
    return a


def main() -> dict:
    o = json.loads((ROOT / "research/observations/evidence_decu_choice_set_2026-10-01.json").read_text())
    rows = o["rows"]
    tr, te = [r for r in rows if r["t"] < CUT], [r for r in rows if r["t"] >= CUT]
    sc = StandardScaler().fit(X(tr))
    clf = LogisticRegression(C=0.1, class_weight="balanced", max_iter=2000).fit(sc.transform(X(tr)), [r["picked"] for r in tr])
    s = clf.predict_proba(sc.transform(X(te)))[:, 1]
    order = np.argsort(-s)
    out = {"train": {"n": len(tr), "picks": sum(r["picked"] for r in tr)}, "test": {"n": len(te), "picks": sum(r["picked"] for r in te)},
           "test_auc": round(float(roc_auc_score([r["picked"] for r in te], s)), 3), "top_k": {}}
    for k in (10, 20, 40, 80):
        top = [te[i] for i in order[:k]]
        sim = [r["sim_pnl_sol"] for r in top if r.get("sim_pnl_sol") is not None]
        out["top_k"][k] = {"decu_picks": sum(r["picked"] for r in top), "sim_trades": len(sim),
                           "pnl_sol": round(sum(sim), 3), "expectancy_sol": round(statistics.mean(sim), 4) if sim else None}
    for name, g in (("before_17", tr), ("after_17", te)):
        p = [r["sim_pnl_sol"] for r in g if r["picked"] and r.get("sim_pnl_sol") is not None]
        out[f"decu_picks_{name}"] = {"n": len(p), "pnl_sol": round(sum(p), 3)}
    (ROOT / "research/observations/evidence_decu_selection_model_2026-10-01.json").write_text(json.dumps(out, indent=1))
    return out


def record(o: dict) -> None:
    con = db.connect()
    con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)", [f"%{EX}%"])
    con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
    con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
    tid = annotations.trader_by_slug(con, "decu")
    p = ROOT / "research/observations/evidence_decu_selection_model_2026-10-01.json"
    sid, snap = ingest_document(con, str(p), title="Decu selection model from tape features (out of time)",
                                canonical_url="stream://pump_curve/2026-10-01/decu-selection-model")
    obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="model_eval",
                                       trader_id=tid, extractor=EX, status="reviewed", value=o,
                                       content="Logistic model of Decu's picks on tape features, trained before 17:00, tested after.")
    t40 = o["top_k"]["40"] if "40" in o["top_k"] else o["top_k"][40]
    findings.add_finding(
        con, trader_id=tid, funnel_stage="matching", evidence_type="observed",
        statement=f"Decu's picks among creator-dump candidates were profitable for a simulated bot in both halves "
                  f"(before 17:00: {o['decu_picks_before_17']['pnl_sol']:+.2f} SOL on {o['decu_picks_before_17']['n']}; "
                  f"after: {o['decu_picks_after_17']['pnl_sol']:+.2f} on {o['decu_picks_after_17']['n']}), but a model of "
                  f"their choice from 22 tape and metadata features, trained before 17:00, ranks the later candidates "
                  f"no better than chance (AUC {o['test_auc']}) and its top 40 lose ({t40['pnl_sol']:+.2f} SOL). "
                  "What Decu selects on is not in these features.",
        evidence=[("observation", obs, "supports")], n_supporting=o["test"]["picks"], n_observable=o["test"]["n"],
        confidence=0.65, notes=f"{EX}; exploratory; 19 picks in total")


if __name__ == "__main__":
    res = main()
    record(json.loads(json.dumps(res)))
    print(json.dumps(res, indent=1))
