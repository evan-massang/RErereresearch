"""H-NIGHT: fetch Binance USDT-M monthly 1h klines + fundingRate (data.binance.vision), months 2022-01..2026-03 only.

Holdout guard: no month >= 2026-04 is requested. Zips are read in memory and not kept; compact parquet per symbol in
data/raw/web/night/. Stops if free disk < 2.5 GB. Real data, is_synthetic = False.
"""
import io, json, shutil, sys, zipfile, urllib.request, urllib.error, pathlib
import pandas as pd

SYMS = ["PUMPUSDT", "DOGEUSDT", "FARTCOINUSDT", "1000SHIBUSDT", "TRUMPUSDT", "1000PEPEUSDT", "PENGUUSDT",
        "WIFUSDT", "1000BONKUSDT", "BTCUSDT"]
OUT = pathlib.Path("data/raw/web/night")
BASE = "https://data.binance.vision/data/futures/um/monthly"
MONTHS = [f"{y}-{m:02d}" for y in range(2022, 2027) for m in range(1, 13) if f"{y}-{m:02d}" <= "2026-03"]


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def read_csv(blob):
    z = zipfile.ZipFile(io.BytesIO(blob))
    raw = z.read(z.namelist()[0]).decode()
    first = raw.split("\n", 1)[0]
    has_header = not first[:1].isdigit()
    return pd.read_csv(io.StringIO(raw), header=0 if has_header else None)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    state = {"bytes": 0, "missing": [], "files": 0}
    for s in SYMS:
        kl, fr = [], []
        for m in MONTHS:
            if shutil.disk_usage(".").free < 2.5e9:
                print("STOP: disk < 2.5 GB"); state["stop"] = True; break
            b = get(f"{BASE}/klines/{s}/1h/{s}-1h-{m}.zip")
            if b is None:
                state["missing"].append(f"klines {s} {m}")
            else:
                state["bytes"] += len(b); state["files"] += 1
                d = read_csv(b).iloc[:, :8]
                d.columns = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume"]
                kl.append(d[["open_time", "open", "high", "low", "close", "quote_volume"]])
            b = get(f"{BASE}/fundingRate/{s}/{s}-fundingRate-{m}.zip")
            if b is None:
                state["missing"].append(f"funding {s} {m}")
            else:
                state["bytes"] += len(b); state["files"] += 1
                fr.append(read_csv(b))
        if kl:
            k = pd.concat(kl).drop_duplicates("open_time").sort_values("open_time")
            k = k.astype({"open_time": "int64", "open": float, "high": float, "low": float, "close": float})
            k.to_parquet(OUT / f"k1h_{s}.parquet", index=False)
        if fr:
            f = pd.concat(fr)
            f.columns = [str(c) for c in f.columns]
            f.to_parquet(OUT / f"funding_{s}.parquet", index=False)
        print(s, len(kl), len(fr), state["bytes"] / 1e6, flush=True)
    json.dump(state, open(OUT / "fetch_state.json", "w"), indent=1)


if __name__ == "__main__":
    main()
