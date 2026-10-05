"""H-NIGHT simulator (rules: reports/hypotheses/night_preregistration.json). Real data, is_synthetic = False.

usage: python scripts/research/night_sim.py train            -> all 12 configs + placebo on train
       python scripts/research/night_sim.py validation <cfg> -> ONE config, once (lock file guards a re-run)
Only Binance bars with open_time < 2026-04-01 exist on disk (holdout never downloaded); asserted below.
"""
import json, sys, pathlib, datetime
import numpy as np, pandas as pd

D = pathlib.Path("data/raw/web/night")
PRE = json.load(open("reports/hypotheses/night_preregistration.json"))
COINS = PRE["universe"]["binance_symbols"]
LNAME = dict(zip(COINS, PRE["universe"]["lighter_names"]))
SPLITS = {"train": ("2022-01-01", "2025-06-30"), "validation": ("2025-07-01", "2026-03-31")}
HOLDOUT = pd.Timestamp("2026-04-01")
BN_RT = 10.0  # bp, Binance taker 5 bp per side, informational


def lighter_costs():
    rows = []
    for f in sorted(D.glob("lighter_spreads_*.jsonl")):
        rows += [json.loads(l) for l in open(f)]
    df = pd.DataFrame(rows)
    df = df[df.get("error").isna()] if "error" in df else df
    g = df.groupby("coin").agg(n=("quoted_bp", "size"), quoted_med=("quoted_bp", "median"),
                               rt1000_med=("rt1000_bp", "median"), rt1000_p90=("rt1000_bp", lambda x: x.quantile(.9)),
                               rt1000_null=("rt1000_bp", lambda x: int(x.isna().sum())))
    g["cost_bp"] = g[["quoted_med", "rt1000_med"]].max(axis=1)
    return g


def load():
    px, fund = {}, {}
    for s in COINS + ["BTCUSDT"]:
        k = pd.read_parquet(D / f"k1h_{s}.parquet")
        k["t"] = pd.to_datetime(k.open_time, unit="ms")
        assert k.t.max() < HOLDOUT, "holdout data on disk"
        start = k.t.min()
        if s == "PUMPUSDT":  # bars before 2025-07-10 are an earlier, different contract (agent_pumppulse.md)
            start = pd.Timestamp("2025-07-10 07:00")
            k = k[k.t >= start]
        k = k.set_index("t")
        px[s] = (k, start + pd.Timedelta(days=7))
        f = pd.read_parquet(D / f"funding_{s}.parquet")
        f["t"] = pd.to_datetime(f.calc_time, unit="ms")
        if s == "PUMPUSDT":
            f = f[f.t >= start]
        f["m"] = f.t.dt.to_period("M")
        fm = f.groupby("m").apply(lambda x: x.last_funding_rate.sum() / x.funding_interval_hours.sum())
        fund[s] = fm  # per-hour mean rate, by calendar month (cost proxy)
    return px, fund


def coin_legs(px, fund, s, h, L, d0, d1):
    k, elig = px[s]
    days = pd.date_range(d0, d1, freq="D")
    t_in = days + pd.Timedelta(hours=h)
    t_out = t_in + pd.Timedelta(hours=L - 1)
    ok = t_in.isin(k.index) & t_out.isin(k.index) & (t_in >= elig)
    t_in, t_out, days = t_in[ok], t_out[ok], days[ok]
    if len(days) == 0:
        return pd.DataFrame()
    g = k.loc[t_out, "close"].values / k.loc[t_in, "open"].values - 1
    fh = fund[s].reindex(t_in.to_period("M")).fillna(0.0).values
    return pd.DataFrame({"day": days, "coin": s, "gross": g * 1e4, "fund_bp": fh * L * 1e4})


def trades(px, fund, cost, h, L, variant, d0, d1):
    legs = pd.concat([coin_legs(px, fund, s, h, L, d0, d1) for s in COINS], ignore_index=True)
    legs["cost_bp"] = legs.coin.map(lambda s: cost[LNAME[s]])
    if variant == "PC":
        t = legs
    else:
        t = legs.groupby("day").agg(gross=("gross", "mean"), fund_bp=("fund_bp", "mean"),
                                    cost_bp=("cost_bp", "mean"), ncoins=("coin", "size")).reset_index()
        t = t[t.ncoins >= 2]
        if variant == "BKH":
            b = coin_legs(px, fund, "BTCUSDT", h, L, d0, d1).set_index("day")
            t = t[t.day.isin(b.index)]
            t["gross"] = t.gross.values - b.loc[t.day, "gross"].values
            t["fund_bp"] = t.fund_bp.values - b.loc[t.day, "fund_bp"].values
            t["cost_bp"] = t.cost_bp.values + cost["BTC"]
    t = t.copy()
    t["net"] = t.gross - t.cost_bp - t.fund_bp
    t["net_stress"] = t.gross - 1.5 * t.cost_bp - t.fund_bp
    t["net_bn"] = t.gross - BN_RT - t.fund_bp
    return t


