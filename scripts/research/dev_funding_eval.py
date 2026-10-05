"""Agent dev_funding (2026-10-05): migration lift by funding class, and the pre-declared trade grid.

Grid (declared before any trade outcome was printed): 5 filters x 2 entries x 3 exits = 30 configs.
  filters  cex          funder in the Dune CEX list
           exch         funder_class in (cex, whale)            # labelled or unlabelled exchange-like
           aged         creator_class == aged (first signature >= 30 d before launch)
           real         (funder_class in (cex, whale) OR creator_class == aged) AND funder_class != farm
           notfarm      funder_class not in (farm, fresh) AND creator_class != fresh AND funder_class != unknown
  entries  L1 (create + 1 s), M2 (first print at 2x initial price within 600 s, + 1 s)
  exits    tp50_sl20_300, tp100_sl30_1800, tp200_sl50_1800
  'all' (no filter) is reported as a reference only, not selectable.
Costs: fills already include 1.25% per side; tips 0.001 (primary) and 0.01 SOL per transaction, 2 per trade.
Bar: n >= 50, net > 0, PF > 1.2, net without the best 3 trades > 0.

    python scripts/research/dev_funding_eval.py lift
    python scripts/research/dev_funding_eval.py train
    python scripts/research/dev_funding_eval.py validation   # only configs that passed on train
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCR = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad/dev_funding")
EV = ROOT / "research/observations"
TIPS = (0.001, 0.01)
ENTRIES = ("L1", "M2")
EXITS = ("tp50_sl20_300", "tp100_sl30_1800", "tp200_sl50_1800")


def filters(d):
    exch = d.funder_class.isin(["cex", "whale"])
    return {
        "all": pd.Series(True, index=d.index),
        "cex": d.funder_class == "cex",
        "exch": exch,
        "aged": d.creator_class == "aged",
        "real": (exch | (d.creator_class == "aged")) & (d.funder_class != "farm"),
        "notfarm": ~d.funder_class.isin(["farm", "fresh", "unknown"]) & (d.creator_class != "fresh"),
    }


def summary(v):
    v = np.sort(np.asarray(v, float))
    if not len(v):
        return {"n": 0}
    w, l = v[v > 0], v[v <= 0]
    return {"n": int(len(v)), "net": round(float(v.sum()), 3), "exp": round(float(v.mean()), 4),
            "pf": round(float(w.sum() / -l.sum()), 3) if l.sum() < 0 else None,
            "wo3": round(float(v[:-3].sum()), 3) if len(v) > 3 else None, "win": round(float((v > 0).mean()), 3)}


def passes(s):
    return s["n"] >= 50 and s["net"] > 0 and (s["pf"] or 0) > 1.2 and (s["wo3"] or -1) > 0


def lift():
    d = pd.read_parquet(SCR / "dev_funding_train.parquet")
    # a completion inside the create transaction (ttc < 1 s, a bundled buy of the whole curve) cannot be traded
    d["instant"] = d.migrated & (d.ttc < 1.0)
    d["mig_all"] = d.migrated
    d["migrated"] = d.migrated & ~d.instant
    print("instant completions", int(d.instant.sum()), "tradable migrations", int(d.migrated.sum()))
    out = {"instant_completions": int(d.instant.sum()), "tradable_migrations": int(d.migrated.sum()),"n_launches": len(d), "n_creators": int(d.creator.nunique()), "base_mig": round(float(d.migrated.mean()), 4)}
    for col in ("funder_class", "creator_class"):
        t = d.groupby(col).agg(n=("mint", "size"), creators=("creator", "nunique"), mig=("migrated", "mean"),
                               mig_incl_instant=("mig_all", "mean"), instant=("instant", "sum"),
                               peak2=("peak_x", lambda x: float((x >= 2).mean())),
                               tape_prior_med=("tape_prior", "median"))
        t["lift"] = t.mig / d.migrated.mean()
        print(t.round(4))
        out[col] = t.round(4).reset_index().to_dict("records")
    for name, m in filters(d).items():
        x = d[m]
        out.setdefault("filters", {})[name] = {"n": int(len(x)), "mig": round(float(x.migrated.mean()), 4),
                                               "lift": round(float(x.migrated.mean() / d.migrated.mean()), 3)}
    # 95% CI by creator-cluster bootstrap for the main classes (serial launchers repeat)
    rng = np.random.default_rng(1)
    cr = d.groupby("creator")
    for name, m in filters(d).items():
        x = d[m]
        g = x.groupby("creator").migrated.agg(["sum", "size"])
        bs = []
        for _ in range(1000):
            i = rng.integers(0, len(g), len(g))
            bs.append(g["sum"].to_numpy()[i].sum() / max(g["size"].to_numpy()[i].sum(), 1))
        out["filters"][name]["mig_ci95"] = [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]
    print(json.dumps(out["filters"], indent=1))
    print(out["base_mig"], out["n_launches"])
    (EV / "evidence_dev_funding_lift_train_20261005.json").write_text(json.dumps(out, indent=1, default=str))


def grid(split, only=None):
    d = pd.read_parquet(SCR / f"dev_funding_{split}.parquet")
    res = {}
    for fname, m in filters(d).items():
        for e in ENTRIES:
            for x in EXITS:
                key = f"{fname}|{e}|{x}"
                if only is not None and key not in only:
                    continue
                col = f"{e}_{x}"
                v = d.loc[m, col].dropna().to_numpy() if col in d else np.array([])
                res[key] = {str(t): summary(v - 2 * t) for t in TIPS}
                res[key]["migrated_share"] = round(float(d.loc[m & d[col].notna(), "migrated"].mean()), 4) if len(v) else None
    return res


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "lift":
        lift()
    elif mode == "train":
        r = grid("train")
        sel = [k for k in r if not k.startswith("all|")]
        print("selectable configs:", len(sel))
        passed = [k for k in sel if passes(r[k]["0.001"])]
        for k, v in r.items():
            print(f"{k:34} {v['0.001']}  tip.01 net {v['0.01'].get('net')}  mig {v['migrated_share']}")
        print("PASS on train:", passed)
        (EV / "evidence_dev_funding_train_20261005.json").write_text(json.dumps(
            {"n_selectable": len(sel), "passed": passed, "results": r}, indent=1))
    elif mode == "validation":
        t = json.loads((EV / "evidence_dev_funding_train_20261005.json").read_text())
        if not t["passed"]:
            sys.exit("nothing passed on train; validation not opened")
        r = grid("validation", only=set(t["passed"]))
        for k, v in r.items():
            print(k, v)
        (EV / "evidence_dev_funding_validation_20261005.json").write_text(json.dumps(
            {"configs": t["passed"], "results": r}, indent=1))
