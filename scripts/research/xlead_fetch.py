"""H-XLEAD data fetch: Binance USD-M futures 1m klines from the public archive (data.binance.vision).

Universe (pre-declared before looking at any returns; selection rule):
  leaders: BTCUSDT, ETHUSDT, SOLUSDT
  memes:   Binance USD-M perps in the CoinGecko "meme" category that are (or were) also listed as Hyperliquid
           perps (HL `meta` universe, delisted included, checked 2026-10-05) and whose Binance perp was listed
           on or before 2024-12-31 (so each has >= 6 months of train). Fixed list of 22 below.
Months: 2024-01 .. 2026-03 only. Holdout (2026-04 onward) is NEVER downloaded.
Each monthly zip is reduced to a parquet of (open_time, open, high, low, close, quote_volume, trades) and the zip is
deleted to save disk; URL, byte size and sha256 of every zip are kept in manifest.json.
"""
import hashlib, io, json, os, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import pandas as pd

OUT = "/home/user/RErereresearch/data/raw/web/binance_fut/xlead"
LEADERS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
MEMES = ["DOGEUSDT", "1000PEPEUSDT", "1000SHIBUSDT", "1000BONKUSDT", "1000FLOKIUSDT", "WIFUSDT", "BOMEUSDT",
         "MEMEUSDT", "PEOPLEUSDT", "MYROUSDT", "POPCATUSDT", "TURBOUSDT", "BRETTUSDT", "MEWUSDT", "NEIROUSDT",
         "GOATUSDT", "MOODENGUSDT", "PNUTUSDT", "CHILLGUYUSDT", "PENGUUSDT", "FARTCOINUSDT", "DOGSUSDT"]
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13)
          if f"{y}-{m:02d}" <= "2026-03"]
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
        "tb_base", "tb_quote", "ignore"]


def fetch(sym, month):
    path = f"{OUT}/{sym}/{sym}-1m-{month}.parquet"
    if os.path.exists(path):
        return sym, month, "cached", None
    url = f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/1m/{sym}-1m-{month}.zip"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                raw = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return sym, month, "missing", None
            time.sleep(2 + attempt * 3)
        except Exception:
            time.sleep(2 + attempt * 3)
    else:
        return sym, month, "error", None
    z = zipfile.ZipFile(io.BytesIO(raw))
    with z.open(z.namelist()[0]) as f:
        first = f.readline().decode()
    header = 0 if first.startswith("open_time") else None
    with z.open(z.namelist()[0]) as f:
        df = pd.read_csv(f, header=header, names=None if header == 0 else COLS)
    df.columns = COLS
    df = df[["open_time", "open", "high", "low", "close", "quote_volume", "trades"]].astype(
        {"open_time": "int64", "open": "float64", "high": "float64", "low": "float64", "close": "float64",
         "quote_volume": "float64", "trades": "int64"})
    os.makedirs(f"{OUT}/{sym}", exist_ok=True)
    df.to_parquet(path, index=False)
    return sym, month, "ok", {"url": url, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                              "rows": len(df), "fetched_at": time.time()}


def main():
    os.makedirs(OUT, exist_ok=True)
    mpath = f"{OUT}/manifest.json"
    man = json.load(open(mpath)) if os.path.exists(mpath) else {"files": {}, "missing": []}
    jobs = [(s, m) for s in LEADERS + MEMES for m in MONTHS]
    with ThreadPoolExecutor(6) as ex:
        for sym, month, st, info in ex.map(lambda a: fetch(*a), jobs):
            if st == "ok":
                man["files"][f"{sym}-{month}"] = info
            elif st == "missing":
                if f"{sym}-{month}" not in man["missing"]:
                    man["missing"].append(f"{sym}-{month}")
            elif st == "error":
                print("ERROR", sym, month, file=sys.stderr)
    man["universe_rule"] = __doc__
    json.dump(man, open(mpath, "w"), indent=1)
    print(len(man["files"]), "files;", len(man["missing"]), "missing")


if __name__ == "__main__":
    main()
