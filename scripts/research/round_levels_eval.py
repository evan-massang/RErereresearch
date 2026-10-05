"""Describe + score the round USD market-cap level study (agent round_levels). Reads the scratchpad outputs of
round_levels_build.py. Train only unless --validate CONFIG ... is given (only for configs that pass the full
bar on train, once).

Bar: >= 50 trades, net profit after costs, profit factor > 1.2, still profitable without the best 3 trades.
Net = gross (exact fills, fees, 1 s latency) - 2 x tip; tip 0.001 SOL (main) and 0.01 SOL.

    python scripts/research/round_levels_eval.py
    python scripts/research/round_levels_eval.py --validate CONFIG [CONFIG ...]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad")
OCT3, HOLD0 = 1790985600.0, 1790882100.0
TIPS = (0.001, 0.01)
R10 = {10000, 20000, 30000, 40000}
R5 = {15000, 25000, 35000, 45000}


def stats(v):
    v = np.sort(np.asarray(v, float))
    w, l = v[v > 0], v[v <= 0]
    return {"n": int(len(v)), "total": round(float(v.sum()), 3), "mean": round(float(v.mean()), 4) if len(v) else None,
            "pf": round(float(w.sum() / -l.sum()), 3) if l.sum() < 0 else None,
            "wo3": round(float(v[:-3].sum()), 3) if len(v) > 3 else None,
            "win": round(float((v > 0).mean()), 3) if len(v) else None}


def passes(s):
    return s["n"] >= 50 and s["total"] > 0 and (s["pf"] or 0) > 1.2 and (s["wo3"] or -1) > 0


def describe():
    raw = json.load(open(SCRATCH / "round_levels_desc_raw.json"))
    ath = pd.read_parquet(SCRATCH / "round_levels_ath_train.parquet").ath.to_numpy()
    rows = []
    for k in raw["pass"]:
        L = int(k)
        ne, nr = raw["pass"][k]
        nb, sb, na, sa = raw["sell"][k]
        rows.append({"L": L, "cls": "R10" if L in R10 else "R5" if L in R5 else "other",
                     "entered": ne, "pass": nr / ne if ne else np.nan,
                     "n_below": nb, "sell_below": sb / nb if nb else np.nan,
                     "n_above": na, "sell_above": sa / na if na else np.nan,
                     "ath_below": int(((ath >= 0.95 * L) & (ath < L)).sum()),
                     "ath_above": int(((ath >= L) & (ath < 1.05 * L)).sum())})
    d = pd.DataFrame(rows).set_index("L").sort_index()
    d["ath_ratio"] = d.ath_below / d.ath_above.replace(0, np.nan)
    # excess vs neighbouring whole-$1k levels (L+-1k, L+-2k), which are all non-round for R10 levels
    for col in ("pass", "sell_below", "sell_above", "ath_ratio"):
        nb = []
        for L in d.index:
            nn = [x for x in (L - 2000, L - 1000, L + 1000, L + 2000) if x in d.index]
            nb.append(d.loc[nn, col].mean())
        d[col + "_nbr"] = nb
        d[col + "_ex"] = d[col] - d[col + "_nbr"]
    out = {"per_level": d.reset_index().round(4).replace({np.nan: None}).to_dict("records")}
    summ = {}
    for cls in ("R10", "R5", "other"):
        g = d[d.cls == cls]
        summ[cls] = {c + "_ex_mean": round(float(g[c + "_ex"].mean()), 4) for c in ("pass", "sell_below", "sell_above", "ath_ratio")}
        summ[cls]["levels"] = [int(x) for x in g.index]
    # distribution of the 'other' levels' excess, to place R10 against (rank-based placebo test)
    for c in ("pass", "sell_below", "ath_ratio"):
        oth = d[d.cls == "other"][c + "_ex"].dropna().to_numpy()
        summ["placebo_" + c] = {"other_ex_sd": round(float(oth.std()), 4),
                                "R10_ex": {int(L): round(float(d.loc[L, c + "_ex"]), 4) for L in sorted(R10) if L in d.index},
                                "R10_pct_rank_vs_other": {int(L): round(float((oth < d.loc[L, c + "_ex"]).mean()), 3)
                                                          for L in sorted(R10) if L in d.index}}
    out["summary"] = summ
    out["n_ath_tokens"] = int(len(ath))
    return d, out


def main():
    td = pd.read_parquet(SCRATCH / "round_levels_trades.parquet")
    raw = json.load(open(SCRATCH / "round_levels_desc_raw.json"))
    cfgs, ctrl = raw["configs"], raw["controls"]
    if len(sys.argv) > 2 and sys.argv[1] == "--validate":
        va = td[td.t >= OCT3]
        res = {}
        for c in sys.argv[2:]:
            assert c in cfgs
            res[c] = {str(tip): stats(va[va.config == c].gross - 2 * tip) for tip in TIPS}
            print(c, res[c])
        (ROOT / "research/observations/evidence_round_levels_validation_20261005.json").write_text(json.dumps(res, indent=1))
        return
    d, desc = describe()
    pd.set_option("display.width", 220)
    print(d[["cls", "entered", "pass", "pass_ex", "n_below", "sell_below", "sell_below_ex", "sell_above",
             "sell_above_ex", "ath_below", "ath_above", "ath_ratio", "ath_ratio_ex"]].round(3).to_string())
    print(json.dumps(desc["summary"], indent=1))
    tr = td[td.t < OCT3]
    res = {}
    for c in cfgs + ctrl:
        g = tr[tr.config == c]
        res[c] = {"eligible": c in cfgs}
        for tip in TIPS:
            res[c][str(tip)] = stats(g.gross - 2 * tip)
        res[c]["oct1"] = stats(g[g.t < HOLD0].gross - 0.002)
        res[c]["oct2"] = stats(g[g.t >= HOLD0].gross - 0.002)
        res[c]["by_level_mean"] = {int(L): round(float(x), 4) for L, x in (g.groupby("level").gross.mean() - 0.002).items()}
        res[c]["passes_train"] = passes(res[c]["0.001"])
        print(f"{c:42} {'' if c in cfgs else '(ctrl)'} {res[c]['0.001']}  pass={res[c]['passes_train']}")
    out = {"n_configs_eligible": len(cfgs), "n_controls": len(ctrl), "describe": desc, "train": res,
           "passing_train": [c for c in cfgs if res[c]["passes_train"]]}
    (ROOT / "research/observations/evidence_round_levels_train_20261005.json").write_text(json.dumps(out, indent=1))
    print("passing on train:", out["passing_train"])


if __name__ == "__main__":
    main()
