"""H-XSREV simulation (pre-registration: reports/hypotheses/xsrev_preregistration.json).

Point in time: tier membership from daily bars closed before day d; beta from 720 hourly bars before 00:00 of d;
signal from hourly bars closed by rebalance time t; entry at the open of the bar starting at t.

    python scripts/research/xsrev_sim.py train            # all 12 configs on train
    python scripts/research/xsrev_sim.py validation KEY   # ONE config, run once
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
import xsrev_lib as xl  # noqa: E402

K1H = ROOT / "data/raw/web/xsrev/k1h"
FUND = ROOT / "data/raw/web/xsrev/funding"  # private copy of momentum/funding (Binance fundingRate archive)
PRE = json.load(open(ROOT / "reports/hypotheses/xsrev_preregistration.json"))
SPLITS = {"train": ("2023-02-01", "2025-06-30 23:00"), "validation": ("2025-07-01", "2026-03-31 23:00")}
COST_PRIMARY = 4.5e-4 + 2e-4
COST_BINANCE = 5e-4 + 2e-4
STOP = 0.15
DELIST_PEN = 0.02
NSIDE = 5
HOURS = pd.date_range("2023-01-01", "2026-03-31 23:00", freq="h")


def load():
    syms = sorted(f.stem for f in K1H.glob("*.parquet"))
    O, Hh, Lw, C = (np.full((len(HOURS), len(syms)), np.nan) for _ in range(4))
    t0 = HOURS[0].value // 10**6
    for j, s in enumerate(syms):
        d = pd.read_parquet(K1H / f"{s}.parquet")
        idx = ((d.open_time.values - t0) // 3_600_000).astype(int)
        ok = (idx >= 0) & (idx < len(HOURS))
        idx = idx[ok]
        O[idx, j], Hh[idx, j], Lw[idx, j], C[idx, j] = (d[c].values[ok] for c in ("open", "high", "low", "close"))
    return syms, O, Hh, Lw, C


def betas(syms, C):
    """beta[day_index_hour] per symbol, computed at each 00:00 from the previous 720 hourly returns."""
    R = C[1:] / C[:-1] - 1                      # R[h-1] = return of bar h (close h vs close h-1)
    R = np.vstack([np.full((1, C.shape[1]), np.nan), R])
    b = R[:, syms.index("BTCUSDT")]
    B = {}
    for h in range(720, len(HOURS), 24):
        x = b[h - 720:h]
        Y = R[h - 720:h]
        m = ~np.isnan(Y) & ~np.isnan(x)[:, None]
        n = m.sum(0)
        xm = np.where(m, x[:, None], 0.0)
        ym = np.where(m, Y, 0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            mx, my = xm.sum(0) / n, ym.sum(0) / n
            cov = (xm * ym).sum(0) / n - mx * my
            var = (xm * xm).sum(0) / n - mx * mx
            beta = cov / var
        beta[n < 500] = np.nan
        B[HOURS[h].normalize()] = beta
    return R, B


def funding_cum(syms):
    out = {}
    for s in syms:
        f = FUND / f"{s}.parquet"
        if not f.exists():
            continue
        d = pd.read_parquet(f).sort_values("calc_time")
        out[s] = (d.calc_time.values.astype("int64"), np.concatenate([[0.0], np.cumsum(d.last_funding_rate.values)]))
    return out


def fsum(fc, s, t_in, t_out):
    if s not in fc:
        return 0.0, False
    ts, cs = fc[s]
    a = np.searchsorted(ts, t_in, side="right")
    b = np.searchsorted(ts, t_out, side="right")
    return cs[b] - cs[a], True


def simulate(cfg, split, D, delay=0):
    syms, O, Hh, Lw, C, R, B, tiers, fc = D
    L, H, tier = cfg["L_hours"], cfg["H_hours"], cfg["tier"]
    t0, t1 = (pd.Timestamp(x) for x in SPLITS[split])
    sidx = {s: j for j, s in enumerate(syms)}
    jb = sidx["BTCUSDT"]
    hs = [h for h in range(len(HOURS)) if t0 <= HOURS[h] <= t1 and HOURS[h].hour % H == 0]
    last_h = max(h for h in range(len(HOURS)) if HOURS[h] <= t1)
    held = {}   # j -> dict(side, px, h_in)
    trades, baskets = [], []

    def close(j, px, h_out, why, pen=0.0):
        p = held.pop(j)
        gross = p["side"] * (px / p["px"] - 1) - pen
        ms = lambda h: int(HOURS[h].value // 10**6)  # noqa: E731
        f, ok = fsum(fc, syms[j], ms(p["h_in"]), ms(h_out) if why != "split_end" else ms(h_out) + 3_600_000)
        trades.append(dict(symbol=syms[j], side=p["side"], t_in=HOURS[p["h_in"]], t_out=HOURS[min(h_out, len(HOURS) - 1)],
                           gross=gross, funding=-p["side"] * f, fund_ok=ok, why=why,
                           hold_h=h_out - p["h_in"]))

    def last_close(j, h):
        k = h - 1
        while k >= 0 and np.isnan(C[k, j]):
            k -= 1
        return C[k, j], k

    for i, h in enumerate(hs):
        day = HOURS[h].normalize()
        mem = tiers.get((day, tier), [])
        beta = B.get(day)
        he = h + delay                      # execution bar
        if he > last_h:
            break
        cand = []
        for s in mem:
            j = sidx.get(s)
            if j is None or beta is None or np.isnan(beta[j]):
                continue
            rr = R[h - L:h, j]
            if np.isnan(rr).any() or np.isnan(O[he, j]):
                continue
            cand.append(j)
        tgt = {}
        if len(cand) >= 2 * NSIDE:
            cj = np.array(cand)
            rr = R[h - L:h][:, cj]
            if cfg["signal"] == "btc_resid":
                rb = R[h - L:h, jb]
                e = (rr - beta[cj][None, :] * rb[:, None]).sum(0)
            else:
                e = (rr - rr.mean(1, keepdims=True)).sum(0)
            order = cj[np.argsort(e, kind="stable")]
            for j in order[:NSIDE]:
                tgt[j] = 1
            for j in order[-NSIDE:]:
                tgt[j] = -1
        # close legs not kept
        for j in list(held):
            if tgt.get(j) != held[j]["side"]:
                if np.isnan(O[he, j]):
                    px, _ = last_close(j, he)
                    close(j, px, he, "delisted", DELIST_PEN)
                else:
                    close(j, O[he, j], he, "rebalance")
        n_new = 0
        for j, sd in tgt.items():
            if j not in held:
                held[j] = dict(side=sd, px=O[he, j], h_in=he)
                n_new += 1
        # hold bars he .. next execution bar - 1 ; check stops
        h_next = (hs[i + 1] + delay) if i + 1 < len(hs) else last_h + 1
        h_next = min(h_next, last_h + 1)
        for k in range(he, h_next):
            for j in list(held):
                p = held[j]
                if np.isnan(Lw[k, j]):
                    continue
                if p["side"] == 1:
                    sp = p["px"] * (1 - STOP)
                    if Lw[k, j] <= sp:
                        close(j, min(O[k, j], sp), k, "stop")
                else:
                    sp = p["px"] * (1 + STOP)
                    if Hh[k, j] >= sp:
                        close(j, max(O[k, j], sp), k, "stop")
        baskets.append(dict(t=HOURS[h], n_legs=len(held), n_new=n_new))
    for j in list(held):  # force-close at the split's last close
        px = C[last_h, j]
        if np.isnan(px):
            px, _ = last_close(j, last_h + 1)
            close(j, px, last_h, "split_end", DELIST_PEN)
        else:
            close(j, px, last_h, "split_end")
    T = pd.DataFrame(trades)
    T["net"] = T.gross + T.funding - 2 * COST_PRIMARY
    T["net_bn"] = T.gross + T.funding - 2 * COST_BINANCE
    return T, pd.DataFrame(baskets)


def stats(x):
    x = np.asarray(x, float)
    if len(x) == 0:
        return dict(n=0)
    w, lo = x[x > 0].sum(), -x[x < 0].sum()
    srt = np.sort(x)
    return dict(n=int(len(x)), mean_bp=round(x.mean() * 1e4, 2), sum=round(x.sum(), 4),
                pf=round(w / lo, 3) if lo > 0 else None, sum_ex_top3=round(srt[:-3].sum(), 4),
                win=round((x > 0).mean(), 3), median_bp=round(np.median(x) * 1e4, 2))


def passes(s):
    return s["n"] >= 50 and s["sum"] > 0 and (s["pf"] or 0) > 1.2 and s["sum_ex_top3"] > 0


def basket_returns(T, H):
    """Per-rebalance-period portfolio return approx: each trade's net spread evenly over its rebalance periods, 1/10 weight."""
    T = T.copy()
    T["per"] = T.t_in.dt.floor(f"{H}h")
    g = (T.groupby("per").net.sum() / (2 * NSIDE))
    return g


