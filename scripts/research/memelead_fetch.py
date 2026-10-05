"""H-MEMELEAD fetch: Binance USD-M daily aggTrades -> compact 1-second tables (real data, is_synthetic=False).

Pre-registration: reports/hypotheses/memelead_preregistration.json (written before this script ran).
For each sample day and coin: download the zip to a temp dir, reduce to 86,400 rows (see prereg 'processing'),
write data/raw/web/memelead/s1/<SYM>_<day>.parquet, delete the zip. Manifest: data/raw/web/memelead/manifest.jsonl
(url, bytes, sha256, rows). Holdout days (>= 2026-04-01) are refused. Stops if free disk < 2.5 GB.
"""
import hashlib, io, json, os, shutil, subprocess, sys, tempfile, zipfile, pathlib
import numpy as np, pandas as pd

ROOT = pathlib.Path("data/raw/web/memelead")
OUT = ROOT / "s1"
PRE = json.load(open("reports/hypotheses/memelead_preregistration.json"))
COINS = PRE["universe"]["coins_13"]
DAYS = PRE["data"]["sample_days"]
TMP = pathlib.Path(os.environ.get("MEMELEAD_TMP", tempfile.gettempdir()))
MIN_FREE = 2.5e9
BUDGET = 800e6


def free():
    return shutil.disk_usage("/home/user").free


def reduce_day(df, day):
    t0 = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
    ts = df["transact_time"].to_numpy(np.int64) - t0
    keep = (ts >= 0) & (ts < 86_400_000)
    ts, px = ts[keep], df["price"].to_numpy(float)[keep]
    q = df["quantity"].to_numpy(float)[keep]
    ibm = df["is_buyer_maker"].to_numpy()[keep]
    ibm = (ibm == True) | (ibm == "true") | (ibm == "True")
    order = np.argsort(ts, kind="stable"); ts, px, q, ibm = ts[order], px[order], q[order], ibm[order]
    sec = np.arange(86_400)
    res = {"sec": sec.astype(np.int32)}

    def last_at(mask, cut_ms):  # last price of trades in mask with ts <= cut_ms (per second), ffilled
        tt, pp = ts[mask], px[mask]
        idx = np.searchsorted(tt, cut_ms, side="right") - 1
        out = np.where(idx >= 0, pp[np.clip(idx, 0, None)] if len(pp) else np.nan, np.nan)
        tsec = np.where(idx >= 0, (tt[np.clip(idx, 0, None)] // 1000) if len(tt) else -1, -1)
        return out, tsec
    end_ms = sec * 1000 + 999
    at6_ms = sec * 1000 + 600
    res["bid_c"], res["bid_ts"] = last_at(ibm, end_ms)
    res["ask_c"], res["ask_ts"] = last_at(~ibm, end_ms)
    res["bid_6"], _ = last_at(ibm, at6_ms)
    res["ask_6"], _ = last_at(~ibm, at6_ms)
    res["last_c"], _ = last_at(np.ones_like(ibm), end_ms)
    s = ts // 1000
    res["n_trades"] = np.bincount(s, minlength=86_400).astype(np.int32)
    res["quote_vol"] = np.bincount(s, weights=px * q, minlength=86_400)
    out = pd.DataFrame(res)
    for c in ("bid_ts", "ask_ts"):
        out[c] = out[c].astype(np.int32)
    for c in ("bid_c", "ask_c", "bid_6", "ask_6", "last_c", "quote_vol"):
        out[c] = out[c].astype(np.float32)  # 24-bit mantissa: < 0.001 bp relative error
    return out


def main(days=None):
    OUT.mkdir(parents=True, exist_ok=True)
    man = ROOT / "manifest.jsonl"
    done = set()
    total = 0
    if man.exists():
        for l in open(man):
            r = json.loads(l); done.add((r["symbol"], r["day"])); total += r.get("bytes") or 0
    kl = {}
    for c in COINS:
        k = pd.read_parquet(f"data/raw/web/momentum/klines/{c}USDT.parquet")
        kl[c] = pd.to_datetime(k.open_time, unit="ms")
    for day in (days or DAYS):
        assert day < "2026-04-01", "holdout refused"
        for c in COINS:
            sym = c + "USDT"
            if (sym, day) in done:
                continue
            if c == "PUMP" and day < "2025-07-11":
                continue
            if (kl[c] < pd.Timestamp(day)).sum() < 30 or (c == "PUMP" and day < "2025-08-10"):
                continue  # < 30 daily bars before the day: cannot be ranked (leader rule), not used
            if free() < MIN_FREE:
                print("STOP: free disk < 2.5 GB", free()); return
            url = f"https://data.binance.vision/data/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip"
            zp = TMP / f"{sym}-{day}.zip"
            r = subprocess.run(["curl", "-sS", "-f", "--max-time", "600", "-o", str(zp), url])
            if r.returncode != 0 or not zp.exists():
                rec = {"symbol": sym, "day": day, "url": url, "error": f"curl rc {r.returncode}"}
            else:
                b = zp.read_bytes(); total += len(b)
                sha = hashlib.sha256(b).hexdigest()
                with zipfile.ZipFile(io.BytesIO(b)) as z:
                    raw = z.read(z.namelist()[0])
                del b
                first = raw[:200].decode(errors="ignore").splitlines()[0]
                hdr = 0 if first.startswith("agg_trade_id") else None
                names = ["agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id", "transact_time", "is_buyer_maker"]
                df = pd.read_csv(io.BytesIO(raw), header=hdr, names=names if hdr is None else None,
                                 usecols=["price", "quantity", "transact_time", "is_buyer_maker"])
                del raw
                red = reduce_day(df, day)
                red.to_parquet(OUT / f"{sym}_{day}.parquet", compression="zstd", index=False)
                rec = {"symbol": sym, "day": day, "url": url, "bytes": zp.stat().st_size, "sha256": sha,
                       "agg_trades": int(len(df)), "rows": int(len(red)), "is_synthetic": False}
                zp.unlink()
            with open(man, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(day, sym, rec.get("bytes"), rec.get("agg_trades"), rec.get("error", ""), f"total {total/1e6:.0f} MB", flush=True)
            if total > BUDGET:
                print("STOP: download budget reached"); return


if __name__ == "__main__":
    main(sys.argv[1:] or None)
