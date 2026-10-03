"""Gradient-boosted model of net round-trip PnL from point-in-time snapshots (ml_snapshots.py).

Train: Oct 1 before 19:15 UTC (the Oct 1 holdout 19:15-21:15 and later are excluded) and Oct 2.
Validation: Oct 3 snapshots before VAL_END. The buy threshold is the prediction quantile chosen on TRAIN
(out-of-fold predictions), then applied unchanged to validation.

    python scripts/research/ml_model.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from pipeline import config  # noqa: E402

HOLDOUT_START = 1790882100.0          # 2026-10-01 19:15 UTC
OCT2 = 1790899200.0                   # 2026-10-02 00:00 UTC
OCT3 = 1790985600.0
VAL_END = OCT3 + 6 * 3600             # 2026-10-03 06:00 UTC
FEATURES = ["age", "creator_prior", "creator_prior_mig", "mcap", "vsol", "n_trades", "s_since_last", "ret_5", "ret_15",
            "ret_60", "buys_10", "sells_10", "net_flow_10", "uniq_buyers_10", "buys_30", "sells_30", "net_flow_30",
            "uniq_buyers_30", "uniq_buyers", "largest_buy", "dev_in", "dev_out", "launch_block_buyers", "sell_share"]
QUANTILES = (0.99, 0.995, 0.999)


def split(d):
    tr = d[(d.t < HOLDOUT_START) | ((d.t >= OCT2) & (d.t < OCT3))]
    va = d[(d.t >= OCT3) & (d.t < VAL_END)]
    return tr, va


def model():
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200,
                                         l2_regularization=1.0, random_state=0)


def summary(x: pd.Series) -> dict:
    v = np.sort(x.to_numpy())
    w, l = v[v > 0], v[v <= 0]
    return {"n": int(len(v)), "pnl_sol": round(float(v.sum()), 3), "expectancy_sol": round(float(v.mean()), 4) if len(v) else None,
            "profit_factor": round(float(w.sum() / -l.sum()), 3) if len(l) and l.sum() < 0 else None,
            "pnl_without_top3": round(float(v[:-3].sum()), 3) if len(v) > 3 else None}


def run(target: str) -> dict:
    d = pd.read_parquet(config.path("data") / "processed" / "ml_snapshots.parquet")
    tr, va = split(d)
    X, y = tr[FEATURES], tr[target]
    oof = np.zeros(len(tr))
    for a, b in GroupKFold(5).split(X, y, tr.mint):
        oof[b] = model().fit(X.iloc[a], y.iloc[a]).predict(X.iloc[b])
    m = model().fit(X, y)
    pv = m.predict(va[FEATURES])
    out = {"target": target, "train_n": len(tr), "val_n": len(va), "train_base": summary(y), "val_base": summary(va[target])}
    for q in QUANTILES:
        thr = float(np.quantile(oof, q))
        # one trade per token: its first snapshot over the threshold
        ftr = tr.assign(p=oof)[oof >= thr].sort_values("t").drop_duplicates("mint")
        fva = va.assign(p=pv)[pv >= thr].sort_values("t").drop_duplicates("mint")
        out[f"q{q}"] = {"threshold": round(thr, 4), "train_oof": summary(ftr[target]), "validation": summary(fva[target])}
    return out


if __name__ == "__main__":
    res = [run(t) for t in ("pnl_30", "pnl_120", "pnl_600")]
    for r in res:
        print(r["target"], "train base", r["train_base"]["expectancy_sol"], "val base", r["val_base"]["expectancy_sol"])
        for q in QUANTILES:
            k = r[f"q{q}"]
            print(f"  top {1 - q:.3%}: thr {k['threshold']}  train(oof) {k['train_oof']}  val {k['validation']}")
    (ROOT / "research/observations/evidence_ml_model_20261003.json").write_text(json.dumps(res, indent=1))
