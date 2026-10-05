"""H-QHOI simulation (real data, is_synthetic=False). Pre-registration: reports/hypotheses/qhoi_preregistration.json.

python scripts/research/qhoi_sim.py train        -> all 12 configs on train, selection, kill test
python scripts/research/qhoi_sim.py validation   -> ONCE, the config named in evidence_qhoi_train.json
Signals use only data at or before T (point in time); prices only for entry/exit.
"""
import json, sys, hashlib, pathlib, datetime
import numpy as np, pandas as pd
from scipy.stats import spearmanr

ROOT = pathlib.Path("data/raw/web/qhoi")
PRE_P = "reports/hypotheses/qhoi_preregistration.json"; PRE = json.load(open(PRE_P))
COINS = PRE["universe"]["coins"]; DAYS = PRE["data"]["sample_days"]
OBS = pathlib.Path("research/observations")
H_MS = 3_600_000; Q_MS = 900_000
DEC_J = [16, 32, 48, 64, 80, 96]


def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


def spreads():
    rows = [json.loads(l) for l in open("data/raw/web/memelead/lighter_spreads_20261005T1021Z.jsonl")]
    d = pd.DataFrame(rows); g = d.groupby("coin")["rt1000_bp"]
    return {c: {"rt1000_median_bp": float(g.median()[c]), "n": int(g.size()[c])} for c in g.median().index}


def split_of(day):
    if day <= "2025-06-30": return "train"
    if day <= "2026-03-31": return "validation"
    raise SystemExit("holdout day refused")


def build_signals():
    """Per coin: DataFrame of grid points T' (ms) with S_open10s, S_all; plus decision rows."""
    out = {}
    for sym in COINS:
        rows = []
        for day in DAYS:
            p = ROOT / "qh" / f"{sym}_{day}.parquet"
            if not p.exists(): continue
            if sym == "PUMPUSDT" and day < "2025-07-11": continue
            q = pd.read_parquet(p)
            t10 = (q.buy_10 + q.sell_10).to_numpy(); ta = (q.buy_all + q.sell_all).to_numpy()
            oi10 = np.where(t10 > 0, (q.buy_10 - q.sell_10).to_numpy() / np.where(t10 > 0, t10, 1), np.nan)
            oia = np.where(ta > 0, (q.buy_all - q.sell_all).to_numpy() / np.where(ta > 0, ta, 1), np.nan)
            d0 = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
            for j in range(16, 97):
                w10, wa = oi10[j - 16:j], oia[j - 16:j]
                s10 = np.nanmean(w10) if np.isfinite(w10).sum() >= 12 else np.nan
                sa = np.nanmean(wa) if np.isfinite(wa).sum() >= 12 else np.nan
                rows.append((day, d0 + j * Q_MS, j, s10, sa))
        out[sym] = pd.DataFrame(rows, columns=["day", "T", "j", "S_open10s", "S_all_control"]).sort_values("T").reset_index(drop=True)
    return out


def zscore(df, col):
    T = df["T"].to_numpy(); S = df[col].to_numpy(); z = np.full(len(df), np.nan); npool = np.zeros(len(df), int)
    for i in range(len(df)):
        m = (T < T[i]) & (T >= T[i] - 30 * 86_400_000) & np.isfinite(S)
        npool[i] = m.sum()
        if npool[i] >= 100 and np.isfinite(S[i]):
            sd = S[m].std(ddof=1)
            if sd > 0: z[i] = (S[i] - S[m].mean()) / sd
    return z, npool


def decisions():
    sig = build_signals(); allrows = []
    for sym, df in sig.items():
        if df.empty: continue
        for arm in ("open10s", "all_control"):
            df["z_" + arm], df["pool_" + arm] = zscore(df, "S_" + arm)
        k = pd.read_parquet(ROOT / "klines1h" / f"{sym}.parquet"); px = dict(zip(k.open_time.astype(np.int64), k.open))
        f = pd.read_parquet(ROOT / "funding" / f"{sym}.parquet"); ft = f.calc_time.to_numpy(np.int64); fr = f.rate.to_numpy()
        dec = df[df.j.isin(DEC_J)].copy(); dec["sym"] = sym
        for H in (4, 8, 12):
            e = dec["T"].map(px); x = (dec["T"] + H * H_MS).map(px)
            dec[f"ret_{H}"] = (x / e - 1) * 1e4
            dec[f"fund_{H}"] = [fr[(ft > t) & (ft <= t + H * H_MS)].sum() * 1e4 for t in dec["T"]]
        allrows.append(dec)
    d = pd.concat(allrows, ignore_index=True); d["split"] = d.day.map(split_of)
    return d


