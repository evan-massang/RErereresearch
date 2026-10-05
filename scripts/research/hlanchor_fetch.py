"""Fetch Tardis.dev free first-of-month sample days for HL + Binance-futures meme perps.

H-HLANCHOR / H-HLLAG family. Public free samples (no key). Downloads one raw csv.gz at a time,
extracts the needed columns to parquet under data/raw/web/tardis/parquet/, then deletes the raw file.

Holdout (2026-04-01 onward) is NEVER downloaded.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/web/tardis"
PQ = RAW / "parquet"
PQ.mkdir(parents=True, exist_ok=True)

# pre-registered universe: HL coin -> Binance-futures symbol
COINS = {"WIF": "WIFUSDT", "kBONK": "1000BONKUSDT", "FARTCOIN": "FARTCOINUSDT", "PUMP": "PUMPUSDT"}
TRAIN = ["2024-11-01", "2024-12-01", "2025-01-01", "2025-02-01", "2025-03-01", "2025-04-01",
         "2025-05-01", "2025-06-01"]
VALID = ["2025-07-01", "2025-08-01", "2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01",
         "2026-01-01", "2026-02-01", "2026-03-01"]
HOLDOUT_START = "2026-04-01"


def url(exchange: str, dtype: str, day: str, sym: str) -> str:
    y, m, d = day.split("-")
    return f"https://datasets.tardis.dev/v1/{exchange}/{dtype}/{y}/{m}/{d}/{sym}.csv.gz"


def fetch(exchange: str, dtype: str, day: str, sym: str) -> Path | None:
    assert day < HOLDOUT_START, "holdout must not be fetched"
    out = RAW / f"{exchange}_{dtype}_{day}_{sym}.csv.gz"
    r = subprocess.run(["curl", "-sS", "--max-time", "600", "-o", str(out), "-w", "%{http_code}",
                        url(exchange, dtype, day, sym)], capture_output=True, text=True)
    if r.stdout.strip() != "200":
        out.unlink(missing_ok=True)
        print(f"  {exchange} {dtype} {day} {sym}: HTTP {r.stdout.strip()} {r.stderr.strip()}")
        return None
    return out


def process(exchange: str, dtype: str, day: str, sym: str, coin: str) -> None:
    dst = PQ / f"{dtype}_{day}_{coin}.parquet"
    if dst.exists():
        return
    raw = fetch(exchange, dtype, day, sym)
    if raw is None:
        return
    df = pd.read_csv(raw)
    if dtype == "book_ticker":  # binance-futures top of book
        df = df[["local_timestamp", "bid_price", "ask_price", "bid_amount", "ask_amount"]]
        # keep only rows where the top-of-book prices change (mid is all the signal needs)
        chg = (df.bid_price.diff() != 0) | (df.ask_price.diff() != 0)
        df = df[chg]
    elif dtype == "quotes":  # hyperliquid top of book
        df = df[["timestamp", "local_timestamp", "bid_price", "ask_price", "bid_amount", "ask_amount"]]
    elif dtype == "trades":
        df = df[["timestamp", "local_timestamp", "side", "price", "amount"]]
    df.to_parquet(dst, index=False)
    raw.unlink()
    print(f"  {dst.name}: {len(df)} rows")


def main(days: list[str]) -> None:
    for day in days:
        for coin, bsym in COINS.items():
            print(day, coin, flush=True)
            process("hyperliquid", "quotes", day, coin, coin)
            process("hyperliquid", "trades", day, coin, coin)
            if (PQ / f"quotes_{day}_{coin}.parquet").exists():
                process("binance-futures", "book_ticker", day, bsym, coin)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "train"
    main(TRAIN if which == "train" else VALID)
