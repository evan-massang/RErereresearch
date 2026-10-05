"""H-LISTSHORT step 1: universe of perp listings + memecoin classification (cached raw).

Public, unauthenticated sources only:
  - Hyperliquid info API "meta" (all main-dex perps incl. delisted).
  - Binance public data archive (S3 bucket listing of data.binance.vision, futures/um/monthly/klines/*).
    fapi.binance.com is geo-blocked (HTTP 451) so exchangeInfo is not used.
  - CoinGecko public API, category "meme-token" (https://www.coingecko.com/en/categories/meme-token),
    the pre-declared memecoin definition, plus /coins/list for symbol-collision checks.

Writes only under data/raw/web/{hyperliquid,binance_fut,coingecko}/listshort_*.json.
    python scripts/research/listshort_universe.py
"""
import json
import re
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
HL = ROOT / "data/raw/web/hyperliquid"
BN = ROOT / "data/raw/web/binance_fut"
CG = ROOT / "data/raw/web/coingecko"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"


def save(path, obj):
    path.write_text(json.dumps({"fetched_at": time.time(), "data": obj}))


def hl_meta(cl):
    p = HL / "listshort_meta.json"
    if not p.exists():
        save(p, cl.post("https://api.hyperliquid.xyz/info", json={"type": "meta"}).json())


def s3_prefixes(cl, prefix):
    out, marker = [], ""
    while True:
        r = cl.get(S3, params={"prefix": prefix, "delimiter": "/", "marker": marker})
        r.raise_for_status()
        ps = re.findall(r"<Prefix>([^<]+)</Prefix>", r.text)
        ps = [x for x in ps if x != prefix]
        out += ps
        if "<IsTruncated>true</IsTruncated>" not in r.text:
            return out
        marker = re.search(r"<NextMarker>([^<]+)</NextMarker>", r.text).group(1)


def binance_symbols(cl):
    p = BN / "listshort_um_symbols.json"
    if not p.exists():
        ps = s3_prefixes(cl, "data/futures/um/monthly/klines/")
        save(p, sorted(x.rstrip("/").split("/")[-1] for x in ps))


def cg_get(cl, url, params=None):
    for a in range(8):
        r = cl.get(url, params=params)
        if r.status_code == 429:
            time.sleep(20 * (a + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("coingecko rate limit")


def coingecko(cl):
    p = CG / "listshort_meme_category.json"
    if not p.exists():
        rows, page = [], 1
        while True:
            b = cg_get(cl, "https://api.coingecko.com/api/v3/coins/markets",
                       {"vs_currency": "usd", "category": "meme-token", "per_page": 250, "page": page})
            if not b:
                break
            rows += [{k: x.get(k) for k in ("id", "symbol", "name", "market_cap", "market_cap_rank")} for x in b]
            page += 1
            time.sleep(4)
        save(p, rows)
    p2 = CG / "listshort_coins_list.json"
    if not p2.exists():
        save(p2, cg_get(cl, "https://api.coingecko.com/api/v3/coins/list"))


if __name__ == "__main__":
    with httpx.Client(timeout=60) as cl:
        hl_meta(cl)
        binance_symbols(cl)
        coingecko(cl)
    print("ok")
