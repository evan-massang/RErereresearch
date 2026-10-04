"""Score the pregrad grid (see pregrad_build.py) on TRAIN only; validation is scored only for configs that pass
the bar on train at both tips, and only when called with --validation.

Bar: n >= 50, total net > 0, profit factor > 1.2, total net without the 3 best trades > 0.
Costs: gross (already includes 1.25% fee per side and exact curve impact) minus 2 x tip, tip in {0.001, 0.01}.

    python scripts/research/pregrad_eval.py <trades.parquet>                 # train
    python scripts/research/pregrad_eval.py <trades.parquet> --validation    # passing configs only
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
from pregrad_build import GRID  # noqa: E402

TIPS = (0.001, 0.01)


def stats(v):
    v = np.sort(np.asarray(v, float))
    if not len(v):
        return {"n": 0}
    w, l = v[v > 0], v[v <= 0]
    pf = float(w.sum() / -l.sum()) if l.sum() < 0 else None
    wo3 = float(v[:-3].sum()) if len(v) > 3 else None
    return {"n": int(len(v)), "total": round(float(v.sum()), 3), "mean": round(float(v.mean()), 4),
            "median": round(float(np.median(v)), 4), "win": round(float((v > 0).mean()), 3),
            "pf": round(pf, 3) if pf is not None else None, "wo3": round(wo3, 3) if wo3 is not None else None,
            "passes": bool(len(v) >= 50 and v.sum() > 0 and pf is not None and pf > 1.2 and wo3 is not None and wo3 > 0)}


def main():
    d = pd.read_parquet(sys.argv[1])
    split = "validation" if "--validation" in sys.argv else "train"
    tr = d[d.split == "train"]
    out = {}
    for g in GRID:
        x = tr[tr.cfg == g["cfg"]]
        out[g["cfg"]] = {"train": {str(t): stats(x.gross - 2 * t) for t in TIPS},
                         "train_exits": x.exit.value_counts().to_dict(),
                         "train_by_day": {str(k): round(float((y.gross - 0.002).sum()), 3)
                                          for k, y in x.groupby(np.floor(x.t / 86400))}}
    passing = [c for c, o in out.items() if all(o["train"][str(t)]["passes"] for t in TIPS)]
    if split == "validation":
        va = d[d.split == "validation"]
        for c in passing:
            x = va[va.cfg == c]
            out[c]["validation"] = {str(t): stats(x.gross - 2 * t) for t in TIPS}
            out[c]["validation_exits"] = x.exit.value_counts().to_dict()
    for c, o in sorted(out.items(), key=lambda kv: -(kv[1]["train"]["0.001"].get("total") or -1e9)):
        s = o["train"]["0.001"]
        print(f"{c:42} n={s['n']:4} tot={s.get('total')} mean={s.get('mean')} pf={s.get('pf')} wo3={s.get('wo3')} "
              f"win={s.get('win')} | tip.01 tot={o['train']['0.01'].get('total')} {o['train_exits']}"
              + (f" VAL {o.get('validation')}" if 'validation' in o else ""))
    print("configs", len(GRID), "passing on train at both tips:", passing)
    return out, passing


if __name__ == "__main__":
    o, p = main()
    if len(sys.argv) > 2 and sys.argv[2].endswith(".json"):
        Path(sys.argv[2]).write_text(json.dumps({"configs": o, "passing_train": p}, indent=1))
