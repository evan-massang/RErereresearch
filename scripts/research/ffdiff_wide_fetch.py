"""H-FFDIFF-WIDE data fetch: every HL perp with a Binance USDS-M USDT perp of the same base (pre-registration:
reports/hypotheses/ffdiff_wide_preregistration.json).

Public, unauthenticated sources only:
  - Hyperliquid info API: fundingHistory (hourly) and candleSnapshot 4h (latest 5000 served -> from ~2024-06-24).
  - data.binance.vision futures/um monthly fundingRate and klines/4h.
Read-only reuse of existing caches (converted into private compact copies, since shared caches can vanish): data/raw/web/hyperliquid/{funding,candles_4h}_<coin>.json (fundcarry),
  data/raw/web/hyperliquid/ffdiff/*.json, data/raw/web/binance_fut/ffdiff/<SYM>_{funding,k4h}.parquet,
  data/raw/web/binance_carry/funding/<SYM>.parquet.
New files: compact parquet under data/raw/web/ffdiff_wide/ (zips/JSON are never kept).

HOLDOUT GUARD: nothing at or after 2026-04-01T00:00Z is written (rows filtered before writing).

    python scripts/research/ffdiff_wide_fetch.py
"""
import io
import json
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
import listshort_classify as lc  # noqa: E402

HL = ROOT / "data/raw/web/hyperliquid"
BNF = ROOT / "data/raw/web/binance_fut/ffdiff"
OUT = ROOT / "data/raw/web/ffdiff_wide"
CUTOFF_MS = 1775001600000   # 2026-04-01T00:00:00Z
START_MS = 1718236800000    # 2024-06-13 (>= 72h of funding before the first HL 4h candle, 2024-06-24)
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13) if "2024-06" <= f"{y}-{m:02d}" <= "2026-03"]


def universe():
    c = lc.candidates()
    bn = {r["base"]: r for r in c if r["venue"] == "BN"}
    meta = {x["name"]: x for x in lc.load(HL / "listshort_meta.json")["universe"]}
    out = []
    for r in c:
        if r["venue"] == "HL" and r["base"] in bn:
            b = bn[r["base"]]
            out.append({"hl": r["symbol"], "bn": b["symbol"], "base": r["base"], "meme": bool(r["meme"]),
                        "ratio": r["mult"] / b["mult"], "hl_maxlev_now": meta[r["symbol"]].get("maxLeverage"),
                        "hl_delisted": bool(meta[r["symbol"]].get("isDelisted"))})
    return out


