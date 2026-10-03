"""Iteration 6: win-probability model per take-profit / stop-loss exit (labels from ml_snapshots.py).

For each exit variant g_tp*_sl*_<maxhold> (net of protocol fees and curve impact, before per-tx tips), label
= g - 2 x TIP > 0 with TIP = 0.001 SOL. A gradient-boosted classifier is trained on the train split (ml_model.split);
buy thresholds are quantiles of out-of-fold train probabilities; one trade per token (its first qualifying
snapshot). Validation is scored at tips 0.001 / 0.003 / 0.01 SOL per transaction.

    python scripts/research/ml_exits.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/research"))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from ml_model import FEATURES, split, summary  # noqa: E402
from pipeline import config  # noqa: E402

TIP = 0.001
TIPS = (0.001, 0.003, 0.01)
QUANTILES = (0.99, 0.995, 0.998)


def clf():
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200,
                                          l2_regularization=1.0, random_state=0)


def run(d: pd.DataFrame, label: str) -> dict:
    tr, va = split(d)
    y = (tr[label] - 2 * TIP > 0).astype(int)
    oof = np.zeros(len(tr))
    for a, b in GroupKFold(5).split(tr, y, tr.mint):
        oof[b] = clf().fit(tr[FEATURES].iloc[a], y.iloc[a]).predict_proba(tr[FEATURES].iloc[b])[:, 1]
    m = clf().fit(tr[FEATURES], y)
    pv = m.predict_proba(va[FEATURES])[:, 1]
    yv = (va[label] - 2 * TIP > 0).astype(int)
    out = {"label": label, "train_win_rate": round(float(y.mean()), 4), "val_win_rate": round(float(yv.mean()), 4),
           "val_auc": round(float(roc_auc_score(yv, pv)), 4), "by_quantile": {}}
    for q in QUANTILES:
        thr = float(np.quantile(oof, q))
        ftr = tr.assign(p=oof)[oof >= thr].sort_values("t").drop_duplicates("mint")
        fva = va.assign(p=pv)[pv >= thr].sort_values("t").drop_duplicates("mint")
        out["by_quantile"][str(q)] = {
            "threshold": round(thr, 4),
            "train_oof": {f"tip_{t}": summary(ftr[label] - 2 * t) for t in TIPS},
            "validation": {f"tip_{t}": summary(fva[label] - 2 * t) for t in TIPS}}
    return out


if __name__ == "__main__":
    d = pd.read_parquet(config.path("data") / "processed" / "ml_snapshots.parquet")
    labels = [c for c in d.columns if c.startswith("g_tp")]
    res = []
    for lab in labels:
        r = run(d, lab)
        res.append(r)
        print(lab, "val AUC", r["val_auc"], "val win rate", r["val_win_rate"])
        for q, k in r["by_quantile"].items():
            t, v = k["train_oof"]["tip_0.001"], k["validation"]["tip_0.001"]
            print(f"  q{q}: train n={t['n']} exp={t['expectancy_sol']} pf={t['profit_factor']} wo3={t['pnl_without_top3']} | "
                  f"val n={v['n']} exp={v['expectancy_sol']} pf={v['profit_factor']} wo3={v['pnl_without_top3']} "
                  f"| val@0.01 exp={k['validation']['tip_0.01']['expectancy_sol']}")
    (ROOT / "research/observations/evidence_ml_exits_20261003.json").write_text(json.dumps(res, indent=1))
