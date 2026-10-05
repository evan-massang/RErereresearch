"""H-FUNDCARRY data fetch: Hyperliquid funding/premium + daily/4h perp candles, and hourly CEX spot for Solana memecoin perps.

Public, unauthenticated endpoints only:
  - Hyperliquid info API  POST https://api.hyperliquid.xyz/info  (meta, fundingHistory, candleSnapshot)
    NOTE: candleSnapshot only serves the most recent 5000 candles per interval, so 1h perp candles cannot
    reach the train period; we keep 1d and 4h. The hourly basis comes from fundingHistory.premium.
  - DexScreener tokens/v1 (verifies the Solana mint of each mapped coin; lead/document only)
  - Spot hourly klines, first venue that has the pair: Binance (data-api.binance.vision), OKX, MEXC.
    (GeckoTerminal public OHLCV only serves the last 180 days -> HTTP 401 for train dates; Bybit is geo-blocked.)

HOLDOUT GUARD: nothing at or after 2026-07-01T00:00Z is written to disk.

    python scripts/research/fundcarry_fetch.py
"""
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
HL = ROOT / "data/raw/web/hyperliquid"
SPOT = ROOT / "data/raw/web/spot_ohlcv"
CUTOFF_MS = 1782864000000  # 2026-07-01T00:00:00Z  (holdout start; never stored)
START_MS = 1698796800000   # 2023-11-01

# Documented mapping: Hyperliquid perp name -> (Solana SPL mint, spot symbol, price multiplier perp/spot).
# Mints were written from public token lists and are VERIFIED below against DexScreener tokens/v1
# (symbol + chain must match); unverified rows are dropped. Coins whose Solana mint we could not find
# (CASHCAT, PONS) are excluded. Non-Solana memes (kPEPE, kSHIB, kNEIRO, TURBO, BRETT, SPX, AIXBT, TST, kDOGS,
# kFLOKI, MEME, NEIROETH) and Solana non-memes (JUP, JTO, W, PYTH, TNSR, ME, MET, SKR) are out of scope.
MAP = {
    "WIF": ("EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "WIF", 1),
    "kBONK": ("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "BONK", 1000),
    "POPCAT": ("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "POPCAT", 1),
    "MEW": ("MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5", "MEW", 1),
    "BOME": ("ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82", "BOME", 1),
    "MYRO": ("HhJpBhRRn4g56VsyLuT8DL5Bv31HkXqsrahTTUCZeZg4", "MYRO", 1),
    "GOAT": ("CzLSujWBLFsSjncfkh59rUFqvafWcY5tzedWJSuypump", "GOAT", 1),
    "MOODENG": ("ED5nyyWEzpPPiWimP8vYm7sD7TD3LAt3Q3gRTWHzPJBY", "MOODENG", 1),
    "PNUT": ("2qEHjDLDLbuBgRYvsxhc5D6uDWAivNFZGan56P1tpump", "PNUT", 1),
    "CHILLGUY": ("Df6yfrKC8kZE3KNkrHERKzAetSxbrWeniQfyJY4Jpump", "CHILLGUY", 1),
    "FARTCOIN": ("9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump", "FARTCOIN", 1),
    "AI16Z": ("HeLp6NuQkmYB4pYWo2zYs22mESHXPQYzXbB8n4V98jwC", "AI16Z", 1),
    "ZEREBRO": ("8x5VqbHA8D7NkD52uNuS5nnt3PwA8pLD34ymskeSo2Wn", "ZEREBRO", 1),
    "GRIFFAIN": ("KENJSUYLASHUMfHyy5o4Hp2FdNqZg1AsUPhfH2kYvEP", "GRIFFAIN", 1),
    "TRUMP": ("6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN", "TRUMP", 1),
    "MELANIA": ("FUAfBo2jgks6gB4Z4LfZkqSZgzNucisEHqnNebaRxM1P", "MELANIA", 1),
    "VINE": ("6AJcP7wuLwmRYLBNbi825wgguaPsWzPBEHcHndpRpump", "VINE", 1),
    "JELLY": ("FeR8VBqNRSUD5NtXAj2n3j1dAHkZHfyDktKuLXD4pump", "JELLYJELLY", 1),
    "LAUNCHCOIN": ("Ey59PH7Z4BFU4HjyKnyMdWt5GGN76KazTAwQihoUXRnk", "LAUNCHCOIN", 1),
    "PUMP": ("pumpCmXqMfrsAkQ5r49WcJnRayYRqmXz6ae8H7H9Dfn", "PUMP", 1),
    "USELESS": ("Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk", "USELESS", 1),
    "PENGU": ("2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv", "PENGU", 1),
    "YZY": ("DrZ26cKJDksVRWib3DVVsjo9eeXccc7hKhDJviiYEEZY", "YZY", 1),
}


def post(cl, body):
    for a in range(6):
        r = cl.post("https://api.hyperliquid.xyz/info", json=body)
        if r.status_code == 429:
            time.sleep(5 * (a + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("HL rate limited")


def funding(cl, coin):
    f = HL / f"funding_{coin}.json"
    if f.exists():
        return
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


def candles(cl, coin, interval):
    f = HL / f"candles_{interval}_{coin}.json"
    if f.exists():
        return
    b = post(cl, {"type": "candleSnapshot", "req": {"coin": coin, "interval": interval,
                                                     "startTime": START_MS, "endTime": CUTOFF_MS - 1}})
    b = [x for x in b if x["T"] < CUTOFF_MS]
    f.write_text(json.dumps({"coin": coin, "interval": interval, "fetched_at": time.time(), "rows": b}))
    time.sleep(0.3)


def spot_binance(cl, sym, t0):
    out, t = [], t0
    while t < CUTOFF_MS:
        r = cl.get("https://data-api.binance.vision/api/v3/klines",
                   params={"symbol": sym + "USDT", "interval": "1h", "startTime": t, "endTime": CUTOFF_MS - 1, "limit": 1000})
        if r.status_code != 200:
            return None
        b = r.json()
        if not b:
            break
        out += [[x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])] for x in b]
        t = b[-1][0] + 3600_000
        time.sleep(0.2)
    return out


def spot_okx(cl, sym, t0):
    out, after = [], CUTOFF_MS
    while True:
        r = cl.get("https://www.okx.com/api/v5/market/history-candles",
                   params={"instId": f"{sym}-USDT", "bar": "1H", "limit": 100, "after": after})
        j = r.json()
        if j.get("code") != "0":
            return None
        b = j["data"]
        if not b:
            break
        out += [[int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])] for x in b]
        after = int(b[-1][0])
        if after <= t0:
            break
        time.sleep(0.15)
    return sorted(x for x in out if t0 <= x[0] < CUTOFF_MS)


def spot_mexc(cl, sym, t0):
    out, t = [], t0
    while t < CUTOFF_MS:
        end = min(t + 1000 * 3600_000, CUTOFF_MS - 1)
        for a in range(4):
            try:
                r = cl.get("https://api.mexc.com/api/v3/klines",
                           params={"symbol": sym + "USDT", "interval": "60m", "startTime": t, "endTime": end, "limit": 1000})
                break
            except httpx.HTTPError:
                time.sleep(3)
        else:
            return None
        if r.status_code != 200:
            return None
        b = r.json()
        out += [[x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])] for x in b]
        # MEXC returns at most 500 rows per call: continue from the last row returned, not from `end`
        t = (b[-1][0] + 3600_000) if b and b[-1][0] + 3600_000 <= end else end + 1
        time.sleep(0.3)
    return sorted({x[0]: x for x in out if x[0] < CUTOFF_MS}.values())


