"""H-FFDIFF data fetch: HL-vs-Binance funding differential on memecoin perps listed on both venues.

Universe: memecoin perps (agent_listshort's pre-declared CoinGecko meme-token rule, reused from
scripts/research/listshort_classify.py) whose base asset is listed on BOTH Hyperliquid and Binance USDS-M (USDT).

Public, unauthenticated sources only:
  - Hyperliquid info API POST https://api.hyperliquid.xyz/info: fundingHistory (hourly rate + premium),
    candleSnapshot 4h (only the latest 5000 candles are served -> HL 4h perp prices start ~2024-06-23).
    Existing fundcarry caches in data/raw/web/hyperliquid/ are READ ONLY; new files go to .../hyperliquid/ffdiff/.
  - Binance public archive data.binance.vision: futures/um monthly fundingRate and 4h klines.
    Parsed to data/raw/web/binance_fut/ffdiff/<SYM>_{funding,k4h}.parquet (zips are not kept).

HOLDOUT GUARD: nothing at or after 2026-04-01T00:00Z is written to disk (holdout = 2026-04-01 onward).
(The fundcarry caches contain rows to 2026-06-30; every loader in ffdiff_sim.py drops rows >= CUTOFF.)

    python scripts/research/ffdiff_fetch.py
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
HLX = HL / "ffdiff"
BNX = ROOT / "data/raw/web/binance_fut/ffdiff"
CUTOFF_MS = 1775001600000  # 2026-04-01T00:00:00Z
START_MS = 1698796800000   # 2023-11-01
MONTHS = [f"{y}-{m:02d}" for y in (2023, 2024, 2025, 2026) for m in range(1, 13)
          if "2023-11" <= f"{y}-{m:02d}" <= "2026-03"]


def universe():
    c = lc.candidates()
    bn = {r["base"]: r for r in c if r["meme"] and r["venue"] == "BN"}
    meta = {x["name"]: x for x in lc.load(HL / "listshort_meta.json")["universe"]}
    out = []
    for r in c:
        if r["meme"] and r["venue"] == "HL" and r["base"] in bn:
            b = bn[r["base"]]
            out.append({"hl": r["symbol"], "bn": b["symbol"], "base": r["base"],
                        "ratio": r["mult"] / b["mult"],  # HL price / BN price expected
                        "hl_maxlev_now": meta[r["symbol"]].get("maxLeverage"),
                        "hl_delisted": bool(meta[r["symbol"]].get("isDelisted"))})
    return out


def post(cl, body):
    for a in range(8):
        r = cl.post("https://api.hyperliquid.xyz/info", json=body)
        if r.status_code == 429:
            time.sleep(5 * (a + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("HL rate limited")


def hl_funding(cl, coin):
    if (HL / f"funding_{coin}.json").exists():
        return "cached-fundcarry"
    f = HLX / f"funding_{coin}.json"
    if f.exists():
        return "cached"
    rows, t = [], START_MS
    while t < CUTOFF_MS:
        b = post(cl, {"type": "fundingHistory", "coin": coin, "startTime": t, "endTime": CUTOFF_MS - 1})
        if not b:
            break
        rows += [x for x in b if x["time"] < CUTOFF_MS]
        nt = b[-1]["time"] + 1
        if nt <= t or len(b) < 500:
            break
        t = nt
        time.sleep(0.3)
    f.write_text(json.dumps({"coin": coin, "fetched_at": time.time(), "rows": rows}))
    return len(rows)


def hl_candles(cl, coin):
    if (HL / f"candles_4h_{coin}.json").exists():
        return "cached-fundcarry"
    f = HLX / f"candles_4h_{coin}.json"
    if f.exists():
        return "cached"
    b = post(cl, {"type": "candleSnapshot", "req": {"coin": coin, "interval": "4h",
                                                     "startTime": START_MS, "endTime": CUTOFF_MS - 1}})
    b = [x for x in b if x["T"] < CUTOFF_MS]
    f.write_text(json.dumps({"coin": coin, "interval": "4h", "fetched_at": time.time(), "rows": b}))
    time.sleep(0.3)
    return len(b)


def bn_zip(cl, url):
    for a in range(4):
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
            lines = [ln for ln in raw.splitlines() if ln and ln[0].isdigit()]  # drop header if any
            return lines
        time.sleep(2 * (a + 1))
    raise RuntimeError(f"failed {url}")


def bn_symbol(sym):
    ff, fk = BNX / f"{sym}_funding.parquet", BNX / f"{sym}_k4h.parquet"
    base = "https://data.binance.vision/data/futures/um/monthly"
    with httpx.Client(timeout=60) as cl:
        if not ff.exists():
            rows = []
            for m in MONTHS:
                ls = bn_zip(cl, f"{base}/fundingRate/{sym}/{sym}-fundingRate-{m}.zip")
                for ln in ls or []:
                    p = ln.split(",")  # calc_time, funding_interval_hours, last_funding_rate
                    rows.append((int(p[0]), int(p[1]), float(p[2])))
            d = pd.DataFrame(rows, columns=["t", "interval_h", "rate"])
            d = d[d.t < CUTOFF_MS].sort_values("t").drop_duplicates("t")
            d.to_parquet(ff)
        if not fk.exists():
            rows = []
            for m in MONTHS:
                if m < "2024-05":
                    continue
                ls = bn_zip(cl, f"{base}/klines/{sym}/4h/{sym}-4h-{m}.zip")
                for ln in ls or []:
                    p = ln.split(",")
                    rows.append((int(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[7])))
            d = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "qv"])
            d = d[d.t + 4 * 3600_000 <= CUTOFF_MS].sort_values("t").drop_duplicates("t")
            d.to_parquet(fk)
    return sym


def main():
    HLX.mkdir(parents=True, exist_ok=True)
    BNX.mkdir(parents=True, exist_ok=True)
    u = universe()
    (HLX / "universe.json").write_text(json.dumps({"fetched_at": time.time(), "pairs": u}, indent=1))
    print(len(u), "pairs")
    with httpx.Client(timeout=60) as cl:
        for p in u:
            print(p["hl"], hl_funding(cl, p["hl"]), hl_candles(cl, p["hl"]), flush=True)
    with ThreadPoolExecutor(6) as ex:
        for s in ex.map(bn_symbol, [p["bn"] for p in u]):
            print("BN", s, flush=True)


if __name__ == "__main__":
    main()
