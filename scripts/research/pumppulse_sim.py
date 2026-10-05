"""H-PUMPPULSE simulator (pre-registration: reports/hypotheses/pumppulse_preregistration.json).

    python scripts/research/pumppulse_sim.py train                 # all 12 configs on train
    python scripts/research/pumppulse_sim.py validation <CONFIG>   # run ONCE on the selected config

Point in time: day d's activity is used at 06:00 UTC on d+1 (6 h publication lag). z uses days d-28..d-1 for
mean/std. Basket membership, tiers and funding use only data before the entry time. Holdout guard: activity
and prices at or after 2026-04-01 are dropped at load; no price for that period exists on disk.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/pumppulse"
PRE = json.load(open(ROOT / "reports/hypotheses/pumppulse_preregistration.json"))
BASKET = PRE["universe"]["basket"]
HOLDOUT = pd.Timestamp("2026-04-01")
PUMP_START = pd.Timestamp("2025-07-10")
TAKER = 5.0
LIGHTER = 3.0
SPLITS = {"train": (pd.Timestamp("2024-04-01"), pd.Timestamp("2025-06-30")),
          "validation": (pd.Timestamp("2025-07-01"), pd.Timestamp("2026-03-31"))}
ENTRY_HOUR = 6


def load_activity(series="revenue"):
    if series == "revenue":
        j = json.load(open(D / "fees_pump_dailyRevenue.json"))
        rows = [(pd.Timestamp(t, unit="s"), (x.get("Solana") or {}).get("pump.fun"))
                for t, x in j["totalDataChartBreakdown"]]
    else:  # curve volume, robustness only
        j = json.load(open(D / "dexs_pumpfun.json"))
        rows = [(pd.Timestamp(t, unit="s"), v) for t, v in j["totalDataChart"]]
    s = pd.Series({d: v for d, v in rows}, dtype=float).sort_index()
    s = s[s.index < HOLDOUT]
    s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))
    s[(s <= 0)] = np.nan
    return s


def zscores(a, window=28, minobs=20):
    la = np.log(a)
    c = la.diff()
    out = {}
    for name, x in (("level_z", la), ("change_z", c)):
        m = x.shift(1).rolling(window, min_periods=minobs).mean()
        sd = x.shift(1).rolling(window, min_periods=minobs).std()
        out[name] = (x - m) / sd
    return pd.DataFrame(out)


def load_prices():
    px, fund, daily = {}, {}, {}
    for s in BASKET + ["SOLUSDT"]:
        k = pd.read_parquet(D / "k1h" / f"{s}.parquet")
        k["t"] = pd.to_datetime(k.open_time, unit="ms")
        k = k[k.t < HOLDOUT]
        if s == "PUMPUSDT":
            k = k[k.t >= PUMP_START]
        px[s] = k.set_index("t")["open"]
        f = pd.read_parquet(ROOT / "data/raw/web/momentum/funding" / f"{s}.parquet")
        f["t"] = pd.to_datetime(f.calc_time // 1000, unit="s")
        fund[s] = f.set_index("t")["last_funding_rate"].sort_index()
        dk = pd.read_parquet(ROOT / "data/raw/web/momentum/klines" / f"{s}.parquet")
        dk["d"] = pd.to_datetime(dk.open_time, unit="ms")
        dk = dk[dk.d < HOLDOUT]
        if s == "PUMPUSDT":
            dk = dk[dk.d >= PUMP_START]
        daily[s] = dk.set_index("d")["quote_volume"]
    return px, fund, daily


def slip_bp(qv30):
    if qv30 >= 1e9:
        return 2.0
    if qv30 >= 2e8:
        return 5.0
    if qv30 >= 5e7:
        return 10.0
    return 20.0


class Market:
    def __init__(self):
        self.px, self.fund, self.daily = load_prices()

    def members(self, entry_day):
        out = []
        for s in BASKET:
            dq = self.daily[s]
            prior = dq[(dq.index < entry_day) & (dq > 0)]
            if len(prior) >= 30:
                out.append(s)
        return out

    def qv30(self, s, entry_day):
        dq = self.daily[s]
        w = dq[(dq.index < entry_day) & (dq.index >= entry_day - pd.Timedelta(days=30))]
        return float(w.mean()) if len(w) else 0.0

    def price(self, s, t):
        p = self.px[s]
        return float(p.loc[t]) if t in p.index else None

    def mark(self, s, t):
        p = self.px[s]
        sub = p[p.index <= t]
        return float(sub.iloc[-1]) if len(sub) else None

    def funding(self, s, t0, t1):
        f = self.fund[s]
        return f[(f.index > t0) & (f.index <= t1)]


def run_episode(mk, entry_day, direction, H, hedged, slipx=1.0):
    """direction +1 = long basket (short SOL if hedged). Returns list of daily slices or None."""
    t0 = entry_day + pd.Timedelta(hours=ENTRY_HOUR)
    tH = t0 + pd.Timedelta(days=H)
    mem = [s for s in mk.members(entry_day) if mk.price(s, t0) is not None and mk.price(s, tH) is not None]
    if not mem:
        return None
    legs = [(s, direction / len(mem)) for s in mem]
    if hedged:
        if mk.price("SOLUSDT", t0) is None or mk.price("SOLUSDT", tH) is None:
            return None
        legs.append(("SOLUSDT", -direction * 1.0))
    p0 = {s: mk.price(s, t0) for s, _ in legs}
    marks = [t0 + pd.Timedelta(days=j) for j in range(H + 1)]
    slices = []
    prev = {s: p0[s] for s, _ in legs}
    for j in range(1, H + 1):
        tj = marks[j]
        gross = fund = cost = cost_l = 0.0
        for s, w in legs:
            pj = mk.price(s, tj) if j == H else mk.mark(s, tj)
            gross += w * (pj - prev[s]) / p0[s]
            for ft, r in mk.funding(s, marks[j - 1], tj).items():
                pf = mk.mark(s, ft) or p0[s]
                fund -= w * r * pf / p0[s]  # long (w>0) pays positive rate
            per_side = (TAKER + slipx * slip_bp(mk.qv30(s, entry_day))) / 1e4
            if j == 1:
                cost += abs(w) * per_side
                cost_l += abs(w) * LIGHTER / 1e4
            if j == H:
                cost += abs(w) * pj / p0[s] * per_side
                cost_l += abs(w) * pj / p0[s] * LIGHTER / 1e4
            prev[s] = pj
        slices.append({"day": tj, "gross": gross, "funding": fund, "net": gross + fund - cost,
                       "net_lighter": gross + fund - cost_l, "cost": cost})
    return {"entry": t0, "exit": tH, "dir": direction, "n_members": len(mem), "members": mem, "slices": slices}


def simulate(mk, z, cfg, split, slipx=1.0):
    lo, hi = SPLITS[split]
    k, H, hedged = cfg["k"], cfg["H"], cfg["hedge"] == "SOL"
    zs = z[cfg["signal"]]
    day = lo
    eps = []
    while day <= hi:
        exit_t = day + pd.Timedelta(hours=ENTRY_HOUR) + pd.Timedelta(days=H)
        if exit_t > hi + pd.Timedelta(hours=23, minutes=59):
            break
        zd = zs.get(day - pd.Timedelta(days=1), np.nan)  # latest closed day, published by 06:00
        if np.isfinite(zd) and abs(zd) >= k:
            ep = run_episode(mk, day, 1 if zd > 0 else -1, H, hedged, slipx)
            if ep:
                ep["z"] = float(zd)
                eps.append(ep)
                day = day + pd.Timedelta(days=H)  # flat again at the exit time
                continue
        day += pd.Timedelta(days=1)
    return eps


def stats(x):
    x = np.asarray(x, float)
    if len(x) == 0:
        return {"n": 0}
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    srt = np.sort(x)
    return {"n": int(len(x)), "sum": round(float(x.sum()), 4), "mean_bp": round(float(x.mean() * 1e4), 1),
            "median_bp": round(float(np.median(x) * 1e4), 1),
            "pf": round(float(pos / neg), 3) if neg > 0 else None,
            "sum_ex_top3": round(float(srt[:-3].sum()), 4) if len(x) > 3 else None,
            "win": round(float((x > 0).mean()), 3),
            "t": round(float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))), 2) if len(x) > 2 else None}


def summarize(eps):
    rows = []
    for e in eps:
        for sl in e["slices"]:
            rows.append({**sl, "dir": e["dir"], "entry": e["entry"], "year": sl["day"].year})
    df = pd.DataFrame(rows)
    if df.empty:
        return {"n_episodes": 0}, df
    net = stats(df.net)
    out = {"n_episodes": len(eps), "n_long_eps": sum(e["dir"] > 0 for e in eps),
           "n_short_eps": sum(e["dir"] < 0 for e in eps),
           "net": net, "gross": stats(df.gross), "net_lighter": stats(df.net_lighter),
           "funding_mean_bp": round(df.funding.mean() * 1e4, 2), "cost_sum": round(df.cost.sum(), 4),
           "episode_net": stats([sum(s["net"] for s in e["slices"]) for e in eps]),
           "long": stats(df[df.dir > 0].net), "short": stats(df[df.dir < 0].net),
           "mean_members": round(float(np.mean([e["n_members"] for e in eps])), 2),
           "by_year": {str(y): {"net": stats(g.net), "gross_mean_bp": round(g.gross.mean() * 1e4, 1)}
                       for y, g in df.groupby("year")}}
    out["pass"] = bool(net["n"] >= 50 and net["sum"] > 0 and (net["pf"] or 0) > 1.2
                       and (net["sum_ex_top3"] or -1) > 0)
    return out, df


def diagnostics(mk, z, split):
    """Information only: rank IC of z_d with the next 06:00->06:00 basket-minus-SOL return, and with the
    SAME-day (d 06:00 -> d+1 06:00) return as a reverse-causality check."""
    lo, hi = SPLITS[split]
    rows = []
    for day in pd.date_range(lo, hi - pd.Timedelta(days=1)):
        t0 = day + pd.Timedelta(hours=ENTRY_HOUR)
        t1 = t0 + pd.Timedelta(days=1)
        tm = t0 - pd.Timedelta(days=1)
        mem = [s for s in mk.members(day) if all(mk.price(s, t) for t in (tm, t0, t1))]
        if not mem or not all(mk.price("SOLUSDT", t) for t in (tm, t0, t1)):
            continue
        b_next = np.mean([mk.price(s, t1) / mk.price(s, t0) - 1 for s in mem])
        b_prev = np.mean([mk.price(s, t0) / mk.price(s, tm) - 1 for s in mem])
        sol_n = mk.price("SOLUSDT", t1) / mk.price("SOLUSDT", t0) - 1
        sol_p = mk.price("SOLUSDT", t0) / mk.price("SOLUSDT", tm) - 1
        zd = z.loc[day - pd.Timedelta(days=1)] if (day - pd.Timedelta(days=1)) in z.index else None
        if zd is None:
            continue
        rows.append({"level_z": zd["level_z"], "change_z": zd["change_z"], "next_hedged": b_next - sol_n,
                     "next_basket": b_next, "contemp_hedged": b_prev - sol_p, "contemp_basket": b_prev})
    df = pd.DataFrame(rows).dropna()
    out = {"n_days": len(df)}
    for sig in ("level_z", "change_z"):
        for tgt in ("next_hedged", "next_basket", "contemp_hedged", "contemp_basket"):
            out[f"spearman_{sig}_vs_{tgt}"] = round(float(df[sig].corr(df[tgt], method="spearman")), 3)
    return out


def main():
    mode = sys.argv[1]
    mk = Market()
    a = load_activity("revenue")
    z = zscores(a)
    cfgs = {c["id"]: c for c in PRE["grid"]["configs"]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    if mode == "train":
        res = {}
        for cid, c in cfgs.items():
            eps = simulate(mk, z, c, "train")
            res[cid], df = summarize(eps)
            df.to_parquet(D / f"slices_train_{cid}.parquet", index=False)
            r = res[cid]
            print(cid, r["n_episodes"], r["net"], r["pass"], flush=True)
        passing = [c for c in res if res[c]["pass"]]
        pool = passing or list(res)
        sel = max(pool, key=lambda c: res[c]["net"]["mean_bp"])
        c = cfgs[sel]
        sx2, _ = summarize(simulate(mk, z, c, "train", slipx=2.0))
        mk_vol = load_activity("volume")
        vol = summarize(simulate(mk, zscores(mk_vol), c, "train"))[0] if c["signal"] in ("level_z", "change_z") else None
        ev = {"prereg": "reports/hypotheses/pumppulse_preregistration.json", "split": "train",
              "is_synthetic": False, "modality": "onchain+market (own computation)",
              "activity_coverage": {"first": str(a.first_valid_index().date()), "last": str(a.last_valid_index().date()),
                                    "missing_days": int(a.isna().sum())},
              "configs": res, "passing": passing, "selected": sel,
              "selected_reason": "passes train bar, highest net mean" if passing else "none passed; highest train net mean (validation for information only)",
              "selected_slip_x2": sx2, "selected_curve_volume_series_info_only": vol,
              "diagnostics_info_only": diagnostics(mk, z, "train")}
        json.dump(ev, open(ROOT / f"research/observations/evidence_pumppulse_train_{stamp}.json", "w"), indent=1, default=str)
        print("SELECTED", sel, "passing", passing)
        print(json.dumps(ev["diagnostics_info_only"]))
    elif mode == "validation":
        cid = sys.argv[2]
        flag = D / "VALIDATION_RUN.lock"
        if flag.exists():
            sys.exit("validation already run once: " + flag.read_text())
        flag.write_text(f"{cid} {datetime.now(timezone.utc).isoformat()}")
        c = cfgs[cid]
        eps = simulate(mk, z, c, "validation")
        r, df = summarize(eps)
        df.to_parquet(D / f"slices_validation_{cid}.parquet", index=False)
        ev = {"prereg": "reports/hypotheses/pumppulse_preregistration.json", "split": "validation",
              "is_synthetic": False, "config": cid, "result": r,
              "slip_x2": summarize(simulate(mk, z, c, "validation", slipx=2.0))[0],
              "diagnostics_info_only": diagnostics(mk, z, "validation")}
        json.dump(ev, open(ROOT / f"research/observations/evidence_pumppulse_validation_{stamp}.json", "w"), indent=1, default=str)
        print(json.dumps(r, default=str, indent=1))
        print(json.dumps(ev["diagnostics_info_only"]))


if __name__ == "__main__":
    main()
