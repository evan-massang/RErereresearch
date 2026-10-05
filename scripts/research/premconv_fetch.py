"""H-PREMCONV step 2: fetch 1m premiumIndex, perp and spot klines for each universe symbol-month and keep only
compact event windows (no zips/CSVs are written to disk).

For every symbol-month in data/raw/web/binance_prem/universe.json:
  - download futures/um premiumIndexKlines 1m, futures/um klines 1m, spot klines 1m (in memory);
  - candidate bars: PI close >= 0.40% or BAS close >= 0.40% (below the smallest pre-registered bound, 0.52%);
  - keep rows from each candidate bar through +24h+10min (the longest pre-registered hold plus fill latency),
    with the previous bar's signals stored on each row (for the onset test);
  - windows running past month end pull rows from the next month (fetched as a 'tail' month if needed), except at
    split boundaries (2025-06 -> train ends; 2026-03 -> holdout never fetched);
  - daily quote volumes (spot, perp) from 1d archive klines for the month and the month before (ADV tiers);
  - funding prints for the month.
Writes data/raw/web/binance_prem/{win,daily,funding}/<PERP>.parquet and fetch_log.json.
    python scripts/research/premconv_fetch.py [--workers 8]
"""
import argparse
import io
import json
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/binance_prem"
DV = "https://data.binance.vision/data"
CAND = 0.004
WIN_MIN = 24 * 60 + 10
STOP_AFTER = {"2025-06", "2026-03"}  # no tail month across a split boundary
LAST_MONTH = "2026-03"


