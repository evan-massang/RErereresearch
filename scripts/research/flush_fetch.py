"""H-FLUSH data fetch: Binance USD-M futures public archive (data.binance.vision).

Fetches, per symbol, up to 2026-03-31 ONLY (holdout = 2026-04-01 onward is never downloaded):
  - daily `metrics` (5-min open interest)            -> data/raw/web/binance_fut/metrics/<SYM>.parquet
  - monthly `klines` 1m (daily for partial months)   -> data/raw/web/binance_fut/klines1m/<SYM>.parquet
  - monthly `fundingRate`                            -> data/raw/web/binance_fut/funding/<SYM>.parquet
Raw zips are parsed in memory and only compact parquet is cached (disk is tight).

Universe (pre-declared before any return was computed):
  fundcarry's 23 verified Solana-meme HL perps (reports/failures/agent_fundcarry.md, universe_map.json)
  mapped to their Binance USD-M symbols, plus DOGE and 1000PEPE (named in the task brief).
  A symbol is kept if the archive has metrics + klines for it before 2026-04-01.
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/binance_fut"
BASE = "https://data.binance.vision/"
LIST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
LAST_DAY = "2026-03-31"  # holdout guard
LAST_MONTH = "2026-03"

UNIVERSE = {  # HL name -> Binance USD-M symbol
    "WIF": "WIFUSDT", "kBONK": "1000BONKUSDT", "POPCAT": "POPCATUSDT", "MEW": "MEWUSDT",
    "BOME": "BOMEUSDT", "MYRO": "MYROUSDT", "GOAT": "GOATUSDT", "MOODENG": "MOODENGUSDT",
    "PNUT": "PNUTUSDT", "CHILLGUY": "CHILLGUYUSDT", "FARTCOIN": "FARTCOINUSDT", "AI16Z": "AI16ZUSDT",
    "ZEREBRO": "ZEREBROUSDT", "GRIFFAIN": "GRIFFAINUSDT", "TRUMP": "TRUMPUSDT", "MELANIA": "MELANIAUSDT",
    "VINE": "VINEUSDT", "JELLY": "JELLYJELLYUSDT", "LAUNCHCOIN": "LAUNCHCOINUSDT", "PUMP": "PUMPUSDT",
    "USELESS": "USELESSUSDT", "PENGU": "PENGUUSDT", "YZY": "YZYUSDT",
    "DOGE": "DOGEUSDT", "kPEPE": "1000PEPEUSDT",
}

S = requests.Session()


def list_keys(prefix: str) -> list[str]:
    keys, marker = [], ""
    while True:
        r = S.get(LIST, params={"prefix": prefix, "marker": marker, "max-keys": 1000}, timeout=60)
        r.raise_for_status()
        ks = re.findall(r"<Key>([^<]+)</Key>", r.text)
        keys += ks
        if "<IsTruncated>true</IsTruncated>" not in r.text or not ks:
            return [k for k in keys if k.endswith(".zip")]
        marker = ks[-1]


def get_csv(key: str) -> pd.DataFrame | None:
    for _ in range(4):
        try:
            r = S.get(BASE + key, timeout=120)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            z = zipfile.ZipFile(io.BytesIO(r.content))
            raw = z.read(z.namelist()[0])
            first = raw[:40].decode()
            header = 0 if first[0].isalpha() else None
            return pd.read_csv(io.BytesIO(raw), header=header)
        except Exception as e:  # retry
            err = e
    print("FAILED", key, err, file=sys.stderr)
    return None


def date_of(key: str) -> str:
    m = re.search(r"(\d{4}-\d{2}(-\d{2})?)\.zip$", key)
    return m.group(1)


KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
         "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


def fetch_symbol(sym: str) -> dict:
    info = {"symbol": sym}
    for sub in ("metrics", "klines1m", "funding"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    # metrics (daily)
    p = OUT / "metrics" / f"{sym}.parquet"
    if not p.exists():
        keys = [k for k in list_keys(f"data/futures/um/daily/metrics/{sym}/") if date_of(k) <= LAST_DAY]
        with ThreadPoolExecutor(16) as ex:
            dfs = [d for d in ex.map(get_csv, keys) if d is not None]
        if dfs:
            m = pd.concat(dfs)
            m = pd.DataFrame({"ts": pd.to_datetime(m["create_time"]),
                              "oi": m["sum_open_interest"].astype(float),
                              "oi_value": m["sum_open_interest_value"].astype(float)})
            m = m.drop_duplicates("ts").sort_values("ts")
            m = m[m.ts < pd.Timestamp("2026-04-01")]
            m.to_parquet(p, index=False)
        info["metrics_files"] = len(keys)
    # klines 1m: monthly, plus daily for months with no monthly file
    p = OUT / "klines1m" / f"{sym}.parquet"
    if not p.exists():
        mk = [k for k in list_keys(f"data/futures/um/monthly/klines/{sym}/1m/") if date_of(k) <= LAST_MONTH]
        months = {date_of(k) for k in mk}
        dk = [k for k in list_keys(f"data/futures/um/daily/klines/{sym}/1m/")
              if date_of(k) <= LAST_DAY and date_of(k)[:7] not in months]
        with ThreadPoolExecutor(8) as ex:
            dfs = [d for d in ex.map(get_csv, mk + dk) if d is not None]
        if dfs:
            for d in dfs:
                d.columns = KCOLS[: d.shape[1]]
            k = pd.concat(dfs)
            k = k[pd.to_numeric(k["open_time"], errors="coerce").notna()]
            k = pd.DataFrame({"t": pd.to_datetime(k["open_time"].astype("int64"), unit="ms"),
                              **{c: k[c].astype("float64") for c in ("open", "high", "low", "close")},
                              "qv": k["quote_volume"].astype("float32")})
            k = k.drop_duplicates("t").sort_values("t")
            k = k[k.t < pd.Timestamp("2026-04-01")]
            k.to_parquet(p, index=False)
        info["kline_files"] = len(mk) + len(dk)
    # funding (monthly)
    p = OUT / "funding" / f"{sym}.parquet"
    if not p.exists():
        fk = [k for k in list_keys(f"data/futures/um/monthly/fundingRate/{sym}/") if date_of(k) <= LAST_MONTH]
        dfs = [d for d in map(get_csv, fk) if d is not None]
        if dfs:
            f = pd.concat(dfs)
            f = pd.DataFrame({"t": pd.to_datetime(f["calc_time"].astype("int64"), unit="ms"),
                              "rate": f["last_funding_rate"].astype(float)})
            f.sort_values("t").to_parquet(p, index=False)
        info["funding_files"] = len(fk)
    print(info, flush=True)
    return info


if __name__ == "__main__":
    syms = sys.argv[1:] or list(UNIVERSE.values())
    for s in syms:
        fetch_symbol(s)
