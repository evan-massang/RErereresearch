"""H-MEMELEAD scoring (real data, is_synthetic=False). Rules: reports/hypotheses/memelead_preregistration.json.

usage: python scripts/research/memelead_sim.py costs
       python scripts/research/memelead_sim.py train
       python scripts/research/memelead_sim.py validation <config_id>   (runs ONCE; refuses if evidence exists)
"""
import glob, json, sys, pathlib, hashlib, datetime
import numpy as np, pandas as pd

PRE_PATH = "reports/hypotheses/memelead_preregistration.json"
PRE = json.load(open(PRE_PATH))
COINS = PRE["universe"]["coins_13"]
S1 = pathlib.Path("data/raw/web/memelead/s1")
EV = pathlib.Path("research/observations")
TRAIN = [d for d in PRE["data"]["sample_days"] if d <= "2025-06-30"]
VALID = [d for d in PRE["data"]["sample_days"] if "2025-07-01" <= d <= "2026-03-31"]
CONFIGS = {c["id"]: c for c in PRE["grid"]["configs"]}
STALE_S, COOLDOWN_S, CLUSTER_S = 30, 10, 5
NDAY = 86_400


def costs():
    rows = []
    for f in sorted(glob.glob("data/raw/web/memelead/lighter_spreads_*.jsonl")):
        rows += [json.loads(l) for l in open(f)]
    df = pd.DataFrame(rows)
    df = df[df.get("rt1000_bp").notna()] if "rt1000_bp" in df else df
    g = df.groupby("coin")
    out = pd.DataFrame({"n_snapshots": g.size(), "quoted_median_bp": g.quoted_bp.median(),
                        "rt1000_median_bp": g.rt1000_bp.median(), "rt1000_p90_bp": g.rt1000_bp.quantile(0.9),
                        "first_ts": g.ts.min(), "last_ts": g.ts.max()})
    out["primary_cost_bp"] = 1.5 * out.rt1000_median_bp
    out["stress_p90_cost_bp"] = 1.5 * out.rt1000_p90_bp
    return out


def rank_day(day):
    D = pd.Timestamp(day); r = {}
    for c in COINS:
        k = pd.read_parquet(f"data/raw/web/momentum/klines/{c}USDT.parquet")
        t = pd.to_datetime(k.open_time, unit="ms")
        if c == "PUMP":
            k, t = k[t >= "2025-07-11"], t[t >= "2025-07-11"]
        w = k[(t >= D - pd.Timedelta(days=30)) & (t < D)]
        if len(w) >= 30:
            r[c] = float(w.quote_volume.mean())
    rk = sorted(r, key=r.get, reverse=True)
    return rk[:3], rk[3:], r


def load(c, day):
    d = pd.read_parquet(S1 / f"{c}USDT_{day}.parquet")
    sec = d.sec.to_numpy()
    mid_c = ((d.bid_c + d.ask_c) / 2).to_numpy(float)
    mid_6 = ((d.bid_6 + d.ask_6) / 2).to_numpy(float)
    fresh = (sec - d.bid_ts.to_numpy() <= STALE_S) & (sec - d.ask_ts.to_numpy() <= STALE_S) & (d.bid_ts.to_numpy() >= 0) & (d.ask_ts.to_numpy() >= 0)
    return mid_c, mid_6, fresh


def ret2(mid, fresh):
    r = np.full(NDAY, np.nan)
    r[2:] = mid[2:] / mid[:-2] - 1
    ok = fresh.copy(); ok[2:] &= fresh[:-2]; ok[:2] = False
    r[~ok] = np.nan
    return r