def get_csv(cl, url):
    for a in range(5):
        try:
            r = cl.get(url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                raw = z.read(z.namelist()[0])
            df = pd.read_csv(io.BytesIO(raw), header=None, usecols=list(range(8)), dtype=str)
            df = df[df[0].str[0].str.isdigit()].astype(float)
            ts = df[0].to_numpy()
            ts = np.where(ts > 1e14, ts // 1000, ts)  # spot files from 2025 use microseconds
            df[0] = (ts // 60000).astype(np.int64)  # minute index since epoch
            return df
        except Exception as e:  # noqa
            err = e
            time.sleep(3 * (a + 1))
    raise RuntimeError(f"{url}: {err}")


def month_frame(cl, perp, spot, mult, mo):
    pi = get_csv(cl, f"{DV}/futures/um/monthly/premiumIndexKlines/{perp}/1m/{perp}-1m-{mo}.zip")
    fk = get_csv(cl, f"{DV}/futures/um/monthly/klines/{perp}/1m/{perp}-1m-{mo}.zip")
    sk = get_csv(cl, f"{DV}/spot/monthly/klines/{spot}/1m/{spot}-1m-{mo}.zip")
    missing = [n for n, d in (("pi", pi), ("perp", fk), ("spot", sk)) if d is None]
    if missing:
        return None, missing
    start = pd.Period(mo, "M").start_time.value // 60_000_000_000
    end = (pd.Period(mo, "M") + 1).start_time.value // 60_000_000_000
    idx = np.arange(start, end, dtype=np.int64)
    f = pd.DataFrame({"m": idx})
    f = f.merge(pi[[0, 4]].rename(columns={0: "m", 4: "pi"}), on="m", how="left")
    f = f.merge(fk[[0, 1, 2, 4, 7]].rename(columns={0: "m", 1: "fo", 2: "fh", 4: "fc", 7: "fqv"}), on="m", how="left")
    s = sk[[0, 1, 4, 7]].rename(columns={0: "m", 1: "so", 4: "sc", 7: "sqv"})
    s["so"] *= mult
    s["sc"] *= mult
    f = f.merge(s, on="m", how="left")
    f = f.drop_duplicates("m")
    f["bas"] = f.fc / f.sc - 1
    return f, []


def daily_qv(cl, perp, spot, mo):
    out = []
    for mk, sym, path in (("fut", perp, "futures/um"), ("spot", spot, "spot")):
        d = get_csv(cl, f"{DV}/{path}/monthly/klines/{sym}/1d/{sym}-1d-{mo}.zip")
        if d is not None:
            out.append(pd.DataFrame({"day": d[0] // 1440, "market": mk, "qv": d[7]}))
    return pd.concat(out) if out else None


def funding(cl, perp, mo):
    url = f"{DV}/futures/um/monthly/fundingRate/{perp}/{perp}-fundingRate-{mo}.zip"
    for a in range(5):
        try:
            r = cl.get(url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                d = pd.read_csv(z.open(z.namelist()[0]))
            return pd.DataFrame({"t_ms": d.iloc[:, 0].astype(np.int64), "rate": d.iloc[:, -1].astype(float)})
        except Exception:
            time.sleep(3 * (a + 1))
    raise RuntimeError(url)


def do_symbol(perp, spot, mult, months):
    log = {"perp": perp, "months": {}, "rows": 0}
    if (OUT / "win" / f"{perp}.parquet").exists():
        log["cached"] = True
        return log
    keep, daily, fund = [], [], []
    with httpx.Client(timeout=120) as cl:
        todo = sorted(months)
        pend_end = -1  # minute index until which rows must be kept (windows spilling over month end)
        prev_last = None  # last row of the previous month (for prev-signal of the first bar)
        i = 0
        while i < len(todo):
            mo = todo[i]
            tail = mo not in months
            f, missing = month_frame(cl, perp, spot, mult, mo)
            log["months"][mo] = {"tail": tail, "missing": missing}
            if f is None:
                pend_end, prev_last = -1, None
                i += 1
                continue
            f["pi_prev"] = f.pi.shift(1)
            f["bas_prev"] = f.bas.shift(1)
            if prev_last is not None:
                f.loc[f.index[0], ["pi_prev", "bas_prev"]] = prev_last
            prev_last = [f.pi.iloc[-1], f.bas.iloc[-1]]
            mask = np.zeros(len(f), bool)
            m0 = f.m.iloc[0]
            if pend_end >= m0:
                mask[: min(len(f), pend_end - m0 + 1)] = True
            if not tail:
                cand = np.flatnonzero(((f.pi >= CAND) | (f.bas >= CAND)).to_numpy())
                # include the candidate bar and the following WIN_MIN bars
                diff = np.zeros(len(f) + 1, int)
                np.add.at(diff, cand, 1)
                np.add.at(diff, np.minimum(cand + WIN_MIN + 1, len(f)), -1)
                mask |= np.cumsum(diff[:-1]) > 0
                pend_end = int(cand.max() + m0 + WIN_MIN) if len(cand) else -1
                if pend_end < f.m.iloc[-1]:
                    pend_end = -1
                log["months"][mo]["cand_bars"] = int(len(cand))
                log["months"][mo]["median_bas"] = float(np.nanmedian(f.bas))
                log["months"][mo]["median_pi"] = float(np.nanmedian(f.pi))
                d = daily_qv(cl, perp, spot, mo)
                dp = daily_qv(cl, perp, spot, str(pd.Period(mo, "M") - 1))
                daily += [x for x in (d, dp) if x is not None]
                fr = funding(cl, perp, mo)
                if fr is not None:
                    fund.append(fr)
            else:
                pend_end = -1
            keep.append(f[mask].copy())
            nxt = str(pd.Period(mo, "M") + 1)
            if pend_end >= 0 and mo not in STOP_AFTER and nxt not in todo and nxt <= LAST_MONTH:
                todo.insert(i + 1, nxt)
                fr = funding(cl, perp, nxt)
                if fr is not None:
                    fund.append(fr)
            if mo in STOP_AFTER:
                prev_last = None
            i += 1
    w = pd.concat(keep, ignore_index=True) if keep else pd.DataFrame()
    if len(w):
        w = w.drop_duplicates("m").sort_values("m")
        w = w.drop(columns=["fqv", "sqv"])
        w["m"] = w["m"].astype("int32")
        for c in w.columns:
            if c != "m":
                w[c] = w[c].astype("float32")
    for sub in ("win", "daily", "funding"):
        (OUT / sub).mkdir(exist_ok=True)
    if daily:
        pd.concat(daily).drop_duplicates(["day", "market"]).to_parquet(OUT / "daily" / f"{perp}.parquet", index=False)
    if fund:
        pd.concat(fund).drop_duplicates("t_ms").to_parquet(OUT / "funding" / f"{perp}.parquet", index=False)
    w.to_parquet(OUT / "win" / f"{perp}.parquet", index=False, compression="zstd")
    log["rows"] = int(len(w))
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    uni = json.loads((OUT / "universe.json").read_text())["data"]
    sym = {}
    for mo, mem in uni.items():
        for x in mem:
            sym.setdefault(x["perp"], {"spot": x["spot"], "mult": x["mult"], "months": set()})["months"].add(mo)
    if a.only:
        sym = {k: v for k, v in sym.items() if k in a.only}
    lp = OUT / "fetch_log.json"
    logs = json.loads(lp.read_text()) if lp.exists() else {}
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(do_symbol, k, v["spot"], v["mult"], v["months"]): k for k, v in sym.items()}
        for n, fu in enumerate(as_completed(futs)):
            k = futs[fu]
            try:
                lg = fu.result()
                if not lg.get("cached"):
                    logs[k] = lg
                    lp.write_text(json.dumps(logs))
                print(n, k, lg.get("rows"), flush=True)
            except Exception as e:
                print("FAIL", k, e, flush=True)
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
