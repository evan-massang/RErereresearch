"""Record research-loop iterations 1-2 (2026-10-03) as observed findings.

Recomputes from stored inputs: blind LLM scores (research/observations/llm_choice_train) against the Decu
choice set, and KOL front-run returns (data/processed/kol_train.parquet, kol_val.parquet).

    python scripts/research/record_paper_loop_iter1_2.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/research"))
import pandas as pd  # noqa: E402

import llm_choice_batches as lcb  # noqa: E402
from pipeline import config, db, findings, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402


def kol() -> dict:
    t = pd.read_parquet(config.path("data") / "processed" / "kol_train.parquet")
    v = pd.read_parquet(config.path("data") / "processed" / "kol_val.parquet")
    med = lambda d: {c: round(float(d[c].median()), 4) for c in ("gap_pre_to_entry", "r5", "r10", "r20", "r30", "r60")}
    g = t.groupby("name").agg(n=("r10", "size"), r10=("r10", "mean"))
    top = g[(g.n >= 6) & (g.r10 > 0.08)].index
    x = v[v.name.isin(top)]
    return {"train": {"n": len(t), "kols": int(t.usr.nunique()), "median": med(t)},
            "validation": {"n": len(v), "kols": int(v.usr.nunique()), "median": med(v)},
            "train_selected_kols": list(top),
            "selected_on_validation": {"n": len(x), "r10_mean": round(float(x.r10.mean()), 4),
                                       "r20_mean": round(float(x.r20.mean()), 4)}}


if __name__ == "__main__":
    o = {"llm_choice_train": lcb.evaluate(ROOT / "research/observations/llm_choice_train", "train"), "kol_frontrun": kol()}
    ex = "claude:paper-loop-iter1-2"
    p = ROOT / "research/observations/evidence_paper_loop_iter1_2.json"
    p.write_text(json.dumps(o, indent=1))
    con = db.connect()
    kept = findings.clear_previous(con, ex, ex)
    sid, snap = ingest_document(con, str(p), title="Research loop iterations 1-2: blind LLM judgement, KOL front-running",
                                canonical_url="stream://pump_curve/2026-10-01/paper-loop-iter1-2")
    obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="signal_study",
                                       extractor=ex, status="reviewed", value=o,
                                       content="LLM card judgement vs Decu's candidate set; KOL front-run price paths.")
    L, K = o["llm_choice_train"], o["kol_frontrun"]
    new = [findings.add_finding(
        con, trader_id=None, funnel_stage="matching", evidence_type="observed",
        statement=f"Blind LLM judgement does not reproduce Decu's selection: on {L['scored']} train creator-dump "
                  f"candidates, cards it rated buy (n={L['score>=4']['n']}) made {L['score>=4']['expectancy_sol']:+.3f} SOL "
                  f"per simulated trade vs {L['all']['expectancy_sol']:+.3f} for all and "
                  f"{L['decu_picked']['expectancy_sol']:+.3f} for Decu's {L['decu_picked']['n']} picks; it rated "
                  f"{L['score>=4']['decu_picks']} of Decu's picks a buy.",
        evidence=[("observation", obs, "supports")], n_supporting=L["score>=4"]["n"], n_observable=L["scored"],
        confidence=0.6, notes=f"{ex}; first-round scripted scores discarded"),
        findings.add_finding(
        con, trader_id=None, funnel_stage="entry", evidence_type="observed",
        statement=f"KOL follower flow is priced in within 1 s: entering 1 s after a tracked KOL's first buy, the price is "
                  f"already up {K['train']['median']['gap_pre_to_entry']:.0%} (train median, n={K['train']['n']}) and the "
                  f"median return is {K['train']['median']['r10']:+.1%} at 10 s and {K['train']['median']['r20']:+.1%} at 20 s "
                  f"(validation {K['validation']['median']['r10']:+.1%} / {K['validation']['median']['r20']:+.1%}, before "
                  f"costs). KOLs that looked best on train averaged {K['selected_on_validation']['r10_mean']:+.1%} at 10 s on "
                  f"validation.",
        evidence=[("observation", obs, "supports")], n_supporting=K["validation"]["n"],
        n_observable=K["train"]["n"] + K["validation"]["n"], confidence=0.65, notes=ex)]
    for k in kept:
        findings.set_finding_status(con, k, "superseded", "Rebuilt.", superseded_by=new[0])
    print(json.dumps(o["kol_frontrun"], indent=1))
