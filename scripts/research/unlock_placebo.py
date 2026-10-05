"""H-UNLOCK post-hoc diagnostics (NOT part of the pre-registered bar; written after validation ran).

Separates the unlock effect from generic 'short alts' beta:
 (a) alt basket: equal-weight short of every archive USDT perp (listed >= 60 d before entry, bars at entry and exit),
     same entry/exit opens, no stop, no costs.
 (b) same-coin placebo: same symbol, same window length, shifted 60 days earlier, gross, no stop.
Excess = trade gross (with stop) - basket short.
"""
import json, glob, pathlib, datetime
import pandas as pd, numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[2]
U = ROOT / "data/raw/web/unlock"; M = ROOT / "data/raw/web/momentum/klines"
DAYMS = 86400000; HOLD = pd.Timestamp("2026-04-01").value // (86400 * 10**9)
EXCL = ("BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD", "USDC")
opens = {}
for f in glob.glob(str(M / "*.parquet")):
    s = pathlib.Path(f).stem
    if "_" in s or s.startswith(EXCL): continue
    k = pd.read_parquet(f, columns=["open_time", "open"]); k["day"] = k.open_time // DAYMS
    k = k[k.day < HOLD]
    if len(k): opens[s] = k.set_index("day").open
O = pd.DataFrame(opens)
first = O.apply(lambda c: c.first_valid_index())

def basket(e, x):
    if e not in O.index or x not in O.index: return np.nan, 0
    elig = first[first <= e - 60].index
    r = (O.loc[x, elig] / O.loc[e, elig] - 1).dropna()
    return -r.mean(), len(r)

def same_coin(s, e, x, shift=60):
    if s not in O: return np.nan
    c = O[s]; e2, x2 = e - shift, x - shift
    if e2 in c.index and x2 in c.index and pd.notna(c[e2]) and pd.notna(c[x2]): return -(c[x2] / c[e2] - 1)
    return np.nan

def diag(df, k_days, m_days):
    out = []
    for t in df.itertuples():
        T = pd.Timestamp(t.unlock_date).value // (86400 * 10**9)
        e, x = T - k_days, T + m_days
        b, nb = basket(e, x)
        out.append(dict(basket_short=b, n_basket=nb, placebo_same_coin=same_coin(t.symbol, e, x), gross=t.gross, net=t.net))
    d = pd.DataFrame(out); d["excess_vs_basket"] = d.gross - d.basket_short
    bp = lambda v: round(1e4 * np.nanmean(v), 1)
    ex = d.excess_vs_basket.dropna()
    return dict(n=len(d), gross_mean_bp=bp(d.gross), basket_short_mean_bp=bp(d.basket_short),
                excess_vs_basket_mean_bp=bp(d.excess_vs_basket), excess_vs_basket_median_bp=round(1e4 * ex.median(), 1),
                excess_t=round(ex.mean() / (ex.std(ddof=1) / np.sqrt(len(ex))), 2),
                excess_win=round((ex > 0).mean(), 3),
                placebo_same_coin_shift60_mean_bp=bp(d.placebo_same_coin),
                placebo_same_coin_median_bp=round(1e4 * d.placebo_same_coin.median(), 1),
                net_minus_basket_mean_bp=bp(d.net - d.basket_short))

res = {}
for split, key in (("train", "k30_m3"), ("validation", "k30_m3"), ("train", "k14_m3"), ("train", "k7_m3"), ("train", "k3_m0")):
    df = pd.read_parquet(U / f"trades_{split}_{key}.parquet")
    k_days = int(key.split("_")[0][1:]); m_days = int(key.split("_m")[1])
    r = diag(df, k_days, m_days)
    df2 = df.copy(); df2["yr"] = df2.unlock_date.str[:4]
    r["by_year"] = {y: diag(g, k_days, m_days) for y, g in df2.groupby("yr")}
    res[f"{split}_{key}"] = r
    print(split, key, {k: v for k, v in r.items() if k != "by_year"})
    for y, v in r["by_year"].items(): print("   ", y, v["n"], v["gross_mean_bp"], v["basket_short_mean_bp"], v["excess_vs_basket_mean_bp"], v["excess_t"])
json.dump(dict(hypothesis="H-UNLOCK", kind="post-hoc diagnostic, not pre-registered, does not change selection",
               generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), results=res,
               finding_type="observed (descriptive diagnostic)"),
          open(ROOT / f"research/observations/evidence_unlock_placebo_{datetime.date.today():%Y%m%d}.json", "w"), indent=1, default=float)
