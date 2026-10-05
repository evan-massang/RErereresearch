"""H-QHOI fetch: Binance USD-M daily aggTrades -> per-quarter-hour taker imbalance sums (real data, is_synthetic=False).

Pre-registration: reports/hypotheses/qhoi_preregistration.json (written before this script ran).
Per coin-day: stream zip to scratch, reduce to 96 rows (buy/sell base qty in the first 10 s and over the whole
quarter hour), write data/raw/web/qhoi/qh/<SYM>_<day>.parquet, delete the zip. Manifest: data/raw/web/qhoi/manifest.jsonl.
Also fetches monthly 1h klines and fundingRate (2025-01..2026-03). Holdout days refused. Stops on budget/disk.
"""
import hashlib, io, json, os, shutil, sys, zipfile, pathlib, concurrent.futures as cf, threading
import numpy as np, pandas as pd, requests

ROOT = pathlib.Path("data/raw/web/qhoi"); QH = ROOT / "qh"; QH.mkdir(parents=True, exist_ok=True)
PRE = json.load(open("reports/hypotheses/qhoi_preregistration.json"))
COINS = PRE["universe"]["coins"]; DAYS = PRE["data"]["sample_days"]
TMP = pathlib.Path(os.environ["QHOI_TMP"]); TMP.mkdir(parents=True, exist_ok=True)
BUDGET, MIN_FREE = 1.2e9, 2.5e9
BASE = "https://data.binance.vision/data/futures/um"
lock = threading.Lock(); used = [0]
MAN = ROOT / "manifest.jsonl"
done = set()
if MAN.exists():
    for l in open(MAN):
        r = json.loads(l); done.add((r["symbol"], r["day"])); used[0] += r.get("bytes", 0)


def read_csv(raw):
    first = raw[:200].split(b"\n")[0]
    hdr = 0 if first.startswith(b"agg_trade_id") else None
    names = None if hdr == 0 else ["agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id", "transact_time", "is_buyer_maker"]
    return pd.read_csv(io.BytesIO(raw), header=hdr, names=names, usecols=["quantity", "transact_time", "is_buyer_maker"])


def reduce_day(df, day):
    t0 = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
    ts = df["transact_time"].to_numpy(np.int64) - t0
    keep = (ts >= 0) & (ts < 86_400_000)
    ts, q = ts[keep], df["quantity"].to_numpy(float)[keep]
    ibm = df["is_buyer_maker"].to_numpy()[keep]
    ibm = (ibm == True) | (ibm == "true") | (ibm == "True")
    qh = ts // 900_000; in10 = (ts % 900_000) < 10_000
    buy = ~ibm
    out = pd.DataFrame({"qh": np.arange(96, dtype=np.int16)})
    out["buy_all"] = np.bincount(qh, weights=q * buy, minlength=96)
    out["sell_all"] = np.bincount(qh, weights=q * ibm, minlength=96)
    out["buy_10"] = np.bincount(qh[in10], weights=(q * buy)[in10], minlength=96)
    out["sell_10"] = np.bincount(qh[in10], weights=(q * ibm)[in10], minlength=96)
    out["n_10"] = np.bincount(qh[in10], minlength=96).astype(np.int32)
    out["n_all"] = np.bincount(qh, minlength=96).astype(np.int32)
    out["is_synthetic"] = False
    return out, int(keep.sum())


def job(sym, day):
    if day >= "2026-04-01": raise SystemExit("holdout refused")
    if sym == "PUMPUSDT" and day < "2025-07-11": return None
    if (sym, day) in done: return None
    if shutil.disk_usage("/home/user").free < MIN_FREE: raise SystemExit("disk < 2.5 GB")
    url = f"{BASE}/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip"
    with lock:
        if used[0] >= BUDGET: return {"symbol": sym, "day": day, "skipped": "budget"}
    r = requests.get(url, timeout=300)
    if r.status_code != 200:
        rec = {"symbol": sym, "day": day, "url": url, "http": r.status_code, "bytes": 0}
    else:
        b = r.content; h = hashlib.sha256(b).hexdigest()
        p = TMP / f"{sym}_{day}.zip"; p.write_bytes(b)
        with zipfile.ZipFile(p) as z: raw = z.read(z.namelist()[0])
        p.unlink(); del b
        out, n = reduce_day(read_csv(raw), day)
        out.to_parquet(QH / f"{sym}_{day}.parquet", index=False)
        rec = {"symbol": sym, "day": day, "url": url, "bytes": int(r.headers.get("Content-Length", len(r.content))), "sha256": h,
               "agg_trades": n, "rows": 96, "is_synthetic": False}
    with lock:
        used[0] += rec["bytes"]
        with open(MAN, "a") as f: f.write(json.dumps(rec) + "\n")
    print(rec["symbol"], rec["day"], rec.get("http", 200), round(used[0] / 1e6), flush=True)
    return rec


def monthly():
    months = [f"{y}-{m:02d}" for y, m in [(2025, i) for i in range(1, 13)] + [(2026, 1), (2026, 2), (2026, 3)]]
    kd = ROOT / "klines1h"; fd = ROOT / "funding"; kd.mkdir(exist_ok=True); fd.mkdir(exist_ok=True)
    for sym in COINS:
        K, F = [], []
        for mo in months:
            for kind, lst in (("klines", K), ("fundingRate", F)):
                url = f"{BASE}/monthly/klines/{sym}/1h/{sym}-1h-{mo}.zip" if kind == "klines" else f"{BASE}/monthly/fundingRate/{sym}/{sym}-fundingRate-{mo}.zip"
                r = requests.get(url, timeout=120)
                if r.status_code != 200: continue
                raw = zipfile.ZipFile(io.BytesIO(r.content)).read(zipfile.ZipFile(io.BytesIO(r.content)).namelist()[0])
                first = raw[:100].split(b"\n")[0]
                if kind == "klines":
                    d = pd.read_csv(io.BytesIO(raw), header=0 if first[:1].isalpha() else None)
                    d = d.iloc[:, :6]; d.columns = ["open_time", "open", "high", "low", "close", "volume"]
                else:
                    d = pd.read_csv(io.BytesIO(raw)); d = d.rename(columns={d.columns[0]: "calc_time", d.columns[-1]: "rate"})[["calc_time", "rate"]]
                lst.append(d)
                with open(ROOT / "manifest_monthly.jsonl", "a") as f:
                    f.write(json.dumps({"symbol": sym, "month": mo, "kind": kind, "url": url, "bytes": len(r.content),
                                        "sha256": hashlib.sha256(r.content).hexdigest(), "is_synthetic": False}) + "\n")
        if K: pd.concat(K).astype(float).drop_duplicates("open_time").sort_values("open_time").to_parquet(kd / f"{sym}.parquet", index=False)
        if F: pd.concat(F).astype(float).drop_duplicates("calc_time").sort_values("calc_time").to_parquet(fd / f"{sym}.parquet", index=False)
        print("monthly", sym, len(K), len(F), flush=True)


if __name__ == "__main__":
    if "monthly" in sys.argv: monthly(); sys.exit()
    jobs = [(s, d) for d in DAYS for s in COINS]
    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda a: job(*a), jobs))
    print("total MB", used[0] / 1e6)
