"""H-UPBITLEAD simulation (rules frozen in reports/hypotheses/upbitlead_preregistration.json).

usage: python scripts/research/upbitlead_sim.py counts            # trigger counts per config, train (no P&L)
       python scripts/research/upbitlead_sim.py train             # 12 configs on train + informational profiles
       python scripts/research/upbitlead_sim.py validation CFG    # chosen config, once
Point in time: Upbit candle t known at t+60s; Binance entry at the open of bar t+1 (approx. t+60s+2s latency);
'--delay1' enters at the open of bar t+2. Never reads data >= 2026-04-01 (not on disk).
"""
from __future__ import annotations

import json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/upbitlead"
M0 = int(datetime(2025, 3, 24, tzinfo=timezone.utc).timestamp()) // 60
M_END = int(datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp()) // 60
SPLIT = {"train": (int(datetime(2025, 4, 1, tzinfo=timezone.utc).timestamp()) // 60,
                   int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()) // 60),
         "validation": (int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()) // 60, M_END)}
N = M_END - M0
GRID = [(z, r, h) for z in (3.0, 4.5) for r in (0.01, 0.02, 0.04) for h in (5, 30)]
FEE = 5.0
MIN_USD = 10_000.0


def cname(z, r, h):
    return f"Z{z}_R{r}_H{h}"


def tier(qv):  # per side bp by trailing-7d mean daily quote volume; nan => not traded
    return np.select([qv >= 100e6, qv >= 30e6, qv >= 10e6, qv >= 1e6], [10.0, 15.0, 20.0, 25.0], np.nan)


def full(df, cols, fill):
    out = {}
    idx = df.minute.values - M0
    ok = (idx >= 0) & (idx < N)
    for c in cols:
        a = np.full(N, np.nan)
        a[idx[ok]] = df[c].values[ok]
        out[c] = a
    return out


def load_krw():
    u = pd.read_parquet(D / "upbit/USDT.parquet")
    k = full(u, ["c"], None)["c"]
    return pd.Series(k).ffill().bfill().values


def load_coin(coin, sym, K):
    u = pd.read_parquet(D / f"upbit/{coin}.parquet")
    b = pd.read_parquet(D / f"binance/{sym}.parquet")
    f = pd.read_parquet(D / f"funding/{sym}.parquet")
    U = full(u, ["c", "krw"], None)
    first = int(np.nanargmax(~np.isnan(U["c"])))
    pc = pd.Series(U["c"]).ffill().values
    usd = np.nan_to_num(U["krw"]) / K
    usd[:first] = np.nan
    pu = pc / K  # USD price
    ret = np.full(N, np.nan); ret[1:] = pu[1:] / pu[:-1] - 1
    L = pd.Series(np.log1p(usd))
    mu = L.rolling(1440, min_periods=1440).mean().shift(1).values
    sd = L.rolling(1440, min_periods=1440).std().shift(1).values
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (L.values - mu) / sd
    z[~(sd > 0)] = np.nan
    B = full(b, ["o", "h", "l", "c", "qv"], None)
    # daily volumes and trailing-7d filters (days d-7..d-1)
    day = (np.arange(N) // 1440)
    nd = day.max() + 1
    up_d = np.bincount(day, weights=np.nan_to_num(usd), minlength=nd)
    bn_d = np.bincount(day, weights=np.nan_to_num(B["qv"]), minlength=nd)
    up7 = pd.Series(up_d).rolling(7).sum().shift(1).values
    bn7 = pd.Series(bn_d).rolling(7).sum().shift(1).values
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio7 = up7 / bn7
    slip_d = tier(bn7 / 7)
    elig_d = (ratio7 >= 0.2) & ~np.isnan(slip_d)
    # Binance burst stats (reverse check)
    Lb = pd.Series(np.log1p(np.nan_to_num(B["qv"])))
    mub = Lb.rolling(1440, min_periods=1440).mean().shift(1).values
    sdb = Lb.rolling(1440, min_periods=1440).std().shift(1).values
    with np.errstate(invalid="ignore", divide="ignore"):
        zb = (Lb.values - mub) / sdb
    bc = pd.Series(B["c"]).ffill().values
    rb = np.full(N, np.nan); rb[1:] = bc[1:] / bc[:-1] - 1
    fund = f.copy(); fund["m"] = (fund.t // 60000).astype(int) - M0
    return dict(usd=usd, ret=ret, z=z, pu=pu, B=B, bc=bc, rb=rb, zb=zb, slip=slip_d[day], elig=elig_d[day],
                fund=fund[(fund.m >= 0) & (fund.m < N)][["m", "rate"]].values)


def triggers(c, Z, R, lo, hi):
    with np.errstate(invalid="ignore"):
        m = (c["z"] >= Z) & (np.abs(c["ret"]) >= R) & (c["usd"] >= MIN_USD) & c["elig"]
    idx = np.nonzero(m)[0]
    return idx[(idx + M0 >= lo) & (idx + M0 < hi)]


def sim(c, idx, R, H, delay=1, slipx=1.0, fee=FEE, gap=False):
    B = c["B"]; o, h, l = B["o"], B["h"], B["l"]
    trades, busy_until, skipped = [], -1, 0
    for t in idx:
        if t <= busy_until:
            continue
        s = 1.0 if c["ret"][t] > 0 else -1.0
        if gap:
            rbt = c["rb"][t]
            if not (np.isfinite(rbt) and s * rbt < R / 2):
                continue
        e = t + delay
        if e + H >= N or not np.isfinite(o[e]):
            skipped += 1; continue
        px = o[e]; tp = px * (1 + s * 2 * R); sl = px * (1 - s * R)
        xp, xm, why = None, None, "time"
        for j in range(e, e + H):
            if not np.isfinite(o[j]):
                continue
            hit_sl = (l[j] <= sl) if s > 0 else (h[j] >= sl)
            hit_tp = (h[j] >= tp) if s > 0 else (l[j] <= tp)
            if hit_sl:
                xp = min(o[j], sl) if s > 0 else max(o[j], sl); xm, why = j, "sl"; break
            if hit_tp:
                xp = max(o[j], tp) if s > 0 else min(o[j], tp); xm, why = j, "tp"; break
        if xp is None:
            j = e + H
            while j < N and not np.isfinite(o[j]) and j < e + H + 5:
                j += 1
            if j >= N or not np.isfinite(o[j]):
                skipped += 1; continue
            xp, xm = o[j], j
        gross = s * (xp / px - 1) * 1e4
        sp = c["slip"][t] * slipx
        cost = 2 * (fee + sp)
        fr = c["fund"]; fsel = (fr[:, 0] > e) & (fr[:, 0] <= xm) if len(fr) else np.array([], bool)
        fund = float(s * fr[fsel, 1].sum() * 1e4) if len(fr) else 0.0
        trades.append(dict(minute=int(t + M0), dir=int(s), gross_bp=gross, cost_bp=cost, fund_bp=fund,
                           net_bp=gross - cost - fund, exit=why, hold=int(xm - e), slip_bp=sp,
                           up_ret=float(c["ret"][t]), bn_same=float(c["rb"][t]) if np.isfinite(c["rb"][t]) else None))
        busy_until = xm
    return trades, skipped


def stats(tr):
    if not tr:
        return dict(n=0, net=0.0, pf=None, net_ex_top3=0.0, passes=False)
    x = np.array([t["net_bp"] for t in tr]); g = np.array([t["gross_bp"] for t in tr])
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    pf = float(pos / neg) if neg > 0 else float("inf")
    ex = float(np.sort(x)[:-3].sum()) if len(x) > 3 else float("nan")
    return dict(n=len(x), net=float(x.sum()), mean_net=float(x.mean()), mean_gross=float(g.mean()),
                median_gross=float(np.median(g)), mean_cost=float(np.mean([t["cost_bp"] for t in tr])),
                win=float((x > 0).mean()), pf=pf, net_ex_top3=ex,
                passes=bool(len(x) >= 50 and x.sum() > 0 and pf > 1.2 and ex > 0))


def main():
    mode = sys.argv[1]
    sel = json.loads((D / "selection_202503.json").read_text())["coin_list"]
    K = load_krw()
    coins = {}
    for s in sel:
        if (D / f"upbit/{s['coin']}.parquet").exists() and (D / f"binance/{s['binance']}.parquet").exists():
            coins[s["coin"]] = load_coin(s["coin"], s["binance"], K)
    hl = {s["coin"] for s in sel if s["hl_listed_20261005"]}
    out = {"coins_used": sorted(coins), "n_coins": len(coins)}
    if mode == "counts":
        lo, hi = SPLIT["train"]; days = (hi - lo) / 1440
        for z, r, h in GRID:
            n_raw = sum(len(triggers(c, z, r, lo, hi)) for c in coins.values())
            out[cname(z, r, h)] = dict(raw_trigger_minutes=n_raw, per_day=round(n_raw / days, 2))
        print(json.dumps(out, indent=1)); return out
    if mode == "train":
        lo, hi = SPLIT["train"]; days = (hi - lo) / 1440
        res, alltr = {}, {}
        for z, r, h in GRID:
            tr = []
            for name, c in coins.items():
                t_, _ = sim(c, triggers(c, z, r, lo, hi), r, h)
                for t in t_: t["coin"] = name
                tr += t_
            st = stats(tr); st["per_day"] = st["n"] / days
            res[cname(z, r, h)] = st; alltr[cname(z, r, h)] = tr
            print(cname(z, r, h), {k: (round(v, 3) if isinstance(v, float) else v) for k, v in st.items()}, flush=True)
        out["configs"] = res
        passing = [k for k, v in res.items() if v["passes"]]
        out["chosen"] = max(passing, key=lambda k: res[k]["net"]) if passing else None
        # informational profiles (train), base events Z=3,R=1%, all trigger minutes (no cooldown)
        prof, rev, same = {k: [] for k in (1, 5, 30)}, {k: [] for k in (1, 5, 30)}, []
        upcont = {k: [] for k in (1, 5, 30)}
        nrev = 0
        for c in coins.values():
            idx = triggers(c, 3.0, 0.01, lo, hi)
            o, bc = c["B"]["o"], c["bc"]
            for t in idx:
                s = np.sign(c["ret"][t])
                if np.isfinite(c["rb"][t]): same.append(c["rb"][t] / c["ret"][t])
                for k in (1, 5, 30):
                    if t + 1 + k < N and np.isfinite(o[t + 1]):
                        prof[k].append(s * (bc[t + k] / o[t + 1] - 1) * 1e4)
                        upcont[k].append(s * (c["pu"][t + k] / c["pu"][t] - 1) * 1e4)
            with np.errstate(invalid="ignore"):
                m = (c["zb"] >= 3.0) & (np.abs(c["rb"]) >= 0.01) & c["elig"]
            ridx = np.nonzero(m)[0]; ridx = ridx[(ridx + M0 >= lo) & (ridx + M0 < hi)]
            nrev += len(ridx)
            for t in ridx:
                s = np.sign(c["rb"][t])
                for k in (1, 5, 30):
                    if t + k < N: rev[k].append(s * (c["pu"][t + k] / c["pu"][t] - 1) * 1e4)
        f = lambda a: dict(n=len(a), mean_bp=float(np.nanmean(a)), median_bp=float(np.nanmedian(a))) if a else None
        out["info_upbit_burst_binance_profile_Z3_R1"] = {f"+{k}m_from_next_open": f(v) for k, v in prof.items()}
        out["info_upbit_burst_upbit_continuation_Z3_R1"] = {f"+{k}m_from_close": f(v) for k, v in upcont.items()}
        out["info_binance_same_minute_over_upbit_return"] = dict(n=len(same), median=float(np.median(same)),
                                                                 share_ge_half=float(np.mean(np.array(same) >= 0.5)))
        out["info_reverse_binance_burst_upbit_followup_Z3_R1"] = dict(events=nrev, **{f"+{k}m": f(v) for k, v in rev.items()})
        ch = out["chosen"]
        if ch:
            z, r, h = [float(x[1:]) for x in ch.split("_")]; h = int(h)
            info = {}
            for lab, kw in {"delay1": dict(delay=2), "slipx2": dict(slipx=2.0), "gap_filter": dict(gap=True)}.items():
                tr = []
                for c in coins.values(): tr += sim(c, triggers(c, z, r, lo, hi), r, h, **kw)[0]
                info[lab] = stats(tr)
            tr = []
            for name, c in coins.items():
                if name in hl: tr += sim(c, triggers(c, z, r, lo, hi), r, h, fee=4.5)[0]
            info["hl_coins_hl_fee"] = stats(tr)
            out["chosen_info"] = info
        # per-coin + per-month concentration for every config's best
        best = max(res, key=lambda k: res[k]["net"])
        df = pd.DataFrame(alltr[best])
        if len(df):
            df["month"] = pd.to_datetime(df.minute * 60, unit="s").dt.strftime("%Y-%m")
            out["best_net_config_train"] = best
            out["best_by_coin"] = df.groupby("coin").net_bp.agg(["count", "sum"]).round(1).to_dict(orient="index")
            out["best_by_month"] = df.groupby("month").net_bp.agg(["count", "sum"]).round(1).to_dict(orient="index")
            out["best_exit_mix"] = df.exit.value_counts().to_dict()
        (D / f"trades_train_{best}.json").write_text(json.dumps(alltr[best]))
    if mode == "validation":
        ch = sys.argv[2]
        z, r, h = [float(x[1:]) for x in ch.split("_")]; h = int(h)
        lo, hi = SPLIT["validation"]; days = (hi - lo) / 1440
        tr = []
        for name, c in coins.items():
            t_, _ = sim(c, triggers(c, z, r, lo, hi), r, h)
            for t in t_: t["coin"] = name
            tr += t_
        out["config"] = ch; out["validation"] = stats(tr); out["validation"]["per_day"] = len(tr) / days
        info = {}
        for lab, kw in {"delay1": dict(delay=2), "slipx2": dict(slipx=2.0)}.items():
            t2 = []
            for c in coins.values(): t2 += sim(c, triggers(c, z, r, lo, hi), r, h, **kw)[0]
            info[lab] = stats(t2)
        out["validation_info"] = info
        (D / f"trades_validation_{ch}.json").write_text(json.dumps(tr))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