def summarize(T, H):
    out = {"all": {"net": stats(T.net), "gross": stats(T.gross), "net_binance": stats(T.net_bn),
                   "funding_mean_bp": round(T.funding.mean() * 1e4, 3), "fund_missing_share": round(1 - T.fund_ok.mean(), 3),
                   "stops": int((T.why == "stop").sum()), "delisted": int((T.why == "delisted").sum()),
                   "mean_hold_h": round(T.hold_h.mean(), 2),
                   "long": stats(T.net[T.side == 1]), "short": stats(T.net[T.side == -1])}}
    out["all"]["pass"] = passes(out["all"]["net"])
    out["by_year"] = {}
    for y, g in T.groupby(T.t_in.dt.year):
        out["by_year"][int(y)] = {"net": stats(g.net), "gross_mean_bp": round(g.gross.mean() * 1e4, 2),
                                  "net_binance_mean_bp": round(g.net_bn.mean() * 1e4, 2)}
    b = basket_returns(T, H)
    out["entry_cohort_basket"] = {"n_periods": int(len(b)), "mean_bp": round(b.mean() * 1e4, 3),
                                  "t_stat": round(b.mean() / b.std() * np.sqrt(len(b)), 2) if len(b) > 2 else None}
    out["trades_per_day"] = round(len(T) / max(1, (T.t_in.max() - T.t_in.min()).days), 1)
    return out


