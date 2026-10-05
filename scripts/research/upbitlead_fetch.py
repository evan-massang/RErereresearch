"""H-UPBITLEAD data fetch (pre-registered: reports/hypotheses/upbitlead_preregistration.json).

- Upbit KRW-X and KRW-USDT 1m candles, 2025-03-24 .. 2026-03-31 (to=2026-04-01T00:00:00Z is exclusive:
  holdout never requested), unauthenticated REST, shared limiter <= 8 req/s.
  -> data/raw/web/upbitlead/upbit/<COIN>.parquet  (minute, o,h,l,c KRW, notional KRW)
- Binance USDT-M perp 1m klines + fundingRate, monthly archives 2025-03 .. 2026-03 (data.binance.vision).
  -> data/raw/web/upbitlead/binance/<SYM>.parquet, funding/<SYM>.parquet
Zips parsed in memory; only compact parquet is kept. Stops if disk free < 2.5 GB or cache > 600 MB.
"""
from __future__ import annotations

import io, json, shutil, sys, threading, time, zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/upbitlead"
UP, BN, FD = OUT / "upbit", OUT / "binance", OUT / "funding"
for d in (UP, BN, FD):
    d.mkdir(parents=True, exist_ok=True)
START = "2025-03-24T00:00:00"
END = "2026-04-01T00:00:00Z"  # exclusive; holdout guard
MONTHS = [f"2025-{m:02d}" for m in range(3, 13)] + [f"2026-{m:02d}" for m in range(1, 4)]
_lock = threading.Lock()
_last = [0.0]


def guard():
    free = shutil.disk_usage(ROOT).free
    used = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    if free < 2.5e9 or used > 600e6:
        print(f"STOP: free={free/1e9:.2f}GB cache={used/1e6:.0f}MB", flush=True)
        sys.exit(2)


def limited_get(sess, url, params):
    for a in range(10):
        with _lock:
            w = _last[0] + 0.11 - time.time()
            if w > 0:
                time.sleep(w)
            _last[0] = time.time()
        try:
            r = sess.get(url, params=params, timeout=30)
        except Exception:
            time.sleep(2 + a); continue
        if r.status_code == 429:
            time.sleep(1 + a); continue
        if r.status_code >= 500:
            time.sleep(2 + a); continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"failed {params}")


def fetch_upbit(coin):
    f = UP / f"{coin}.parquet"
    if f.exists():
        return coin, "cached"
    guard()
    s = requests.Session()
    to, rows, start_ms = END, [], int(datetime.fromisoformat(START).replace(tzinfo=timezone.utc).timestamp() * 1000)
    while True:
        js = limited_get(s, "https://api.upbit.com/v1/candles/minutes/1", {"market": f"KRW-{coin}", "count": 200, "to": to})
        if not js:
            break
        for c in js:
            t = int(datetime.fromisoformat(c["candle_date_time_utc"]).replace(tzinfo=timezone.utc).timestamp())
            rows.append((t // 60, c["opening_price"], c["high_price"], c["low_price"], c["trade_price"], c["candle_acc_trade_price"]))
        oldest = js[-1]["candle_date_time_utc"]
        if datetime.fromisoformat(oldest).replace(tzinfo=timezone.utc).timestamp() * 1000 <= start_ms:
            break
        to = oldest + "Z"
    df = pd.DataFrame(rows, columns=["minute", "o", "h", "l", "c", "krw"]).drop_duplicates("minute").sort_values("minute")
    df = df[df.minute >= start_ms // 60000]
    df = df[["minute", "c", "krw"]].astype({"minute": "int32", "c": "float64", "krw": "float32"})
    df.to_parquet(f, compression="zstd", index=False)
    return coin, len(df)


def bn_zip(s, url):
    for a in range(5):
        try:
            r = s.get(url, timeout=120)
        except Exception:
            time.sleep(3 + a); continue
        if r.status_code == 404:
            return None
        if r.status_code == 200:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            df = pd.read_csv(z.open(z.namelist()[0]), header=None, low_memory=False)
            if not str(df.iloc[0, 0]).lstrip("-").isdigit():
                df = df.iloc[1:]
            return df
        time.sleep(3 + a)
    raise RuntimeError(url)


def fetch_binance(sym):
    f, g = BN / f"{sym}.parquet", FD / f"{sym}.parquet"
    if f.exists() and g.exists():
        return sym, "cached"
    guard()
    s = requests.Session()
    ks, fs = [], []
    for m in MONTHS:
        k = bn_zip(s, f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/1m/{sym}-1m-{m}.zip")
        if k is not None:
            k = k[[0, 1, 2, 3, 4, 7]].astype(float)
            k.columns = ["t", "o", "h", "l", "c", "qv"]
            ks.append(k)
        fr = bn_zip(s, f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip")
        if fr is not None:
            fr = fr[[0, 2]].astype(float); fr.columns = ["t", "rate"]; fs.append(fr)
    k = pd.concat(ks)
    k["minute"] = (k.t // 60000).astype("int32")
    k = k.drop(columns="t").drop_duplicates("minute").sort_values("minute")
    k = k[k.minute < int(datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp()) // 60]
    k.astype({"o": "float32", "h": "float32", "l": "float32", "c": "float32", "qv": "float32"}).to_parquet(f, compression="zstd", index=False)
    fd = pd.concat(fs) if fs else pd.DataFrame(columns=["t", "rate"])
    fd.to_parquet(g, index=False)
    return sym, len(k)


def main():
    sel = json.loads((OUT / "selection_202503.json").read_text())["coin_list"]
    coins = ["USDT"] + [c["coin"] for c in sel]
    syms = [c["binance"] for c in sel]
    with ThreadPoolExecutor(3) as ex:
        bfut = [ex.submit(fetch_binance, s) for s in syms]
        with ThreadPoolExecutor(3) as ex2:
            for r in ex2.map(fetch_upbit, coins):
                print("upbit", r, time.strftime("%H:%M:%S"), flush=True)
        for b in bfut:
            print("binance", b.result(), flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
