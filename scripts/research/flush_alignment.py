"""Check the timestamp alignment of Binance `metrics` OI rows (train period only).

oi_value / oi is a price; compare it to the 1m kline close at lags d (bar opening at t+d) to find
when the snapshot stamped t was really taken. Writes research/observations/evidence_flush_alignment.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BF = ROOT / "data/raw/web/binance_fut"
out = {}
for sym in ("WIFUSDT", "1000BONKUSDT", "POPCATUSDT", "DOGEUSDT", "1000PEPEUSDT"):
    if not (BF / "metrics" / f"{sym}.parquet").exists():
        continue
    m = pd.read_parquet(BF / "metrics" / f"{sym}.parquet")
    k = pd.read_parquet(BF / "klines1m" / f"{sym}.parquet").set_index("t")
    m = m[(m.ts >= "2025-01-01") & (m.ts < "2025-07-01")].set_index("ts")
    px = m.oi_value / m.oi
    row = {}
    for d in range(-2, 8):
        c = k.close.reindex(px.index + pd.Timedelta(minutes=d)).values
        e = np.abs(np.log(px.values / c))
        row[d] = dict(median_abs_err_bp=round(float(np.nanmedian(e) * 1e4), 2),
                      share_within_5bp=round(float(np.nanmean(e < 5e-4)), 3))
    out[sym] = row
json.dump(dict(note="metrics row stamped t vs close of the 1m bar opening at t+d (2025H1); "
                    "best d=4 means the snapshot is at t+5min, so the signal is usable from t+5min.",
               results=out), open(ROOT / "research/observations/evidence_flush_alignment.json", "w"), indent=1)
print(json.dumps({s: min(r, key=lambda d: r[d]["median_abs_err_bp"]) for s, r in out.items()}))
