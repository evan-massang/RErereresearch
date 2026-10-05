"""H-LSRATIO data (pre-registration: reports/hypotheses/lsratio_preregistration.json).

1. Universe: each UTC day d in 2023-01-01..2026-03-31, top 30 HL-mapped USDT perps by quote volume d-30..d-1
   (daily archive klines in data/raw/web/momentum/klines, read-only reuse). -> data/raw/web/lsratio/universe.parquet
2. Metrics: data.binance.vision futures/um/daily/metrics for universe symbol-days plus 8 preceding days.
   Each day is reduced to hourly point-in-time samples: for decision hour t, the latest row with
   create_time in [t-30min, t-5min] (a row is known only at create_time + 5 min).
   -> data/raw/web/lsratio/metrics/<SYM>.parquet (zips are never written to disk)
3. Prices: futures/um/monthly/klines/<SYM>/1h for months 2022-12..2026-03. -> data/raw/web/lsratio/k1h/<SYM>.parquet

HOLDOUT GUARD: nothing dated >= 2026-04-01 is requested or kept.
Stops if free disk < 2.5 GB or downloaded bytes > 780 MB.

    python scripts/research/lsratio_fetch.py universe|metrics|klines
"""
import io
import json
import shutil
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/lsratio"
DAILY = ROOT / "data/raw/web/momentum/klines"
HLMETA = ROOT / "data/raw/web/hyperliquid/meta.json"
MURL = "https://data.binance.vision/data/futures/um/daily/metrics/{s}/{s}-metrics-{d}.zip"
KURL = "https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m}.zip"
CUTOFF = pd.Timestamp("2026-04-01")
CUTOFF_MS = 1775001600000
MAX_BYTES = 780e6
MIN_FREE = 2.5e9
EXCL = {"BTCDOMUSDT", "DEFIUSDT", "FOOTBALLUSDT", "BLUEBIRDUSDT", "USDCUSDT"}
STABLE = {"USDC", "TUSD", "BUSD", "FDUSD", "USDP", "USDE", "USD1", "DAI", "PYUSD", "USDT"}
STATE_F = OUT / "fetch_state.json"
lock = threading.Lock()
state = {"bytes": 0, "files": 0, "missing": 0, "failed": 0, "stop": False}
if STATE_F.exists():
    state["bytes"] = json.load(open(STATE_F)).get("bytes_total", 0)
sess = requests.Session()
sess.mount("https://", requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32))


def hl_symbols():
    avail = {f.stem for f in DAILY.glob("*.parquet")}
    out = set()
    for x in json.load(open(HLMETA))["meta"]["universe"]:
        n = x["name"]
        s = ("1000" + n[1:] + "USDT") if (n.startswith("k") and n[1:].isupper()) else n + "USDT"
        if s not in avail and s.startswith("1000") and s[4:] in avail:
            s = s[4:]
        if s in avail and s not in EXCL and s[:-4] not in STABLE and "_" not in s:
            out.add(s)
    return out


def universe():
    cols = {}
    for s in hl_symbols():
        d = pd.read_parquet(DAILY / f"{s}.parquet", columns=["open_time", "quote_volume"])
        d["day"] = pd.to_datetime(d.open_time, unit="ms").dt.normalize()
        d = d[d.day < CUTOFF]
        cols[s] = d.drop_duplicates("day").set_index("day").quote_volume
    qv = pd.DataFrame(cols).sort_index()
    qv = qv.reindex(pd.date_range(qv.index.min(), qv.index.max()))
    v30 = qv.shift(1).rolling(30, min_periods=25).sum()
    rows = []
    for d in pd.date_range("2023-01-01", "2026-03-31"):
        v = v30.loc[d].dropna().sort_values(ascending=False).head(30)
        rows += [(d, s, i + 1) for i, s in enumerate(v.index)]
    U = pd.DataFrame(rows, columns=["day", "symbol", "rank"])
    OUT.mkdir(parents=True, exist_ok=True)
    U.to_parquet(OUT / "universe.parquet")
    print(U.symbol.nunique(), "symbols", len(U), "symbol-days")


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
                state["bytes"] += len(r.content)
                state["files"] += 1
            z = zipfile.ZipFile(io.BytesIO(r.content))
            return z.read(z.namelist()[0]).decode()
        except Exception:
            time.sleep(2 * (a + 1))
    with lock:
        state["failed"] += 1
    print("FAILED", url, file=sys.stderr)
    return None


