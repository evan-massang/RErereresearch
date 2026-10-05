"""H-BLOWOFF features and event counts (NO returns are computed here).

Lead: sources/leads/documented_edges_round13.md idea 1. Universe: the frozen memexs meme list
(reports/hypotheses/memexs_preregistration.json, CoinGecko meme-token rule of listshort_classify.py), Binance USDT-M.

Decision time t = 00:00 UTC of day D. Point in time: only data stamped before t.
  F = sum of Binance funding prints with calc_time in [t-72h, t)       (data/raw/web/momentum/funding)
  O = ln(OI(t) / OI(t-72h)); OI(t) = metrics row sampled for hour t (create_time in [t-30m, t-5m])
      (data/raw/web/lsratio/metrics read-only, plus data/raw/web/blowoff/metrics)
  R = close(D-1) / close(D-4) - 1 (daily archive klines; close(D-1) is the 23:59:59 close before t)
  pX = percentile of X(D) within the coin's own X values on days D-180..D-1 (strictly prior),
       mid-rank for ties; needs >= 90 prior valid values, else NaN (no event).
Eligibility on D (memexs): >= 35 daily bars up to D-1, bar on D-1, 30-day mean quote volume (D-30..D-1) >= $5M.
Data hygiene: PUMPUSDT before 2025-07-10 was a different asset (agent_flush.md) -> dropped; zero-volume
daily bars are treated as missing (stale settlement prints); OI <= 0 is missing.
Arms:  short: pF>=q & pO>=q & pR>=q.   long: pF<=1-q & F<0 & pO>=q & pR<=1-q.
Accepted events: one position per coin; an event is accepted only if >= H days have passed since the coin's
previous accepted entry in that arm (return-free rule; stops do not free the slot early).

    python scripts/research/blowoff_features.py      -> data/raw/web/blowoff/features.parquet
                                                       research/observations/evidence_blowoff_counts.json
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/web/momentum"
MET = [ROOT / "data/raw/web/lsratio/metrics", ROOT / "data/raw/web/blowoff/metrics"]
OUT = ROOT / "data/raw/web/blowoff"
PRE = json.load(open(ROOT / "reports/hypotheses/memexs_preregistration.json"))
MEMES = PRE["universe_classification"]["meme_symbols"]
CUT = pd.Timestamp("2026-04-01")
TRAIN_END, VAL_END = pd.Timestamp("2025-07-01"), CUT
REUSED = {"PUMPUSDT": pd.Timestamp("2025-07-10")}
WIN, MINP = 180, 90


def split_of(d):
    return "train" if d < TRAIN_END else ("validation" if d < VAL_END else "holdout")


def load_daily(s):
    k = pd.read_parquet(RAW / "klines" / f"{s}.parquet")
    k.index = pd.to_datetime(k.open_time, unit="ms").dt.normalize()
    k = k[~k.index.duplicated()]
    k = k[k.index < CUT]
    if s in REUSED:
        k = k[k.index >= REUSED[s]]
    k = k[k.quote_volume > 0]
    full = pd.date_range(k.index.min(), CUT - pd.Timedelta(days=1))
    return k.reindex(full)


def load_funding(s):
    p = RAW / "funding" / f"{s}.parquet"
    if not p.exists():
        return None
    f = pd.read_parquet(p).drop_duplicates("calc_time")
    t = pd.to_datetime(f.calc_time, unit="ms").dt.round("h")
    x = pd.Series(f.last_funding_rate.values, index=t).groupby(level=0).last().sort_index()
    x = x[x.index < CUT]
    if s in REUSED:
        x = x[x.index >= REUSED[s]]
    return x


def load_oi(s):
    fr = [pd.read_parquet(m / f"{s}.parquet", columns=["t", "sum_open_interest"]) for m in MET
          if (m / f"{s}.parquet").exists()]
    if not fr:
        return None
    d = pd.concat(fr).drop_duplicates("t").sort_values("t")
    oi = d.set_index("t").sum_open_interest
    oi = oi[(oi > 0) & (oi.index < CUT)]
    if s in REUSED:
        oi = oi[oi.index >= REUSED[s] + pd.Timedelta(days=1)]
    return oi


def trailing_pct(x):
    """percentile of x[i] within x[i-WIN..i-1] (mid-rank), NaN if < MINP prior valid values."""
    v = x.values
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if np.isnan(v[i]):
            continue
        w = v[max(0, i - WIN):i]
        w = w[~np.isnan(w)]
        if len(w) < MINP:
            continue
        out[i] = ((w < v[i]).sum() + 0.5 * (w == v[i]).sum()) / len(w)
    return pd.Series(out, index=x.index)


def features():
    rows = []
    for s in MEMES:
        if not (RAW / "klines" / f"{s}.parquet").exists():
            continue
        k = load_daily(s)
        fund, oi = load_funding(s), load_oi(s)
        D = k.index
        c = k.close
        R = c.shift(1) / c.shift(4) - 1
        q = k.quote_volume
        adv = q.fillna(0).rolling(30, min_periods=1).sum().shift(1) / 30
        nb = q.notna().cumsum().shift(1)
        elig = (nb >= 35) & q.shift(1).notna() & (adv >= 5e6)
        if fund is not None and len(fund):
            cs = fund.cumsum()
            # sum over [t-72h, t): prints stamped < t minus prints stamped < t-72h
            before = lambda ts: cs.reindex(cs.index.union(ts)).ffill().fillna(0).reindex(ts).values - \
                fund.reindex(ts).fillna(0).values
            nF = fund.groupby(fund.index.normalize()).size()
            F = pd.Series(before(D) - before(D - pd.Timedelta(hours=72)), index=D)
            # require funding coverage: at least one print in the window and the coin had funding history >= 72h
            first = fund.index.min()
            F[D < first + pd.Timedelta(hours=72)] = np.nan
        else:
            F = pd.Series(np.nan, index=D)
        if oi is not None and len(oi):
            o_t = oi.reindex(D)
            o_l = oi.reindex(D - pd.Timedelta(hours=72)).values
            O = np.log(o_t / o_l)
        else:
            O = pd.Series(np.nan, index=D)
        sig30 = np.log(c).diff().rolling(30, min_periods=20).std().shift(1)
        df = pd.DataFrame(dict(sym=s, F=F.values, O=np.asarray(O, float), R=R.values, elig=elig.values,
                               adv=adv.values, sig30=sig30.values), index=D)
        for x in ("F", "O", "R"):
            df["p" + x] = trailing_pct(df[x]).values
        rows.append(df)
    X = pd.concat(rows)
    X.index.name = "day"
    X = X.reset_index()
    X["split"] = X.day.map(split_of)
    return X


def events(X, arm, q):
    if arm == "short":
        m = (X.pF >= q) & (X.pO >= q) & (X.pR >= q)
    else:
        m = (X.pF <= 1 - q) & (X.F < 0) & (X.pO >= q) & (X.pR <= 1 - q)
    return X[m & X.elig.astype(bool)].sort_values(["sym", "day"])


def accept(E, H):
    keep, last = [], {}
    for i, r in E.iterrows():
        if r.sym in last and (r.day - last[r.sym]).days < H:
            continue
        last[r.sym] = r.day
        keep.append(i)
    return E.loc[keep]


if __name__ == "__main__":
    X = features()
    X.to_parquet(OUT / "features.parquet", compression="zstd")
    el = X[X.elig.astype(bool)]
    cov = {sp: dict(eligible_symbol_days=int((el.split == sp).sum()),
                    with_all_three_percentiles=int(((el.split == sp) & el[["pF", "pO", "pR"]].notna().all(1)).sum()),
                    missing_pO=int(((el.split == sp) & el.pO.isna()).sum()),
                    missing_pF=int(((el.split == sp) & el.pF.isna()).sum()),
                    symbols=int(el[el.split == sp].sym.nunique()))
           for sp in ("train", "validation")}
    counts = {}
    for arm in ("short", "long"):
        for q in (0.90, 0.95):
            E = events(X, arm, q)
            E = E[E.split != "holdout"]
            row = {"raw_event_days": {sp: int((E.split == sp).sum()) for sp in ("train", "validation")}}
            for H in (1, 3, 7):
                A = accept(E, H)
                row[f"accepted_H{H}"] = {sp: int((A.split == sp).sum()) for sp in ("train", "validation")}
            row["symbols_with_events"] = {sp: int(E[E.split == sp].sym.nunique()) for sp in ("train", "validation")}
            A3 = accept(E, 3)
            row["top_symbols_validation_H3"] = A3[A3.split == "validation"].sym.value_counts().head(5).to_dict()
            row["events_by_halfyear_H3"] = A3.groupby(A3.day.dt.year.astype(str) + "H" +
                                                       ((A3.day.dt.month > 6) + 1).astype(str)).size().to_dict()
            counts[f"{arm}_q{q:.2f}"] = row
    first_event_day = str(X[X[["pF", "pO", "pR"]].notna().all(1) & X.elig.astype(bool)].day.min().date())
    out = {
        "hypothesis": "H-BLOWOFF", "created": "2026-10-05", "is_synthetic": False,
        "note": "Feature-only event counts (no returns, prices after t, or outcomes used). Holdout (>= 2026-04-01) "
                "not loaded: all caches capped at 2026-03-31.",
        "definitions": __doc__.strip().split("\n\n")[1] if "\n\n" in __doc__ else __doc__,
        "splits": {"train": "<= 2025-06-30", "validation": "2025-07-01..2026-03-31"},
        "first_day_with_all_features": first_event_day,
        "coverage_eligible_symbol_days": cov,
        "counts": counts,
        "sources": ["data/raw/web/momentum/klines (daily, read-only)", "data/raw/web/momentum/funding (read-only)",
                    "data/raw/web/lsratio/metrics (read-only)", "data/raw/web/blowoff/metrics (new, data.binance.vision)"],
    }
    p = ROOT / "research/observations/evidence_blowoff_counts.json"
    json.dump(out, open(p, "w"), indent=1, default=str)
    print(json.dumps({"coverage": cov, "counts": counts}, indent=1, default=str))
