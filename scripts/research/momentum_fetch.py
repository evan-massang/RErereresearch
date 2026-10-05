"""Fetch Binance USDT-M perp daily klines + fundingRate monthly archives (data.binance.vision).

Only months <= 2026-03 are downloaded (holdout 2026-04+ is never touched).
Output: data/raw/web/momentum/{klines,funding}/<SYM>.parquet ; zips are not kept.
"""
import io, re, sys, zipfile, json, time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/momentum"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DL = "https://data.binance.vision/"
LAST_MONTH = "2026-03"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
sess = requests.Session()


def s3_list(prefix, delim=True):
    keys, prefixes, marker = [], [], ""
    while True:
        params = {"prefix": prefix, "marker": marker}
        if delim:
            params["delimiter"] = "/"
        for i in range(5):
            try:
                r = sess.get(S3, params=params, timeout=30); r.raise_for_status(); break
            except Exception:
                time.sleep(2 * (i + 1))
        root = ET.fromstring(r.content)
        keys += [e.text for e in root.findall("s:Contents/s:Key", NS)]
        prefixes += [e.text for e in root.findall("s:CommonPrefixes/s:Prefix", NS)]
        if root.find("s:IsTruncated", NS).text != "true":
            return keys, prefixes
        marker = root.find("s:NextMarker", NS).text if root.find("s:NextMarker", NS) is not None else (keys or prefixes)[-1]


def get_zip_csv(key):
    for i in range(5):
        try:
            r = sess.get(DL + key, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            z = zipfile.ZipFile(io.BytesIO(r.content))
            return z.read(z.namelist()[0]).decode()
        except Exception:
            time.sleep(2 * (i + 1))
    print("FAILED", key, file=sys.stderr)
    return None


def month_ok(key):
    m = re.search(r"(\d{4}-\d{2})\.zip$", key)
    return m and m.group(1) <= LAST_MONTH


KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


def parse_csv(txt, cols):
    lines = [l for l in txt.strip().splitlines() if l]
    if lines and not lines[0][0].isdigit() and not lines[0][0] == "-":
        lines = lines[1:]
    return pd.read_csv(io.StringIO("\n".join(lines)), header=None, names=cols) if lines else None


def do_symbol(sym, kind):
    dest = OUT / kind / f"{sym}.parquet"
    if dest.exists():
        return sym, "cached"
    pref = f"data/futures/um/monthly/klines/{sym}/1d/" if kind == "klines" else f"data/futures/um/monthly/fundingRate/{sym}/"
    keys, _ = s3_list(pref)
    keys = sorted(k for k in keys if k.endswith(".zip") and month_ok(k))
    frames = []
    for k in keys:
        txt = get_zip_csv(k)
        if txt is None:
            continue
        if kind == "klines":
            df = parse_csv(txt, KCOLS)
            if df is not None:
                frames.append(df[["open_time", "open", "high", "low", "close", "volume", "quote_volume"]])
        else:
            df = parse_csv(txt, ["calc_time", "funding_interval_hours", "last_funding_rate"])
            if df is not None:
                frames.append(df)
    if not frames:
        return sym, "empty"
    d = pd.concat(frames).drop_duplicates().reset_index(drop=True)
    d = d.apply(pd.to_numeric, errors="coerce")
    d.to_parquet(dest)
    return sym, len(d)


if __name__ == "__main__":
    kind = sys.argv[1]
    (OUT / kind).mkdir(parents=True, exist_ok=True)
    symf = OUT / "symbols.json"
    if symf.exists():
        syms = json.load(open(symf))
    else:
        _, prefs = s3_list("data/futures/um/monthly/klines/")
        syms = sorted(p.split("/")[-2] for p in prefs)
        syms = [s for s in syms if s.endswith("USDT") and "_" not in s]
        json.dump(syms, open(symf, "w"))
    print(len(syms), "symbols")
    with ThreadPoolExecutor(16) as ex:
        for i, (s, st) in enumerate(ex.map(lambda s: do_symbol(s, kind), syms)):
            if i % 50 == 0:
                print(i, s, st, flush=True)


def fetch_files(sym, kind, months=(), days=()):
    """Direct GETs (no listing) of monthly and daily archive files; 404s are skipped.
    kind 'klines' (1d) or 'funding' (monthly only: the archive has no daily fundingRate files)."""
    keys = []
    for m in months:
        keys.append(f"data/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{m}.zip" if kind == "klines"
                    else f"data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip")
    if kind == "klines":
        keys += [f"data/futures/um/daily/klines/{sym}/1d/{sym}-1d-{d}.zip" for d in days]
    frames = []
    for k in keys:
        txt = get_zip_csv(k)
        if txt is None:
            continue
        if kind == "klines":
            df = parse_csv(txt, KCOLS)
            if df is not None:
                frames.append(df[["open_time", "open", "high", "low", "close", "volume", "quote_volume"]])
        else:
            df = parse_csv(txt, ["calc_time", "funding_interval_hours", "last_funding_rate"])
            if df is not None:
                frames.append(df)
    if not frames:
        return None
    return pd.concat(frames).drop_duplicates().reset_index(drop=True).apply(pd.to_numeric, errors="coerce")


def current_symbols():
    _, prefs = s3_list("data/futures/um/monthly/klines/")
    _, prefs_d = s3_list("data/futures/um/daily/klines/")
    syms = sorted({p.split("/")[-2] for p in prefs + prefs_d})
    return [s for s in syms if s.endswith("USDT") and "_" not in s]
