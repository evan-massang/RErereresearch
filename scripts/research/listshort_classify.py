"""H-LISTSHORT step 2: classify perp listings as memecoins (pre-declared rule) -> candidate list.

Pre-declared memecoin rule (fixed before any price data was looked at):
  * A perp's base asset is its symbol with the venue's size prefix removed
    (Hyperliquid 'k' = 1000x; Binance '1000000', '1000', '1M') and the quote (USDT) removed.
    Only USDT-margined Binance perps are used (USDC/BUSD duplicates and dated futures dropped);
    'SETTLED' suffix symbols are dropped.
  * It is a memecoin if a coin with that symbol (case-insensitive) is in CoinGecko's
    "meme-token" category (https://www.coingecko.com/en/categories/meme-token, API
    /coins/markets?category=meme-token, fetched 2026-10-05) AND that meme coin is the largest
    (by CoinGecko market cap) of all CoinGecko coins sharing the symbol, or the only one with a
    market cap. Collisions are resolved by /coins/markets?ids=..., cached.
  * Era: listings from 2023-01-01 (Hyperliquid perps start in 2023). Earlier listings are counted
    and excluded.
Writes data/raw/web/coingecko/listshort_collisions.json (cache) and returns the candidate list.
"""
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
CG = ROOT / "data/raw/web/coingecko"
HL = ROOT / "data/raw/web/hyperliquid"
BN = ROOT / "data/raw/web/binance_fut"


def load(p):
    return json.loads(Path(p).read_text())["data"]


def hl_base(name):
    if name.startswith("k") and name[1:].isupper():
        return name[1:], 1000
    return name, 1


def bn_base(sym):
    if not sym.endswith("USDT") or "SETTLED" in sym or "_" in sym:
        return None, None
    b = sym[:-4]
    for pre, m in (("1000000", 1_000_000), ("1000", 1000), ("1M", 1_000_000)):
        if b.startswith(pre) and len(b) > len(pre):
            return b[len(pre):], m
    return b, 1


def meme_symbols():
    meme = load(CG / "listshort_meme_category.json")
    allc = load(CG / "listshort_coins_list.json")
    by_sym = {}
    for c in allc:
        by_sym.setdefault(c["symbol"].lower(), []).append(c["id"])
    meme_by_sym = {}
    for m in meme:
        meme_by_sym.setdefault(m["symbol"].lower(), []).append(m)
    return meme_by_sym, by_sym


def resolve_collisions(cands, meme_by_sym, by_sym):
    """For symbols with >1 CoinGecko id, fetch market caps of all ids (cached)."""
    p = CG / "listshort_collisions.json"
    cache = load(p) if p.exists() else {}
    need = sorted({i for s in cands if s in meme_by_sym and len(by_sym.get(s, [])) > 1
                   for i in by_sym[s] if i not in cache})
    with httpx.Client(timeout=60) as cl:
        for k in range(0, len(need), 50):
            chunk = need[k:k + 50]
            for a in range(8):
                r = cl.get("https://api.coingecko.com/api/v3/coins/markets",
                           params={"vs_currency": "usd", "ids": ",".join(chunk), "per_page": 250})
                if r.status_code == 429:
                    time.sleep(20 * (a + 1))
                    continue
                r.raise_for_status()
                break
            got = {x["id"]: x.get("market_cap") for x in r.json()}
            for i in chunk:
                cache[i] = got.get(i)  # None = no market data on CoinGecko
            time.sleep(5)
    if need:
        p.write_text(json.dumps({"fetched_at": time.time(), "data": cache}))
    return cache


def is_meme(sym, meme_by_sym, by_sym, caps):
    s = sym.lower()
    if s not in meme_by_sym:
        return False, "not in meme-token category"
    ids = by_sym.get(s, [])
    if len(ids) <= 1:
        return True, "unique symbol"
    meme_ids = {m["id"] for m in meme_by_sym[s]}
    ranked = sorted(((caps.get(i) or 0), i) for i in ids)
    top_cap, top_id = ranked[-1]
    if top_cap == 0:
        return True, "collision, no caps; meme id kept"
    return (top_id in meme_ids), f"collision: largest={top_id}"


# Documented identity corrections (made from asset identity only, before any price data was loaded).
# Symbol matching can pick a different coin than the one the perp tracks; these fix that both ways.
REMOVE = {
    "AI": "Sleepless AI (perp asset), not the matched 'Artificial Inu'; Sleepless AI not in meme-token",
    "OMNI": "Omni Network (perp asset), not 'OmniCat'; Omni Network not in meme-token",
    "AMC": "US stock perp (AMC Entertainment), not a crypto memecoin",
    "GME": "US stock perp (GameStop), not a crypto memecoin",
    "HOOD": "US stock perp (Robinhood), not a crypto memecoin",
    "COPPER": "commodity perp (copper), matched coin is a $9k 'Copper Inu'",
    "XAU": "commodity perp (gold)", "XPD": "commodity perp (palladium)",
    "FOOTBALL": "identity unverified; matched coin has a ~$3k market cap",
    "MILK": "MilkyWay (liquid staking) perp, not 'Cool Cats Milk'",
    "RONIN": "Ronin network perp, not the $0.4M 'RONIN' meme",
    "RATS": "ordinals 'rats' perp; matched 'GoldenRat' is a different coin; rats not in meme-token",
    "X": "X Empire perp; x-empire not in meme-token (matched 'Free Speech' is a different coin)",
    "KORU": "identity unverified; matched coin has a ~$11k market cap",
}
ADD = {
    "HPOS": "HarryPotterObamaSonic10Inu; CoinGecko symbol is BITCOIN, id harrypotterobamasonic10inu in meme-token",
    "NEIROETH": "Neiro on Ethereum; venue suffix ETH; CoinGecko 'neiro' coins are in meme-token",
    "BROCCOLI714": "Broccoli (BSC, contract ...714); Broccoli coins are in meme-token",
    "BROCCOLIF3B": "Broccoli (BSC, contract ...f3b); Broccoli coins are in meme-token",
}


def candidates():
    meme_by_sym, by_sym = meme_symbols()
    hl = load(HL / "listshort_meta.json")["universe"]
    bn = load(BN / "listshort_um_symbols.json")
    rows = []
    for u in hl:
        b, m = hl_base(u["name"])
        rows.append({"venue": "HL", "symbol": u["name"], "base": b, "mult": m,
                     "delisted": bool(u.get("isDelisted"))})
    for s in bn:
        b, m = bn_base(s)
        if b:
            rows.append({"venue": "BN", "symbol": s, "base": b, "mult": m, "delisted": None})
    caps = resolve_collisions({r["base"].lower() for r in rows}, meme_by_sym, by_sym)
    out = []
    for r in rows:
        ok, why = is_meme(r["base"], meme_by_sym, by_sym, caps)
        if r["base"] in REMOVE:
            ok, why = False, "override remove: " + REMOVE[r["base"]]
        if r["base"] in ADD:
            ok, why = True, "override add: " + ADD[r["base"]]
        r["meme"], r["meme_reason"] = ok, why
        out.append(r)
    return out


if __name__ == "__main__":
    c = candidates()
    m = [r for r in c if r["meme"]]
    print(len(c), "perps;", len(m), "meme")
    for r in m:
        print(r["venue"], r["symbol"], r["base"], r["meme_reason"])
    print("--- rejected by collision:")
    for r in c:
        if not r["meme"] and r["meme_reason"].startswith("collision"):
            print(r["venue"], r["symbol"], r["meme_reason"])
