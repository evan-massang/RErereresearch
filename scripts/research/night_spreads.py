"""H-NIGHT: sample Lighter public order books for the tight-set memes + 1000BONK + BTC (real data).

Reuses the method of memelead_spreads.py: quoted spread and $1,000 round-trip VWAP cost in bp of mid, walking the
displayed book of https://mainnet.zklighter.elliot.ai/api/v1/orderBookOrders. Output JSONL in data/raw/web/night/.
"""
import json, sys, time, datetime, pathlib, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from memelead_spreads import snap

MARKETS = {"PUMP": 45, "DOGE": 3, "FARTCOIN": 21, "1000SHIB": 17, "TRUMP": 15, "1000PEPE": 4, "PENGU": 47,
           "WIF": 5, "1000BONK": 18, "BTC": 1}


def main(rounds=30, interval=20):
    out = pathlib.Path("data/raw/web/night") / f"lighter_spreads_{datetime.datetime.utcnow():%Y%m%dT%H%MZ}.jsonl"
    with open(out, "a") as f:
        for _ in range(rounds):
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