def trades(d, arm, k, H, costs):
    out = []
    for sym, g in d.sort_values("T").groupby("sym"):
        busy_until = -1
        for r in g.itertuples():
            z = getattr(r, "z_" + arm); ret = getattr(r, f"ret_{H}")
            if not np.isfinite(z) or abs(z) < k or not np.isfinite(ret): continue
            if r.T < busy_until: continue
            busy_until = r.T + H * H_MS
            dr = 1 if z > 0 else -1
            fund = dr * getattr(r, f"fund_{H}")
            c = costs[sym.replace("USDT", "")]
            g_bp = dr * ret
            out.append(dict(sym=sym, day=r.day, T=int(r.T), split=r.split, z=z, dir=dr, gross_bp=g_bp, funding_bp=fund,
                            spread_cost_bp=1.5 * c, net_bp=g_bp - 1.5 * c - fund, net_1x_bp=g_bp - c - fund,
                            net_binance10_bp=g_bp - 10.0 - fund))
    return pd.DataFrame(out)


def metrics(t, col="net_bp"):
    if t.empty: return {"n": 0}
    n = t[col].to_numpy(); pos, neg = n[n > 0].sum(), -n[n < 0].sum()
    by_day = t.groupby("day")[col].sum()
    tt = by_day.mean() / by_day.std(ddof=1) * np.sqrt(len(by_day)) if len(by_day) > 1 and by_day.std(ddof=1) > 0 else None
    return {"n": int(len(t)), "mean_gross_bp": round(float(t.gross_bp.mean()), 2), "mean_funding_bp": round(float(t.funding_bp.mean()), 2),
            "mean_cost_bp": round(float((t.gross_bp - t[col]).mean()), 2), "mean_net_bp": round(float(n.mean()), 3),
            "sum_net_bp": round(float(n.sum()), 1), "pf": round(float(pos / neg), 3) if neg > 0 else None,
            "net_sum_ex_top3_bp": round(float(np.sort(n)[:-3].sum()), 1) if len(n) > 3 else None,
            "win_rate": round(float((n > 0).mean()), 3), "days": int(len(by_day)), "days_pos": int((by_day > 0).sum()),
            "day_cluster_t": round(float(tt), 2) if tt is not None else None, "longs": int((t.dir > 0).sum())}


def bar(m):
    return bool(m.get("n", 0) >= 50 and m["mean_net_bp"] > 0 and (m["pf"] or 0) > 1.2 and (m["net_sum_ex_top3_bp"] or -1) > 0)


def ic(d, arm, H):
    x = d[["z_" + arm, f"ret_{H}"]].dropna()
    r = spearmanr(x.iloc[:, 0], x.iloc[:, 1]).correlation if len(x) > 10 else None
    return {"n": int(len(x)), "spearman_ic": round(float(r), 4) if r is not None else None}


def common(costs):
    return {"computed_at_utc": datetime.datetime.utcnow().isoformat() + "Z", "is_synthetic": False, "modality": "document",
            "finding_type": "observed", "prereg": PRE_P, "prereg_sha256": sha(PRE_P), "script_sha256": sha(__file__),
            "costs_lighter_rt1000": costs, "data_manifest": "data/raw/web/qhoi/manifest.jsonl"}


