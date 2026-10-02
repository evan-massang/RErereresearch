"""Can a threshold rule on the visible features reproduce Decu's picks among creator-dump candidates?

Uses the full-day choice set (decu_choice_set.py) but only candidates before 19:15 UTC (the holdout starts
there). Train = before 16:15, validation = 16:15-19:15. Grid over unique buyers (10 s), net flow (10 s),
market cap and "links an X post". Every candidate's PnL is the same simulated H3 execution used for the picks.

    python scripts/research/decu_filter_replication.py [--record]
"""
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402

SRC = ROOT / "research/observations/evidence_decu_choice_set_2026-10-01.json"
TRAIN_END, HOLDOUT_START = 1790874900.0, 1790882100.0


def main() -> dict:
    r = pd.DataFrame(json.loads(SRC.read_text())["rows"]).dropna(subset=["sim_pnl_sol"])
    tr, va = r[r.t < TRAIN_END], r[(r.t >= TRAIN_END) & (r.t < HOLDOUT_START)]
    grp = lambda g: {"n": int(len(g)), "expectancy_sol": round(float(g.sim_pnl_sol.mean()), 4) if len(g) else None,
                     "pnl_sol": round(float(g.sim_pnl_sol.sum()), 3)}
    out = {"train": {"all": grp(tr), "decu_picked": grp(tr[tr.picked])},
           "validation": {"all": grp(va), "decu_picked": grp(va[va.picked])}, "grid": []}
    for ub, nf, mc, tw in itertools.product([12, 16, 20, 25, 30], [0, 10, 15, 20], [0, 50, 60, 80], [False, True]):
        m = lambda g: (g.uniq_buyers_10s >= ub) & (g.net_flow_10s >= nf) & (g.mcap_sol >= mc) & (
            (g.twitter_kind == "status") if tw else True)
        a, b = tr[m(tr)], va[m(va)]
        if len(a) >= 15:
            out["grid"].append({"uniq_buyers_10s>=": ub, "net_flow_10s>=": nf, "mcap_sol>=": mc, "x_post": tw,
                                "train": grp(a), "validation": grp(b)})
    out["grid"].sort(key=lambda x: -x["train"]["expectancy_sol"])
    out["n_rules"] = len(out["grid"])
    out["n_rules_positive_train"] = sum(x["train"]["expectancy_sol"] > 0 for x in out["grid"])
    return out


if __name__ == "__main__":
    o = main()
    print(json.dumps({k: v for k, v in o.items() if k != "grid"}, indent=1))
    for g in o["grid"][:5]:
        print(g)
    if "--record" in sys.argv:
        from pipeline import annotations, db, findings, observations
        from pipeline.ingest_web import ingest_document
        ex = "claude:decu-filter-replication-2026-10-02"
        p = ROOT / "research/observations/evidence_decu_filter_replication_2026-10-02.json"
        p.write_text(json.dumps(o, indent=1))
        con = db.connect()
        kept = findings.clear_previous(con, ex, ex)
        tid = annotations.trader_by_slug(con, "decu")
        sid, snap = ingest_document(con, str(p), title="Threshold rules vs Decu's picks (creator-dump candidates)",
                                    canonical_url="stream://pump_curve/2026-10-01/decu-filter-replication")
        obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain",
                                           kind="choice_set", trader_id=tid, extractor=ex, status="reviewed",
                                           value={k: v for k, v in o.items() if k != "grid"} | {"best": o["grid"][:3]},
                                           content="Grid of visible-feature threshold rules vs Decu's picks.")
        t, v, b = o["train"], o["validation"], o["grid"][0]
        new = findings.add_finding(
            con, trader_id=tid, funnel_stage="matching", evidence_type="observed",
            statement=f"Decu's picks among creator-dump candidates made {t['decu_picked']['expectancy_sol']:+.2f} SOL "
                      f"per simulated trade on train (n={t['decu_picked']['n']}) and "
                      f"{v['decu_picked']['expectancy_sol']:+.2f} on validation (n={v['decu_picked']['n']}), vs "
                      f"{t['all']['expectancy_sol']:+.2f} / {v['all']['expectancy_sol']:+.2f} for all candidates. "
                      f"None of {o['n_rules']} threshold rules on buyers, net flow, market cap and X-post link was "
                      f"positive even in-sample (best {b['train']['expectancy_sol']:+.3f} on train, "
                      f"{b['validation']['expectancy_sol']:+.3f} on validation). Their selection uses information "
                      f"these features do not capture.",
            evidence=[("observation", obs, "supports")], n_supporting=o["n_rules"] - o["n_rules_positive_train"],
            n_observable=o["n_rules"], confidence=0.6, notes=f"{ex}; candidates before 19:15 only (holdout untouched)")
        for k in kept:
            findings.set_finding_status(con, k, "superseded", "Rebuilt.", superseded_by=new)
        print("recorded")
