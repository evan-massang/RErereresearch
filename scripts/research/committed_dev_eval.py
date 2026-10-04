"""Evaluate the 36 committed-dev configs (see committed_dev_build.py) on train; validation only for configs
that pass the bar on train, once.

    python scripts/research/committed_dev_eval.py                    # train only
    python scripts/research/committed_dev_eval.py --validate CFG ... # validation for train-passing configs
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
from committed_dev_build import EXITS, OUT  # noqa: E402

TIPS = (0.001, 0.01)
VARIANTS = {
    "A_dev1_org10": lambda d: d.n_org >= 10,
    "B_dev1_org20": lambda d: d.n_org >= 20,
    "C_dev1_org10_first_nomayhem": lambda d: (d.n_org >= 10) & (d.prior == 0) & (d.mayhem != True),  # noqa: E712
    "D_dev2_org10_first_nomayhem_lb3": lambda d: (d.devin >= 2) & (d.n_org >= 10) & (d.prior == 0)
                                                  & (d.mayhem != True) & (d.n_lb <= 3),  # noqa: E712
}


def summary(v):
    v = np.sort(np.asarray(v, dtype=float))
    w, l = v[v > 0], v[v <= 0]
    return {"n": int(len(v)), "total": round(float(v.sum()), 3), "exp": round(float(v.mean()), 4) if len(v) else None,
            "pf": round(float(w.sum() / -l.sum()), 3) if len(l) and l.sum() < 0 else None,
            "wo3": round(float(v[:-3].sum()), 3) if len(v) > 3 else None,
            "win": round(float((v > 0).mean()), 3) if len(v) else None}


def passes(s):
    return s["n"] >= 50 and s["total"] > 0 and (s["pf"] or 0) > 1.2 and (s["wo3"] or -1) > 0


def table(d):
    out = {}
    for vn, f in VARIANTS.items():
        for age in (60, 120, 300):
            sub = d[f(d) & (d.age == age)]
            for ex in EXITS:
                cfg = f"{vn}|T{age}|{ex[0]}"
                out[cfg] = {str(tip): summary(sub[ex[0]].to_numpy() - 2 * tip) for tip in TIPS}
    return out


if __name__ == "__main__":
    d = pd.read_parquet(OUT)
    d = d[d.devin >= 1]
    if "--validate" in sys.argv:
        cfgs = sys.argv[sys.argv.index("--validate") + 1:]
        res = table(d[d.split == "validation"])
        out = {c: res[c] for c in cfgs}
        print(json.dumps(out, indent=1))
        (ROOT / "research/observations/evidence_committed_dev_validation_20261004.json").write_text(json.dumps(out, indent=1))
        sys.exit()
    tr = d[d.split == "train"]
    res = table(tr)
    print(f"configs: {len(res)}")
    for c, v in sorted(res.items(), key=lambda kv: -kv[1]["0.001"]["exp"] if kv[1]["0.001"]["n"] else 0):
        s = v["0.001"]
        print(f"{c:60} {s}  tip.01 total {v['0.01']['total']}  {'PASS' if passes(s) and passes(v['0.01']) else ''}")
    # diagnostics (not used for selection beyond reporting): by train day, migration rate, mayhem coverage
    diag = {"n_train_events_by_age": tr.groupby("age").size().to_dict(),
            "migrated_rate_by_age": tr.groupby("age").migrated.mean().round(3).to_dict(),
            "mayhem_flag_counts": tr.mayhem.astype(str).value_counts().to_dict(),
            "exp_by_day_A_tp100": {str(k): round(float(v), 4) for k, v in
                                   tr.assign(day=(tr.t // 86400).astype(int)).groupby("day").tp100_sl30_1800.mean().items()}}
    print(json.dumps(diag, indent=1))
    (ROOT / "research/observations/evidence_committed_dev_train_20261004.json").write_text(
        json.dumps({"configs": len(res), "results": res, "diagnostics": diag}, indent=1, default=str))
