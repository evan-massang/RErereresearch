"""H-MEMELEAD: measure Lighter public order-book round-trip cost per coin (real data, not synthetic).

Polls https://mainnet.zklighter.elliot.ai/api/v1/orderBookOrders (public, unauthenticated) for each coin every
INTERVAL s, N rounds. For each snapshot records best bid/ask, quoted spread (bp of mid) and the $1,000 round-trip
cost: (VWAP to buy $1,000 - VWAP to sell $1,000) / mid in bp (walks the displayed book). Output: one JSON line per
snapshot in data/raw/web/memelead/lighter_spreads_<UTC>.jsonl.
"""
import json, sys, time, urllib.request, datetime, pathlib

MARKETS = {"DOGE": 3, "1000PEPE": 4, "WIF": 5, "FARTCOIN": 21, "PUMP": 45, "POPCAT": 23, "1000FLOKI": 19,
           "PENGU": 47, "SPX": 42, "TRUMP": 15, "1000BONK": 18, "1000SHIB": 17, "USELESS": 66}
URL = "https://mainnet.zklighter.elliot.ai/api/v1/orderBookOrders?market_id={}&limit=100"
NOTIONAL = 1000.0


def vwap(levels, usd):
    got_q = got_usd = 0.0
    for px, q in levels:
        take = min(q, (usd - got_usd) / px)
        got_q += take; got_usd += take * px
        if got_usd >= usd - 1e-9:
            return got_usd / got_q
    return None  # displayed depth (top 100 orders) insufficient


def snap(coin, mid_id):
    with urllib.request.urlopen(URL.format(mid_id), timeout=20) as r:
        d = json.load(r)
    asks = sorted((float(o["price"]), float(o["remaining_base_amount"])) for o in d["asks"])
    bids = sorted(((float(o["price"]), float(o["remaining_base_amount"])) for o in d["bids"]), reverse=True)
    if not asks or not bids:
        return {"coin": coin, "empty": True}
    a, b = asks[0][0], bids[0][0]
    mid = (a + b) / 2
    va, vb = vwap(asks, NOTIONAL), vwap(bids, NOTIONAL)
    return {"coin": coin, "bid": b, "ask": a, "quoted_bp": (a - b) / mid * 1e4,
            "rt1000_bp": ((va - vb) / mid * 1e4) if va and vb else None}


def main(rounds=40, interval=20):
    out = pathlib.Path("data/raw/web/memelead") / f"lighter_spreads_{datetime.datetime.utcnow():%Y%m%dT%H%MZ}.jsonl"
    with open(out, "a") as f:
        for i in range(rounds):
            ts = time.time()
            for c, m in MARKETS.items():
                try:
                    rec = snap(c, m)
                except Exception as e:  # recorded, not hidden
                    rec = {"coin": c, "error": repr(e)}
                rec["ts"] = round(ts, 3); rec["is_synthetic"] = False
                f.write(json.dumps(rec) + "\n")
            f.flush()
            time.sleep(max(0, interval - (time.time() - ts)))
    print(out)


if __name__ == "__main__":
    main(*map(int, sys.argv[1:]))
