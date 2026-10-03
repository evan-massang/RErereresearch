"""Fetch 15-minute OHLCV (USD) from GeckoTerminal for every PumpSwap pool of a token that migrated while recording.

The universe is every recorded migration (survivors and dead tokens alike), so there is no survivorship bias.
Cached as data/raw/web/ohlcv15/<pool>.json; reruns refresh pools whose last fetch is older than --max-age-h.
Free API: ~30 calls/min, so requests are spaced 2.1 s apart.

    python scripts/research/fetch_pool_ohlcv.py [--max-age-h 6]
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import httpx  # noqa: E402

from pipeline import config  # noqa: E402

OUT = ROOT / "data/raw/web/ohlcv15"


def main(max_age_h: float) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    pools = con.execute("""SELECT p.pool, p.mint, min(p.recv) FROM amm_pools p JOIN curve_completes USING (mint)
                           GROUP BY 1, 2 ORDER BY 3""").fetchall()
    con.close()
    done = fail = 0
    with httpx.Client(timeout=20, headers={"Accept": "application/json"}) as cl:
        for pool, mint, t in pools:
            f = OUT / f"{pool}.json"
            if f.exists() and time.time() - json.loads(f.read_text()).get("fetched_at", 0) < max_age_h * 3600:
                continue
            for attempt in range(4):
                r = cl.get(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute",
                           params={"aggregate": 15, "limit": 1000, "currency": "usd"})
                if r.status_code == 429:
                    time.sleep(15 * (attempt + 1))
                    continue
                break
            if r.status_code == 200:
                rows = r.json()["data"]["attributes"]["ohlcv_list"]
                f.write_text(json.dumps({"pool": pool, "mint": mint, "migrated_recv": t, "fetched_at": time.time(),
                                         "ohlcv": sorted(rows)}))
                done += 1
            else:
                fail += 1
            time.sleep(2.1)
    print({"fetched": done, "failed": fail, "pools": len(pools)})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-h", type=float, default=6)
    main(ap.parse_args().max_age_h)
