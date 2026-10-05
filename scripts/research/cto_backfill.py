"""Backfill DexScreener paid orders (incl. communityTakeover) for every recorded migrated mint, and sample the
public CTO feed to measure the payment -> public (claimDate) visibility lag.

Public, keyless endpoints (60 req/min): /orders/v1/solana/{mint}, /community-takeovers/latest/v1.
Writes research/observations/evidence_cto_orders_backfill.json (raw order rows per mint, receive time stamped).

    python scripts/research/cto_backfill.py backfill
    python scripts/research/cto_backfill.py lag
"""
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OHLCV = ROOT / "data/raw/web/ohlcv15"
OUT = ROOT / "research/observations/evidence_cto_orders_backfill.json"
LAG = ROOT / "research/observations/evidence_cto_visibility_lag.json"
API = "https://api.dexscreener.com"


def get(cl, url):
    for attempt in range(5):
        try:
            r = cl.get(url)
        except httpx.HTTPError:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429:
            time.sleep(20 * (attempt + 1))
            continue
        return r
    return None


def backfill():
    mints = sorted({json.loads(f.read_text())["mint"] for f in OHLCV.glob("*.json")})
    res = json.loads(OUT.read_text()) if OUT.exists() else {"source": f"{API}/orders/v1/solana/<mint>", "rows": {}}
    with httpx.Client(timeout=20) as cl:
        for i, m in enumerate(mints):
            if m in res["rows"]:
                continue
            shared = ROOT / "data/raw/web/dexscreener_orders" / f"{m}.json"   # agent dex_paid's cache (read only)
            if shared.exists():
                c = json.loads(shared.read_text())
                if isinstance(c.get("response"), dict) and "orders" in c["response"]:
                    res["rows"][m] = {"recv": c["fetched_at"], "via": "dexscreener_orders_cache", **c["response"]}
                    continue
            r = get(cl, f"{API}/orders/v1/solana/{m}")
            if r is None or r.status_code != 200:
                res["rows"][m] = {"error": None if r is None else r.status_code, "recv": time.time()}
            else:
                res["rows"][m] = {"recv": time.time(), **r.json()}
            if i % 50 == 0:
                OUT.write_text(json.dumps(res))
                print(i, len(mints), flush=True)
            time.sleep(1.05)
    OUT.write_text(json.dumps(res))
    print("done", len(res["rows"]))


def lag():
    """Feed claimDate minus orders paymentTimestamp for the CTOs currently in the public feed."""
    from datetime import datetime
    with httpx.Client(timeout=20) as cl:
        feed = get(cl, f"{API}/community-takeovers/latest/v1").json()
        rows = []
        for e in feed:
            r = get(cl, f"{API}/orders/v1/{e['chainId']}/{e['tokenAddress']}")
            time.sleep(1.05)
            if r is None or r.status_code != 200:
                continue
            pays = [o["paymentTimestamp"] / 1000 for o in r.json().get("orders", []) if o["type"] == "communityTakeover"]
            claim = datetime.fromisoformat(e["claimDate"].replace("Z", "+00:00")).timestamp() if e.get("claimDate") else None
            rows.append({"chain": e["chainId"], "mint": e["tokenAddress"], "claim": claim, "payments": pays,
                         "lag_s": (claim - max(p for p in pays if p <= claim)) if claim and any(p <= claim for p in pays) else None})
    LAG.write_text(json.dumps({"recv": time.time(), "rows": rows}, indent=1))
    print(len(rows), sorted(r["lag_s"] for r in rows if r["lag_s"] is not None))


if __name__ == "__main__":
    {"backfill": backfill, "lag": lag}[sys.argv[1]]()
