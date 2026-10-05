"""H-SPOTCARRY-WIDE data fetch from data.binance.vision (public archive, no key).

For every pair in data/raw/web/binance_carry/universe.json (built by spotcarry_universe.py) downloads, for months
<= 2026-03 only (holdout 2026-04+ is never downloaded):
  futures/um/monthly/fundingRate  -> funding/<PERP>.parquet  (t_ms int64, interval_h int8, rate float64)
  futures/um/monthly/klines 1h    -> perp/<PERP>.parquet     (h int32 = open_time hours since epoch, open/high/close float32)
  spot/monthly/klines 1h          -> spot/<SPOT>.parquet     (h int32, close float32, qv float32 = quote volume USDT)
Zips are read in memory and never written to disk. Spot timestamps switch to microseconds in 2025; normalised.
URL, bytes and sha256 per zip are kept in manifest_<dataset>.json.
"""
import hashlib, io, json, os, sys, time, zipfile, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

D = "/home/user/RErereresearch/data/raw/web/binance_carry"
BASE = "https://data.binance.vision/data"


def get(url):
    url = urllib.parse.quote(url, safe=":/")
    for a in range(6):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 + 3 * a)
        except Exception:
            time.sleep(2 + 3 * a)
    return "ERR"


def read_zip(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    with z.open(z.namelist()[0]) as f:
        txt = f.read().decode()
    first = txt.split("\n", 1)[0]
    header = 0 if first[:1].isalpha() else None
    return pd.read_csv(io.StringIO(txt), header=header)


def one(job):
    kind, sym, months = job
    out = f"{D}/{kind}/{sym}.parquet"
    if os.path.exists(out):
        return kind, sym, "cached", {}
    frames, man = [], {}
    for m in months:
        if kind == "funding":
            url = f"{BASE}/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip"
        elif kind == "perp":
            url = f"{BASE}/futures/um/monthly/klines/{sym}/1h/{sym}-1h-{m}.zip"
        else:
            url = f"{BASE}/spot/monthly/klines/{sym}/1h/{sym}-1h-{m}.zip"
        raw = get(url)
        if raw is None or raw == "ERR":
            man[m] = None if raw is None else "ERR"
            continue
        man[m] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        df = read_zip(raw)
        if kind == "funding":
            df = df.iloc[:, :3]; df.columns = ["t_ms", "interval_h", "rate"]
            frames.append(df.astype({"t_ms": "int64", "interval_h": "float64", "rate": "float64"}))
        else:
            df = df.iloc[:, :8]; df.columns = ["ot", "open", "high", "low", "close", "vol", "ct", "qv"]
            ot = df["ot"].astype("int64").to_numpy()
            ot = np.where(ot > 1e14, ot // 1000, ot)  # microseconds -> ms
            h = (ot // 3_600_000).astype("int32")
            if kind == "perp":
                frames.append(pd.DataFrame({"h": h, "open": df["open"].astype("float32"),
                                            "high": df["high"].astype("float32"), "close": df["close"].astype("float32")}))
            else:
                frames.append(pd.DataFrame({"h": h, "close": df["close"].astype("float32"), "qv": df["qv"].astype("float32")}))
    if not frames:
        return kind, sym, "empty", man
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(df.columns[0]).sort_values(df.columns[0])
    if kind == "funding":
        df["interval_h"] = df["interval_h"].fillna(0).astype("int8")
    df.to_parquet(out, index=False, compression="zstd")
    return kind, sym, "ok", man


def main():
    kinds = sys.argv[1:] or ["funding", "perp", "spot"]
    U = json.load(open(f"{D}/universe.json"))["pairs"]
    jobs = []
    for k in kinds:
        os.makedirs(f"{D}/{k}", exist_ok=True)
        seen = set()
        for p in U:
            sym = p["spot"] if k == "spot" else p["perp"]
            ms = p["spot_1h"] if k == "spot" else (p["perp_1h"] if k == "perp" else p["funding"])
            if sym in seen or not ms:
                continue
            seen.add(sym)
            ms = [m for m in ms if m <= "2026-03"]
            if k == "spot" and p["perp_1h"]:   # spot only from 2 months before the perp archive starts
                lo = str(pd.Period(p["perp_1h"][0], "M") - 2)
                ms = [m for m in ms if m >= lo]
            jobs.append((k, sym, ms))
    mans = {k: {} for k in kinds}
    for k in kinds:
        mp = f"{D}/manifest_{k}.json"
        if os.path.exists(mp):
            mans[k] = json.load(open(mp))
    done = 0
    with ThreadPoolExecutor(10) as ex:
        for kind, sym, st, man in ex.map(one, jobs):
            done += 1
            if st != "cached":
                mans[kind][sym] = man
            if done % 50 == 0:
                print(done, "/", len(jobs), flush=True)
                for k in kinds:
                    json.dump(mans[k], open(f"{D}/manifest_{k}.json", "w"))
    for k in kinds:
        json.dump(mans[k], open(f"{D}/manifest_{k}.json", "w"))
    print("done", len(jobs))


if __name__ == "__main__":
    main()
