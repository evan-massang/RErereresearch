"""H-CBPREM data fetch. Coinbase 1m candles (adapter pipeline/sources/coinbase.py) and Binance USD-M 1m klines +
funding (adapter pipeline/sources/binance_vision.py), 2024-09-20 .. 2026-03-31 (nothing from the holdout).
Output data/raw/web/cbprem/{cb,bn,fund}/<COIN>_<YYYY-MM>.parquet; resumable; stops if disk free < 2.5 GB."""
import json, shutil, sys, threading, datetime as dt, pathlib
import pandas as pd
from pipeline.sources.coinbase import CoinbaseExchangeAdapter
from pipeline.sources.binance_vision import BinanceVisionAdapter

ROOT = pathlib.Path("data/raw/web/cbprem")
U = json.load(open(ROOT / "universe_check.json"))
IN = ["DOGE", "1000PEPE", "WIF", "POPCAT", "1000FLOKI", "PENGU", "TRUMP", "1000BONK", "1000SHIB"]
START, END = dt.datetime(2024, 9, 1, tzinfo=dt.timezone.utc), dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc)
STOP = threading.Event()
log = open(ROOT / "fetch.log", "a")
def L(*a):
    msg = f"{dt.datetime.utcnow().isoformat()} " + " ".join(map(str, a)); print(msg, flush=True); log.write(msg + "\n"); log.flush()

def months():
    m = START
    while m < END:
        n = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1); yield m, n; m = n

def guard():
    if shutil.disk_usage(".").free < 2.5e9:
        STOP.set(); L("STOP: disk free < 2.5 GB")
    return STOP.is_set()

def cb_coin(coin, prod):
    a = CoinbaseExchangeAdapter(min_interval_s=1.4)
    first = int(dt.datetime.fromisoformat(U[coin]["first_1m_candle_utc"]).replace(tzinfo=dt.timezone.utc).timestamp())
    first = max(first, int(dt.datetime(2024, 9, 20, tzinfo=dt.timezone.utc).timestamp()))
    for m, n in months():
        f = ROOT / "cb" / f"{coin}_{m:%Y-%m}.parquet"
        if f.exists() or int(n.timestamp()) <= first or guard():
            continue
        rows = []; s = max(int(m.timestamp()), first // 60 * 60)
        while s < int(n.timestamp()):
            e = min(s + 300 * 60, int(n.timestamp()))
            rows += a.candles_1m(prod, s, e); s = e
        df = pd.DataFrame(rows, columns=["t", "low", "high", "open", "close", "volume"])[["t", "close", "volume"]]
        df.to_parquet(f, index=False); L("cb", coin, m.strftime("%Y-%m"), len(df))

def bn_all():
    a = BinanceVisionAdapter()
    for coin in IN:
        sym = coin + "USDT"
        for m, n in months():
            f = ROOT / "bn" / f"{coin}_{m:%Y-%m}.parquet"
            if not f.exists() and not guard():
                df = a.klines_1m(sym, f"{m:%Y-%m}")
                if df is None:  # monthly missing -> daily files
                    parts = [a.klines_1m(sym, f"{d:%Y-%m-%d}", "daily") for d in pd.date_range(m, n - dt.timedelta(days=1))]
                    parts = [p for p in parts if p is not None]
                    df = pd.concat(parts) if parts else pd.DataFrame(columns=["open_time_ms", "close"])
                df.to_parquet(f, index=False); L("bn", coin, m.strftime("%Y-%m"), len(df), "MB_dl", round(a.bytes_downloaded / 1e6, 1))
            g = ROOT / "fund" / f"{coin}_{m:%Y-%m}.parquet"
            if not g.exists() and not guard():
                df = a.funding_monthly(sym, f"{m:%Y-%m}")
                (df if df is not None else pd.DataFrame(columns=["calc_time_ms", "funding_rate"])).to_parquet(g, index=False)

if __name__ == "__main__":
    for d in ("cb", "bn", "fund"): (ROOT / d).mkdir(parents=True, exist_ok=True)
    jobs = [threading.Thread(target=cb_coin, args=(c, U[c]["product"])) for c in IN + ["USDT"]]
    jobs.append(threading.Thread(target=bn_all))
    for j in jobs: j.start()
    for j in jobs: j.join()
    L("DONE", "stopped" if STOP.is_set() else "complete")
