"""H-FUNDCLOCK simulator (rules frozen in reports/hypotheses/fundclock_preregistration.json).

    python scripts/research/fundclock_sim.py train            # all 12 configs on train
    python scripts/research/fundclock_sim.py validation KEY   # the ONE selected config, run once

Point in time: PRE uses the previous settled print (known before T-k); POST uses the print at T and enters
at T+1 min. Prices are Binance USDT-M 1m bars. Costs: 5 bp taker + 2 bp slippage per side (14 bp round trip).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/fundclock"
PRE = json.loads((ROOT / "reports/hypotheses/fundclock_preregistration.json").read_text())
CFGS = {c["key"]: c for c in PRE["configs"]}
RT = 2 * (PRE["costs"]["taker_fee_per_side"] + PRE["costs"]["slippage_per_side"])
SPLITS = {"train": ("2023-01-01", "2025-07-01"), "validation": ("2025-07-01", "2026-04-01")}
MIN = 60_000


def load_symbol(sym):
    fs = sorted((D / "win").glob(f"{sym}_*.parquet"))
    if not fs:
        return None
    df = pd.concat([pd.read_parquet(f) for f in fs]).drop_duplicates("t").sort_values("t")
    k = df.t.values.astype("datetime64[ms]").astype("int64")
    return dict(zip(k, df.o.values)), dict(zip(k, df.c.values))


def events(split):
    """One row per (symbol, settlement T) with T in split and symbol in T-month's universe."""
    uni = json.loads((D / "universe.json").read_text())["data"]
    lo, hi = SPLITS[split]
    rows = []
    for sym in sorted({s for v in uni.values() for s in v}):
        f = pd.read_parquet(D / "funding" / f"{sym}.parquet")
        f["T"] = f.t.dt.round("min")
        f = f.drop_duplicates("T").sort_values("T").reset_index(drop=True)
        f["f_prev"] = f.rate.shift(1)
        f["interval_h"] = (f["T"].diff().dt.total_seconds() / 3600).round(2)
        f["month"] = f["T"].dt.strftime("%Y-%m")
        f = f[(f["T"] >= lo) & (f["T"] < hi)]
        f = f[[sym in uni.get(m, []) for m in f.month]]
        f = f.assign(sym=sym)
        rows.append(f)
    return pd.concat(rows, ignore_index=True)


def simulate(ev, keys):
    out = {k: [] for k in keys}
    skipped = {k: 0 for k in keys}
    for sym, g in ev.groupby("sym"):
        px = load_symbol(sym)
        if px is None:
            for k in keys:
                skipped[k] += len(g)
            continue
        op, cl = px
        for r in g.itertuples():
            T = r.T.value // 10**6
            for k in keys:
                c = CFGS[k]
                thr, w = c["abs_funding_threshold"], c["window_min"]
                f = r.f_prev if c["mode"] == "PRE" else r.rate
                if not np.isfinite(f) or abs(f) < thr:
                    continue
                if c["mode"] == "PRE":
                    side = -1 if f > 0 else 1
                    e, x = op.get(T - w * MIN), cl.get(T - MIN)
                else:
                    side = 1 if f > 0 else -1
                    e, x = op.get(T + MIN), cl.get(T + w * MIN)
                if e is None or x is None or e <= 0:
                    skipped[k] += 1
                    continue
                g_ret = side * (x / e - 1)
                out[k].append({"sym": sym, "T": r.T, "f": f, "f_at_T": r.rate, "side": side,
                               "interval_h": r.interval_h, "gross": g_ret, "net": g_ret - RT})
    return {k: pd.DataFrame(v) for k, v in out.items()}, skipped