MCOLS = ["sum_open_interest", "sum_open_interest_value", "count_toptrader_long_short_ratio",
         "sum_toptrader_long_short_ratio", "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]


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
    # hourly point-in-time sample: decision hour t uses latest row with ct in [t-30m, t-5m]
    d["t"] = (d.ct + pd.Timedelta(minutes=5)).dt.ceil("h")
    d = d[d.ct >= d.t - pd.Timedelta(minutes=30)]
    h = d.groupby("t").tail(1)
    return h[["t", "ct"] + MCOLS]


def do_metrics(sym, days):
    dest = OUT / "metrics" / f"{sym}.parquet"
    if dest.exists():
        return sym, "cached"
    frames = []
    for day in days:
        if guard():
            return sym, "stopped (disk/bytes guard)"
        h = metrics_day(sym, day)
        if h is not None and len(h):
            frames.append(h)
    if not frames:
        return sym, "empty"
    d = pd.concat(frames).drop_duplicates("t", keep="last").sort_values("t")
    d = d[d.t < CUTOFF]  # a 23:55 row on 2026-03-31 maps to t=2026-04-01 00:00: dropped (holdout)
    for c in MCOLS:
        d[c] = d[c].astype("float64" if "interest" in c else "float32")
    d.reset_index(drop=True).to_parquet(dest, compression="zstd")
    return sym, len(d)


def metrics():
    U = pd.read_parquet(OUT / "universe.parquet")
    (OUT / "metrics").mkdir(parents=True, exist_ok=True)
    jobs = []
    for s, g in U.groupby("symbol"):
        need = set()
        for d in g.day:
            for k in range(9):
                need.add(d - pd.Timedelta(days=k))
        jobs.append((s, sorted(x for x in need if x < CUTOFF)))
    print(len(jobs), "symbols", sum(len(j[1]) for j in jobs), "symbol-days", flush=True)
    run(do_metrics, jobs)


def do_klines(sym, months):
    dest = OUT / "k1h" / f"{sym}.parquet"
    if dest.exists():
        return sym, "cached"
    frames = []
    for m in months:
        if guard():
            return sym, "stopped (disk/bytes guard)"
        txt = fetch(KURL.format(s=sym, m=m))
        if txt is None:
            continue
        lines = [ln for ln in txt.strip().splitlines() if ln]
        if lines and not lines[0][0].isdigit():
            lines = lines[1:]
        d = pd.read_csv(io.StringIO("\n".join(lines)), header=None, usecols=range(8))
        d.columns = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume"]
        frames.append(d[["open_time", "open", "high", "low", "close", "quote_volume"]])
    if not frames:
        return sym, "empty"
    d = pd.concat(frames).apply(pd.to_numeric, errors="coerce").drop_duplicates("open_time")
    d = d[d.open_time < CUTOFF_MS].sort_values("open_time").reset_index(drop=True)
    d["quote_volume"] = d.quote_volume.astype("float32")
    d.to_parquet(dest, compression="zstd")
    return sym, len(d)


def klines():
    U = pd.read_parquet(OUT / "universe.parquet")
    (OUT / "k1h").mkdir(parents=True, exist_ok=True)
    jobs = []
    for s, g in U.groupby("symbol"):
        m0 = (g.day.min() - pd.Timedelta(days=9)).strftime("%Y-%m")
        m1 = min((g.day.max() + pd.Timedelta(days=2)).strftime("%Y-%m"), "2026-03")
        jobs.append((s, [m.strftime("%Y-%m") for m in pd.period_range(m0, m1, freq="M")]))
    print(len(jobs), "symbols", sum(len(j[1]) for j in jobs), "symbol-months", flush=True)
    run(do_klines, jobs)


def run(fn, jobs):
    with ThreadPoolExecutor(16) as ex:
        for i, (s, st) in enumerate(ex.map(lambda j: fn(*j), jobs)):
            print(i, s, st, f"{state['bytes'] / 1e6:.0f}MB free={shutil.disk_usage(ROOT).free / 1e9:.2f}GB",
                  flush=True)
    print("done", state)
    json.dump({"bytes_total": state["bytes"], **{k: v for k, v in state.items() if k != "bytes"}},
              open(STATE_F, "w"))


if __name__ == "__main__":
    {"universe": universe, "metrics": metrics, "klines": klines}[sys.argv[1]]()
