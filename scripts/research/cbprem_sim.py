"""H-CBPREM simulation per reports/hypotheses/cbprem_preregistration.json.
Usage: python scripts/research/cbprem_sim.py train | validation
train: all 12 configs + kill test + selection -> research/observations/evidence_cbprem_train_<date>.json
validation: ONLY the selected config from the train evidence file, run once."""
import json, sys, glob, hashlib, datetime as dt, pathlib
import numpy as np, pandas as pd

ROOT = pathlib.Path("data/raw/web/cbprem"); PRE = "reports/hypotheses/cbprem_preregistration.json"
IN = ["DOGE", "1000PEPE", "WIF", "POPCAT", "1000FLOKI", "PENGU", "TRUMP", "1000BONK", "1000SHIB"]
SPLITS = {"train": ("2024-10-01", "2025-07-01"), "validation": ("2025-07-01", "2026-04-01")}
HALF = pd.Timestamp("2025-02-15", tz="UTC")
GRID = [(W, k, H) for W in (3, 7) for k in (1.5, 2.5) for H in (15, 30, 60)]
U = json.load(open(ROOT / "universe_check.json"))
TODAY = dt.datetime.utcnow().strftime("%Y%m%d")

def spreads():
    df = pd.concat(pd.read_json(f, lines=True) for f in sorted(glob.glob(str(ROOT / "lighter_spreads_*.jsonl"))))
    return df.groupby("coin")["rt1000_bp"].median().to_dict(), df.groupby("coin")["rt1000_bp"].count().to_dict()

def load(kind, coin):
    fs = sorted(glob.glob(str(ROOT / kind / f"{coin}_*.parquet")))
    return pd.concat([pd.read_parquet(f) for f in fs]) if fs else None

IDX = pd.date_range("2024-09-01", "2026-04-01", freq="1min", tz="UTC", inclusive="left")
usdt = load("cb", "USDT"); usdt = pd.Series(usdt.close.values, pd.to_datetime(usdt.t, unit="s", utc=True)).sort_index()
usdt = usdt[~usdt.index.duplicated()].reindex(IDX).ffill(limit=60)

def prep(coin):
    cb = load("cb", coin); bn = load("bn", coin); fu = load("fund", coin)
    cbs = pd.Series(cb.close.values.astype(float), pd.to_datetime(cb.t, unit="s", utc=True)).sort_index()
    cbs = cbs[~cbs.index.duplicated()].reindex(IDX)
    bns = pd.Series(bn.close.values.astype(float), pd.to_datetime(bn.open_time_ms.astype("int64"), unit="ms", utc=True)).sort_index()
    bns = bns[~bns.index.duplicated()].reindex(IDX)
    scale = 1000.0 if coin.startswith("1000") else 1.0
    p = np.log(cbs / (bns / scale * usdt))
    level = p.rolling(1440, min_periods=360).median().shift(1)        # value at t covers [t-1440, t-1]
    fr = pd.Series(fu.funding_rate.values.astype(float), pd.to_datetime(fu.calc_time_ms.astype("int64"), unit="ms", utc=True)).sort_index()
    cb_first = cbs.first_valid_index(); bn_first = bns.first_valid_index()
    start = max(pd.Timestamp("2024-10-01", tz="UTC"), cb_first + pd.Timedelta(days=30), bn_first + pd.Timedelta(days=30))
    B = IDX[(IDX.minute % 15 == 0)]
    lvl_B = level.reindex(B)
    # x(t) = mean over [t-15, t-1] of p - level(t)
    pv = p.values; pos = IDX.get_indexer(B)
    xs = np.full(len(B), np.nan)
    for i, j in enumerate(pos):
        if j < 15 or np.isnan(lvl_B.iat[i]): continue
        w = pv[j - 15:j]; w = w[~np.isnan(w)]
        if len(w) >= 5: xs[i] = w.mean() - lvl_B.iat[i]
    x = pd.Series(xs, B)
    bv = bns.values
    mom = pd.Series([np.log(bv[j - 1] / bv[j - 16]) if j >= 16 else np.nan for j in pos], B)
    frl = fr.reindex(B, method="ffill")  # latest fundingTime <= t
    return dict(x=x, bns=bns, B=B, pos=pos, start=start, frl=frl, cb_first=str(cb_first), bn_first=str(bn_first),
                cb_cov=float(cbs[start:].notna().mean()), p_sd=float(p[start:].std()))

