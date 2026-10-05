"""H-FLUSH-MW: market-wide flush rule, pre-registered in
reports/hypotheses/flush_marketwide_preregistration.json (written before this script was run).

A coin flush (q=2.5) at snapshot s is eligible iff >= K distinct coins (incl. itself) flushed at snapshot
times in (s-30min, s]. Execution/costs reuse flush_sim.simulate unchanged.
Usage: python flush_marketwide.py train | validation <comma-separated configs that passed train>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from flush_sim import (BF, ROOT, TRAIN_END, VAL_END, TRD, UNIVERSE, load_funding, passes,  # noqa: E402
                       signals, simulate, stats)

Q = 2.5
CONFIGS = [dict(K=K, entry=e, H=H) for K in (3, 5) for e in (0.003, "mkt") for H in (60, 120)]


def cname(c):
    return f"K{c['K']}_{'mkt' if c['entry'] == 'mkt' else 'lim0.3%'}_H{c['H']}"


split = sys.argv[1]
only = sys.argv[2].split(",") if len(sys.argv) > 2 else None
if split == "validation" and not only:
    sys.exit("validation requires the list of train-passing configs")
configs = [c for c in CONFIGS if only is None or cname(c) in only]
lo, hi = (pd.Timestamp(0), TRAIN_END) if split == "train" else (TRAIN_END, VAL_END)
hl_of = {v: k for k, v in UNIVERSE.items()}
syms = sorted(p.stem for p in (BF / "klines1m").glob("*.parquet")
              if p.stem in hl_of and (BF / "metrics" / p.name).exists())

data, flushes = {}, []
for sym in syms:
    k, sig = signals(sym)
    sig = sig[sig.index < hi]  # never beyond the split end (holdout never loaded anyway)
    data[sym] = (k, sig)
    f = sig[(sig.zoi <= -Q) & (sig.zp <= -Q)]
    flushes += [(t, sym) for t in f.index]
fl = pd.DataFrame(flushes, columns=["s", "sym"]).sort_values("s").reset_index(drop=True)

# point-in-time breadth: distinct coins flushing in (s-30m, s]
ts = fl.s.values
breadth = np.empty(len(fl), dtype=int)
j0 = 0
for i in range(len(fl)):
    while ts[j0] <= ts[i] - np.timedelta64(30, "m"):
        j0 += 1
    j1 = i
    while j1 + 1 < len(fl) and ts[j1 + 1] == ts[i]:
        j1 += 1
    breadth[i] = fl.sym.iloc[j0:j1 + 1].nunique()
fl["breadth"] = breadth
fl_split = fl[(fl.s >= lo) & (fl.s < hi)]

res, evcount = {}, {}
for c in configs:
    rows = []
    elig = fl_split[fl_split.breadth >= c["K"]]
    evcount[f"K{c['K']}"] = dict(eligible_flush_bars=int(len(elig)),
                                 distinct_days=int(elig.s.dt.date.nunique()),
                                 per_coin=elig.sym.value_counts().to_dict())
    for sym, g in elig.groupby("sym"):
        k, sig = data[sym]
        sub = sig.loc[sig.index.isin(g.s)]
        rows += simulate(sym, hl_of[sym], k, sub, dict(kind="flush", q=Q, entry=c["entry"], H=c["H"]),
                         3e-4, load_funding(hl_of[sym], sym))
    df = pd.DataFrame(rows)
    tr = df[df.filled & ~df.get("gap", pd.Series(False, index=df.index)).fillna(False).astype(bool)].copy()
    st = stats(tr) if len(tr) else dict(n=0)
    st["fill_rate"] = round(float(df.filled.mean()), 3) if len(df) else None
    st["pass"] = bool(passes(st)) if st.get("n") else False
    if len(tr):
        st["gross_mean_bp"] = round(1e4 * tr.gross.mean(), 1)
        st["per_coin"] = {s: dict(n=int(len(g)), net_pct=round(100 * g.net.sum(), 2)) for s, g in tr.groupby("sym")}
        st["per_quarter"] = {str(p): dict(n=int(len(g)), net_pct=round(100 * g.net.sum(), 2))
                             for p, g in tr.groupby(tr.t_in.dt.to_period("Q"))}
        st["top3_bp"] = [round(1e4 * v, 1) for v in np.sort(tr.net.values)[::-1][:3]]
        st["top3_days"] = {str(d): round(100 * v, 2) for d, v in
                           tr.groupby(tr.t_in.dt.date).net.sum().sort_values(ascending=False).head(3).items()}
        tr.to_csv(TRD / f"mw_{split}_{cname(c)}.csv", index=False)
    res[cname(c)] = st
    print(cname(c), {x: st.get(x) for x in ("n", "days", "fill_rate", "net_sum_pct", "mean_bp", "gross_mean_bp",
                                            "pf", "net_ex_top3_pct", "win", "day_t", "pass")})
out = dict(split=split, preregistration="reports/hypotheses/flush_marketwide_preregistration.json",
           n_configs_total=len(CONFIGS), configs_run=[cname(c) for c in configs], event_counts=evcount, results=res)
json.dump(out, open(ROOT / f"research/observations/evidence_flush_marketwide_{split}.json", "w"), indent=1, default=str)
