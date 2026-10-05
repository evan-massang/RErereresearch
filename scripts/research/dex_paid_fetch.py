"""Backfill DexScreener paid orders (agent dex_paid, 2026-10-05). READ-ONLY on data/market.duckdb.

Sample (not conditioned on outcome): every mint whose trusted curve state (|vsol - rsol - 30| < 0.01) first reached
real SOL >= 20 inside the train or validation window (point-in-time milestone), excluding mints created in the
holdout. Each mint is queried once at
    GET https://api.dexscreener.com/orders/v1/solana/{mint}
(public, documented limit 60 req/min; we space requests >= 1.1 s). Raw responses are cached verbatim with the fetch
time under data/raw/web/dexscreener_orders/{mint}.json. Train mints are fetched first.

    python scripts/research/dex_paid_fetch.py
"""
import json
import time
from pathlib import Path

import duckdb
import requests

ROOT = Path("/home/user/RErereresearch")
OUT = ROOT / "data/raw/web/dexscreener_orders"
HOLD_A, HOLD_B, VAL_A, VAL_B = 1790882100, 1790899200, 1790985600, 1791072000
URL = "https://api.dexscreener.com/orders/v1/solana/{}"


def sample():
    con = duckdb.connect(str(ROOT / "data/market.duckdb"), read_only=True)
    d = con.execute("""
        with m as (select mint, min(recv) t20 from curve_trades
                   where rsol >= 20 and abs(vsol - rsol - 30) < 0.01 group by mint),
             c as (select mint, min(recv) ct from curve_creates group by mint)
        select m.mint, m.t20, c.ct from m left join c using(mint)""").df()
    con.close()
    t = d.t20
    d["split"] = None
    d.loc[(t < HOLD_A) | ((t >= HOLD_B) & (t < VAL_A)), "split"] = "train"
    d.loc[(t >= VAL_A) & (t < VAL_B), "split"] = "valid"
    d = d[d.split.notna()]
    d = d[~((d.ct >= HOLD_A) & (d.ct < HOLD_B))]
    return d.sort_values(["split", "t20"], key=lambda s: s.map({"train": 0, "valid": 1}) if s.name == "split" else s)


def main():
    d = sample()
    print("sample", d.split.value_counts().to_dict(), flush=True)
    s = requests.Session()
    s.headers["User-Agent"] = "RErereresearch/0.1 research backfill"
    done = 0
    for mint in d.mint:
        f = OUT / f"{mint}.json"
        if f.exists():
            continue
        for attempt in range(6):
            t0 = time.time()
            try:
                r = s.get(URL.format(mint), timeout=20)
                code = r.status_code
            except requests.RequestException as e:
                code, r = -1, None
                print("err", mint, e, flush=True)
            if code == 200:
                f.write_text(json.dumps({"mint": mint, "fetched_at": t0, "url": URL.format(mint),
                                         "response": r.json()}))
                break
            wait = 30 * (attempt + 1) if code == 429 else 5
            print("http", code, mint, "sleep", wait, flush=True)
            time.sleep(wait)
        done += 1
        if done % 200 == 0:
            print("done", done, time.strftime("%H:%M:%S"), flush=True)
        time.sleep(max(0.0, 1.1 - (time.time() - t0)))


if __name__ == "__main__":
    main()
