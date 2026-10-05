"""Weekly TS / XS momentum backtest on Binance USDT-M perps per
reports/hypotheses/momentum_preregistration.json.

usage: python scripts/research/momentum_sim.py train|validation [CONFIG ...] [--slipx 2]
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/web/momentum"
PRE = json.load(open(ROOT / "reports/hypotheses/momentum_preregistration.json"))
CFG = {c["key"]: c for c in PRE["configs"]}
N_UNIV, SIG_T, TAKER = 40, 0.50, 0.0005
EXCL = {"BTCDOMUSDT", "DEFIUSDT", "FOOTBALLUSDT", "BLUEBIRDUSDT", "USDCUSDT"}
STABLE_BASES = ("TUSD", "BUSD", "FDUSD", "USDP", "USDE")
SPLITS = {"train": (None, pd.Timestamp("2024-07-01")),            # [start, end) of positions
          "validation": (pd.Timestamp("2024-07-01"), pd.Timestamp("2026-04-01"))}


def _read_merged(kind, sym, dirs):
    parts = [pd.read_parquet(d / kind / f"{sym}.parquet") for d in dirs if (d / kind / f"{sym}.parquet").exists()]
    return pd.concat(parts, ignore_index=True) if parts else None


def load(extra=(), last_day="2026-03-31"):
    """extra: further data roots (same layout as RAW) merged after RAW, e.g. the holdout or forward cache.
    Defaults reproduce the train/validation data exactly."""
    dirs = [RAW, *extra]
    syms = sorted({f.stem for d in dirs for f in (d / "klines").glob("*.parquet")})
    cl, qv = {}, {}
    for s in syms:
        if s in EXCL or s[:-4] in STABLE_BASES:
            continue
        d = _read_merged("klines", s, dirs)
        idx = pd.to_datetime(d.open_time, unit="ms").dt.normalize()
        d.index = idx
        d = d[~d.index.duplicated()]
        cl[s] = d.close; qv[s] = d.quote_volume
    C = pd.DataFrame(cl).sort_index(); Q = pd.DataFrame(qv).reindex(C.index)
    C = C[C.index <= pd.Timestamp(last_day)]; Q = Q.reindex(C.index)
    fund = {}
    for s in C.columns:
        d = _read_merged("funding", s, dirs)
        if d is not None:
            d = d.drop_duplicates("calc_time")
            t = pd.to_datetime(d.calc_time, unit="ms").dt.round("h")
            fund[s] = pd.Series(d.last_funding_rate.values, index=t).groupby(level=0).last()
    return C, Q, fund


def slip(advq):
    return np.where(advq >= 1e9, 2e-4, np.where(advq >= 2e8, 5e-4, np.where(advq >= 5e7, 10e-4, 20e-4)))


def run(cfg, split, C, Q, fund, slipx=1.0, delay=0):
    """delay (diagnostic only): fill `delay` days after the signal close; holding window shifted the same."""
    L, skip, fam, lo = cfg["L_days"], cfg["skip_days"], cfg["family"], cfg["side"] == "long_only"
    start, end = SPLITS[split]
    n_bars = C.notna().cumsum()
    pres30 = C.notna().rolling(30, min_periods=1).sum()
    vol30 = Q.fillna(0).rolling(30, min_periods=1).sum()
    lr = np.log(C).diff()
    sig = lr.rolling(30, min_periods=20).std() * np.sqrt(365)
    # last valid close (for delisting exits)
    mondays = [d for d in C.index if d.weekday() == 0]
    # first Monday with >= 40 eligible
    ts_list = []
    for t in mondays:
        dprev = t - pd.Timedelta(days=1)
        if dprev not in C.index:
            continue
        elig = (n_bars.loc[dprev] >= 60) & C.loc[dprev].notna() & (pres30.loc[dprev] >= 25)
        ts_list.append((t, elig))
    first = next(t for t, e in ts_list if e.sum() >= N_UNIV)
    lo_t = max(first, start) if start is not None else first
    weeks = [(t, e) for t, e in ts_list if lo_t <= t < end]
    w_old = pd.Series(dtype=float)
    open_ep = {}   # sym -> episode dict
    episodes, weekly = [], []
    for wi, (t, elig) in enumerate(weeks):
        dprev = t - pd.Timedelta(days=1)
        univ = vol30.loc[dprev][elig].sort_values(ascending=False).index[:N_UNIV]
        dsig = dprev - pd.Timedelta(days=skip)
        p1 = C.loc[dsig, univ]; p0 = C.shift(L).loc[dsig, univ] if False else C.loc[dsig - pd.Timedelta(days=L), univ] if (dsig - pd.Timedelta(days=L)) in C.index else p1 * np.nan
        R = (p1 / p0 - 1).dropna()
        if fam == "ts":
            side = np.sign(R)
            if lo:
                side = side.clip(lower=0)
            scale = (SIG_T / sig.loc[dprev, R.index]).clip(upper=1).fillna(0)
            w = side * scale / N_UNIV
        elif fam == "bench":   # diagnostic only (not a pre-registered config): equal-weight long the universe
            w = pd.Series(1.0 / len(R), index=R.index)
        else:
            k = len(univ) // 5
            r = R.sort_values()
            w = pd.Series(0.0, index=R.index)
            if lo:
                w[r.index[-k:]] = 1.0 / k
            else:
                w[r.index[-k:]] = 0.5 / k; w[r.index[:k]] = -0.5 / k
        w = w[w != 0]
        tend = min(t + pd.Timedelta(days=7), end)
        dexit = tend - pd.Timedelta(days=1)
        # costs at rebalance
        allsym = w.index.union(w_old.index)
        advq = (vol30.loc[dprev, allsym] / 30).fillna(0)
        cps = TAKER + slip(advq.values) * slipx
        cps = pd.Series(cps, index=allsym)
        wn = w.reindex(allsym).fillna(0); wo = w_old.reindex(allsym).fillna(0)
        cost_week = 0.0
        for s in allsym:
            a, b = wo[s], wn[s]
            if a != 0 and (b == 0 or np.sign(a) != np.sign(b)):
                c = abs(a) * cps[s]; open_ep[s]["cost"] += c; cost_week += c
                episodes.append(open_ep.pop(s))
                a = 0.0
            if b != 0:
                if a == 0:
                    open_ep[s] = dict(sym=s, side=int(np.sign(b)), start=t, end=None, ret=0.0, fund=0.0, cost=0.0, weeks=0, delist=False)
                c = abs(b - a) * cps[s]; open_ep[s]["cost"] += c; cost_week += c
        # hold
        pnl_week, fund_week, longp, shortp = 0.0, 0.0, 0.0, 0.0
        for s, ws in w.items():
            ep = open_ep[s]
            dd_ = pd.Timedelta(days=delay)
            seg = C.loc[dprev + dd_:min(dexit + dd_, end - pd.Timedelta(days=1)), s]
            last = seg.last_valid_index()
            r = seg.loc[last] / seg.iloc[0] - 1
            pr = ws * r
            if last < min(dexit + dd_, end - pd.Timedelta(days=1)):   # data ended: delisting exit
                pr -= abs(ws) * 0.02; ep["delist"] = True
            fs = fund.get(s)
            fr = 0.0
            if fs is not None:
                fr = fs[(fs.index > t + dd_) & (fs.index <= min(tend + dd_, end, last + pd.Timedelta(days=1)))].sum() * ws
            ep["ret"] += pr; ep["fund"] += fr; ep["weeks"] += 1; ep["end"] = tend
            pnl_week += pr - fr; fund_week += fr
            if ws > 0: longp += pr - fr
            else: shortp += pr - fr
            if ep["delist"]:
                episodes.append(open_ep.pop(s)); w = w.drop(s)
        weekly.append(dict(t=t, pnl=pnl_week - cost_week, gross=pnl_week + fund_week, fund=fund_week, cost=cost_week,
                           turnover=float((wn - wo).abs().sum()), n_pos=int((wn != 0).sum()), long=longp, short=shortp,
                           univ_n=len(univ)))
        w_old = w
    # force-close at split end
    advq = (vol30.iloc[vol30.index.get_indexer([end - pd.Timedelta(days=1)], method="ffill")[0]] / 30)
    for s, ep in list(open_ep.items()):
        c = abs(w_old.get(s, 0)) * (TAKER + float(slip(np.array([advq.get(s, 0)]))[0]) * slipx)
        ep["cost"] += c; weekly[-1]["pnl"] -= c; weekly[-1]["cost"] += c
        episodes.append(ep)
    E = pd.DataFrame(episodes); E["pnl"] = E.ret - E.fund - E.cost
    return E, pd.DataFrame(weekly)


def stats(E, W):
    p = E.pnl.sort_values(ascending=False)
    wins, losses = p[p > 0].sum(), -p[p < 0].sum()
    eq = W.pnl.cumsum(); dd = (eq - eq.cummax()).min()
    bycoin = E.groupby("sym").pnl.sum().sort_values(ascending=False)
    net = p.sum()
    yr = W.groupby(W.t.dt.year).pnl.sum().round(4).to_dict()
    out = dict(n=int(len(p)), net=round(net, 4), pf=round(wins / losses, 3) if losses > 0 else None,
               net_minus_top3=round(p.iloc[3:].sum(), 4), top3=[round(x, 4) for x in p.iloc[:3]],
               sharpe=round(W.pnl.mean() / W.pnl.std() * np.sqrt(52), 3), maxdd=round(dd, 4),
               weeks=len(W), mean_weekly_turnover=round(W.turnover.mean(), 3),
               gross_price=round(W.gross.sum(), 4), funding_paid=round(W.fund.sum(), 4), costs=round(W.cost.sum(), 4),
               long_leg=round(W.long.sum(), 4), short_leg=round(W.short.sum(), 4),
               per_year=yr, top3_coin_share=round(bycoin.iloc[:3].sum() / net, 3) if net > 0 else None,
               top3_coins=bycoin.iloc[:3].round(4).to_dict(), worst3_coins=bycoin.iloc[-3:].round(4).to_dict(),
               delist_exits=int(E.delist.sum()), median_episode_weeks=float(E.weeks.median()),
               first_week=str(W.t.min().date()), last_week=str(W.t.max().date()))
    out["pass"] = bool(out["n"] >= 50 and net > 0 and (out["pf"] or 0) > 1.2 and out["net_minus_top3"] > 0)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    slipx = 1.0
    if "--slipx" in args:
        i = args.index("--slipx"); slipx = float(args[i + 1]); del args[i:i + 2]
    split, keys = args[0], args[1:] or list(CFG)
    assert split in SPLITS
    C, Q, fund = load()
    res = {}
    for k in keys:
        E, W = run(CFG[k], split, C, Q, fund, slipx)
        res[k] = stats(E, W)
        print(k, {x: res[k][x] for x in ["n", "net", "pf", "net_minus_top3", "sharpe", "maxdd", "pass"]}, flush=True)
        E.to_parquet(RAW / f"episodes_{split}_{k}_sx{slipx}.parquet")
        W.to_parquet(RAW / f"weekly_{split}_{k}_sx{slipx}.parquet")
    tag = "" if slipx == 1.0 else f"_slipx{slipx:g}"
    json.dump(dict(split=split, slipx=slipx, preregistration="reports/hypotheses/momentum_preregistration.json", results=res),
              open(ROOT / f"research/observations/evidence_momentum_{split}{tag}.json", "w"), indent=1, default=str)
