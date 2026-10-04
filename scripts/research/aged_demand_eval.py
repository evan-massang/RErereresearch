"""Agent aged_demand (2026-10-04): evaluate aged-wallet-demand triggers with exact curve fills.

Reads scratchpad/aged_demand_features.parquet (aged_demand_build.py). For each config the trigger is the FIRST
aged-buy print of a token (age 10-600 s, on curve, non-Mayhem) where the condition holds; entry at the curve
state 1 s later (must be a clean state, |vsol - rsol - 30| < 0.01), exits on later clean prints with the same
model as event_studies.outcomes (take-profit / stop-loss trigger -> fill 1 s later; max hold; completion cut).
0.5 SOL, 1.25% fee per side, tip per transaction 0.001 (main) and 0.01 SOL.

Grid (fixed before any outcome was computed; 36 configs):
  W  in (30, 60) s window
  K  in (3, 5) distinct aged (>= 3 h), non-round-trip buyers in the window
  filter in: none | share (aged share of window buyers >= 0.5 AND wash share <= 0.2)
             | human (count only aged buyers with <= 100 prior mints, same share/wash filter)
  exit in: tp30_sl15 300 s | tp50_sl20 300 s | tp100_sl30 1800 s
Baseline (not selectable, hypothesis check): K raw distinct buyers in W, no age requirement, same exits.

Selection on train only; validation only for configs passing the bar on train.

    python scripts/research/aged_demand_eval.py [--validate]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import event_studies as es  # noqa: E402
from aged_demand_build import ALLOWED, SCR, OUT as FEAT  # noqa: E402

EXITS = (("tp30_sl15_300", 0.3, 0.15, 300.0), ("tp50_sl20_300", 0.5, 0.2, 300.0), ("tp100_sl30_1800", 1.0, 0.3, 1800.0))
TIPS = (0.001, 0.01)
EVID = ROOT / "research/observations"


def sim(T, vs, vt, clean, t, tc, a, b, mh):
    kraw = np.searchsorted(T, t + es.LATENCY, side="right")
    if kraw == 0 or not clean[kraw - 1]:
        return None
    Tc, vsc, vtc = T[clean], vs[clean], vt[clean]
    k = np.searchsorted(Tc, t + es.LATENCY, side="right")
    vs0, vt0 = vsc[k - 1], vtc[k - 1]
    p0 = vs0 / vt0
    end = t + es.LATENCY + mh
    lim = np.searchsorted(Tc, min(end, tc), side="left") if tc is not None and tc <= end else np.searchsorted(Tc, end, side="right")
    lim = max(lim, k)
    px = vsc[k:lim] / vtc[k:lim]
    hit = np.nonzero((px >= p0 * (1 + a)) | (px <= p0 * (1 - b)))[0]
    e = np.searchsorted(Tc, Tc[k + hit[0]] + es.LATENCY, side="right") if len(hit) else lim
    if tc is not None:
        e = min(e, np.searchsorted(Tc, tc, side="left"))
    e = max(e, k)
    return es.rt(vs0, vt0, vsc[e - 1], vtc[e - 1])


def configs(f):
    out = {}
    for W in (30, 60):
        for K in (3, 5):
            sh = (f[f"share{W}"] >= 0.5) & (f[f"wash{W}"] <= 0.2)
            out[f"W{W}_K{K}_none"] = f[f"nA{W}"] >= K
            out[f"W{W}_K{K}_share"] = (f[f"nA{W}"] >= K) & sh
            out[f"W{W}_K{K}_human"] = (f[f"nAh{W}"] >= K) & sh
            out[f"BASE_W{W}_K{K}_raw"] = f[f"nB{W}"] >= K
    return out


def summary(v):
    v = np.sort(np.asarray(v, float))
    w, l = v[v > 0], v[v <= 0]
    return {"n": int(len(v)), "net": round(float(v.sum()), 3) if len(v) else None,
            "exp": round(float(v.mean()), 4) if len(v) else None,
            "pf": round(float(w.sum() / -l.sum()), 3) if len(l) and l.sum() < 0 else None,
            "wo3": round(float(v[:-3].sum()), 3) if len(v) > 3 else None,
            "win": round(float((v > 0).mean()), 3) if len(v) else None}


def passes(s):
    return s["n"] >= 50 and s["net"] > 0 and (s["pf"] or 0) > 1.2 and (s["wo3"] or -1) > 0


def run(validate=False):
    f = pd.read_parquet(FEAT)
    f = f.sort_values(["mint", "t"])
    trig = []
    for name, mask in configs(f).items():
        g = f[mask].groupby("mint", sort=False).head(1)
        trig.append(g[["mint", "t", "split", "migrated"]].assign(cfg=name))
    trig = pd.concat(trig)
    mints = trig.mint.unique()
    con = duckdb.connect(str(ROOT / "data" / "market.duckdb"), read_only=True)
    con.execute(f"SET memory_limit='2GB'; SET threads=2; SET temp_directory='{SCR}/duck_tmp'")
    con.register("mm", pd.DataFrame({"mint": mints}))
    px = con.execute(f"""SELECT mint, recv, vsol, vtok, abs(vsol - rsol - 30) < 0.01 clean FROM curve_trades
                         WHERE mint IN (SELECT mint FROM mm) AND {ALLOWED} ORDER BY mint, recv, rowid""").df()
    comp = dict(con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall())
    arr = {m: (g.recv.to_numpy(), g.vsol.to_numpy(), g.vtok.to_numpy(), g.clean.to_numpy()) for m, g in px.groupby("mint", sort=False)}
    del px
    cache, rows = {}, []
    for r in trig.itertuples():
        key = (r.mint, r.t)
        if key not in cache:
            T, vs, vt, cl = arr[r.mint]
            cache[key] = {n: sim(T, vs, vt, cl, r.t, comp.get(r.mint), a, b, mh) for n, a, b, mh in EXITS}
        rows.append({"cfg": r.cfg, "mint": r.mint, "t": r.t, "split": r.split, "migrated": r.migrated, **cache[key]})
    d = pd.DataFrame(rows)
    d.to_parquet(SCR / "aged_demand_trades.parquet")
    res = {}
    for cfg, g in d.groupby("cfg"):
        for n, *_ in EXITS:
            for tip in TIPS:
                tr = g[(g.split == "train")][n].dropna().to_numpy() - 2 * tip
                res[f"{cfg}|{n}|{tip}"] = {"train": summary(tr)}
    sel = [k for k, v in res.items() if not k.startswith("BASE") and passes(v["train"])]
    if validate:
        for k in sel:
            cfg, n, tip = k.split("|")
            g = d[(d.cfg == cfg) & (d.split == "validation")]
            res[k]["validation"] = summary(g[n].dropna().to_numpy() - 2 * float(tip))
    return d, res, sel


if __name__ == "__main__":
    validate = "--validate" in sys.argv
    d, res, sel = run(validate)
    for k, v in sorted(res.items(), key=lambda kv: -(kv[1]["train"]["exp"] or -9)):
        if k.endswith("|0.001"):
            print(f"{k:42} {v['train']}  {v.get('validation', '')}")
    print("configs passing train bar:", sel)
    tag = "validation" if validate else "train"
    (EVID / f"evidence_aged_demand_{tag}_20261004.json").write_text(json.dumps(
        {"n_selectable_configs": 36, "passing_train": sel, "results": res}, indent=1))