def zscore(x, W):
    n = W * 96
    m = x.rolling(n, min_periods=n // 2).mean().shift(1); s = x.rolling(n, min_periods=n // 2).std().shift(1)
    return (x - m) / s

def entry_exit(d, j, H):
    bv = d["bns"].values
    if j >= len(bv) or np.isnan(bv[j]): return None
    for jj in range(j + H, min(j + H + 60, len(bv))):
        if not np.isnan(bv[jj]): return bv[j], bv[jj], jj
    return None

def run(D, W, k, H, split, spread):
    lo, hi = (pd.Timestamp(s, tz="UTC") for s in SPLITS[split]); trades = []
    for coin, d in D.items():
        z = zscore(d["x"], W); busy_until = -1; B = d["B"]
        for i, t in enumerate(B):
            if t < lo or t >= hi or t < d["start"]: continue
            j = d["pos"][i]
            if j < busy_until or np.isnan(z.iat[i]) or abs(z.iat[i]) < k: continue
            ee = entry_exit(d, j, H)
            if ee is None: continue
            en, ex, jj = ee; dd = np.sign(z.iat[i]); busy_until = jj + 1
            gross = dd * (ex / en - 1) * 1e4
            fr = d["frl"].iat[i]; fund = dd * (0 if np.isnan(fr) else fr) * H / 480 * 1e4
            trades.append(dict(coin=coin, t=str(t), d=int(dd), z=float(z.iat[i]), gross_bp=gross, fund_bp=fund,
                               net_bp=gross - 1.5 * spread[coin] - fund, net1x_bp=gross - spread[coin] - fund,
                               bnt_bp=gross - 10 - fund))
    return pd.DataFrame(trades)

def stats(v):
    v = np.asarray(v) * 0.1  # bp on $1,000 -> USD
    if len(v) == 0: return dict(n=0)
    w, l = v[v > 0].sum(), -v[v < 0].sum(); srt = np.sort(v)
    return dict(n=int(len(v)), net_usd=round(float(v.sum()), 2), mean_bp=round(float(v.mean() * 10), 2),
                pf=round(float(w / l), 3) if l > 0 else None, net_ex_top3_usd=round(float(srt[:-3].sum()), 2),
                win=round(float((v > 0).mean()), 3))

def summarize(tr):
    if len(tr) == 0: return {"primary": dict(n=0)}
    out = {"primary": stats(tr.net_bp), "lighter_1x": stats(tr.net1x_bp), "binance_taker_10bp": stats(tr.bnt_bp),
           "gross": stats(tr.gross_bp), "mean_fund_bp": round(float(tr.fund_bp.mean()), 3)}
    out["by_coin"] = {c: stats(g.net_bp) | {"gross_mean_bp": round(float(g.gross_bp.mean()), 2)} for c, g in tr.groupby("coin")}
    return out

def bar(s):
    return bool(s.get("n", 0) >= 50 and s["net_usd"] > 0 and (s["pf"] or 0) > 1.2 and s["net_ex_top3_usd"] > 0)

def ic_test(D, W, H):
    rows = []
    lo, hi = (pd.Timestamp(s, tz="UTC") for s in SPLITS["train"])
    for coin, d in D.items():
        z = zscore(d["x"], W); mom = None
        bv = d["bns"].values
        for i, t in enumerate(d["B"]):
            if t < lo or t >= hi or t < d["start"] or np.isnan(z.iat[i]): continue
            j = d["pos"][i]; ee = entry_exit(d, j, H)
            if ee is None or j < 16 or np.isnan(bv[j - 1]) or np.isnan(bv[j - 16]): continue
            rows.append((t, z.iat[i], np.log(bv[j - 1] / bv[j - 16]), np.log(ee[1] / ee[0])))
    df = pd.DataFrame(rows, columns=["t", "z", "m", "r"])
    ic = lambda g: dict(n=int(len(g)), ic_z=round(float(g.z.corr(g.r)), 4), ic_mom=round(float(g.m.corr(g.r)), 4))
    res = {"all": ic(df), "half1": ic(df[df.t < HALF]), "half2": ic(df[df.t >= HALF])}
    res["pass"] = bool(res["all"]["ic_z"] > res["all"]["ic_mom"] and res["half1"]["ic_z"] > 0 and res["half2"]["ic_z"] > 0)
    return res

if __name__ == "__main__":
    mode = sys.argv[1]; assert mode in SPLITS
    spread, nsp = spreads()
    D = {c: prep(c) for c in IN}
    meta = {c: dict(start=str(d["start"]), cb_first=d["cb_first"], bn_first=d["bn_first"], cb_minute_coverage=round(d["cb_cov"], 3),
                    lighter_rt1000_bp_median=round(spread[c], 2), n_spread_snaps=int(nsp[c])) for c, d in D.items()}
    ev = dict(generated_utc=dt.datetime.utcnow().isoformat(timespec="seconds"), mode=mode, prereg=PRE,
              prereg_sha256=hashlib.sha256(open(PRE, "rb").read()).hexdigest(), is_synthetic=False,
              script_sha256=hashlib.sha256(open(__file__, "rb").read()).hexdigest(), coins=meta)
    if mode == "train":
        ev["configs"] = {}
        for W, k, H in GRID:
            tr = run(D, W, k, H, "train", spread); s = summarize(tr)
            ev["configs"][f"W{W}d_k{k}_H{H}"] = s; print(W, k, H, s["primary"], s.get("gross"), flush=True)
        elig = [(c, v["primary"]) for c, v in ev["configs"].items() if v["primary"].get("n", 0) >= 50]
        elig.sort(key=lambda cv: ((cv[1]["pf"] or 0), cv[1]["n"]), reverse=True)
        sel = elig[0][0] if elig else None
        ok = bool(sel and ev["configs"][sel]["primary"]["net_usd"] > 0 and (ev["configs"][sel]["primary"]["pf"] or 0) > 1.0)
        W, k, H = sel.split("_") if sel else ("W7d", "k1.5", "H15"); W, k, H = int(W[1:-1]), float(k[1:]), int(H[1:])
        ev["selected"] = sel; ev["selection_pass_net_pf"] = ok
        ev["kill_test"] = ic_test(D, int(W), int(H)); print(ev["kill_test"])
        ev["selected_train_meets_bar"] = bar(ev["configs"][sel]["primary"]) if sel else False
        ev["verdict_train"] = "PROCEED_TO_VALIDATION" if ok and ev["kill_test"]["pass"] else "KILLED"
    else:
        trn = json.load(open(sorted(glob.glob("research/observations/evidence_cbprem_train_*.json"))[-1]))
        assert trn["verdict_train"] == "PROCEED_TO_VALIDATION", "killed on train; validation not run"
        sel = trn["selected"]; W, k, H = sel.split("_"); W, k, H = int(W[1:-1]), float(k[1:]), int(H[1:])
        tr = run(D, W, k, H, "validation", spread); ev["selected"] = sel; ev["result"] = summarize(tr)
        ev["meets_bar"] = bar(ev["result"]["primary"]); print(ev["result"])
    json.dump(ev, open(f"research/observations/evidence_cbprem_{mode}_{TODAY}.json", "w"), indent=1, default=str)
