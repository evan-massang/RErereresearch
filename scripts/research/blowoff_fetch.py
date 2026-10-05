"""H-BLOWOFF data fetch (lead: sources/leads/documented_edges_round13.md idea 1).

Downloads ONLY what the read-only caches lack:
  metrics: data.binance.vision futures/um/daily/metrics/<SYM> (5-min OI) for meme symbol-days not already in
           data/raw/web/lsratio/metrics (read-only reuse). Days: from max(first daily bar, 2023-01-01,
           first eligible day - 185 d) to the last eligible day (<= 2026-03-31). Reduced to the same hourly point-in-time sample as
           lsratio_fetch.py (decision hour t uses the latest row with create_time in [t-30m, t-5m]).
           -> data/raw/web/blowoff/metrics/<SYM>.parquet  (zips never written to disk)
  k1h:     futures/um/monthly/klines/<SYM>/1h for months the lsratio/qhoi 1h caches lack, months <= 2026-03.
           -> data/raw/web/blowoff/k1h/<SYM>.parquet
HOLDOUT GUARD: nothing dated >= 2026-04-01 is requested or kept.
Stops if free disk < 2.5 GB or downloaded bytes > 290 MB (budget 300 MB).

    python scripts/research/blowoff_fetch.py plan|metrics|klines
"""
import io, json, shutil, sys, threading, time, zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd, requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/blowoff"
DAILY = ROOT / "data/raw/web/momentum/klines"
LSM = ROOT / "data/raw/web/lsratio/metrics"
LSK = ROOT / "data/raw/web/lsratio/k1h"
QHK = ROOT / "data/raw/web/qhoi/klines1h"
MURL = "https://data.binance.vision/data/futures/um/daily/metrics/{s}/{s}-metrics-{d}.zip"
KURL = "https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m}.zip"
CUTOFF = pd.Timestamp("2026-04-01")
CUTOFF_MS = 1775001600000
MAX_BYTES, MIN_FREE = 290e6, 2.5e9
PRE = json.load(open(ROOT / "reports/hypotheses/memexs_preregistration.json"))
MEMES = PRE["universe_classification"]["meme_symbols"]
STATE_F = OUT / "fetch_state.json"
lock = threading.Lock()
state = {"bytes": 0, "files": 0, "missing": 0, "failed": 0, "stop": False}
if STATE_F.exists():
    state.update(json.load(open(STATE_F))); state["stop"] = False
