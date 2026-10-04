"""Early-detector wallets: detector lists, trigger, grid and evaluation (step 2 of 2).

Input: per-buy tables written by early_detectors_build.py (ED_OUT dir; buys_A = Oct 1 before the holdout,
buys_B = Oct 2, buys_V = Oct 3 validation).

Detector list (from a set of train buys only): wallets with >= MIN_N label-complete qualifying first buys and
precision (share of those buys followed by a 2x peak or a migration within 30 min) >= P.
Train performance is cross-fitted so no trade is scored with a list built from its own fold:
list(A) -> triggers in B, list(B) -> triggers in A, pooled. Validation: list(A + B) -> triggers in V.

Trigger: the first qualifying first buy in a token by any detector (mcap <= 50 SOL, age <= 900 s, slot > create
slot + 1, buyer is not a creator); optional quiet tape: other wallets bought <= 1 SOL and <= 2 distinct wallets in
the 30 s before. Entry 1 s after the detector's buy, exact curve fills via event_studies.outcomes (0.5 SOL,
1.25% fee per side); tip per transaction 0.001 or 0.01 SOL, two transactions per trade.

Grid (40 configs): P in {0.3, 0.5} x quiet in {off, on} x 5 TP/SL x 2 max holds.
Bar: n >= 50, net > 0, profit factor > 1.2, net without the 3 best trades > 0.  Validation is read only for
configs that pass on train at the 0.001 tip.

    ED_OUT=<dir> python scripts/research/early_detectors_eval.py
"""
import itertools
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

D = Path(os.environ.get("ED_OUT", "/tmp/early_detectors"))
MIN_N, PS, TIPS = 8, (0.3, 0.5), (0.001, 0.01)
EXITS = ["g_tp20_sl10", "g_tp30_sl15", "g_tp50_sl20", "g_tp100_sl30", "g_tp200_sl50"]
HOLDS = [300, 1800]


def detectors(d: pd.DataFrame, p: float) -> set:
    g = d[d.label_ok].groupby("usr").ran.agg(["size", "mean"])
    return set(g[(g["size"] >= MIN_N) & (g["mean"] >= p)].index)


def triggers(d: pd.DataFrame, det: set, quiet: bool) -> pd.DataFrame:
    x = d[d.usr.isin(det)].sort_values("t").groupby("mint").head(1)
    if quiet:
        x = x[(x.q_sol30 <= 1.0) & (x.q_n30 <= 2)]
    return x


def stats(v: np.ndarray) -> dict:
    v = np.sort(v[~np.isnan(v)])
    w, l = v[v > 0], v[v <= 0]
    pf = float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else None
    s = {"n": int(len(v)), "net": round(float(v.sum()), 3), "exp": round(float(v.mean()), 4) if len(v) else None,
         "pf": round(pf, 3) if pf is not None else None, "win": round(float((v > 0).mean()), 3) if len(v) else None,
         "net_wo_top3": round(float(v[:-3].sum()), 3) if len(v) > 3 else None}
    s["pass"] = bool(s["n"] >= 50 and s["net"] > 0 and pf is not None and pf > 1.2 and (s["net_wo_top3"] or -1) > 0)
    return s


def describe(x: pd.DataFrame) -> dict:
    return {"n": len(x), "ran_rate": round(float(x.ran.mean()), 3),
            **{f"median_{h}": round(float(x[h].median()), 4) for h in ("r1", "r5", "r30")},
            **{f"mean_{h}": round(float(x[h].mean()), 4) for h in ("r1", "r5", "r30")}}


if __name__ == "__main__":
    A, B = pd.read_parquet(D / "buys_A.parquet"), pd.read_parquet(D / "buys_B.parquet")
    AB = pd.concat([A, B])
    out = {"grid_size": 0, "persistence": {}, "train": {}, "describe_train": {}, "validation": {}}
    # precision persistence (does early-entry precision carry from fold A to fold B at all?)
    ga = A[A.label_ok].groupby("usr").ran.agg(["size", "sum"])
    gb = B[B.label_ok].groupby("usr").ran.agg(["size", "sum"])
    j = ga.join(gb, lsuffix="_a", rsuffix="_b", how="inner")
    j = j[(j.size_a >= MIN_N) & (j.size_b >= 5)]
    j["q"] = pd.qcut((j.sum_a / j.size_a).rank(method="first"), 5, labels=False)
    out["persistence"] = {"base_ran_A": round(float(A[A.label_ok].ran.mean()), 3), "base_ran_B": round(float(B[B.label_ok].ran.mean()), 3),
                          "wallets": len(j), "B_precision_by_A_quintile": {int(q): round(float(g.sum_b.sum() / g.size_b.sum()), 3)
                                                                           for q, g in j.groupby("q")}}
    trig = {}
    for p, quiet in itertools.product(PS, (False, True)):
        x = pd.concat([triggers(B, detectors(A, p), quiet), triggers(A, detectors(B, p), quiet)])
        trig[(p, quiet)] = x
        out["describe_train"][f"P{p}|quiet{int(quiet)}"] = describe(x)
    for (p, quiet), ex, mh in itertools.product(trig, EXITS, HOLDS):
        out["grid_size"] += 1
        key = f"P{p}|quiet{int(quiet)}|{ex}_{mh}"
        x = trig[(p, quiet)]
        out["train"][key] = {str(tip): stats(x[f"{ex}_{mh}"].to_numpy() - 2 * tip) for tip in TIPS}
    passing = [k for k, v in out["train"].items() if v["0.001"]["pass"]]
    out["train_passing"] = passing
    if passing:  # validation is read only here, only for train passes
        V = pd.read_parquet(D / "buys_V.parquet")
        for k in passing:
            p, q, col = k.split("|")
            x = triggers(V, detectors(AB, float(p[1:])), q == "quiet1")
            out["validation"][k] = {str(tip): stats(x[col].to_numpy() - 2 * tip) for tip in TIPS} | {"describe": describe(x)}
    best = max(out["train"], key=lambda k: out["train"][k]["0.001"]["net"])
    out["best_train"] = {"config": best, **out["train"][best]}
    print(json.dumps({k: out[k] for k in ("grid_size", "persistence", "describe_train", "best_train", "train_passing", "validation")}, indent=1))
    for k, v in sorted(out["train"].items(), key=lambda kv: -kv[1]["0.001"]["net"])[:8]:
        print(k, v["0.001"], v["0.01"]["net"])
    (ROOT / "research/observations/evidence_early_detectors_20261004.json").write_text(json.dumps(out, indent=1))
