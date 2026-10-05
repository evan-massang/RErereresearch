"""H-LISTBASIS step 1: count clean Solana-memecoin perp listing events per split (no P&L, no prices beyond
spot-availability probes around the listing date). Holdout rows record existence only.

Universe (declared before any outcome):
  - Solana memecoin = CoinGecko category `solana-meme-coins` (api /coins/markets?category=solana-meme-coins,
    fetched today). Venue base symbol (prefixes k / 1000 / 1000000 / 1M stripped) must match a coin in that
    category, and that coin must be the largest-mcap CoinGecko coin with that symbol (listshort collision rule).
  - Venues: Hyperliquid main dex (`meta`, first 1d candle via candleSnapshot), Binance USDT-M (S3 archive
    data/futures/um/monthly/klines, first 1d kline), Lighter (`orderBooks.created_at`; matches first funding
    stamps checked in PROPCARRY: PUMP 2025-07-14, PENGU 2025-07-23, TRUMP 2025-01-30).
  - Event = (venue, coin) first trading day. Clean = spot history covers [listing, listing+21d] from Binance spot
    archive, MEXC 60m klines or Gate 4h candlesticks; and coin not in round-3's 23 "seen" set.
  - Splits: train <= 2025-06-30, validation 2025-07-01..2026-03-31, holdout >= 2026-04-01 (existence only,
    no spot probe, no prices).
Caches under data/raw/web/listbasis/. Writes research/observations/evidence_listbasis_counts.json.
"""
import io, json, re, time, zipfile, datetime as dt
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "data/raw/web/listbasis"; C.mkdir(parents=True, exist_ok=True)
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
VAL0 = dt.datetime(2025, 7, 1, tzinfo=dt.timezone.utc); HOLD0 = dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc)
SEEN23 = None  # loaded from listshort evidence (seen23 flag) + round-3 names below
# Identity overrides, decided from asset identity only (no prices), documented in the counts JSON.
# REMOVE: symbol matched a Solana-meme ticker but the perp is a different asset.
REMOVE = {"XAU": "Lighter gold perp, not gold-8", "XAUUSDT": "Binance gold perp", "XPD": "palladium perp",
          "XPDUSDT": "palladium perp", "RONINUSDT": "Ronin (gaming L1)", "FOOTBALLUSDT": "pre-2023, unverifiable",
          "1MBABYDOGEUSDT": "Baby Doge Coin is BSC-native (bridged copies only)"}
# ADD: Solana-native meme/AI-meme tokens that CoinGecko files outside `solana-meme-coins` or that the
# largest-mcap collision rule dropped because the real coin's id is outside the category.
ADD = {"PUMP": "pump-fun", "PUMPUSDT": "pump-fun", "YZY": "yzy", "LAUNCHCOIN": "launch-coin-on-believe",
       "AI16Z": "ai16z", "AI16ZUSDT": "ai16z", "GRIFFAIN": "griffain", "GRIFFAINUSDT": "griffain",
       "JELLY": "jelly-my-jelly", "JELLYJELLYUSDT": "jelly-my-jelly", "CASHCAT": "cashcat"}
# Binance PUMPUSDT: archive files start 2025-04 with a different asset; the price is frozen at 0.0471 until
# 2025-07-09 and pump.fun PUMP trades from 2025-07-10 (daily bar 1752105600000). Listing date overridden.
FIRST_OVERRIDE = {("BN", "PUMPUSDT"): 1752105600000}
cl = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0"})


def cached(name, fn):
    p = C / name
    if p.exists():
        return json.loads(p.read_text())["data"]
    d = fn(); p.write_text(json.dumps({"fetched_at": time.time(), "data": d})); return d


def cg(url, params=None):
    for a in range(8):
        r = cl.get(url, params=params)
        if r.status_code == 429: time.sleep(20 * (a + 1)); continue
        r.raise_for_status(); return r.json()
    raise RuntimeError("cg 429")


def cg_cat():
    rows, page = [], 1
    while True:
        b = cg("https://api.coingecko.com/api/v3/coins/markets",
               {"vs_currency": "usd", "category": "solana-meme-coins", "per_page": 250, "page": page})
        if not b: return rows
        rows += [{k: x.get(k) for k in ("id", "symbol", "name", "market_cap")} for x in b]
        page += 1; time.sleep(4)


def split(t):
    return "train" if t < VAL0 else ("validation" if t < HOLD0 else "holdout")


def strip(s):
    for p in ("1000000", "1M", "1000", "k"):
        if s.startswith(p) and len(s) > len(p) and (p != "k" or s[1].isupper()):
            return s[len(p):]
    return s