sess = requests.Session()
sess.mount("https://", requests.adapters.HTTPAdapter(pool_connections=24, pool_maxsize=24))
MCOLS = ["sum_open_interest", "sum_open_interest_value", "count_toptrader_long_short_ratio",
         "sum_toptrader_long_short_ratio", "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]


def guard():
    if shutil.disk_usage(ROOT).free < MIN_FREE or state["bytes"] > MAX_BYTES:
        state["stop"] = True
    return state["stop"]


def fetch(url):
    for a in range(5):
        try:
            r = sess.get(url, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            with lock:
                state["bytes"] += len(r.content); state["files"] += 1
            z = zipfile.ZipFile(io.BytesIO(r.content))
            return z.read(z.namelist()[0]).decode()
        except Exception:
            time.sleep(2 * (a + 1))
    with lock:
        state["failed"] += 1
    print("FAILED", url, file=sys.stderr)
    return None


def daily(s):
    k = pd.read_parquet(DAILY / f"{s}.parquet")
    k.index = pd.to_datetime(k.open_time, unit="ms").dt.normalize()
    k = k[~k.index.duplicated()]
    full = pd.date_range(k.index.min(), min(k.index.max(), CUTOFF - pd.Timedelta(days=1)))
    return k.reindex(full)


def plan():
    jobs_m, jobs_k = [], []
    for s in MEMES:
        if not (DAILY / f"{s}.parquet").exists():
            continue
        k = daily(s)
        q = k.quote_volume
        adv = q.fillna(0).rolling(30, min_periods=1).sum() / 30
        el = (adv >= 5e6) & (q.notna().cumsum() >= 35)
        if not el.any():
            continue
        start = max(k.index.min(), pd.Timestamp("2023-01-01"), el[el].index.min() - pd.Timedelta(days=185))
        end = el[el].index.max()  # no event can occur after the last eligible day
        days = [d for d in pd.date_range(start, end) if pd.notna(q.get(d))]
        have = set()
        if (LSM / f"{s}.parquet").exists():
            have = set(pd.read_parquet(LSM / f"{s}.parquet", columns=["ct"]).ct.dt.normalize())
        need = [d for d in days if d not in have]
        if need:
            jobs_m.append((s, need))
        hk = set()
        for p in (LSK / f"{s}.parquet", QHK / f"{s}.parquet"):
            if p.exists():
                x = pd.read_parquet(p, columns=["open_time"])
                t = pd.to_datetime(x.open_time, unit="ms")
                cnt = t.dt.to_period("M").value_counts()
                hk |= {str(m) for m, c in cnt.items() if c >= 24 * 27}
        months = sorted({str(d.to_period("M")) for d in days})
        nk = [m for m in months if m not in hk]
        if nk:
            jobs_k.append((s, nk))
    return jobs_m, jobs_k


def metrics_day(sym, day):
    txt = fetch(MURL.format(s=sym, d=day.strftime("%Y-%m-%d")))
    if txt is None:
        with lock:
            state["missing"] += 1
        return None
    d = pd.read_csv(io.StringIO(txt))
    if "create_time" not in d.columns:
        return None
    d["ct"] = pd.to_datetime(d.create_time)
    for c in MCOLS:
        d[c] = pd.to_numeric(d[c], errors="coerce") if c in d.columns else np.nan
    d = d.dropna(subset=["ct"]).sort_values("ct")
    d["t"] = (d.ct + pd.Timedelta(minutes=5)).dt.ceil("h")
    d = d[d.ct >= d.t - pd.Timedelta(minutes=30)]
    return d.groupby("t").tail(1)[["t", "ct"] + MCOLS]


def do_metrics(sym, days):
    dest = OUT / "metrics" / f"{sym}.parquet"
    if dest.exists():
        return sym, "cached"
    frames = []
    for day in days:
        if guard():
            return sym, "stopped (guard)"
        h = metrics_day(sym, day)
        if h is not None and len(h):
            frames.append(h)
    if not frames:
        return sym, "empty"
    d = pd.concat(frames).drop_duplicates("t", keep="last").sort_values("t")
    d = d[d.t < CUTOFF]
    d.reset_index(drop=True).to_parquet(dest, compression="zstd")
    return sym, len(d)


def do_klines(sym, months):
    dest = OUT / "k1h" / f"{sym}.parquet"
    if dest.exists():
        return sym, "cached"
    frames = []
    for m in months:
        if guard():
            return sym, "stopped (guard)"
        txt = fetch(KURL.format(s=sym, m=m))
        if txt is None:
            continue
        d = pd.read_csv(io.StringIO(txt), header=None)
        if not str(d.iloc[0, 0]).isdigit():
            d = d.iloc[1:]
        d = d.iloc[:, [0, 1, 2, 3, 4, 7]].astype(float)
        d.columns = ["open_time", "open", "high", "low", "close", "quote_volume"]
        d["open_time"] = d.open_time.astype("int64")
        frames.append(d)
    if not frames:
        return sym, "empty"
    d = pd.concat(frames).drop_duplicates("open_time").sort_values("open_time")
    d = d[d.open_time < CUTOFF_MS]
    d.reset_index(drop=True).to_parquet(dest, compression="zstd")
    return sym, len(d)


def run(fn, jobs):
    with ThreadPoolExecutor(12) as ex:
        for r in ex.map(lambda j: fn(*j), jobs):
            print(r, state["bytes"] / 1e6, "MB", flush=True)
            json.dump({k: v for k, v in state.items()}, open(STATE_F, "w"))
    json.dump(state, open(STATE_F, "w"))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    jm, jk = plan()
    if sys.argv[1] == "plan":
        print("metrics", len(jm), "symbols", sum(len(j[1]) for j in jm), "symbol-days")
        print("klines", len(jk), "symbols", sum(len(j[1]) for j in jk), "symbol-months")
    elif sys.argv[1] == "metrics":
        (OUT / "metrics").mkdir(exist_ok=True); run(do_metrics, jm)
    elif sys.argv[1] == "klines":
        (OUT / "k1h").mkdir(exist_ok=True); run(do_klines, jk)
