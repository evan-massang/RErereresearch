"""H-XSREV data: Binance USDT-M 1h klines (data.binance.vision monthly archive) for BTCUSDT and every
HL-listed symbol that ever ranks 11-150 by trailing 30d quote volume (pre-registration:
reports/hypotheses/xsrev_preregistration.json).

Reuses read-only: data/raw/web/momentum/klines (1d, for ranking), data/raw/web/ffdiff_wide/universe_raw.json.
Writes compact parquet to data/raw/web/xsrev/k1h/<SYM>.parquet; zips are never written to disk.
HOLDOUT GUARD: only months 2023-01..2026-03 are requested; rows >= 2026-04-01 are dropped before writing.
Stops if free disk < 2.5 GB or downloaded bytes > 600 MB.

    python scripts/research/xsrev_fetch.py
"""
import io
import json
import shutil
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
import xsrev_lib as xl  # noqa: E402

OUT = ROOT / "data/raw/web/xsrev/k1h"
DL = "https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m}.zip"
MONTHS = [f"{y}-{m:02d}" for y in (2023, 2024, 2025, 2026) for m in range(1, 13) if f"{y}-{m:02d}" <= "2026-03"]
CUTOFF_MS = 1775001600000  # 2026-04-01T00:00Z
MAX_BYTES = 600e6
MIN_FREE = 2.5e9
KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "count",
         "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
lock = threading.Lock()
state = {"bytes": 0, "files": 0, "missing": 0, "stop": False}
sess = requests.Session()


def get(sym, month):
    url = DL.format(s=sym, m=month)
    for a in range(5):
        try:
            r = sess.get(url, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            with lock:
                state["bytes"] += len(r.content)
                state["files"] += 1
            z = zipfile.ZipFile(io.BytesIO(r.content))
            txt = z.read(z.namelist()[0]).decode()
            lines = [ln for ln in txt.strip().splitlines() if ln]
            if lines and not lines[0][0].isdigit():
                lines = lines[1:]
            if not lines:
                return None
            d = pd.read_csv(io.StringIO("\n".join(lines)), header=None, names=KCOLS)
            return d[["open_time", "open", "high", "low", "close", "quote_volume"]]
        except Exception:
            time.sleep(2 * (a + 1))
    print("FAILED", url, file=sys.stderr)
    return None


def do_symbol(sym, months):
    dest = OUT / f"{sym}.parquet"
    if dest.exists():
        return sym, "cached"
    frames = []
    for m in months:
        if state["stop"]:
            return sym, "stopped"
        if shutil.disk_usage(ROOT).free < MIN_FREE or state["bytes"] > MAX_BYTES:
            state["stop"] = True
            return sym, "stopped (disk/bytes guard)"
        d = get(sym, m)
        if d is None:
            with lock:
                state["missing"] += 1
            continue
        frames.append(d)
    if not frames:
        return sym, "empty"
    d = pd.concat(frames).apply(pd.to_numeric, errors="coerce").drop_duplicates("open_time")
    d = d[d.open_time < CUTOFF_MS].sort_values("open_time").reset_index(drop=True)
    for c in ("open", "high", "low", "close", "quote_volume"):
        d[c] = d[c].astype("float32") if c == "quote_volume" else d[c].astype("float64")
    d.to_parquet(dest, compression="zstd")
    return sym, len(d)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    need = xl.symbols_needed()  # {sym: [first_month, last_month]} from daily data only
    jobs = [("BTCUSDT", MONTHS)]
    for s, (m0, m1) in sorted(need.items()):
        if s == "BTCUSDT":
            continue
        jobs.append((s, [m for m in MONTHS if m0 <= m <= m1]))
    print(len(jobs), "symbols,", sum(len(m) for _, m in jobs), "symbol-months", flush=True)
    with ThreadPoolExecutor(12) as ex:
        for i, (s, st) in enumerate(ex.map(lambda j: do_symbol(*j), jobs)):
            if i % 20 == 0 or "stop" in str(st):
                print(i, s, st, f"{state['bytes'] / 1e6:.0f}MB", flush=True)
    print("done", state, f"free={shutil.disk_usage(ROOT).free / 1e9:.2f}GB")
    json.dump({k: v for k, v in state.items()}, open(OUT.parent / "fetch_state.json", "w"))


if __name__ == "__main__":
    main()