def s3_prefixes(prefix):
    out, marker = [], ""
    while True:
        r = cl.get(S3, params={"prefix": prefix, "delimiter": "/", "marker": marker}); r.raise_for_status()
        out += [x for x in re.findall(r"<Prefix>([^<]+)</Prefix>", r.text) if x != prefix]
        out += re.findall(r"<Key>([^<]+)</Key>", r.text)
        if "<IsTruncated>true</IsTruncated>" not in r.text: return out
        marker = re.search(r"<NextMarker>([^<]+)</NextMarker>", r.text).group(1)


def main():
    cat = cached("cg_solana_meme_category.json", cg_cat)
    clist = json.loads((ROOT / "data/raw/web/coingecko/listshort_coins_list.json").read_text())["data"]
    by_sym = {}
    for c in clist: by_sym.setdefault(c["symbol"].lower(), []).append(c["id"])
    sol = {}
    for c in cat:
        s = c["symbol"].lower()
        if s not in sol or (c["market_cap"] or 0) > (sol[s]["market_cap"] or 0): sol[s] = c
    # venues
    hl_meta = cached("hl_meta.json", lambda: cl.post("https://api.hyperliquid.xyz/info", json={"type": "meta"}).json())
    bn_syms = cached("bn_um_symbols.json", lambda: sorted(x.rstrip("/").split("/")[-1] for x in s3_prefixes("data/futures/um/monthly/klines/")))
    lt = cached("lighter_orderbooks.json", lambda: cl.get("https://mainnet.zklighter.elliot.ai/api/v1/orderBooks").json())
    cands = []
    for u in hl_meta["universe"]: cands.append(("HL", u["name"], strip(u["name"])))
    for s in bn_syms:
        if s.endswith("USDT"): cands.append(("BN", s, strip(s[:-4])))
    for o in lt["order_books"]:
        if o["market_type"] == "perp" and "/" not in o["symbol"]: cands.append(("LT", o["symbol"], strip(o["symbol"])))
    cands = [c for c in cands if c[2].lower() in sol or c[1] in ADD]
    # collision rule: solana-meme coin must be largest mcap among same-symbol CoinGecko ids
    need = sorted({i for c in cands for i in by_sym.get(c[2].lower(), []) if len(by_sym[c[2].lower()]) > 1})
    def caps():
        out = {}
        for k in range(0, len(need), 50):
            for x in cg("https://api.coingecko.com/api/v3/coins/markets", {"vs_currency": "usd", "ids": ",".join(need[k:k+50]), "per_page": 250}):
                out[x["id"]] = x.get("market_cap")
            time.sleep(8)
        return out
    capm = cached("cg_collision_caps.json", caps)
    keep, dropped = [], []
    for v, sym, base in cands:
        if sym in REMOVE: dropped.append((v, sym, base, "identity_override_remove", REMOVE[sym])); continue
        if sym in ADD: keep.append((v, sym, base, ADD[sym], ADD[sym])); continue
        ids = by_sym.get(base.lower(), [])
        me = sol[base.lower()]["id"]
        best = max(ids, key=lambda i: capm.get(i) or 0) if len(ids) > 1 else me
        (keep if best == me else dropped).append((v, sym, base, me, best))
    return sol, keep, dropped, lt


def first_date(v, sym, lt):
    if (v, sym) in FIRST_OVERRIDE: return FIRST_OVERRIDE[(v, sym)]
    if v == "LT":
        o = next(o for o in lt["order_books"] if o["symbol"] == sym)
        return int(o["created_at"])
    if v == "HL":
        def f():
            return cl.post("https://api.hyperliquid.xyz/info", json={"type": "candleSnapshot", "req": {
                "coin": sym, "interval": "1d", "startTime": 1640995200000, "endTime": int(time.time() * 1000)}}).json()
        c = cached(f"hl_1d_{sym}.json", f)
        return int(c[0]["t"]) if c else None
    def f():
        ks = [k for k in s3_prefixes(f"data/futures/um/monthly/klines/{sym}/1d/") if k.endswith(".zip")]
        if not ks: return None
        z = zipfile.ZipFile(io.BytesIO(cl.get(f"https://data.binance.vision/{sorted(ks)[0]}").content))
        line = z.read(z.namelist()[0]).decode().splitlines()
        line = [l for l in line if l[:1].isdigit()]
        return int(line[0].split(",")[0])
    return cached(f"bn_first_{sym}.json", f)