def stats(t):
    if t.empty:
        return {"n": 0}
    n = t.net.sort_values(ascending=False)
    pos, neg = t.net[t.net > 0].sum(), -t.net[t.net < 0].sum()
    day = t.groupby(t["T"].dt.date).net.sum()
    by_sym = t.groupby("sym").net.agg(["count", "sum"]).sort_values("sum")
    tot = t.net.sum()
    return {
        "n": int(len(t)), "net_sum_pct": round(100 * tot, 3), "mean_bp": round(1e4 * t.net.mean(), 2),
        "gross_mean_bp": round(1e4 * t.gross.mean(), 2), "gross_median_bp": round(1e4 * t.gross.median(), 2),
        "pf": round(pos / neg, 3) if neg > 0 else None,
        "net_ex_top3_pct": round(100 * n.iloc[3:].sum(), 3), "win_rate": round(float((t.net > 0).mean()), 3),
        "gross_win_rate": round(float((t.gross > 0).mean()), 3),
        "days": int(len(day)), "day_t": round(float(day.mean() / day.std() * np.sqrt(len(day))), 2) if len(day) > 2 else None,
        "n_long": int((t.side > 0).sum()), "n_short": int((t.side < 0).sum()),
        "gross_mean_bp_long": round(1e4 * t.gross[t.side > 0].mean(), 2) if (t.side > 0).any() else None,
        "gross_mean_bp_short": round(1e4 * t.gross[t.side < 0].mean(), 2) if (t.side < 0).any() else None,
        "by_year": {str(y): {"n": int(len(g)), "net_sum_pct": round(100 * g.net.sum(), 3),
                             "gross_mean_bp": round(1e4 * g.gross.mean(), 2)} for y, g in t.groupby(t["T"].dt.year)},
        "by_interval_h": {str(y): {"n": int(len(g)), "gross_mean_bp": round(1e4 * g.gross.mean(), 2)}
                          for y, g in t.groupby("interval_h")},
        "n_symbols": int(t.sym.nunique()),
        "top_symbols": {s: [int(r["count"]), round(100 * r["sum"], 3)] for s, r in by_sym.tail(5).iloc[::-1].iterrows()},
        "worst_symbols": {s: [int(r["count"]), round(100 * r["sum"], 3)] for s, r in by_sym.head(5).iterrows()},
        "top_symbol_trade_share": round(float(t.sym.value_counts(normalize=True).iloc[0]), 3),
        "top3_trades_pct": [round(100 * x, 3) for x in n.iloc[:3]],
        "top3_days_pct": {str(d): round(100 * v, 3) for d, v in day.sort_values(ascending=False).head(3).items()},
        "passes_bar": bool(len(t) >= 50 and tot > 0 and neg > 0 and pos / neg > 1.2 and n.iloc[3:].sum() > 0),
    }


def main():
    split = sys.argv[1]
    keys = list(CFGS) if split == "train" else [sys.argv[2]]
    if split == "validation":
        tr = json.loads((ROOT / "research/observations/evidence_fundclock_train.json").read_text())
        assert tr["selected_config"] == keys[0], "validation only for the config selected on train"
    ev = events(split)
    res, skipped = simulate(ev, keys)
    pr = ev.dropna(subset=["f_prev"])
    out = {
        "hypothesis": PRE["hypothesis"], "split": split, "window": SPLITS[split], "is_synthetic": False,
        "preregistration": "reports/hypotheses/fundclock_preregistration.json",
        "round_trip_cost": RT, "n_settlement_events": int(len(ev)), "n_symbols": int(ev.sym.nunique()),
        "events_by_interval_h": {str(k): int(v) for k, v in ev.interval_h.value_counts().items()},
        "diag_corr_fprev_f": round(float(np.corrcoef(pr.f_prev, pr.rate)[0, 1]), 3),
        "diag_share_abs_f_ge_0.03pct": round(float((ev.rate.abs() >= 0.0003).mean()), 4),
        "diag_share_abs_f_ge_0.10pct": round(float((ev.rate.abs() >= 0.0010).mean()), 4),
        "skipped_missing_bars": skipped,
        "configs": {k: stats(res[k]) for k in keys},
    }
    if split == "train":
        passing = [k for k in keys if out["configs"][k].get("passes_bar")]
        out["passing_configs"] = passing
        out["selected_config"] = (max(passing, key=lambda k: (out["configs"][k]["net_sum_pct"], out["configs"][k]["pf"]))
                                  if passing else None)
    tdir = D / "trades"
    tdir.mkdir(exist_ok=True)
    for k in keys:
        res[k].to_csv(tdir / f"{split}_{k}.csv", index=False)
    p = ROOT / f"research/observations/evidence_fundclock_{split}.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    for k in keys:
        s = out["configs"][k]
        print(k, {x: s.get(x) for x in ("n", "net_sum_pct", "mean_bp", "gross_mean_bp", "pf", "net_ex_top3_pct", "day_t", "passes_bar")})
    print("selected", out.get("selected_config"))


if __name__ == "__main__":
    main()
