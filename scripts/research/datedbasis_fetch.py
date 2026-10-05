"""H-DATEDBASIS data fetch (pre-registration: reports/hypotheses/datedbasis_preregistration.json).

Sources (public, no keys):
  - Binance public data archive https://data.binance.vision/ (S3 listing
    https://s3-ap-northeast-1.amazonaws.com/data.binance.vision):
      futures/{um,cm}/monthly/klines/<SYM_YYMMDD>/1h   dated futures 1h klines
      futures/{um,cm}/daily/indexPriceKlines/<PAIR>/1m  index on delivery day (settlement proxy)
      spot/monthly/klines/<COIN>USDT/1h, spot/daily/klines/<COIN>USDT/1m (delivery day)
  - FRED DTB3 https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3

Holdout contracts (delivery >= 2026-04-01) are never downloaded.
Output: compact parquet under data/raw/web/binance_dated/; zips are read in memory, never written.
"""
import io
import re
import zipfile
from datetime import date
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/binance_dated"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DV = "https://data.binance.vision/"
LAST_DELIVERY = date(2026, 3, 31)  # train+validation only
COLS = ["open_time", "open", "high", "low", "close", "volume"]

cl = httpx.Client(timeout=120, follow_redirects=True)


def s3_list(prefix, delim=True):
    out, marker = [], ""
    while True:
        p = {"prefix": prefix, "marker": marker}
        if delim:
            p["delimiter"] = "/"
        r = cl.get(S3, params=p)
        r.raise_for_status()
        keys = re.findall(r"<Prefix>([^<]+)</Prefix>", r.text) if delim else re.findall(r"<Key>([^<]+)</Key>", r.text)
        out += [k for k in keys if k != prefix]
        if "<IsTruncated>true</IsTruncated>" not in r.text:
            return out
        m = re.search(r"<NextMarker>([^<]+)</NextMarker>", r.text)
        marker = m.group(1) if m else out[-1]


def read_zip(url):
    r = cl.get(url)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    raw = z.read(z.namelist()[0]).decode()
    lines = [ln for ln in raw.splitlines() if ln and ln[0].isdigit()]
    if not lines:
        return None
    df = pd.read_csv(io.StringIO("\n".join(lines)), header=None).iloc[:, :6]
    df.columns = COLS
    t = df.open_time.astype("int64")
    t = t.where(t < 10**14, t // 1000)  # spot switched to microseconds in 2025
    df["open_time"] = pd.to_datetime(t, unit="ms", utc=True)
    return df


def delivery(sym):
    d = sym.split("_")[1]
    return date(2000 + int(d[:2]), int(d[2:4]), int(d[4:]))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    contracts = []
    for mkt in ("um", "cm"):
        for p in s3_list(f"data/futures/{mkt}/monthly/klines/"):
            s = p.rstrip("/").split("/")[-1]
            if re.fullmatch(r"[A-Z]+(USDT|USD)_\d{6}", s) and delivery(s) <= LAST_DELIVERY:
                contracts.append((mkt, s))
    print(len(contracts), "contracts")

    fut_p = OUT / "futures_1h.parquet"
    if not fut_p.exists():
        parts = []
        for mkt, s in contracts:
            for k in s3_list(f"data/futures/{mkt}/monthly/klines/{s}/1h/", delim=False):
                if k.endswith(".zip"):
                    df = read_zip(DV + k)
                    if df is not None:
                        df["symbol"], df["market"] = s, mkt
                        parts.append(df)
            print("fut", s)
        pd.concat(parts).drop_duplicates(["symbol", "open_time"]).to_parquet(fut_p, index=False)

    coins = sorted({s.split("_")[0].replace("USDT", "").replace("USD", "") for _, s in contracts})
    spot_p = OUT / "spot_1h.parquet"
    if not spot_p.exists():
        parts = []
        for c in coins:
            for k in s3_list(f"data/spot/monthly/klines/{c}USDT/1h/", delim=False):
                m = re.search(r"-(\d{4})-(\d{2})\.zip$", k)
                if m and "2020-01" <= f"{m.group(1)}-{m.group(2)}" <= "2026-03":
                    df = read_zip(DV + k)
                    if df is not None:
                        df["coin"] = c
                        parts.append(df)
            print("spot", c)
        pd.concat(parts).drop_duplicates(["coin", "open_time"]).to_parquet(spot_p, index=False)

    dd_p = OUT / "delivery_day_1m.parquet"
    if not dd_p.exists():
        parts = []
        for mkt, s in contracts:
            d = delivery(s).isoformat()
            pair = s.split("_")[0]
            coin = pair.replace("USDT", "").replace("USD", "")
            srcs = {
                "index": f"data/futures/{mkt}/daily/indexPriceKlines/{pair}/1m/{pair}-1m-{d}.zip",
                "future": f"data/futures/{mkt}/daily/klines/{s}/1m/{s}-1m-{d}.zip",
                "spot": f"data/spot/daily/klines/{coin}USDT/1m/{coin}USDT-1m-{d}.zip",
            }
            for kind, k in srcs.items():
                df = read_zip(DV + k)
                if df is None:
                    print("missing", kind, s)
                    continue
                df = df[(df.open_time.dt.hour >= 6) & (df.open_time.dt.hour < 9)]
                df["symbol"], df["kind"] = s, kind
                parts.append(df)
        pd.concat(parts).to_parquet(dd_p, index=False)

    fr_p = OUT / "fred_dtb3.parquet"
    if not fr_p.exists():
        r = cl.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3")
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = ["date", "dtb3"]
        df["dtb3"] = pd.to_numeric(df.dtb3, errors="coerce")
        df["date"] = pd.to_datetime(df.date)
        df.dropna().to_parquet(fr_p, index=False)


if __name__ == "__main__":
    main()
