"""First Hyperliquid daily candle per coin (proxy for HL listing date), via public info API candleSnapshot 1d.
Output: data/raw/web/pairs/hl_first_day.json"""
import json, time
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/pairs"
m = json.load(open(OUT / "hl_meta_20261005.json"))
res = {}
for u in m["universe"]:
    c = u["name"]
    for i in range(4):
        try:
            r = requests.post("https://api.hyperliquid.xyz/info", json={"type": "candleSnapshot", "req": {"coin": c, "interval": "1d", "startTime": 1640995200000, "endTime": 1790000000000}}, timeout=30)
            r.raise_for_status(); d = r.json(); break
        except Exception as e:
            d = None; time.sleep(2 + 3 * i)
    res[c] = {"first_t": d[0]["t"] if d else None, "last_t": d[-1]["t"] if d else None, "n": len(d) if d else 0}
    time.sleep(0.25)
json.dump(res, open(OUT / "hl_first_day.json", "w"), indent=0)
print(sum(1 for v in res.values() if v["first_t"]), "of", len(res))
