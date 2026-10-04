"""Agent ml_wallet (2026-10-04): ml_exits-style evaluation of the snapshot model with wallet features added.

Input: scratchpad/ml_wallet_snapshots.parquet from ml_wallet_build.py (allowed data only; clean curve states;
Mayhem and unknown-flag tokens skipped; every label inside its split and recording segment).

Splits: train = fold A (recv < 1790882100) + fold B (1790899200-1790985600); validation = V (1790985600-1791072000).
For each exit label g_tp*_sl*_<maxhold> (net of protocol fees and curve impact, before tips): target
= g - 2 x 0.001 > 0; HistGradientBoostingClassifier (ml_exits.py settings), GroupKFold(5) by mint on train;
buy thresholds = quantiles 0.99 / 0.995 / 0.998 of out-of-fold train probabilities; one trade per token (its first
qualifying snapshot). Scored at tips 0.001 and 0.01 SOL per transaction (two per trade).

Selectable grid: 8 exits x 3 quantiles = 24 configs, FEATURES = 24 tape + 13 wallet features. The same grid with
the 24 tape features only (and with wallet features only) is reported as a non-selectable reference.
Bar: n >= 50, net > 0, PF > 1.2, net without the best 3 > 0, at the 0.001 tip on train out-of-fold.
Validation is computed only for configs that pass on train.

    python scripts/research/ml_wallet_eval.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

SCR = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad")
BASE = ["age", "creator_prior", "creator_prior_mig", "mcap", "vsol", "n_trades", "s_since_last", "ret_5", "ret_15",
        "ret_60", "buys_10", "sells_10", "net_flow_10", "uniq_buyers_10", "buys_30", "sells_30", "net_flow_30",
        "uniq_buyers_30", "uniq_buyers", "largest_buy", "dev_in", "dev_out", "launch_block_buyers", "sell_share"]
WALLET = ["det_n_since", "det_sol_since", "det_n_30", "det_sol_30", "prec_max", "prec_mean", "prec_known_n",
          "aged_n_30", "aged_share_30", "aged_n_since", "aged_share_since", "wash_share_30", "wash_share_since"]
TIP, TIPS, QUANTILES = 0.001, (0.001, 0.01), (0.99, 0.995, 0.998)


def clf():
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200,
                                          l2_regularization=1.0, random_state=0)


def stats(x) -> dict:
    v = np.sort(np.asarray(x, dtype=float))
    w, l = v[v > 0], v[v <= 0]
    pf = float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else None
    s = {"n": int(len(v)), "net": round(float(v.sum()), 3), "exp": round(float(v.mean()), 4) if len(v) else None,
         "pf": round(pf, 3) if pf is not None else None, "win": round(float((v > 0).mean()), 3) if len(v) else None,
         "net_wo_top3": round(float(v[:-3].sum()), 3) if len(v) > 3 else None}
    s["pass"] = bool(s["n"] >= 50 and s["net"] > 0 and pf is not None and pf > 1.2 and (s["net_wo_top3"] or -1) > 0)
    return s


def picks(df, p, thr):
    return df.assign(p=p)[p >= thr].sort_values("t").drop_duplicates("mint")


def run(tr, label, feats):
    y = (tr[label] - 2 * TIP > 0).astype(int)
    oof = np.zeros(len(tr))
    for a, b in GroupKFold(5).split(tr, y, tr.mint):
        oof[b] = clf().fit(tr[feats].iloc[a], y.iloc[a]).predict_proba(tr[feats].iloc[b])[:, 1]
    res = {"oof_auc": round(float(roc_auc_score(y, oof)), 4), "by_q": {}}
    for q in QUANTILES:
        thr = float(np.quantile(oof, q))
        ft = picks(tr, oof, thr)
        res["by_q"][str(q)] = {"thr": thr, "train_oof": {str(t): stats(ft[label] - 2 * t) for t in TIPS},
                               "train_oof_by_fold": {f: stats(g[label] - 2 * TIP) for f, g in ft.groupby("fold")},
                               "mean_age": round(float(ft.age.mean()), 1)}
    return res


if __name__ == "__main__":
    d = pd.read_parquet(SCR / "ml_wallet_snapshots.parquet")
    tr, va = d[d.fold.isin(["A", "B"])].reset_index(drop=True), d[d.fold == "V"].reset_index(drop=True)
    labels = sorted(c for c in d.columns if c.startswith("g_tp"))
    out = {"n_train": len(tr), "n_val": len(va), "train_tokens": int(tr.mint.nunique()),
           "val_tokens": int(va.mint.nunique()), "selectable_configs": len(labels) * len(QUANTILES),
           "base_rates_train": {l: stats(tr[l] - 2 * TIP)["exp"] for l in labels},
           "feature_sets": {}, "validation": {}}
    sets = {"base+wallet": BASE + WALLET, "base_only_reference": BASE, "wallet_only_reference": ["age", "mcap"] + WALLET}
    for name, feats in sets.items():
        out["feature_sets"][name] = {}
        for lab in labels:
            r = run(tr, lab, feats)
            out["feature_sets"][name][lab] = r
            for q, k in r["by_q"].items():
                s = k["train_oof"]["0.001"]
                print(f"{name:22s} {lab:18s} q{q} auc={r['oof_auc']} n={s['n']} net={s['net']} exp={s['exp']} "
                      f"pf={s['pf']} wo3={s['net_wo_top3']} | @0.01 net={k['train_oof']['0.01']['net']}", flush=True)
    sel = out["feature_sets"]["base+wallet"]
    passing = [(lab, q) for lab in labels for q in sel[lab]["by_q"] if sel[lab]["by_q"][q]["train_oof"]["0.001"]["pass"]]
    out["train_passing"] = [f"{lab}|q{q}" for lab, q in passing]
    best = max(((lab, q) for lab in labels for q in sel[lab]["by_q"]),
               key=lambda z: sel[z[0]]["by_q"][z[1]]["train_oof"]["0.001"]["net"])
    out["best_train"] = {"config": f"{best[0]}|q{best[1]}", **sel[best[0]]["by_q"][best[1]]}
    if passing:  # validation read only for train passes, once
        for lab in sorted({lab for lab, _ in passing}):
            y = (tr[lab] - 2 * TIP > 0).astype(int)
            pv = clf().fit(tr[BASE + WALLET], y).predict_proba(va[BASE + WALLET])[:, 1]
            for l2, q in passing:
                if l2 != lab:
                    continue
                fv = picks(va, pv, sel[lab]["by_q"][q]["thr"])
                out["validation"][f"{lab}|q{q}"] = {str(t): stats(fv[lab] - 2 * t) for t in TIPS}
    print(json.dumps({k: out[k] for k in ("n_train", "n_val", "selectable_configs", "train_passing", "best_train",
                                          "validation")}, indent=1, default=str))
    (ROOT / "research/observations/evidence_ml_wallet_20261004.json").write_text(json.dumps(out, indent=1, default=str))
