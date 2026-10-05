"""H-MEMEXS weekly cross-sectional backtest on Binance USDT-M MEMECOIN perps, per
reports/hypotheses/memexs_preregistration.json (frozen before any return was computed).

usage: python scripts/research/memexs_sim.py train            # all 12 configs on train
       python scripts/research/memexs_sim.py validation KEY   # the one selected config, run once
       python scripts/research/memexs_sim.py diag SPLIT KEY   # diagnostics (not used for selection)
Reads data/raw/web/momentum/{klines,funding} read-only (months <= 2026-03). Never reads the holdout cache.
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/web/momentum"
OUT = ROOT / "data/raw/web/memexs"
PRE = json.load(open(ROOT / "reports/hypotheses/memexs_preregistration.json"))
CFG = {c["key"]: c for c in PRE["configs"]}
MEMES = PRE["universe_classification"]["meme_symbols"]
DOUBT = {"GHSTUSDT", "ORDIUSDT", "MUSDT", "BUSDT", "PEOPLEUSDT", "AIXBTUSDT", "AI16ZUSDT", "GRIFFAINUSDT", "ZEREBROUSDT"}
TAKER, MIN_ADV, MIN_N, MIN_BARS = 0.0005, 5e6, 8, 35
SPLITS = {"train": (None, pd.Timestamp("2025-07-01")),
          "validation": (pd.Timestamp("2025-07-01"), pd.Timestamp("2026-04-01"))}
LAST_DAY = pd.Timestamp("2026-03-31")


def load():
    cl, qv, fund = {}, {}, {}
    for s in MEMES:
        p = RAW / "klines" / f"{s}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        d.index = pd.to_datetime(d.open_time, unit="ms").dt.normalize()
        d = d[~d.index.duplicated()]
        cl[s], qv[s] = d.close, d.quote_volume
        pf = RAW / "funding" / f"{s}.parquet"
        if pf.exists():
            f = pd.read_parquet(pf).drop_duplicates("calc_time")
            t = pd.to_datetime(f.calc_time, unit="ms").dt.round("h")
            fund[s] = pd.Series(f.last_funding_rate.values, index=t).groupby(level=0).last().sort_index()
    C = pd.DataFrame(cl).sort_index()
    C = C[C.index <= LAST_DAY]
    full = pd.date_range(C.index.min(), C.index.max(), freq="D")
    C = C.reindex(full); Q = pd.DataFrame(qv).reindex(full)
    return C, Q, fund


def slip(advq):
    return np.where(advq >= 1e9, 2e-4, np.where(advq >= 2e8, 5e-4, np.where(advq >= 5e7, 10e-4, 20e-4)))


def run(cfg, split, C, Q, fund, taker=TAKER, slipx=1.0, use_funding=True, exclude=()):
    start, end = SPLITS[split]
    cols = [c for c in C.columns if c not in exclude]
    C, Q = C[cols], Q[cols]
    nb = C.notna().cumsum(); p30 = C.notna().rolling(30, min_periods=1).sum()
    adv = Q.fillna(0).rolling(30, min_periods=1).sum() / 30
    qv7 = Q.fillna(0).rolling(7, min_periods=1).sum()
    mondays = [d for d in C.index if d.weekday() == 0 and (start is None or d >= start) and d < end]
    legs, weekly, w_old, last_leg, skipped = [], [], pd.Series(dtype=float), {}, 0
    started = False
    for t in mondays:
        dp = t - pd.Timedelta(days=1)
        if dp not in C.index:
            continue
        elig = (nb.loc[dp] >= MIN_BARS) & C.loc[dp].notna() & (p30.loc[dp] >= 25) & (adv.loc[dp] >= MIN_ADV)
        u = elig[elig].index
        sig = cfg["signal"]
        if sig in ("R7", "R28"):
            L = 7 if sig == "R7" else 28
            d0 = dp - pd.Timedelta(days=L)
            S = C.loc[dp, u] / C.loc[d0, u] - 1 if d0 in C.index else pd.Series(dtype=float)
        elif sig == "FUND7":
            S = pd.Series({s: fund[s][(fund[s].index >= t - pd.Timedelta(days=7)) & (fund[s].index < t)].sum()
                           for s in u if s in fund and len(fund[s][(fund[s].index >= t - pd.Timedelta(days=7)) & (fund[s].index < t)])})
        else:  # VOLG
            prev = Q.fillna(0).loc[dp - pd.Timedelta(days=34):dp - pd.Timedelta(days=7), u].sum() / 4
            S = qv7.loc[dp, u] / prev.replace(0, np.nan)
        S = S.replace([np.inf, -np.inf], np.nan).dropna()
        n = len(S)
        if n < MIN_N:
            if not started:
                continue
            w = pd.Series(dtype=float); skipped += 1
        else:
            started = True
            k = max(2, n // 5)
            hi_long = cfg["direction"] in ("mom", "high_long")
            r = S.sort_values()
            top = r.index[-k:] if hi_long else r.index[:k]
            bot = r.index[:k] if hi_long else r.index[-k:]
            w = pd.Series(0.0, index=S.index)
            if cfg["portfolio"] == "LS":
                w[top] += 0.5 / k; w[bot] -= 0.5 / k
            else:
                w[top] += 0.5 / k; w -= 0.5 / n
            w = w[w.abs() > 1e-12]
        tend = min(t + pd.Timedelta(days=7), end)
        dexit = tend - pd.Timedelta(days=1)
        allsym = w.index.union(w_old.index)
        cps = pd.Series(taker + slip((adv.loc[dp, allsym]).fillna(0).values) * slipx, index=allsym)
        cost_week = 0.0
        new_legs = {}
        for s, ws in w.items():
            new_legs[s] = dict(sym=s, t=t, w=ws, ret=0.0, fund=0.0, cost=0.0, delist=False)
        for s in allsym:
            c = abs(w.get(s, 0.0) - w_old.get(s, 0.0)) * cps[s]
            cost_week += c
            if s in new_legs:
                new_legs[s]["cost"] += c
            else:
                legs[last_leg[s]]["cost"] += c
        pw = fw = lp = sp = 0.0
        drop = []
        for s, ws in w.items():
            lg = new_legs[s]
            seg = C.loc[dp:dexit, s]
            last = seg.last_valid_index()
            pr = ws * (seg.loc[last] / seg.iloc[0] - 1)
            if last < dexit:
                pr -= abs(ws) * 0.02; lg["delist"] = True; drop.append(s)
            fr = 0.0
            if use_funding and s in fund:
                fs = fund[s]
                fr = fs[(fs.index > t) & (fs.index <= min(tend, last + pd.Timedelta(days=1)))].sum() * ws
            lg["ret"], lg["fund"] = pr, fr
            pw += pr - fr; fw += fr
            if ws > 0: lp += pr - fr - lg["cost"]
            else: sp += pr - fr - lg["cost"]
            last_leg[s] = len(legs); legs.append(lg)
        weekly.append(dict(t=t, pnl=pw - cost_week, fund=fw, cost=cost_week, n_elig=n, n_legs=len(w),
                           long=lp, short=sp, turnover=float((w.reindex(allsym).fillna(0) - w_old.reindex(allsym).fillna(0)).abs().sum())))
        w_old = w.drop(drop)
    # force-close at split end
    if len(w_old):
        dl = C.index[C.index < end][-1]
        for s, ws in w_old.items():
            c = abs(ws) * (taker + float(slip(np.array([adv.loc[dl, s] if pd.notna(adv.loc[dl, s]) else 0]))[0]) * slipx)
            legs[last_leg[s]]["cost"] += c; weekly[-1]["pnl"] -= c; weekly[-1]["cost"] += c
            if ws > 0: weekly[-1]["long"] -= c
            else: weekly[-1]["short"] -= c
    E = pd.DataFrame(legs); E["pnl"] = E.ret - E.fund - E.cost
    W = pd.DataFrame(weekly); W.attrs["skipped"] = skipped
    return E, W


def stats(E, W):
    p = E.pnl.sort_values(ascending=False)
    wins, losses = p[p > 0].sum(), -p[p < 0].sum()
    net = float(p.sum())
    Wt = W[W.n_legs > 0]
    eq = W.pnl.cumsum(); dd = float((eq - eq.cummax()).min())
    bycoin = E.groupby("sym").pnl.sum().sort_values(ascending=False)
    out = dict(n=int(len(p)), net=round(net, 4), pf=round(wins / losses, 3) if losses > 0 else None,
               net_minus_top3=round(float(p.iloc[3:].sum()), 4), top3_legs=[round(x, 4) for x in p.iloc[:3]],
               mean_leg_bp=round(net / len(p) * 1e4, 2),
               weekly_sharpe=round(float(Wt.pnl.mean() / Wt.pnl.std() * np.sqrt(52)), 3), weeks_traded=int(len(Wt)),
               weeks_skipped=int(W.attrs.get("skipped", 0)), mean_weekly_pnl_bp=round(float(Wt.pnl.mean()) * 1e4, 1),
               maxdd_additive=round(dd, 4), price_pnl=round(float(E.ret.sum()), 4), funding_paid=round(float(E.fund.sum()), 4),
               costs=round(float(E.cost.sum()), 4), long_legs=round(float(E[E.w > 0].pnl.sum()), 4),
               short_legs=round(float(E[E.w < 0].pnl.sum()), 4), mean_weekly_turnover=round(float(Wt.turnover.mean()), 3),
               mean_eligible=round(float(Wt.n_elig.mean()), 1), delist_exits=int(E.delist.sum()),
               per_year=W.groupby(W.t.dt.year).pnl.sum().round(4).to_dict(),
               per_quarter={str(k): round(v, 4) for k, v in W.groupby(W.t.dt.to_period("Q")).pnl.sum().items()},
               top3_coins=bycoin.iloc[:3].round(4).to_dict(), worst3_coins=bycoin.iloc[-3:].round(4).to_dict(),
               first_week=str(W.t.min().date()), last_week=str(W.t.max().date()))
    out["pass"] = bool(out["n"] >= 50 and net > 0 and (out["pf"] or 0) > 1.2 and out["net_minus_top3"] > 0)
    return out


def show(k, r):
    print(k, {x: r[x] for x in ["n", "net", "pf", "net_minus_top3", "mean_leg_bp", "weekly_sharpe", "weeks_traded", "pass"]},
          "yr", r["per_year"], flush=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    a = sys.argv[1:]
    C, Q, fund = load()
    if a[0] == "train":
        res = {}
        for k in CFG:
            E, W = run(CFG[k], "train", C, Q, fund)
            res[k] = stats(E, W); show(k, res[k])
            E.to_parquet(OUT / f"legs_train_{k}.parquet"); W.to_parquet(OUT / f"weekly_train_{k}.parquet")
        passing = [k for k in res if res[k]["pass"]]
        pool = passing or list(res)
        sel = max(pool, key=lambda k: res[k]["net_minus_top3"])
        print("passing:", passing, "selected:", sel)
        json.dump(dict(split="train", preregistration="reports/hypotheses/memexs_preregistration.json",
                       passing=passing, selected=sel, results=res),
                  open(ROOT / "research/observations/evidence_memexs_train.json", "w"), indent=1, default=str)
    elif a[0] == "validation":
        k = a[1]
        ev = json.load(open(ROOT / "research/observations/evidence_memexs_train.json"))
        assert ev["selected"] == k, "validation must use the config selected on train"
        f = ROOT / "research/observations/evidence_memexs_validation.json"
        assert not f.exists(), "validation already run once"
        E, W = run(CFG[k], "validation", C, Q, fund)
        r = stats(E, W); show(k, r)
        E.to_parquet(OUT / f"legs_validation_{k}.parquet"); W.to_parquet(OUT / f"weekly_validation_{k}.parquet")
        json.dump(dict(split="validation", config=k, result=r), open(f, "w"), indent=1, default=str)
    elif a[0] == "diag":
        split, k = a[1], a[2]
        out = {}
        for name, kw in [("primary", {}), ("lighter_0fee", dict(taker=0.0)), ("slipx2", dict(slipx=2.0)),
                         ("no_funding", dict(use_funding=False)), ("ex_identity_doubtful", dict(exclude=DOUBT))]:
            E, W = run(CFG[k], split, C, Q, fund, **kw)
            out[name] = stats(E, W); show(name, out[name])
        json.dump(dict(split=split, config=k, note="diagnostics, not used for selection", results=out),
                  open(ROOT / f"research/observations/evidence_memexs_diag_{split}.json", "w"), indent=1, default=str)
