"""H-ITSM simulation (pre-registration: reports/hypotheses/itsm_preregistration.json).

    python scripts/research/itsm_sim.py train                 # all 12 configs on train
    python scripts/research/itsm_sim.py validation <CONFIG>   # once, the selected config

Point in time: the signal window ends at or before the trade window starts; sigma uses only the 30 previous days.
Trades enter at the open of the first 15m bar of the trade window and exit at the close of its last bar, taker.
"""
import json, sys
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/itsm"
PRE = json.loads((ROOT / "reports/hypotheses/itsm_preregistration.json").read_text())
COST = 2 * (4.5 + 2) / 1e4
COST_BN = 2 * (5 + 2) / 1e4
SPLITS = {"train": ("2022-01-01", "2025-06-30"), "validation": ("2025-07-01", "2026-03-31")}
NY = ZoneInfo("America/New_York")
M15 = 15 * 60 * 1000


def hm(s):
    h, m = s.split(":"); return (int(h) * 60 + int(m)) * 60000


def utc_windows(day, spec):
    """Return (start_ms, end_ms) list for a window spec on a given UTC day."""
    d0 = int(pd.Timestamp(day).value // 10**6)
    if spec.startswith("US_sig") or spec.startswith("US_trd"):
        lo, hi = ("09:30", "10:00") if spec == "US_sig" else ("15:30", "16:00")
        a = pd.Timestamp(f"{day} {lo}", tz=NY).tz_convert("UTC"); b = pd.Timestamp(f"{day} {hi}", tz=NY).tz_convert("UTC")
        return int(a.value // 10**6), int(b.value // 10**6)
    a, b = spec.split("-")
    return d0 + hm(a), d0 + (hm(b) if b != "24:00" else 86400000)


CFG = {
    "F30_L30": (["00:00-00:30"], "23:30-24:00"),
    "F60_L60": (["00:00-01:00"], "23:00-24:00"),
    "PF": (["00:15-01:15"], "23:00-24:00"),
    "PL": (["23:00-23:30"], "23:30-24:00"),
    "BOTH": (["00:00-00:30", "23:00-23:30"], "23:30-24:00"),
    "US": (["US_sig"], "US_trd"),
}


def window_returns(bars, days, spec):
    """bars: Series o,c indexed by t ms. Returns array of window returns per day (nan if any bar missing)."""
    o, c = bars["o"], bars["c"]
    out = np.full(len(days), np.nan)
    for i, d in enumerate(days):
        a, b = utc_windows(d, spec)
        ts = range(a, b, M15)
        if all(t in o.index for t in ts):
            out[i] = c[b - M15] / o[a] - 1
    return out


def build():
    uni = json.loads((D / "universe.json").read_text())["data"]
    specs = sorted({s for v in CFG.values() for s in v[0] + [v[1]]})
    rows = []
    for p in sorted((D / "k15").glob("*.parquet")):
        s = p.stem
        df = pd.read_parquet(p).set_index("t")
        df = df[~df.index.duplicated()]
        t0, t1 = pd.to_datetime(df.index.min(), unit="ms").normalize(), pd.to_datetime(df.index.max(), unit="ms").normalize()
        days = [d.strftime("%Y-%m-%d") for d in pd.date_range(t0, t1, freq="D")]
        r = pd.DataFrame({"day": days, "symbol": s})
        for sp in specs:
            r[sp] = window_returns(df, days, sp)
        r["member"] = [s in uni.get(d[:7], []) for d in days]
        rows.append(r)
    W = pd.concat(rows, ignore_index=True)
    W.to_parquet(D / "window_returns.parquet", index=False)
    return W


def trades(W, name, k):
    sigs, trd = CFG[name]
    W = W.sort_values(["symbol", "day"]).copy()
    ok = W[trd].notna()
    sign = None
    for sp in sigs:
        sd = W.groupby("symbol")[sp].transform(lambda x: x.shift(1).rolling(30, min_periods=20).std())
        okk = W[sp].notna() & (W[sp] != 0)
        if k > 0:
            okk &= sd.notna() & (W[sp].abs() >= k * sd)
        ok &= okk
        sg = np.sign(W[sp])
        if sign is None:
            sign = sg
        else:
            ok &= (sg == sign)
    ok &= W.member
    T = W[ok][["day", "symbol"]].copy()
    T["dir"] = sign[ok]
    T["gross"] = T.dir * W.loc[ok, trd]
    T["net"] = T.gross - COST
    T["net_bn"] = T.gross - COST_BN
    return T


def stats(T):
    if not len(T):
        return {"n": 0}
    n = T.net
    win, loss = n[n > 0].sum(), -n[n < 0].sum()
    daily = T.groupby("day").net.sum()
    yr = T.assign(y=T.day.str[:4]).groupby("y").net.agg(["size", "sum", "mean"])
    return {"n": int(len(T)), "days": int(daily.size), "net_sum_pct": round(100 * n.sum(), 2),
            "mean_bp": round(1e4 * n.mean(), 2), "gross_mean_bp": round(1e4 * T.gross.mean(), 2),
            "mean_bp_binance": round(1e4 * T.net_bn.mean(), 2), "net_sum_pct_binance": round(100 * T.net_bn.sum(), 2),
            "pf": round(win / loss, 3) if loss else None,
            "net_ex_top3_pct": round(100 * (n.sum() - n.nlargest(3).sum()), 2),
            "win_rate": round(float((n > 0).mean()), 3),
            "daily_t": round(float(daily.mean() / daily.std() * np.sqrt(len(daily))), 2) if len(daily) > 2 else None,
            "pos_days": round(float((daily > 0).mean()), 3),
            "long_mean_bp": round(1e4 * T[T.dir > 0].net.mean(), 2), "short_mean_bp": round(1e4 * T[T.dir < 0].net.mean(), 2),
            "n_long": int((T.dir > 0).sum()),
            "by_year": {y: {"n": int(r["size"]), "net_sum_pct": round(100 * r["sum"], 2), "mean_bp": round(1e4 * r["mean"], 2)} for y, r in yr.iterrows()}}


def passes(s):
    return s.get("n", 0) >= 50 and s["net_sum_pct"] > 0 and (s["pf"] or 0) > 1.2 and s["net_ex_top3_pct"] > 0


def run(split, only=None):
    p = D / "window_returns.parquet"
    W = pd.read_parquet(p) if p.exists() else build()
    lo, hi = SPLITS[split]
    out = {}
    for c in PRE["grid"]:
        if only and c["id"] != only:
            continue
        name, k = c["id"].rsplit("_k", 1)
        T = trades(W, name, int(k))
        T = T[(T.day >= lo) & (T.day <= hi)]
        s = stats(T); s["pass"] = passes(s)
        out[c["id"]] = s
        T.to_parquet(D / f"trades_{split}_{c['id']}.parquet", index=False)
        print(c["id"], {k_: s.get(k_) for k_ in ("n", "net_sum_pct", "mean_bp", "gross_mean_bp", "pf", "net_ex_top3_pct", "daily_t", "pos_days", "pass")}, flush=True)
    return out


if __name__ == "__main__":
    split = sys.argv[1]
    only = sys.argv[2] if len(sys.argv) > 2 else None
    if split == "validation" and not only:
        raise SystemExit("validation runs once, on the selected config only")
    res = run(split, only)
    tag = f"_{only}" if only else ""
    (ROOT / f"research/observations/evidence_itsm_{split}{tag}_20261005.json").write_text(json.dumps({
        "hypothesis": "H-ITSM", "split": split, "is_synthetic": False, "modality": "document",
        "source": "data.binance.vision USDT-M 15m klines; own computation", "preregistration": "reports/hypotheses/itsm_preregistration.json",
        "costs": "primary 13 bp round trip (HL 4.5 + 2 slip per side); *_binance 14 bp", "results": res}, indent=1))