def spot_probe(base, t0ms):
    """Spot coverage of [listing, listing+21d]: list of sources that have >= 90% of the 4h/1h bars."""
    t1ms = t0ms + 21 * 86400000
    got = {}
    # Binance spot archive (monthly 1h files present for the listing month and the month of t1)
    def bsp():
        ks = [k for k in s3_prefixes(f"data/spot/monthly/klines/{base}USDT/1h/") if k.endswith(".zip")]
        return sorted(k.split("-1h-")[-1][:7] for k in ks)
    months = cached(f"bnspot_months_{base}.json", bsp)
    m0 = dt.datetime.utcfromtimestamp(t0ms / 1000).strftime("%Y-%m"); m1 = dt.datetime.utcfromtimestamp(t1ms / 1000).strftime("%Y-%m")
    got["binance_spot"] = bool(months) and months[0] <= m0 and m1 in months
    def mexc():
        r = cl.get("https://api.mexc.com/api/v3/klines", params={"symbol": f"{base}USDT", "interval": "4h", "startTime": t0ms, "endTime": t1ms, "limit": 1000})
        return r.json() if r.status_code == 200 else {"status": r.status_code, "body": r.text[:200]}
    m = cached(f"mexc_4h_{base}_{t0ms}.json", mexc)
    got["mexc"] = isinstance(m, list) and len(m) >= 0.9 * 126 and m[0][0] <= t0ms + 86400000
    def gate():
        r = cl.get("https://api.gateio.ws/api/v4/spot/candlesticks", params={"currency_pair": f"{base}_USDT", "interval": "4h", "from": t0ms // 1000, "to": t1ms // 1000})
        return r.json() if r.status_code == 200 else {"status": r.status_code, "body": r.text[:200]}
    g = cached(f"gate_4h_{base}_{t0ms}.json", gate)
    got["gate"] = isinstance(g, list) and len(g) >= 0.9 * 126 and int(g[0][0]) * 1000 <= t0ms + 86400000
    return got


if __name__ == "__main__":
    sol, keep, dropped, lt = main()
    ls = json.loads((ROOT / "research/observations/evidence_listshort_universe.json").read_text())
    seen = {"WIF", "BONK", "POPCAT", "MEW", "BOME", "MYRO", "GOAT", "MOODENG", "PNUT", "CHILLGUY", "FARTCOIN", "PENGU",
            "AI16Z", "ZEREBRO", "GRIFFAIN", "TRUMP", "MELANIA", "VINE", "JELLY", "LAUNCHCOIN", "PUMP", "USELESS", "YZY"}
    # round-3 OWN-PRECHECK set of 23 HL Solana-meme listings: names recorded in listshort's seen23 flags (+LAUNCHCOIN,
    # which round 3 used but listshort excluded as non-meme-category)
    ev = []
    for v, sym, base, cid, _ in keep:
        t = first_date(v, sym, lt)
        if t is None:
            ev.append({"venue": v, "symbol": sym, "base": base, "cg_id": cid, "listing_utc": None, "split": None, "status": "no_venue_history"}); continue
        T = dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc)
        e = {"venue": v, "symbol": sym, "base": base, "cg_id": cid, "listing_utc": T.isoformat(), "split": split(T),
             "seen23": base.upper() in seen or base.upper() == "JELLYJELLY"}
        if T.year < 2023: e["split"] = "pre2023"
        if e["split"] in ("train", "validation"):
            e["spot"] = spot_probe({"JELLY": "JELLYJELLY"}.get(base.upper(), base.upper()), t)
            e["spot_ok"] = any(e["spot"].values())
        ev.append(e)
        time.sleep(0.2)
    def cnt(sp):
        xs = [e for e in ev if e["split"] == sp]
        return {"venue_events": len(xs), "with_spot": sum(e.get("spot_ok", False) for e in xs),
                "clean": sum(e.get("spot_ok", False) and not e["seen23"] for e in xs),
                "contaminated_with_spot": sum(e.get("spot_ok", False) and e["seen23"] for e in xs),
                "distinct_coins_clean_or_contam_with_spot": len({e["base"] for e in xs if e.get("spot_ok")}),
                "by_venue": {v: sum(e["venue"] == v for e in xs) for v in ("HL", "BN", "LT")}}
    out = {"hypothesis": "H-LISTBASIS", "generated": dt.datetime.now(dt.timezone.utc).isoformat(), "doc": __doc__,
           "n_solana_meme_category": len(sol),
           "counts": {sp: cnt(sp) for sp in ("train", "validation")},
           "holdout_existence_only": sorted(f"{e['venue']}:{e['symbol']}" for e in ev if e["split"] == "holdout"),
           "events": sorted([e for e in ev if e["split"] != "holdout"], key=lambda e: e["listing_utc"] or ""),
           "dropped_symbol_collision": [{"venue": v, "symbol": s, "base": b, "solana_meme_id": m, "largest_id": bst} for v, s, b, m, bst in dropped]}
    p = ROOT / "research/observations/evidence_listbasis_counts.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out["counts"], indent=1)); print(out["holdout_existence_only"])
