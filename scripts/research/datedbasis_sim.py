"""H-DATEDBASIS simulation, exactly as pre-registered in
reports/hypotheses/datedbasis_preregistration.json.

Usage: python scripts/research/datedbasis_sim.py train
       python scripts/research/datedbasis_sim.py validation V1_base ...   (run once, passing configs only)

Point-in-time: the decision uses the 1h bar closing at Monday 00:00 and the DTB3 print dated strictly
before the decision date; fills use the next 1h close; the only later data used is the realised path
for P&L (settlement, margin event, early-exit decisions made on later Monday closes).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/binance_dated"
OBS = ROOT / "research/observations"

SPOT_FEE, FUT_FEE, SETTLE_FEE = 0.001, 0.0005, 0.0005
MARGIN_STOP, STOP_PEN = 0.60, 0.005

VARIANTS = {
    "V1_base": dict(margin=0.02, early=False, coins=None),
    "V2_cash_hurdle": dict(margin=0.0, early=False, coins=None),
    "V3_high_hurdle": dict(margin=0.05, early=False, coins=None),
    "V4_base_early_exit": dict(margin=0.02, early=True, coins=None),
    "V5_btc_eth_only": dict(margin=0.02, early=False, coins={"BTC", "ETH"}),
}


def delivery_ts(sym):
    d = sym.split("_")[1]
    return pd.Timestamp(datetime(2000 + int(d[:2]), int(d[2:4]), int(d[4:]), 8, tzinfo=timezone.utc))


def coin_of(sym):
    p = sym.split("_")[0]
    return p[:-4] if p.endswith("USDT") else p[:-3]


def load():
    fut = pd.read_parquet(D / "futures_1h.parquet")
    spot = pd.read_parquet(D / "spot_1h.parquet")
    dd = pd.read_parquet(D / "delivery_day_1m.parquet")
    fr = pd.read_parquet(D / "fred_dtb3.parquet").sort_values("date")
    return fut, spot, dd, fr


def tbill(fr, ts):
    """Latest DTB3 dated strictly before the decision date."""
    d = pd.Timestamp(ts.date())
    s = fr[fr.date < d]
    return float(s.dtb3.iloc[-1]) / 100.0


def settlement(dd, sym, minutes=60):
    deliv = delivery_ts(sym)
    lo = deliv - pd.Timedelta(minutes=minutes)
    g = dd[(dd.symbol == sym) & (dd.open_time >= lo) & (dd.open_time < deliv)]
    idx = g[g.kind == "index"].close
    sp = g[g.kind == "spot"].close
    fu = g[g.kind == "future"].close
    if len(idx) < minutes * 0.8 or len(sp) < minutes * 0.8:
        return None
    return dict(P=float(idx.mean()), S=float(sp.mean()), F_last=float(fu.iloc[-1]) if len(fu) else np.nan)


def build_trades(fut, spot, dd, fr, split, cfg, slip_mult=1.0, spot_fee=SPOT_FEE, settle_min=60, usdm_margin=1.0):
    lo, hi = {"train": (None, pd.Timestamp("2025-06-30 23:59", tz="UTC")),
              "validation": (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-03-31 23:59", tz="UTC"))}[split]
    trades, skipped = [], {"no_bar": 0, "zero_vol": 0, "no_settle": 0, "no_spot": 0}
    spot_by = {c: g.set_index("open_time").sort_index() for c, g in spot.groupby("coin")}
    for sym, g in fut.groupby("symbol"):
        deliv = delivery_ts(sym)
        if (lo is not None and deliv < lo) or deliv > hi:
            continue
        coin = coin_of(sym)
        if cfg["coins"] is not None and coin not in cfg["coins"]:
            continue
        if coin not in spot_by:
            skipped["no_spot"] += 1
            continue
        mkt = g.market.iloc[0]
        f = g.set_index("open_time").sort_index()
        s = spot_by[coin]
        slip = (0.0002 if coin in ("BTC", "ETH") else 0.0005) * slip_mult
        c_rt = 2 * spot_fee + FUT_FEE + SETTLE_FEE + 4 * slip
        st = settlement(dd, sym, settle_min)
        first = f.index.min().ceil("D")
        mondays = pd.date_range(first, deliv, freq="W-MON")
        for t in mondays:
            Dd = (deliv - t).total_seconds() / 86400
            if not (21 <= Dd <= 120):
                continue
            bar = t - pd.Timedelta(hours=1)
            if bar not in f.index or bar not in s.index:
                skipped["no_bar"] += 1
                continue
            if f.at[bar, "volume"] <= 0:
                skipped["zero_vol"] += 1
                continue
            F, S = f.at[bar, "close"], s.at[bar, "close"]
            h = tbill(fr, t)
            b = (F / S - 1) * 365 / Dd
            if b - c_rt * 365 / Dd < h + cfg["margin"]:
                continue
            if t not in f.index or t not in s.index or f.at[t, "volume"] <= 0:
                skipped["zero_vol"] += 1
                continue
            if st is None:
                skipped["no_settle"] += 1
                continue
            t_in = t + pd.Timedelta(hours=1)
            F_in = f.at[t, "close"] * (1 - slip)
            S_in = s.at[t, "close"] * (1 + slip)
            # path after the fill bar
            fpath = f[(f.index > t) & (f.index < deliv)]
            spath = s[(s.index > t) & (s.index < deliv)]
            exit_kind, t_out = "delivery", deliv
            F_out = S_out = None
            if mkt == "um":
                hit = fpath[fpath.high >= F_in * (1 + MARGIN_STOP)]
                if len(hit):
                    tb = hit.index[0]
                    if tb in s.index:
                        exit_kind, t_out = "margin_event", tb + pd.Timedelta(hours=1)
                        F_out = fpath.at[tb, "close"] * (1 + STOP_PEN)
                        S_out = s.at[tb, "close"] * (1 - slip)
            if cfg["early"] and exit_kind == "delivery":
                for m in pd.date_range(t + pd.Timedelta(days=7), deliv, freq="W-MON"):
                    Drem = (deliv - m).total_seconds() / 86400
                    if Drem < 7:
                        break
                    bm = m - pd.Timedelta(hours=1)
                    if bm not in f.index or bm not in s.index or m not in f.index or m not in s.index:
                        continue
                    if (f.at[bm, "close"] / s.at[bm, "close"] - 1) * 365 / Drem < tbill(fr, m):
                        exit_kind, t_out = "early", m + pd.Timedelta(hours=1)
                        F_out = f.at[m, "close"] * (1 + slip)
                        S_out = s.at[m, "close"] * (1 - slip)
                        break
            days = (t_out - t_in).total_seconds() / 86400
            if exit_kind == "delivery":
                P = st["P"]
                S_out = st["S"] * (1 - slip)
                fexit_fee = SETTLE_FEE
                F_out = P
            else:
                fexit_fee = FUT_FEE
            if mkt == "um":
                q = 1.0 / S_in  # $1 of spot
                K = q * S_in * (1 + spot_fee) + usdm_margin * q * F_in
                pnl = (q * (S_out * (1 - spot_fee) - S_in * (1 + spot_fee))
                       + q * (F_in - F_out) - q * F_in * FUT_FEE - q * F_out * fexit_fee)
            else:
                V = 1.0
                Q = V / F_in
                K = Q * S_in * (1 + spot_fee)
                coins_end = Q + V * (1 / F_out - 1 / F_in) - FUT_FEE * V / F_in - fexit_fee * V / F_out
                pnl = coins_end * S_out * (1 - spot_fee) - K
            r_raw = pnl / K
            r_ex = r_raw - h * days / 365
            trades.append(dict(symbol=sym, coin=coin, market=mkt, delivery=str(deliv.date()), entry=str(t_in),
                               exit=str(t_out), exit_kind=exit_kind, days=days, D_entry=Dd, basis_ann=b,
                               hurdle=h + cfg["margin"], tbill=h, K=K, r_raw=r_raw, r_ex=r_ex,
                               settle_vs_spot=(st["P"] / st["S"] - 1)))
    return pd.DataFrame(trades), skipped


def stats(df, col="r_ex"):
    if len(df) == 0:
        return dict(n=0)
    r = df[col].sort_values(ascending=False)
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    yrs = (df.K * df.days / 365).sum()
    return dict(n=int(len(r)), net=float(r.sum()), mean=float(r.mean()), median=float(r.median()),
                pf=float(pos / neg) if neg > 0 else float("inf"), ex_top3=float(r.iloc[3:].sum()),
                win=float((r > 0).mean()),
                ann_raw=float((df.r_raw * df.K).sum() / yrs), ann_ex=float((df.r_ex * df.K).sum() / yrs),
                worst=float(r.min()), clusters=int(df.groupby(["symbol"]).ngroups))


def passes(s):
    return s.get("n", 0) >= 50 and s["net"] > 0 and s["pf"] > 1.2 and s["ex_top3"] > 0


def cluster_stats(df):
    c = df.groupby("symbol").r_ex.sum().sort_values(ascending=False)
    pos, neg = c[c > 0].sum(), -c[c < 0].sum()
    return dict(n_clusters=int(len(c)), net=float(c.sum()), pf=float(pos / neg) if neg > 0 else float("inf"),
                ex_top3=float(c.iloc[3:].sum()))


def run(split, names):
    fut, spot, dd, fr = load()
    out = {"split": split, "prereg": "reports/hypotheses/datedbasis_preregistration.json", "is_synthetic": False,
           "variants": {}}
    for name in names:
        cfg = VARIANTS[name]
        df, skipped = build_trades(fut, spot, dd, fr, split, cfg)
        res = {"cfg": {k: (sorted(v) if isinstance(v, set) else v) for k, v in cfg.items()}, "skipped": skipped,
               "primary_r_ex": stats(df), "raw_r": stats(df, "r_raw")}
        if len(df):
            res["passes_bar"] = passes(res["primary_r_ex"])
            res["cluster_level"] = cluster_stats(df)
            res["exit_kinds"] = df.exit_kind.value_counts().to_dict()
            df["q"] = pd.to_datetime(df.entry).dt.to_period("Q").astype(str)
            res["by_entry_quarter"] = df.groupby("q").r_ex.agg(["count", "sum"]).round(5).to_dict("index")
            res["by_coin"] = df.groupby("coin").r_ex.agg(["count", "sum", "mean"]).round(5).to_dict("index")
            res["by_market"] = df.groupby("market").r_ex.agg(["count", "sum", "mean"]).round(5).to_dict("index")
            res["by_delivery"] = df.groupby("delivery").r_ex.agg(["count", "sum"]).round(5).to_dict("index")
            no24 = df[~pd.to_datetime(df.entry).dt.to_period("Q").astype(str).eq("2024Q4")]
            res["without_2024Q4"] = stats(no24)
            res["settle_vs_spot_bp"] = (df.drop_duplicates("symbol").settle_vs_spot * 1e4).describe().round(2).to_dict()
            sens = {}
            for lab, kw in {"slip_x2": dict(slip_mult=2), "spot_fee_bnb": dict(spot_fee=0.00075),
                            "settle_30min": dict(settle_min=30), "usdm_margin_0.5": dict(usdm_margin=0.5)}.items():
                d2, _ = build_trades(fut, spot, dd, fr, split, cfg, **kw)
                sens[lab] = stats(d2)
            res["sensitivities"] = sens
            res["trades"] = df[["symbol", "entry", "exit_kind", "days", "basis_ann", "hurdle", "r_raw", "r_ex"]].round(6).to_dict("records")
            res["top5"] = df.nlargest(5, "r_ex")[["symbol", "entry", "exit_kind", "r_ex"]].to_dict("records")
            res["bottom5"] = df.nsmallest(5, "r_ex")[["symbol", "entry", "exit_kind", "r_ex"]].to_dict("records")
        out["variants"][name] = res
        print(name, json.dumps(res["primary_r_ex"]), "raw", json.dumps(res["raw_r"].get("ann_raw")),
              "PASS" if res.get("passes_bar") else "fail")
    p = OBS / f"evidence_datedbasis_{split}.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    print("wrote", p)
    return out


if __name__ == "__main__":
    split = sys.argv[1]
    names = sys.argv[2:] or list(VARIANTS)
    if split == "validation" and not sys.argv[2:]:
        sys.exit("validation requires explicit train-passing variant names")
    run(split, names)
