"""Fetch Binance SPOT BTCUSDT 1-s klines for H-WICKNET train+validation days (market-wide filter).
Holdout guard: refuses any day >= 2026-04-01. Stores compact parquet (open_time_us, close)."""
from __future__ import annotations
import io, sys, zipfile, urllib.request
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from hlanchor_fetch import TRAIN, VALID, HOLDOUT_START  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data/raw/web/binance_spot/klines1s"
OUT.mkdir(parents=True, exist_ok=True)
URL = "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1s/BTCUSDT-1s-{d}.zip"

for d in TRAIN + VALID:
    assert d < HOLDOUT_START
    f = OUT / f"BTCUSDT_1s_{d}.parquet"
    if f.exists():
        continue
    raw = urllib.request.urlopen(URL.format(d=d), timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(raw))
    df = pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=[0, 4], names=["open_time", "close"])
    ot = df.open_time.astype("int64")
    ot = ot.where(ot > 10**14, ot * 1000)  # ms (pre-2025) -> us; 2025+ files are already us
    pd.DataFrame({"open_time_us": ot, "close": df.close.astype(float)}).to_parquet(f, index=False)
    print(d, len(df), len(raw))
