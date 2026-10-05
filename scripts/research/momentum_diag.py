"""Diagnostics (no selection) for the momentum configs that passed train+validation:
cost stress, funding excluded, delisting-settlement episodes excluded, per-quarter, and an
equal-weight long-universe benchmark under the same cost model."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import momentum_sim as M

C, Q, fund = M.load()
out = {}
bench = dict(key="BENCH_EW_LONG", family="bench", L_days=28, skip_days=0, side="long_only")
for split in ["train", "validation"]:
    E, W = M.run(bench, split, C, Q, fund)
    out[f"benchmark_{split}"] = M.stats(E, W)
    print("bench", split, {k: out[f"benchmark_{split}"][k] for k in ["n", "net", "pf", "net_minus_top3", "sharpe", "maxdd", "per_year"]})
# zero-volume tail = contract settled/delisted
dead = {s: Q[s][Q[s] > 0].last_valid_index() for s in Q.columns}
for k in ["XS_L7_LO", "XS_L28_LO"]:
    for sx in [2.0, 4.0]:
        E, W = M.run(M.CFG[k], "validation", C, Q, fund, sx)
        out[f"{k}_val_slipx{sx:g}"] = M.stats(E, W)
        print(k, "slipx", sx, {x: out[f"{k}_val_slipx{sx:g}"][x] for x in ["n", "net", "pf", "net_minus_top3", "pass"]})
    for split in ["train", "validation"]:
        E = pd.read_parquet(M.RAW / f"episodes_{split}_{k}_sx1.0.parquet")
        W = pd.read_parquet(M.RAW / f"weekly_{split}_{k}_sx1.0.parquet")
        def bar(p):
            p = p.sort_values(ascending=False); w, l = p[p > 0].sum(), -p[p < 0].sum()
            return dict(n=len(p), net=round(p.sum(), 4), pf=round(w / l, 3), net_minus_top3=round(p.iloc[3:].sum(), 4))
        nofund = E.ret - E.cost
        settled = E.apply(lambda r: dead[r.sym] is not None and dead[r.sym] < r.end - pd.Timedelta(days=1), axis=1)
        out[f"{k}_{split}_nofunding"] = bar(nofund)
        out[f"{k}_{split}_ex_settled"] = dict(bar(E.pnl[~settled]), settled_eps=E[settled][["sym", "start", "pnl"]].astype(str).values.tolist())
        q = W.groupby(W.t.dt.to_period("Q")).pnl.sum().round(3)
        out[f"{k}_{split}_per_quarter"] = {str(a): b for a, b in q.items()}
        out[f"{k}_{split}_pos_quarters"] = f"{(q > 0).sum()}/{len(q)}"
        print(k, split, "nofund", out[f"{k}_{split}_nofunding"], "ex_settled", {a: b for a, b in out[f"{k}_{split}_ex_settled"].items() if a != "settled_eps"}, "posQ", out[f"{k}_{split}_pos_quarters"])
json.dump(out, open(M.ROOT / "research/observations/evidence_momentum_diagnostics.json", "w"), indent=1, default=str)

# one-day execution delay (fill at the close of day t instead of t-1)
for k in ["XS_L7_LO", "XS_L28_LO"]:
    for split in ["train", "validation"]:
        E, W = M.run(M.CFG[k], split, C, Q, fund, 1.0, delay=1)
        out[f"{k}_{split}_delay1"] = M.stats(E, W)
        print(k, split, "delay1", {x: out[f"{k}_{split}_delay1"][x] for x in ["n", "net", "pf", "net_minus_top3", "sharpe", "pass"]})
json.dump(out, open(M.ROOT / "research/observations/evidence_momentum_diagnostics.json", "w"), indent=1, default=str)
