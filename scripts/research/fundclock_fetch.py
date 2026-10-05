"""H-FUNDCLOCK data: point-in-time universe + funding prints + 1m kline windows around settlements.

Public data only (data.binance.vision). Holdout guard: nothing for months >= 2026-04 is requested.
Pre-registration: reports/hypotheses/fundclock_preregistration.json

Writes data/raw/web/fundclock/:
  um_symbols.json            S3 listing of USDT-M monthly kline symbols
  monthly_vol.parquet        (symbol, month, qv, days) from 1d klines, months 2022-12..2026-02
  universe.json              {month M: [top-20 perps by M-1 quote volume]}
  funding/<SYM>.parquet      (t, rate) settled funding prints, <= 2026-03-31
  win/<SYM>_<YYYY-MM>.parquet 1m bars (open_time, o, h, l, c, qv) within [T-35m, T+35m] of each settlement T in M
  fetch_log.json             bytes downloaded, missing files
Zips are streamed into memory and discarded. Stops if free disk < 2.5 GB.

    python scripts/research/fundclock_fetch.py universe
    python scripts/research/fundclock_fetch.py data
"""
import io
import json
import re
import shutil
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/fundclock"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DV = "https://data.binance.vision/data"
STABLE = {"USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "EUR", "AEUR", "USDE", "PYUSD", "USD1", "UST", "USTC"}
RANK_MONTHS = [str(p) for p in pd.period_range("2022-12", "2026-02", freq="M")]
TRADE_MONTHS = [str(p) for p in pd.period_range("2023-01", "2026-03", freq="M")]
LAST_MONTH = "2026-03"  # holdout guard
TOPN = 20
WIN = 35  # minutes each side of a settlement
MIN_FREE = 2.5e9
BYTES = {"n": 0}


def free_ok():
    return shutil.disk_usage("/").free > MIN_FREE


def s3_prefixes(cl, prefix):
    out, marker = [], ""
    while True:
        r = cl.get(S3, params={"prefix": prefix, "delimiter": "/", "marker": marker})
        r.raise_for_status()
        ps = [x for x in re.findall(r"<Prefix>([^<]+)</Prefix>", r.text) if x != prefix]
        out += ps
        if "<IsTruncated>true</IsTruncated>" not in r.text:
            return [x.rstrip("/").split("/")[-1] for x in out]
        marker = re.search(r"<NextMarker>([^<]+)</NextMarker>", r.text).group(1)


def get_zip_rows(cl, url):
    for a in range(5):
        try:
            r = cl.get(url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            BYTES["n"] += len(r.content)
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                raw = z.read(z.namelist()[0]).decode()
            return [l.split(",") for l in raw.strip().splitlines() if l and l[0].isdigit()]
        except Exception:
            time.sleep(2 * (a + 1))
    return "ERR"


def universe():
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, limits=httpx.Limits(max_connections=24)) as cl:
        p = OUT / "um_symbols.json"
        if not p.exists():
            p.write_text(json.dumps({"fetched_at": time.time(),
                                     "data": s3_prefixes(cl, "data/futures/um/monthly/klines/")}))
        um = json.loads(p.read_text())["data"]
        perps = [s for s in um if s.endswith("USDT") and "_" not in s and s[:-4] not in STABLE]
        print("USDT perps listed", len(perps))
        vp = OUT / "monthly_vol.parquet"
        done = pd.read_parquet(vp) if vp.exists() else pd.DataFrame(columns=["symbol", "month", "qv", "days"])
        have = set(zip(done.symbol, done.month))
        jobs = [(s, m) for s in perps for m in RANK_MONTHS if (s, m) not in have]

        def one(j):
            s, m = j
            return get_zip_rows(cl, f"{DV}/futures/um/monthly/klines/{s}/1d/{s}-1d-{m}.zip")

        rows = []
        with ThreadPoolExecutor(24) as ex:
            for (s, m), res in zip(jobs, ex.map(one, jobs)):
                if res == "ERR":
                    print("ERR", s, m)
                    continue
                rows.append({"symbol": s, "month": m, "qv": sum(float(x[7]) for x in res) if res else 0.0,
                             "days": len(res) if res else 0})
        done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
        done.to_parquet(vp, index=False)
    uni = {}
    for m in RANK_MONTHS:
        c = done[(done.month == m) & (done.days >= 28)].sort_values("qv", ascending=False).head(TOPN)
        uni[str(pd.Period(m, "M") + 1)] = list(c.symbol)
    (OUT / "universe.json").write_text(json.dumps({"rule": "top20 USDT-M perps by prior-month quote volume, >=28 days, no stables",
                                                   "bytes_1d": BYTES["n"], "data": uni}, indent=0))
    syms = sorted({s for v in uni.values() for s in v})
    print("months", len(uni), "unique symbols", len(syms), "1d bytes", BYTES["n"])
    for m in ("2023-01", "2024-06", "2025-07", "2026-03"):
        print(m, uni[m])


def funding(cl, sym):
    p = OUT / "funding" / f"{sym}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    rows = []
    for m in TRADE_MONTHS:
        res = get_zip_rows(cl, f"{DV}/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip")
        if res and res != "ERR":
            rows += [(int(x[0]), float(x[2])) for x in res]
    df = pd.DataFrame(rows, columns=["t", "rate"])
    df["t"] = pd.to_datetime(df.t, unit="ms")
    df = df[df.t < "2026-04-01"].drop_duplicates("t").sort_values("t").reset_index(drop=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return df


def windows(cl, sym, month, fund):
    p = OUT / "win" / f"{sym}_{month}.parquet"
    if p.exists():
        return "cached"
    if month > LAST_MONTH:
        raise RuntimeError("holdout guard")
    rows = get_zip_rows(cl, f"{DV}/futures/um/monthly/klines/{sym}/1m/{sym}-1m-{month}.zip")
    if rows is None:
        return "missing"
    if rows == "ERR":
        return "err"
    a = np.array([[float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])] for x in rows])
    t = a[:, 0].astype("int64")
    t = np.where(t > 10**14, t // 1000, t)  # microsecond timestamps in newer files
    T = fund.t.dt.round("min").values.astype("datetime64[ms]").astype("int64")
    lo = pd.Timestamp(month + "-01").value // 10**6 - WIN * 60000
    hi = (pd.Timestamp(month + "-01") + pd.offsets.MonthBegin(1)).value // 10**6 + WIN * 60000
    T = T[(T >= lo) & (T < hi)]
    keep = np.zeros(len(t), bool)
    for s in T:
        keep |= (t >= s - WIN * 60000) & (t <= s + WIN * 60000)
    df = pd.DataFrame({"t": pd.to_datetime(t[keep], unit="ms"), "o": a[keep, 1], "h": a[keep, 2], "l": a[keep, 3],
                       "c": a[keep, 4], "qv": a[keep, 5].astype("float32")})
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return "ok"


def data():
    uni = json.loads((OUT / "universe.json").read_text())["data"]
    jobs = [(s, m) for m, ss in uni.items() if m <= LAST_MONTH for s in ss]
    syms = sorted({s for s, _ in jobs})
    log = {"missing": [], "err": [], "bytes": 0}
    with httpx.Client(timeout=120, limits=httpx.Limits(max_connections=8)) as cl:
        with ThreadPoolExecutor(8) as ex:
            funds = dict(zip(syms, ex.map(lambda s: funding(cl, s), syms)))
        print("funding done", len(funds), "bytes", BYTES["n"])
        jobs_ok = []
        for i in range(0, len(jobs), 16):
            if not free_ok():
                print("STOP: free disk < 2.5 GB")
                log["stopped_low_disk"] = True
                break
            batch = jobs[i:i + 16]
            with ThreadPoolExecutor(8) as ex:
                res = list(ex.map(lambda j: windows(cl, j[0], j[1], funds[j[0]]), batch))
            for j, r in zip(batch, res):
                if r in ("missing", "err"):
                    log[r].append(j)
            print(i + len(batch), "/", len(jobs), "MB", round(BYTES["n"] / 1e6), flush=True)
    log["bytes"] = BYTES["n"]
    prev = OUT / "fetch_log.json"
    if prev.exists():
        log["bytes_previous_runs"] = json.loads(prev.read_text()).get("bytes", 0)
    prev.write_text(json.dumps(log, indent=0))
    print("missing", log["missing"], "err", log["err"])


if __name__ == "__main__":
    {"universe": universe, "data": data}[sys.argv[1]]()