def data():
    syms, O, Hh, Lw, C = load()
    R, B = betas(syms, C)
    t = xl.tiers()
    tiers = {k: list(g.symbol) for k, g in t.groupby(["day", "tier"])}
    return syms, O, Hh, Lw, C, R, B, tiers, funding_cum(syms)


if __name__ == "__main__":
    split = sys.argv[1]
    D = data()
    cfgs = PRE["configs"]
    obs = ROOT / "research/observations"
    if split == "train":
        res = {}
        for c in cfgs:
            T, _ = simulate(c, "train", D)
            res[c["key"]] = summarize(T, c["H_hours"])
            T.to_parquet(ROOT / f"data/raw/web/xsrev/trades_train_{c['key']}.parquet")
            a = res[c["key"]]["all"]
            print(c["key"], a["net"], "gross", a["gross"]["mean_bp"], "bn", a["net_binance"]["mean_bp"], "pass", a["pass"], flush=True)
        ok = [k for k in res if res[k]["all"]["pass"]]
        best = max(ok or res, key=lambda k: res[k]["all"]["net"]["mean_bp"])
        out = {"prereg": "reports/hypotheses/xsrev_preregistration.json", "split": "train", "configs": res,
               "passing": ok, "selected": best, "selected_passes_train": bool(ok)}
        json.dump(out, open(obs / "evidence_xsrev_train_20261005.json", "w"), indent=1, default=str)
        print("passing", ok, "selected", best)
    elif split == "validation":
        key = sys.argv[2]
        tr = json.load(open(obs / "evidence_xsrev_train_20261005.json"))
        assert key == tr["selected"], "validation may only run the config selected on train"
        f = obs / "evidence_xsrev_validation_20261005.json"
        assert not f.exists(), "validation already run once"
        c = next(c for c in cfgs if c["key"] == key)
        T, _ = simulate(c, "validation", D)
        T.to_parquet(ROOT / f"data/raw/web/xsrev/trades_validation_{key}.parquet")
        s = summarize(T, c["H_hours"])
        json.dump({"prereg": "reports/hypotheses/xsrev_preregistration.json", "split": "validation", "config": key,
                   "selected_passes_train": tr["selected_passes_train"], "result": s}, open(f, "w"), indent=1, default=str)
        print(json.dumps(s["all"], default=str, indent=1))