def hourly_beta(mL, fL, mF, fF):
    """beta[h] for h in 0..23 from non-overlapping 10-s log returns in [h-2, h) hours; NaN if h<2."""
    idx = np.arange(9, NDAY, 10)
    ok = fL[idx] & fF[idx]
    lL, lF = np.log(mL[idx]), np.log(mF[idx])
    rL, rF = np.diff(lL), np.diff(lF); ok2 = ok[1:] & ok[:-1] & np.isfinite(rL) & np.isfinite(rF)
    endsec = idx[1:]
    beta = np.full(24, np.nan)
    for h in range(2, 24):
        m = ok2 & (endsec >= (h - 2) * 3600) & (endsec < h * 3600)
        if m.sum() >= 100 and (rL[m] ** 2).sum() > 0:
            beta[h] = min(3.0, float((rL[m] * rF[m]).sum() / (rL[m] ** 2).sum()))
    return beta


def run_day(day, cfgs, cost):
    leaders, followers, qv = rank_day(day)
    data = {c: load(c, day) for c in leaders + followers}
    r2 = {c: ret2(data[c][0], data[c][2]) for c in data}
    betas = {}
    if any(c["beta"] == "trailing" for c in cfgs):
        for L in leaders:
            for F in followers:
                betas[(L, F)] = hourly_beta(data[L][0], data[L][2], data[F][0], data[F][2])
    out = []
    for cfg in cfgs:
        th, H = cfg["theta_bp"] / 1e4, cfg["H_s"]
        trig = []
        for li, L in enumerate(leaders):
            r = r2[L]; cand = np.where(np.abs(np.nan_to_num(r)) >= th)[0]; last = -10**9
            for s in cand:
                if s - last >= COOLDOWN_S:
                    trig.append((s, li, L, np.sign(r[s]), r[s])); last = s
        trig.sort()
        busy = {F: -1 for F in followers}
        for (s, li, L, d, rL) in trig:
            if s + 1 + H >= NDAY:
                continue
            for F in followers:
                if s <= busy[F]:
                    continue
                if cfg["beta"] == "trailing":
                    if s < 2 * 3600:
                        continue
                    b = betas[(L, F)][s // 3600]
                    if not np.isfinite(b) or b < 0.25:
                        continue
                else:
                    b = 1.0
                rF = r2[F][s]
                if not np.isfinite(rF) or d * rF >= th * b / 2:
                    continue
                e, x = data[F][1][s + 1], data[F][1][s + 1 + H]
                if not (np.isfinite(e) and np.isfinite(x)):
                    continue
                g = d * (x / e - 1) * 1e4
                busy[F] = s + 1 + H
                out.append({"config": cfg["id"], "day": day, "sec": int(s), "leader": L, "follower": F,
                            "dir": int(d), "r_leader_bp": float(rL * 1e4), "r_follower_bp": float(rF * 1e4),
                            "beta": float(b), "gross_bp": float(g),
                            "cost_primary_bp": float(cost.loc[F, "primary_cost_bp"]),
                            "cost_1x_bp": float(cost.loc[F, "rt1000_median_bp"]),
                            "cost_p90_bp": float(cost.loc[F, "stress_p90_cost_bp"])})
    return out, {"day": day, "leaders": leaders, "followers": followers}


def metrics(t, col="cost_primary_bp"):
    if len(t) == 0:
        return {"n": 0}
    net = t.gross_bp - t[col]
    w, l = net[net > 0].sum(), -net[net < 0].sum()
    srt = np.sort(net.to_numpy())[::-1]
    trig_id = t.day + "|" + t.leader + "|" + t.sec.astype(str)
    # clusters: triggers (any leader) within CLUSTER_S s of the previous trigger on the same day
    tr = t.assign(net=net, trig=trig_id).groupby(["day", "sec", "leader"], as_index=False).net.sum().sort_values(["day", "sec"])
    cl = (tr.day != tr.day.shift()) | (tr.sec - tr.sec.shift() > CLUSTER_S)
    tr["cluster"] = cl.cumsum()
    cs = tr.groupby("cluster").net.sum()
    ds = t.assign(net=net).groupby("day").net.sum()
    return {"n": int(len(t)), "gross_mean_bp": float(t.gross_bp.mean()), "cost_mean_bp": float(t[col].mean()),
            "net_mean_bp": float(net.mean()), "net_sum_bp": float(net.sum()), "pf": float(w / l) if l > 0 else None,
            "net_ex_top3_bp": float(srt[3:].sum()), "win_rate": float((net > 0).mean()),
            "n_distinct_leader_triggers": int(trig_id.nunique()), "n_clusters": int(len(cs)),
            "cluster_t": float(cs.mean() / cs.std(ddof=1) * np.sqrt(len(cs))) if len(cs) > 2 else None,
            "n_days": int(ds.size), "days_positive": int((ds > 0).sum()),
            "per_day_net_bp": {k: round(float(v), 1) for k, v in ds.items()}}


def passes(m):
    return m["n"] >= 50 and m["net_sum_bp"] > 0 and (m["pf"] or 0) > 1.2 and m["net_ex_top3_bp"] > 0


def breakdown(t, by):
    return {k: {"n": int(len(g)), "gross_mean_bp": round(float(g.gross_bp.mean()), 2),
                "net_mean_bp": round(float((g.gross_bp - g.cost_primary_bp).mean()), 2)} for k, g in t.groupby(by)}


def summarize(t):
    return {"primary_1.5x_median": metrics(t), "cost_1x_median": metrics(t, "cost_1x_bp"),
            "cost_1.5x_p90": metrics(t, "cost_p90_bp"), "by_follower": breakdown(t, "follower"),
            "by_leader": breakdown(t, "leader"),
            "gross_only": {"mean_bp": float(t.gross_bp.mean()) if len(t) else None,
                           "median_bp": float(t.gross_bp.median()) if len(t) else None}}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    mode = sys.argv[1]
    cost = costs()
    if mode == "costs":
        print(cost.round(2).to_string()); return
    if mode == "train":
        cfgs = list(CONFIGS.values()); days = TRAIN
    else:
        assert mode == "validation"
        evp = EV / "evidence_memelead_validation.json"
        assert not evp.exists(), "validation already run once"
        cfgs = [CONFIGS[sys.argv[2]]]; days = VALID
    trades, meta = [], []
    for day in days:
        o, m = run_day(day, cfgs, cost); trades += o; meta.append(m)
        print(day, m["leaders"], len(o), flush=True)
    T = pd.DataFrame(trades)
    T.to_parquet(f"data/raw/web/memelead/trades_{mode}.parquet", index=False)
    res = {}
    for cid in [c["id"] for c in cfgs]:
        t = T[T.config == cid] if len(T) else T
        res[cid] = summarize(t)
        res[cid]["passes_bar"] = passes(res[cid]["primary_1.5x_median"]) if res[cid]["primary_1.5x_median"]["n"] else False
    ev = {"hypothesis": "H-MEMELEAD", "split": mode, "days": days, "day_universe": meta,
          "computed_at_utc": datetime.datetime.utcnow().isoformat() + "Z", "is_synthetic": False,
          "modality": "document", "finding_type": "observed",
          "prereg": PRE_PATH, "prereg_sha256": sha(PRE_PATH), "script_sha256": sha(__file__),
          "costs_bp_per_round_trip": cost.round(3).reset_index().to_dict(orient="records"),
          "trades_file": f"data/raw/web/memelead/trades_{mode}.parquet", "results": res}
    p = EV / f"evidence_memelead_{mode}.json"
    json.dump(ev, open(p, "w"), indent=1, default=float)
    print(p)
    for cid, r in res.items():
        m = r["primary_1.5x_median"]
        if m["n"]:
            print(f"{cid:14s} n={m['n']:5d} trig={m['n_distinct_leader_triggers']:4d} cl={m['n_clusters']:4d} gross={m['gross_mean_bp']:7.2f} cost={m['cost_mean_bp']:6.2f} net={m['net_mean_bp']:7.2f} PF={m['pf']:.2f} sum={m['net_sum_bp']:9.1f} ex3={m['net_ex_top3_bp']:9.1f} t={m['cluster_t']} days+={m['days_positive']}/{m['n_days']} pass={r['passes_bar']}")
        else:
            print(cid, "n=0")


if __name__ == "__main__":
    main()