def stats(t):
    if len(t) == 0:
        return {"n": 0, "pass": False}
    n = t.net.values
    pos, neg = n[n > 0].sum(), -n[n < 0].sum()
    daily = t.groupby("day").net.sum()
    hy = t.day.dt.year.astype(str) + np.where(t.day.dt.month <= 6, "H1", "H2")
    by_hy = {k: {"n": int(len(g)), "gross_bp": round(g.gross.mean(), 2), "net_bp": round(g.net.mean(), 2)}
             for k, g in t.groupby(hy)}
    ex3 = np.sort(n)[:-3].sum() if len(n) > 3 else float("nan")
    r = {"n": int(len(t)), "days": int(daily.size), "gross_bp": round(t.gross.mean(), 3),
         "cost_bp": round(t.cost_bp.mean(), 3), "fund_bp": round(t.fund_bp.mean(), 3),
         "net_bp": round(n.mean(), 3), "net_stress_bp": round(t.net_stress.mean(), 3),
         "net_binance_bp": round(t.net_bn.mean(), 3), "pf": round(pos / neg, 3) if neg else None,
         "net_sum_pct": round(n.sum() / 100, 2), "net_ex_top3_pct": round(ex3 / 100, 2),
         "win_rate": round((n > 0).mean(), 3),
         "daily_t": round(daily.mean() / daily.std(ddof=1) * np.sqrt(daily.size), 2) if daily.size > 2 else None,
         "pos_days": round((daily > 0).mean(), 3), "gross_median_bp": round(float(np.median(t.gross)), 3),
         "by_half_year": by_hy}
    r["pass"] = bool(r["n"] >= 50 and r["net_bp"] > 0 and (r["pf"] or 0) > 1.2 and r["net_ex_top3_pct"] > 0)
    r["stress_net_positive"] = bool(r["net_stress_bp"] > 0)
    return r


def placebo(px, fund, cost, L, variant, d0, d1, arm_h):
    rows = {}
    for h in range(24):
        t = trades(px, fund, cost, h, L, variant, d0, d1)
        rows[h] = {"gross_bp": round(t.gross.mean(), 3), "net_bp": round(t.net.mean(), 3), "n": int(len(t)),
                   "daily_t_gross": round(t.groupby("day").gross.sum().pipe(lambda d: d.mean() / d.std() * np.sqrt(d.size)), 2)}
    g = pd.Series({h: v["gross_bp"] for h, v in rows.items()})
    nt = pd.Series({h: v["net_bp"] for h, v in rows.items()})
    other = g.drop(arm_h)
    return {"by_entry_hour": rows, "arm_rank_gross_of24": int(g.rank(ascending=False)[arm_h]),
            "arm_rank_net_of24": int(nt.rank(ascending=False)[arm_h]),
            "other_hours_mean_gross_bp": round(other.mean(), 3), "other_hours_sd_gross_bp": round(other.std(), 3),
            "arm_minus_other_mean_bp": round(g[arm_h] - other.mean(), 3),
            "arm_z_vs_other_hours": round((g[arm_h] - other.mean()) / other.std(), 2),
            "label": "seasonal" if g.rank(ascending=False)[arm_h] <= 3 else "beta/noise"}


def main():
    split = sys.argv[1]
    d0, d1 = SPLITS[split]
    cg = lighter_costs()
    cost = cg.cost_bp.to_dict()
    px, fund = load()
    grid = PRE["grid"]
    if split == "validation":
        lock = D / "VALIDATION_RUN.lock"
        assert not lock.exists(), "validation already run once"
        grid = [c for c in grid if c["id"] == sys.argv[2]]
        lock.write_text(f"{sys.argv[2]} {datetime.datetime.utcnow().isoformat()}Z\n")
    res, tr_all = {}, {}
    for c in grid:
        h, L, v = c["entry_hour_utc"], c["hours"], c["variant"]
        t = trades(px, fund, cost, h, L, v, d0, d1)
        r = stats(t)
        r["placebo"] = placebo(px, fund, cost, L, v, d0, d1, h)
        if v == "PC":
            r["by_coin"] = {s: {"n": int(len(g)), "gross_bp": round(g.gross.mean(), 2), "net_bp": round(g.net.mean(), 2)}
                            for s, g in t.groupby("coin")}
            r["weekend_info"] = {k: round(g.gross.mean(), 2) for k, g in t.groupby(t.day.dt.dayofweek >= 5)}
        res[c["id"]] = r
        t.to_parquet(D / f"trades_{split}_{c['id']}.parquet", index=False)
        print(c["id"], {k: r[k] for k in ("n", "gross_bp", "cost_bp", "fund_bp", "net_bp", "net_stress_bp", "pf",
                                          "net_ex_top3_pct", "daily_t", "pass")},
              "placebo rank", r["placebo"]["arm_rank_gross_of24"], r["placebo"]["label"], flush=True)
    # always-long reference: mean 1h gross across coins (per-coin legs), train/val period
    al = pd.concat([coin_legs(px, fund, s, h, 1, d0, d1) for s in COINS for h in range(24)])
    out = {"hypothesis": "H-NIGHT", "split": split, "dates": [d0, d1], "is_synthetic": False, "modality": "document",
           "source": "data.binance.vision USDT-M 1h klines + fundingRate (2022-01..2026-03); Lighter public orderBookOrders REST sampler 2026-10-05; own computation",
           "preregistration": "reports/hypotheses/night_preregistration.json",
           "lighter_cost_table": json.loads(cg.round(3).to_json(orient="index")),
           "always_long_mean_gross_bp_per_hour_per_coin": round(al.gross.mean(), 3),
           "results": res, "generated_utc": datetime.datetime.utcnow().isoformat() + "Z"}
    tag = split if split == "train" else f"validation_{sys.argv[2]}"
    p = pathlib.Path(f"research/observations/evidence_night_{tag}_20261005.json")
    json.dump(out, open(p, "w"), indent=1)
    print(p)


if __name__ == "__main__":
    main()
