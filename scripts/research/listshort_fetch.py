"""H-LISTSHORT step 3: fetch prices + funding around each meme perp listing (cached raw).

HOLDOUT GUARD: listings on/after 2026-04-01T00:00Z are never fetched (only their existence, from
the venue's symbol list, is known). For every listing we fetch only [listing, listing + 40 d].
Hedge series (BTC/ETH/SOL USDT perps, Binance 1h) are fetched 2023-01 .. 2026-05 (needed for
the hedge leg of validation trades whose 30-d holds end in Apr/May 2026); nothing later.

Sources (public, no keys):
  Hyperliquid POST https://api.hyperliquid.xyz/info candleSnapshot (1d, 4h) + fundingHistory.
    candleSnapshot serves only the latest 5000 candles: 4h reaches back to ~2024-06-23 for
    live coins; earlier HL listings have 1d only (recorded as such).
  Binance data archive https://data.binance.vision/data/futures/um/monthly/{klines/<S>/1h,fundingRate}
    (monthly zips of USDT-M klines and funding; listing time = first 1h kline).
    python scripts/research/listshort_fetch.py
"""
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from listshort_classify import candidates  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HL = ROOT / "data/raw/web/hyperliquid"
BN = ROOT / "data/raw/web/binance_fut"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DV = "https://data.binance.vision/"
HOLDOUT_MS = 1775001600000  # 2026-04-01T00:00:00Z
ERA_MS = 1672531200000      # 2023-01-01
WIN_MS = 40 * 86400_000
DAY = 86400_000


def save(p, obj):
    p.write_text(json.dumps({"fetched_at": time.time(), **obj}))


def hl_post(cl, body):
    for a in range(8):
        r = cl.post("https://api.hyperliquid.xyz/info", json=body)
        if r.status_code == 429:
            time.sleep(4 * (a + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("HL rate limited")


def hl_listing(cl, coin):
    p = HL / f"listshort_{coin}.json"
    if p.exists():
        return json.loads(p.read_text())
    d1 = hl_post(cl, {"type": "candleSnapshot", "req": {"coin": coin, "interval": "1d", "startTime": 0,
                                                         "endTime": HOLDOUT_MS - 1}})
    if not d1:
        out = {"coin": coin, "status": "no_data_before_holdout"}
        save(p, out)  # stores nothing about prices
        return out
    t0 = d1[0]["t"]
    end = t0 + WIN_MS
    d1 = [x for x in d1 if x["t"] < end]
    h4 = hl_post(cl, {"type": "candleSnapshot", "req": {"coin": coin, "interval": "4h", "startTime": t0,
                                                         "endTime": end}})
    h1 = hl_post(cl, {"type": "candleSnapshot", "req": {"coin": coin, "interval": "1h", "startTime": t0,
                                                         "endTime": end}})
    fund, t = [], t0
    while t < end:
        b = hl_post(cl, {"type": "fundingHistory", "coin": coin, "startTime": t, "endTime": end})
        b = [x for x in b if x["time"] < end]
        if not b:
            break
        fund += b
        t = b[-1]["time"] + 1
        time.sleep(0.3)
    out = {"coin": coin, "status": "ok", "first_1d_t": t0, "c1d": d1, "c4h": h4, "c1h": h1, "funding": fund}
    save(p, out)
    time.sleep(0.5)
    return out


def s3_keys(cl, prefix):
    keys, marker = [], ""
    while True:
        r = cl.get(S3, params={"prefix": prefix, "marker": marker})
        r.raise_for_status()
        ks = re.findall(r"<Key>([^<]+)</Key>", r.text)
        keys += ks
        if "<IsTruncated>true</IsTruncated>" not in r.text or not ks:
            return keys
        marker = ks[-1]


def zip_csv(cl, key):
    r = cl.get(DV + key)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    txt = z.read(z.namelist()[0]).decode()
    rows = [ln.split(",") for ln in txt.strip().splitlines()]
    if rows and not rows[0][0].lstrip("-").isdigit():
        rows = rows[1:]
    return rows


def month_of(key):
    return re.search(r"(\d{4}-\d{2})\.zip$", key).group(1)


def bn_listing(cl, sym, hedge=False, months=None):
    p = BN / f"listshort_{sym}.json"
    if p.exists():
        return json.loads(p.read_text())
    keys = sorted(k for k in s3_keys(cl, f"data/futures/um/monthly/klines/{sym}/1h/") if k.endswith(".zip"))
    if not keys:
        out = {"symbol": sym, "status": "no_monthly_files"}
        save(p, out)
        return out
    if hedge:
        sel = [k for k in keys if months[0] <= month_of(k) <= months[1]]
    else:
        first = month_of(keys[0])
        if first >= "2026-04":
            out = {"symbol": sym, "status": "holdout_listing", "first_month": first}
            save(p, out)  # existence only, no prices
            return out
        sel = keys[:3]
    kl = []
    for k in sel:
        kl += [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[7])]
               for r in zip_csv(cl, k)]
    kl.sort()
    if not hedge:
        t0 = kl[0][0]
        if t0 >= HOLDOUT_MS:
            out = {"symbol": sym, "status": "holdout_listing"}
            save(p, out)
            return out
        kl = [x for x in kl if x[0] < t0 + WIN_MS]
    fund = []
    for k in sel:
        fk = f"data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{month_of(k)}.zip"
        rows = zip_csv(cl, fk)
        if rows:
            fund += [[int(r[0]), float(r[2])] for r in rows]
    fund.sort()
    if not hedge:
        fund = [x for x in fund if x[0] < kl[0][0] + WIN_MS]
    out = {"symbol": sym, "status": "ok", "klines_1h": kl, "kl_cols": "open_ms,o,h,l,c,quote_vol",
           "funding": fund, "funding_cols": "calc_time_ms,rate"}
    save(p, out)
    return out


if __name__ == "__main__":
    cands = [r for r in candidates() if r["meme"]]
    with httpx.Client(timeout=120, follow_redirects=True) as cl:
        for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
            bn_listing(cl, s, hedge=True, months=("2023-01", "2026-05"))
            print("hedge", s, flush=True)
        for r in cands:
            try:
                d = hl_listing(cl, r["symbol"]) if r["venue"] == "HL" else bn_listing(cl, r["symbol"])
                print(r["venue"], r["symbol"], d.get("status"), flush=True)
            except Exception as e:  # record and continue
                print("ERR", r["venue"], r["symbol"], repr(e), flush=True)
