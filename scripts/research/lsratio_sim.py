"""H-LSRATIO simulation (pre-registration: reports/hypotheses/lsratio_preregistration.json).

    python scripts/research/lsratio_sim.py train      # 12 configs on train, follow-crowd + residual check, selection
    python scripts/research/lsratio_sim.py validate   # selected config only, runs ONCE (refuses if output exists)

Inputs: data/raw/web/lsratio/{universe.parquet, metrics/, k1h/}, data/raw/web/momentum/funding/ (read-only).
Nothing dated >= 2026-04-01 exists in the inputs (fetch guard) and the code also drops it (holdout guard).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/lsratio"
FUND = ROOT / "data/raw/web/momentum/funding"
PRE = json.load(open(ROOT / "reports/hypotheses/lsratio_preregistration.json"))
OBS = ROOT / "research/observations"
TRAIN_OUT = OBS / "evidence_lsratio_train_20261005.json"
VALID_OUT = OBS / "evidence_lsratio_validation_20261005.json"
SPLITS = {"train": ("2023-01-01", "2025-07-01"), "validation": ("2025-07-01", "2026-04-01")}
HOLDOUT = pd.Timestamp("2026-04-01")
COST = 0.0013          # 2 x (4.5 bp taker + 2 bp slippage)
COST_BN = 0.0014       # sensitivity: 2 x (5 + 2) bp
STOP = 0.05
ZWIN, ZMIN = 168, 120


def tz(v):
    m = v.shift(1).rolling(ZWIN, min_periods=ZMIN).mean()
    s = v.shift(1).rolling(ZWIN, min_periods=ZMIN).std()
    return (v - m) / s


def load_symbol(sym, udays):
    mf, kf = D / "metrics" / f"{sym}.parquet", D / "k1h" / f"{sym}.parquet"
    if not (mf.exists() and kf.exists()):
        return None
    m = pd.read_parquet(mf)
    m = m[m.t < HOLDOUT].set_index("t")
    k = pd.read_parquet(kf)
    k["t"] = pd.to_datetime(k.open_time, unit="ms")
    k = k[k.t < HOLDOUT].set_index("t")
    grid = pd.date_range(min(m.index.min(), k.index.min()), max(m.index.max(), k.index.max()), freq="h")
    m, k = m.reindex(grid), k.reindex(grid)
    f = pd.DataFrame(index=grid)
    f["open"], f["high"], f["low"], f["close"] = k.open, k.high, k.low, k.close
    lnC = np.log(m.count_long_short_ratio.where(m.count_long_short_ratio > 0))
    lnT = np.log(m.sum_toptrader_long_short_ratio.where(m.sum_toptrader_long_short_ratio > 0))
    lnO = np.log(m.sum_open_interest.where(m.sum_open_interest > 0))
    lnP = np.log(k.close)
    for L in (1, 4):
        dC, dT, dO = lnC - lnC.shift(L), lnT - lnT.shift(L), lnO - lnO.shift(L)
        f[f"zD{L}"] = tz(dC - dT)
        f[f"zC{L}"] = tz(dC)
        f[f"zO{L}"] = tz(dO)
        f[f"zR{L}"] = tz((lnP - lnP.shift(L)).shift(1))  # trailing L-h return, bars closed by t
    f["in_u"] = f.index.normalize().isin(udays)
    return f


def funding(sym):
    p = FUND / f"{sym}.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p)
    d["t"] = pd.to_datetime(d.calc_time, unit="ms")
    d = d[d.t < HOLDOUT]
    return d.set_index("t").last_funding_rate.sort_index()


def signal_side(f, sig, L):
    if sig == "div":
        z = f[f"zD{L}"]
        return np.where(z >= 2.0, -1, np.where(z <= -2.0, 1, 0))
    zO, zC = f[f"zO{L}"], f[f"zC{L}"]
    return np.where((zO >= 1.5) & (zC >= 1.5), -1, np.where((zO >= 1.5) & (zC <= -1.5), 1, 0))


def simulate(f, fr, sym, sig, L, H, lo, hi, flip=False):
    side = signal_side(f, sig, L) * (-1 if flip else 1)
    idx = f.index
    ok = (side != 0) & f.in_u.values & (idx >= lo) & (idx < hi) & f.open.notna().values
    o, h, l, c = f.open.values, f.high.values, f.low.values, f.close.values
    trades, busy_until = [], None
    pos = {t: i for i, t in enumerate(idx)}
    for i in np.flatnonzero(ok):
        t = idx[i]
        if busy_until is not None and t < busy_until:
            continue
        s, pe = int(side[i]), o[i]
        stop = pe * (1 - STOP) if s == 1 else pe * (1 + STOP)
        px, xt, how = None, None, "time"
        last_close, last_t = None, None
        for j in range(i, min(i + H, len(idx))):
            if np.isnan(o[j]):
                continue
            if (s == 1 and o[j] <= stop) or (s == -1 and o[j] >= stop):
                px, xt, how = o[j], idx[j], "stop_gap"
                break
            if (s == 1 and l[j] <= stop) or (s == -1 and h[j] >= stop):
                px, xt, how = stop, idx[j] + pd.Timedelta(minutes=59), "stop"
                break
            last_close, last_t = c[j], idx[j] + pd.Timedelta(minutes=59)
        if px is None:
            j = i + H
            if j < len(idx) and idx[j] < HOLDOUT and not np.isnan(o[j]):
                px, xt = o[j], idx[j]
            elif last_close is not None:
                px, xt, how = last_close, last_t, "last_close"
            else:
                continue
        gross = s * (px / pe - 1)
        fund = 0.0
        if fr is not None:
            fund = s * fr[(fr.index > t) & (fr.index <= xt)].sum()
        trades.append(dict(symbol=sym, t=t, side=s, entry=pe, exit=px, exit_t=xt, how=how, gross=gross,
                           funding=fund, net=gross - fund - COST, net_bn=gross - fund - COST_BN,
                           fund_missing=fr is None))
        busy_until = xt if how.startswith("stop") else (idx[i + H] if i + H < len(idx) else xt)
    return trades


def stats(tr, col="net"):
    if not len(tr):
        return dict(n=0)
    x = tr[col].sort_values(ascending=False)
    wins, losses = x[x > 0].sum(), -x[x < 0].sum()
    pf = float(wins / losses) if losses > 0 else None
    out = dict(n=int(len(x)), sum=float(x.sum()), mean_bp=float(x.mean() * 1e4), median_bp=float(x.median() * 1e4),
               pf=pf, sum_ex_top3=float(x.iloc[3:].sum()), win_rate=float((x > 0).mean()),
               gross_mean_bp=float(tr.gross.mean() * 1e4), funding_mean_bp=float(tr.funding.mean() * 1e4),
               n_long=int((tr.side == 1).sum()), n_short=int((tr.side == -1).sum()),
               stops=int(tr.how.str.startswith("stop").sum()),
               by_year={str(y): float(g[col].sum()) for y, g in tr.groupby(tr.t.dt.year)},
               n_symbols=int(tr.symbol.nunique()), n_days=int(tr.t.dt.normalize().nunique()))
    daily = tr.groupby(tr.t.dt.normalize())[col].sum()
    out["daily_sum_mean_bp"] = float(daily.mean() * 1e4)
    out["daily_t"] = float(daily.mean() / daily.std() * np.sqrt(len(daily))) if len(daily) > 1 else None
    out["passes_bar"] = bool(out["n"] >= 50 and out["sum"] > 0 and (pf or 0) > 1.2 and out["sum_ex_top3"] > 0)
    return out


def cluster_ols(y, X, g):
    X = np.column_stack([np.ones(len(y)), X])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ y
    u = y - X @ b
    meat = np.zeros((X.shape[1], X.shape[1]))
    for _, ix in pd.Series(np.arange(len(y))).groupby(g):
        s = X[ix.values].T @ u[ix.values]
        meat += np.outer(s, s)
    V = XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))
    return b, b / se


def load_all():
    U = pd.read_parquet(D / "universe.parquet")
    data = {}
    for s, g in U.groupby("symbol"):
        f = load_symbol(s, pd.DatetimeIndex(g.day))
        if f is not None:
            data[s] = (f, funding(s))
    return U, data


def run_configs(data, split, configs, flip=False):
    lo, hi = map(pd.Timestamp, SPLITS[split])
    res = {}
    for c in configs:
        tr = []
        for s, (f, fr) in data.items():
            tr += simulate(f, fr, s, c["signal"], c["L_hours"], c["H_hours"], lo, hi, flip)
        res[c["key"]] = pd.DataFrame(tr)
    return res


def residual_check(data):
    lo, hi = map(pd.Timestamp, SPLITS["train"])
    out = {}
    for sig in ("div", "oi_crowd"):
        for L in (1, 4):
            for H in (1, 4, 8):
                ys, xs, rs, gs = [], [], [], []
                for s, (f, _) in data.items():
                    fwd = np.log(f.open.shift(-H) / f.open)
                    x = f[f"zD{L}"] if sig == "div" else f[f"zC{L}"].where(f[f"zO{L}"] >= 1.5)
                    m = f.in_u & (f.index >= lo) & (f.index < hi) & fwd.notna() & x.notna() & f[f"zR{L}"].notna()
                    ys.append(fwd[m].values); xs.append(x[m].values); rs.append(f[f"zR{L}"][m].values)
                    gs.append(f.index[m].normalize().values)
                y, x, r, g = map(np.concatenate, (ys, xs, rs, gs))
                b, t = cluster_ols(y, np.column_stack([x, r]), g)
                b0, t0 = cluster_ols(y, x[:, None], g)
                out[f"{sig}_L{L}_H{H}"] = dict(n=int(len(y)), coef_signal_bp=float(b[1] * 1e4), t_signal=float(t[1]),
                                               coef_pastret_bp=float(b[2] * 1e4), t_pastret=float(t[2]),
                                               coef_signal_alone_bp=float(b0[1] * 1e4), t_signal_alone=float(t0[1]),
                                               corr_signal_pastret=float(np.corrcoef(x, r)[0, 1]))
    return out


def coverage(U, data):
    hrs = {s: int(f.in_u.sum()) for s, (f, _) in data.items()}
    zok = {s: int((f.in_u & f.zD1.notna()).sum()) for s, (f, _) in data.items()}
    return dict(universe_symbols=int(U.symbol.nunique()), symbols_with_data=len(data),
                universe_symbol_hours=int(sum(hrs.values())), symbol_hours_with_zD1=int(sum(zok.values())),
                symbols_missing=sorted(set(U.symbol) - set(data)))


def main_train():
    U, data = load_all()
    cfgs = PRE["configs"]
    res = run_configs(data, "train", cfgs)
    flip = run_configs(data, "train", cfgs, flip=True)
    table = {k: stats(v) for k, v in res.items()}
    for k in table:
        table[k]["bn_cost_sum"] = float(res[k].net_bn.sum()) if len(res[k]) else None
    follow = {k: stats(v) for k, v in flip.items()}
    passing = [k for k, v in table.items() if v.get("passes_bar")]
    pool = passing or [k for k, v in table.items() if v.get("n", 0) > 0]
    sel = max(pool, key=lambda k: table[k]["mean_bp"])
    resid = residual_check(data)
    out = dict(hypothesis="H-LSRATIO", split="train", window=SPLITS["train"], is_synthetic=False,
               preregistration="reports/hypotheses/lsratio_preregistration.json",
               coverage=coverage(U, data), configs=table, follow_the_crowd_informational=follow,
               residual_check_informational=resid, passing_on_train=passing, selected=sel,
               selected_passes_train=bool(passing), costs="13 bp RT (HL 4.5 bp taker + 2 bp slip per side) + Binance funding proxy")
    json.dump(out, open(TRAIN_OUT, "w"), indent=1)
    for k, v in table.items():
        print(k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items() if a not in ("by_year",)})
    print("FOLLOW", {k: (v.get("n"), round(v.get("mean_bp", 0), 1), v.get("pf") and round(v["pf"], 3)) for k, v in follow.items()})
    print("RESID", json.dumps(resid, indent=0))
    print("passing", passing, "selected", sel)
    res[sel].to_parquet(D / f"trades_train_{sel}.parquet")


def main_validate():
    if VALID_OUT.exists():
        sys.exit("validation already run once: " + str(VALID_OUT))
    tr_ev = json.load(open(TRAIN_OUT))
    sel = tr_ev["selected"]
    cfg = [c for c in PRE["configs"] if c["key"] == sel]
    U, data = load_all()
    res = run_configs(data, "validation", cfg)[sel]
    flip = run_configs(data, "validation", cfg, flip=True)[sel]
    st = stats(res)
    st["bn_cost_sum"] = float(res.net_bn.sum()) if len(res) else None
    out = dict(hypothesis="H-LSRATIO", split="validation", window=SPLITS["validation"], is_synthetic=False,
               preregistration="reports/hypotheses/lsratio_preregistration.json", selected=sel,
               selected_passes_train=tr_ev["selected_passes_train"], result=st,
               follow_the_crowd_informational=stats(flip), run_once=True)
    json.dump(out, open(VALID_OUT, "w"), indent=1)
    res.to_parquet(D / f"trades_validation_{sel}.parquet")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"train": main_train, "validate": main_validate}[sys.argv[1]]()
