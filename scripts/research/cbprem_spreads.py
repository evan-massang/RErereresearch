"""H-CBPREM: measure Lighter $1,000 round-trip cost per coin now (reuses memelead_spreads.snap; real data)."""
import json, time, datetime, pathlib, sys
sys.path.insert(0, "scripts/research")
from memelead_spreads import snap, MARKETS
COINS = ["DOGE", "1000PEPE", "WIF", "POPCAT", "1000FLOKI", "PENGU", "TRUMP", "1000BONK", "1000SHIB"]
out = pathlib.Path("data/raw/web/cbprem") / f"lighter_spreads_{datetime.datetime.utcnow():%Y%m%dT%H%MZ}.jsonl"
with open(out, "a") as f:
    for i in range(15):
        ts = time.time()
        for c in COINS:
            try: rec = snap(c, MARKETS[c])
            except Exception as e: rec = {"coin": c, "error": repr(e)}
            rec["ts"] = round(ts, 3); rec["is_synthetic"] = False; f.write(json.dumps(rec) + "\n")
        f.flush(); time.sleep(max(0, 20 - (time.time() - ts)))
print(out)
