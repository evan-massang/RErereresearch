"""H-PROPCARRY data fetch (pre-registration: reports/hypotheses/propcarry_preregistration.json).

Subcommands:
  jupiter   quote-implied round trips SOL->token->SOL at 0.5/2/5 SOL (QUOTES ONLY, no swap is ever built or sent)
  binance   data.binance.vision monthly fundingRate + 1h perp klines, months <= 2026-03 only (holdout guard)
  useless   USELESS spot 1h from MEXC public klines, < 2026-04-01 only
  lighter   probe Lighter public funding history depth (descriptive only)

Writes under data/raw/web/propcarry/. Aborts if free disk < 2.5 GB.
"""
import io, json, shutil, sys, time, zipfile, datetime as dt
import urllib.request, urllib.error

OUT = "data/raw/web/propcarry"
UA = {"User-Agent": "Mozilla/5.0 (research; quotes only)"}
HOLDOUT_MS = int(dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
MINTS = {  # verified in data/raw/web/hyperliquid/universe_map.json (DexScreener symbol match)
    "PENGU": "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv",
    "PUMP": "pumpCmXqMfrsAkQ5r49WcJnRayYRqmXz6ae8H7H9Dfn",
    "TRUMP": "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "FARTCOIN": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
    "USELESS": "Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk",
}
BIN = {"PENGU": "PENGUUSDT", "PUMP": "PUMPUSDT", "TRUMP": "TRUMPUSDT", "BONK": "1000BONKUSDT",
       "FARTCOIN": "FARTCOINUSDT", "USELESS": "USELESSUSDT"}


def disk_guard():
    free = shutil.disk_usage("/").free / 1e9
    if free < 2.5:
        sys.exit(f"ABORT: free disk {free:.2f} GB < 2.5 GB")
    return free


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def jquote(inp, out, amount):
    url = (f"https://lite-api.jup.ag/swap/v1/quote?inputMint={inp}&outputMint={out}"
           f"&amount={amount}&slippageBps=50")
    for i in range(4):
        try:
            _, b = get(url)
            return json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503):
                time.sleep(2 + 2 * i); continue
            raise
    raise RuntimeError("quote failed " + url)


def jupiter():
    res = {"fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
           "endpoint": "https://lite-api.jup.ag/swap/v1/quote (quote only; no swap built or sent)",
           "rows": []}
    for sol in (0.5, 2, 5):
        lam = int(sol * 1e9)
        for coin, mint in list(MINTS.items()) + [("USDC_hop", USDC)]:
            q1 = jquote(SOL, mint, lam)
            q2 = jquote(mint, SOL, int(q1["outAmount"]))
            back = int(q2["outAmount"])
            rt_bp = (1 - back / lam) * 1e4
            res["rows"].append({
                "coin": coin, "size_sol": sol, "in_lamports": lam, "token_out": q1["outAmount"],
                "sol_back_lamports": back, "rt_bp": round(rt_bp, 2),
                "impact_pct_leg1": q1.get("priceImpactPct"), "impact_pct_leg2": q2.get("priceImpactPct"),
                "route_leg1": [r["swapInfo"].get("label") for r in q1.get("routePlan", [])],
                "route_leg2": [r["swapInfo"].get("label") for r in q2.get("routePlan", [])],
            })
            print(coin, sol, round(rt_bp, 2), res["rows"][-1]["route_leg1"])
            time.sleep(1.1)
    json.dump(res, open(f"{OUT}/jupiter_quotes_20261005.json", "w"), indent=1)


def months(start=(2023, 11), end=(2026, 3)):
    y, m = start
    while (y, m) <= end:
        yield f"{y}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def binance():
    base = "https://data.binance.vision/data/futures/um/monthly"
    funding, klines, manifest = {}, {}, []
    for coin, sym in BIN.items():
        funding[coin], klines[coin] = [], []
        for mo in months():
            assert mo <= "2026-03"  # holdout guard
            for kind in ("fundingRate", "klines"):
                url = (f"{base}/fundingRate/{sym}/{sym}-fundingRate-{mo}.zip" if kind == "fundingRate"
                       else f"{base}/klines/{sym}/1h/{sym}-1h-{mo}.zip")
                try:
                    _, b = get(url)
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        continue
                    raise
                manifest.append({"url": url, "bytes": len(b)})
                z = zipfile.ZipFile(io.BytesIO(b))
                txt = z.read(z.namelist()[0]).decode()
                for line in txt.strip().splitlines():
                    p = line.split(",")
                    if not p[0][:1].isdigit():
                        continue
                    if kind == "fundingRate":  # calc_time, funding_interval_hours, last_funding_rate
                        t = int(p[0])
                        if t < HOLDOUT_MS:
                            funding[coin].append([t, int(p[1]), float(p[2])])
                    else:
                        t = int(p[0])
                        if t > 1e14: t //= 1000
                        if t < HOLDOUT_MS:
                            klines[coin].append([t, float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[7])])
        print(coin, len(funding[coin]), len(klines[coin]), f"free {disk_guard():.2f} GB")
    json.dump({"source": base, "cols": ["calc_time_ms", "interval_h", "rate"], "data": funding},
              open(f"{OUT}/binance_funding.json", "w"))
    json.dump({"source": base, "cols": ["t_open_ms", "o", "h", "l", "c", "quote_vol"], "data": klines},
              open(f"{OUT}/binance_perp_1h.json", "w"))
    json.dump(manifest, open(f"{OUT}/binance_manifest.json", "w"), indent=0)


def useless():
    rows, t0 = [], int(dt.datetime(2025, 5, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    while t0 < HOLDOUT_MS:
        t1 = min(t0 + 500 * 3600_000, HOLDOUT_MS)
        _, b = get(f"https://api.mexc.com/api/v3/klines?symbol=USELESSUSDT&interval=60m&startTime={t0}&endTime={t1}&limit=1000")
        for k in json.loads(b):
            if int(k[0]) < HOLDOUT_MS:
                rows.append([int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[7])])
        t0 = t1
        time.sleep(0.3)
    rows = sorted({r[0]: r for r in rows}.values())
    print("USELESS mexc rows", len(rows), rows[0][0] if rows else None)
    json.dump({"coin": "USELESS", "venue": "mexc", "symbol": "USELESSUSDT",
               "cols": ["t_open_ms", "o", "h", "l", "c", "quote_vol"],
               "fetched_at": time.time(), "rows": rows}, open(f"{OUT}/USELESS_spot_1h.json", "w"))


if __name__ == "__main__":
    import os
    os.makedirs(OUT, exist_ok=True)
    disk_guard()
    {"jupiter": jupiter, "binance": binance, "useless": useless}[sys.argv[1]]()