def main():
    HL.mkdir(parents=True, exist_ok=True)
    SPOT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30) as cl:
        meta = post(cl, {"type": "meta"})
        (HL / "meta.json").write_text(json.dumps({"fetched_at": time.time(), "meta": meta}))
        names = {a["name"]: a for a in meta["universe"]}
        # verify mints
        ver = {}
        for coin, (mint, sym, mult) in MAP.items():
            r = cl.get(f"https://api.dexscreener.com/tokens/v1/solana/{mint}")
            pairs = r.json() if r.status_code == 200 else []
            syms = {p["baseToken"]["symbol"].upper().lstrip("$") for p in pairs if p["baseToken"]["address"] == mint}
            liq = max([(p.get("liquidity") or {}).get("usd", 0) for p in pairs] or [0])
            ver[coin] = {"mint": mint, "spot_symbol": sym, "mult": mult, "dexscreener_symbols": sorted(syms),
                         "dexscreener_liq_usd": liq, "on_hyperliquid": coin in names,
                         "hl_max_leverage_now": names.get(coin, {}).get("maxLeverage"),
                         "hl_delisted": names.get(coin, {}).get("isDelisted", False),
                         "verified": bool(syms) and coin in names}
            time.sleep(0.3)
        (HL / "universe_map.json").write_text(json.dumps(ver, indent=1))
        for coin, v in ver.items():
            if not v["verified"]:
                print("UNVERIFIED", coin, v)
                continue
            funding(cl, coin)
            candles(cl, coin, "1d")
            candles(cl, coin, "4h")
            fr = json.loads((HL / f"funding_{coin}.json").read_text())["rows"]
            if not fr:
                continue
            t0 = fr[0]["time"] // 3600_000 * 3600_000 - 7 * 86400_000
            f = SPOT / f"{coin}_1h.json"
            if f.exists():
                continue
            rows, venue = None, None
            for venue, fn in (("binance", spot_binance), ("okx", spot_okx), ("mexc", spot_mexc)):
                rows = fn(cl, v["spot_symbol"], t0)
                if rows:
                    # need coverage near the perp listing; otherwise try next venue
                    if rows[0][0] <= fr[0]["time"] + 3 * 86400_000:
                        break
                    print(coin, venue, "starts late", rows[0][0])
            if rows:
                f.write_text(json.dumps({"coin": coin, "venue": venue, "symbol": v["spot_symbol"] + "USDT",
                                         "cols": ["t_open_ms", "o", "h", "l", "c", "quote_vol"],
                                         "fetched_at": time.time(), "rows": rows}))
            print(coin, len(fr), venue, len(rows or []), flush=True)


if __name__ == "__main__":
    sys.exit(main())