if __name__ == "__main__":
    stage = sys.argv[1]
    costs = {c: v["rt1000_median_bp"] for c, v in spreads().items()}
    d = decisions()
    if stage == "train":
        tr = d[d.split == "train"]
        res, alltr = [], []
        for arm in ("open10s", "all_control"):
            for k in (1.0, 2.0):
                for H in (4, 8, 12):
                    t = trades(tr, arm, k, H, costs); name = f"{arm}_k{int(k)}_H{H}"
                    m = metrics(t); res.append({"config": name, "arm": arm, "k": k, "H": H, **m, "passes_bar": bar(m),
                                                "net_1x_spread": metrics(t, "net_1x_bp").get("mean_net_bp"),
                                                "net_binance10": metrics(t, "net_binance10_bp").get("mean_net_bp"),
                                                "pf_binance10": metrics(t, "net_binance10_bp").get("pf"),
                                                "by_coin_mean_net": t.groupby("sym").net_bp.agg(["size", "mean"]).round(2).reset_index().to_dict("records") if len(t) else []})
                    if len(t): t["config"] = name; alltr.append(t)
        passers = [r for r in res if r["passes_bar"]]
        if passers:
            sel = sorted(passers, key=lambda r: (-r["pf"], -r["n"]))[0]; mode = "selected_passing"
        else:
            el = [r for r in res if r.get("n", 0) >= 50 and r.get("pf") is not None]
            sel = sorted(el, key=lambda r: (-r["pf"], -r["n"]))[0] if el else None; mode = "info_only_no_train_pass"
        ics = {f"{arm}_H{H}": ic(tr, arm, H) for arm in ("open10s", "all_control") for H in (4, 8, 12)}
        k1h4 = next(r for r in res if r["config"] == "open10s_k1_H4")
        kill = {"ic_open_gt_control_all_H": all((ics[f"open10s_H{H}"]["spearman_ic"] or -9) > (ics[f"all_control_H{H}"]["spearman_ic"] or -9) for H in (4, 8, 12)),
                "open10s_k1_H4_gross_bp": k1h4.get("mean_gross_bp"), "open10s_k1_H4_cost_bp": k1h4.get("mean_cost_bp"),
                "gross_ge_2x_cost": bool(k1h4.get("n", 0) and k1h4["mean_gross_bp"] >= 2 * k1h4["mean_cost_bp"])}
        kill["passes"] = bool(kill["ic_open_gt_control_all_H"] and kill["gross_ge_2x_cost"])
        days = sorted(tr.day.unique())
        ev = {"hypothesis": "H-QHOI", "split": "train", "days": days, "n_decisions": int(len(tr)),
              "decisions_with_z": {a: int(tr["z_" + a].notna().sum()) for a in ("open10s", "all_control")},
              "configs": res, "selection": {"mode": mode, "config": sel["config"] if sel else None}, "ic": ics, "kill_test": kill, **common(costs)}
        json.dump(ev, open(OBS / "evidence_qhoi_train.json", "w"), indent=1, default=float)
        if alltr: pd.concat(alltr).to_parquet(ROOT / "trades_train.parquet", index=False)
        print(json.dumps({"selection": ev["selection"], "kill": kill, "ic": ics}, indent=1))
        for r in res: print(r["config"], {k: r.get(k) for k in ("n", "mean_gross_bp", "mean_cost_bp", "mean_net_bp", "pf", "net_sum_ex_top3_bp", "days_pos", "days", "day_cluster_t", "net_binance10", "passes_bar")})
    elif stage == "validation":
        vp = OBS / "evidence_qhoi_validation.json"
        if vp.exists(): raise SystemExit("validation already run once")
        trn = json.load(open(OBS / "evidence_qhoi_train.json")); name = trn["selection"]["config"]
        arm, rest = name.rsplit("_k", 1); k, H = rest.split("_H"); k, H = float(k), int(H)
        va = d[d.split == "validation"]
        t = trades(va, arm, k, H, costs); m = metrics(t)
        ev = {"hypothesis": "H-QHOI", "split": "validation", "run_once": True, "config": name, "selection_mode": trn["selection"]["mode"],
              "days": sorted(va.day.unique()), **m, "passes_bar": bar(m),
              "net_1x_spread": metrics(t, "net_1x_bp"), "binance10_variant": metrics(t, "net_binance10_bp"),
              "ic_selected_arm_H": ic(va, arm, H),
              "by_coin_mean_net": t.groupby("sym").net_bp.agg(["size", "mean"]).round(2).reset_index().to_dict("records") if len(t) else [],
              **common(costs)}
        json.dump(ev, open(vp, "w"), indent=1, default=float)
        t.to_parquet(ROOT / "trades_validation.parquet", index=False)
        print(json.dumps(ev, indent=1, default=float)[:3000])
