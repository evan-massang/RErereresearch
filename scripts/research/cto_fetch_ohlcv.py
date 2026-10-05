"""Refetch 15-min USD OHLCV (GeckoTerminal) for recorded migration pools with before_timestamp=1791072000, so the
cache never holds a bar at or after 1791072000 (bars are also filtered here as a second guard).
Writes data/raw/web/ohlcv15_cto/<pool>.json in the same format as data/raw/web/ohlcv15 (which is left untouched).

    python scripts/research/cto_fetch_ohlcv.py [ctos|alive|all]
"""
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data/raw/web/ohlcv15"
OUT = ROOT / "data/raw/web/ohlcv15_cto"
ORD = ROOT / "research/observations/evidence_cto_orders_backfill.json"
CUT = 1791072000


def main(which: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pools = [json.loads(f.read_text()) for f in SRC.glob("*.json")]
    if which == "ctos":
        rows = json.loads(ORD.read_text())["rows"]
        cto = {m for m, r in rows.items() if any(o["type"] == "communityTakeover" for o in r.get("orders", []))}
        pools = [p for p in pools if p["mint"] in cto]
    elif which == "alive":   # pools with a bar in the last 3 h of the Oct-3 fetch (the only plausible controls later)
        pools = [p for p in pools if p["ohlcv"] and p["fetched_at"] - p["ohlcv"][-1][0] < 3 * 3600]
    done = fail = 0
    with httpx.Client(timeout=20, headers={"Accept": "application/json"}) as cl:
        for p in sorted(pools, key=lambda p: p["migrated_recv"]):
            f = OUT / f"{p['pool']}.json"
            if f.exists():
                continue
            r = None
            for attempt in range(5):
                try:
                    r = cl.get(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{p['pool']}/ohlcv/minute",
                               params={"aggregate": 15, "limit": 1000, "currency": "usd", "before_timestamp": CUT})
                except httpx.HTTPError:
                    time.sleep(10)
                    continue
                if r.status_code == 429:
                    time.sleep(20 * (attempt + 1))
                    continue
                break
            if r is not None and r.status_code == 200:
                bars = sorted(b for b in r.json()["data"]["attributes"]["ohlcv_list"] if b[0] + 900 <= CUT)
                f.write_text(json.dumps({"pool": p["pool"], "mint": p["mint"], "migrated_recv": p["migrated_recv"],
                                         "fetched_at": time.time(), "data_cut": CUT, "ohlcv": bars}))
                done += 1
            else:
                fail += 1
            time.sleep(2.2)
    print({"fetched": done, "failed": fail, "pools": len(pools)})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ctos")
