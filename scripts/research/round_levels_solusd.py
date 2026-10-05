"""Fetch and cache SOL/USDT 1-minute klines for Oct 1-3 2026 (agent round_levels).

Source: Binance public market-data API mirror, https://data-api.binance.vision/api/v3/klines
(symbol=SOLUSDT, interval=1m). api.binance.com itself returns "Service unavailable from a restricted
location" from this container; data-api.binance.vision is Binance's documented public market-data-only
endpoint serving the same klines. USDT is treated as USD (no adjustment; USDT/USD deviation is tiny
next to the 5% bands used).

Raw JSON responses are cached verbatim under data/raw/web/solusd/ and a parquet of
(open_time_s, open, high, low, close) is written next to them.

    python scripts/research/round_levels_solusd.py
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "web" / "solusd"
URL = "https://data-api.binance.vision/api/v3/klines?symbol=SOLUSDT&interval=1m&startTime={s}&limit=1000"
START, END = 1790812800, 1791072000  # Oct 1 00:00 - Oct 4 00:00 UTC


def main():
    import pandas as pd
    OUT.mkdir(parents=True, exist_ok=True)
    rows, s = [], START * 1000
    while s < END * 1000:
        f = OUT / f"klines_SOLUSDT_1m_{s}.json"
        if not f.exists():
            with urllib.request.urlopen(URL.format(s=s), timeout=30) as r:
                f.write_bytes(r.read())
            time.sleep(0.5)
        k = json.loads(f.read_text())
        if not k:
            break
        rows += [x for x in k if x[0] < END * 1000]
        s = k[-1][0] + 60_000
    d = pd.DataFrame([(x[0] // 1000, float(x[1]), float(x[2]), float(x[3]), float(x[4])) for x in rows],
                     columns=["t", "open", "high", "low", "close"]).drop_duplicates("t").sort_values("t")
    d.to_parquet(OUT / "solusdt_1m_20261001_20261003.parquet")
    (OUT / "SOURCE.txt").write_text(
        "SOL/USDT 1m klines, Binance public market data API (data-api.binance.vision/api/v3/klines,\n"
        "symbol=SOLUSDT, interval=1m), fetched " + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()) +
        " by scripts/research/round_levels_solusd.py. Kline row format: [open_time_ms, open, high, low, close,\n"
        "volume, close_time_ms, quote_volume, trades, taker_buy_base, taker_buy_quote, ignore].\n")
    print(len(d), d.t.min(), d.t.max(), d.close.describe().to_dict(), "missing minutes:",
          (END - START) // 60 - len(d), file=sys.stderr)


if __name__ == "__main__":
    main()