def post(cl, body):
    for a in range(12):
        try:
            r = cl.post("https://api.hyperliquid.xyz/info", json=body)
        except httpx.HTTPError:
            time.sleep(3 * (a + 1))
            continue
        if r.status_code == 429:
            time.sleep(5 * (a + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("HL rate limited")


def hl_cached(kind, coin):
    for p in (HL / f"{kind}_{coin}.json", HL / "ffdiff" / f"{kind}_{coin}.json"):
        if p.exists():
            return p
    return None


def hl_funding(cl, coin):
    f = OUT / "hl_funding" / f"{coin}.parquet"
    if f.exists():
        return "cached"
    c = hl_cached("funding", coin)
    if c:  # convert the read-only ffdiff/fundcarry JSON cache to a compact private copy
        d = pd.DataFrame([(x["time"], float(x["fundingRate"])) for x in json.loads(c.read_text())["rows"]],
                         columns=["t_ms", "rate"]).drop_duplicates("t_ms")
        d[(d.t_ms < CUTOFF_MS) & (d.t_ms >= START_MS)].to_parquet(f, index=False)
        return "converted"
    rows, t = [], START_MS
    while t < CUTOFF_MS:
        b = post(cl, {"type": "fundingHistory", "coin": coin, "startTime": t, "endTime": CUTOFF_MS - 1})
        if not b:
            break
        rows += [(x["time"], float(x["fundingRate"])) for x in b if x["time"] < CUTOFF_MS]
        nt = b[-1]["time"] + 1
        if nt <= t or len(b) < 500:
            break
        t = nt
        time.sleep(0.25)
    d = pd.DataFrame(rows, columns=["t_ms", "rate"]).drop_duplicates("t_ms")
    d = d[d.t_ms < CUTOFF_MS]
    d.to_parquet(f, index=False)
    return len(d)


def hl_candles(cl, coin):
    f = OUT / "hl_k4h" / f"{coin}.parquet"
    if f.exists():
        return "cached"
    c = hl_cached("candles_4h", coin)
    if c:
        d = pd.DataFrame([(x["t"], float(x["o"]), float(x["h"]), float(x["l"]), float(x["c"]), float(x["v"]))
                          for x in json.loads(c.read_text())["rows"] if x["T"] < CUTOFF_MS],
                         columns=["t", "o", "h", "l", "c", "v"])
        d.to_parquet(f, index=False)
        return "converted"
    b = post(cl, {"type": "candleSnapshot", "req": {"coin": coin, "interval": "4h",
                                                     "startTime": START_MS, "endTime": CUTOFF_MS - 1}})
    d = pd.DataFrame([(x["t"], float(x["o"]), float(x["h"]), float(x["l"]), float(x["c"]), float(x["v"]))
                      for x in b if x["T"] < CUTOFF_MS], columns=["t", "o", "h", "l", "c", "v"])
    d.to_parquet(f, index=False)
    time.sleep(0.25)
    return len(d)


def bn_zip(cl, url):
    for a in range(5):
        try:
            r = cl.get(url)
        except httpx.HTTPError:
            time.sleep(2 * (a + 1))
            continue
        if r.status_code == 404:
            return None
        if r.status_code == 200:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            raw = z.read(z.namelist()[0]).decode()
            return [ln for ln in raw.splitlines() if ln and ln[0].isdigit()]
        time.sleep(2 * (a + 1))
    raise RuntimeError(f"failed {url}")


def bn_symbol(sym):
    base = "https://data.binance.vision/data/futures/um/monthly"
    ff, fk = OUT / "bn_funding" / f"{sym}.parquet", OUT / "bn_k4h" / f"{sym}.parquet"
    with httpx.Client(timeout=60) as cl:
        if not ff.exists():
            rows = []
            for m in MONTHS:
                for ln in bn_zip(cl, f"{base}/fundingRate/{sym}/{sym}-fundingRate-{m}.zip") or []:
                    p = ln.split(",")
                    rows.append((int(p[0]), int(p[1]), float(p[2])))
            d = pd.DataFrame(rows, columns=["t", "interval_h", "rate"])
            d = d[d.t < CUTOFF_MS].sort_values("t").drop_duplicates("t")
            d.to_parquet(ff, index=False)
        if (BNF / f"{sym}_k4h.parquet").exists() and not fk.exists():  # private copy of the ffdiff cache
            d = pd.read_parquet(BNF / f"{sym}_k4h.parquet")
            d[(d.t + 4 * 3600_000 <= CUTOFF_MS) & (d.t >= START_MS)].to_parquet(fk, index=False)
        if not fk.exists():
            rows = []
            for m in MONTHS:
                for ln in bn_zip(cl, f"{base}/klines/{sym}/4h/{sym}-4h-{m}.zip") or []:
                    p = ln.split(",")
                    rows.append((int(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[7])))
            d = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "qv"])
            d = d[d.t + 4 * 3600_000 <= CUTOFF_MS].sort_values("t").drop_duplicates("t")
            d.to_parquet(fk, index=False)
    return sym


def main():
    for s in ("hl_funding", "hl_k4h", "bn_funding", "bn_k4h"):
        (OUT / s).mkdir(parents=True, exist_ok=True)
    u = universe()
    (OUT / "universe_raw.json").write_text(json.dumps({"fetched_at": time.time(), "pairs": u}, indent=1))
    print(len(u), "name-matched pairs", flush=True)
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "bn"):
        with ThreadPoolExecutor(6) as ex:
            for s in ex.map(bn_symbol, [p["bn"] for p in u]):
                print("BN", s, flush=True)
    if which in ("all", "hl"):
        with httpx.Client(timeout=60) as cl:
            for p in u:
                print(p["hl"], hl_funding(cl, p["hl"]), hl_candles(cl, p["hl"]), flush=True)


if __name__ == "__main__":
    main()
