"""H-PUMPPULSE data fetch (pre-registration: reports/hypotheses/pumppulse_preregistration.json).

1) DefiLlama (unauthenticated): pump parent fees/revenue summary (with per-child breakdown) and pump.fun dexs volume.
   Raw JSON cached in data/raw/web/pumppulse/.
2) data.binance.vision USDT-M 1h klines for the basket + SOLUSDT, months 2024-01..2026-03 ONLY.
   HOLDOUT GUARD: rows >= 2026-04-01 are dropped before writing. Zips are never written.
   Stops if free disk < 2.5 GB or downloaded bytes > 300 MB.

    python scripts/research/pumppulse_fetch.py
"""
import io
import shutil
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/pumppulse"
SYMS = ["PUMPUSDT", "WIFUSDT", "1000BONKUSDT", "FARTCOINUSDT", "PENGUUSDT", "TRUMPUSDT", "1000PEPEUSDT",
        "POPCATUSDT", "SOLUSDT"]
LLAMA = {
    "fees_pump_dailyRevenue.json": "https://api.llama.fi/summary/fees/pump?dataType=dailyRevenue",
    "fees_pump_dailyFees.json": "https://api.llama.fi/summary/fees/pump?dataType=dailyFees",
    "dexs_pumpfun.json": "https://api.llama.fi/summary/dexs/pump.fun",
}
DL = "https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m}.zip"
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13) if f"{y}-{m:02d}" <= "2026-03"]
CUTOFF_MS = 1775001600000  # 2026-04-01T00:00Z
KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "count",
         "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
state = {"bytes": 0}


def guard():
    if shutil.disk_usage(ROOT).free < 2.5e9 or state["bytes"] > 300e6:
        sys.exit(f"STOP: guard hit (free={shutil.disk_usage(ROOT).free/1e9:.2f} GB, bytes={state['bytes']/1e6:.1f} MB)")


def main():
    s = requests.Session()
    for fn, url in LLAMA.items():
        if not (OUT / fn).exists():
            r = s.get(url, timeout=60)
            r.raise_for_status()
            (OUT / fn).write_bytes(r.content)
            state["bytes"] += len(r.content)
    for sym in SYMS:
        dest = OUT / "k1h" / f"{sym}.parquet"
        if dest.exists():
            continue
        frames = []
        for m in MONTHS:
            guard()
            r = s.get(DL.format(s=sym, m=m), timeout=60)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            state["bytes"] += len(r.content)
            z = zipfile.ZipFile(io.BytesIO(r.content))
            lines = [ln for ln in z.read(z.namelist()[0]).decode().strip().splitlines() if ln]
            if lines and not lines[0][0].isdigit():
                lines = lines[1:]
            if lines:
                d = pd.read_csv(io.StringIO("\n".join(lines)), header=None, names=KCOLS)
                frames.append(d[["open_time", "open", "close", "quote_volume"]])
        df = pd.concat(frames).drop_duplicates("open_time").sort_values("open_time")
        df = df[df.open_time < CUTOFF_MS]
        df.to_parquet(dest, index=False)
        print(sym, len(df), f"{state['bytes']/1e6:.1f} MB", flush=True)
    print("done", f"{state['bytes']/1e6:.1f} MB")


if __name__ == "__main__":
    main()
