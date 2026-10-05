"""H-UNLOCK step 1: map DefiLlama emissions protocols to Binance USDT-M perp symbols.

Mapping rule: DefiLlama gecko_id -> ticker (coins.llama.fi), candidate Binance symbols
<SYM>USDT, 1000<SYM>USDT, 1000000<SYM>USDT, 1M<SYM>USDT. A candidate is accepted only if the
Binance daily close and the DefiLlama historical price (x multiplier) agree within 15% on
3 dates inside the Binance history (median ratio in [0.85, 1.15]). Only prices before
2026-04-01 are compared (holdout untouched). No returns are computed here.
"""
import json, time, urllib.request, urllib.parse, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
U = ROOT / "data/raw/web/unlock"
KL = ROOT / "data/raw/web/momentum/klines"

def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            time.sleep(2 + 3 * i); err = e
    raise err

idx = json.load(open(U / "emissionsIndex.json"))["data"]
syms = set(json.load(open(ROOT / "data/raw/web/momentum/symbols.json")))
gids = sorted({p["gecko_id"] for p in idx if p.get("gecko_id")})
cache = U / "llama_symbols.json"
if cache.exists():
    gsym = json.load(open(cache))
else:
    gsym = {}
    for i in range(0, len(gids), 60):
        ch = gids[i:i + 60]
        d = get("https://coins.llama.fi/prices/current/" + ",".join("coingecko:" + g for g in ch))
        for k, v in d["coins"].items():
            gsym[k.split(":", 1)[1]] = v.get("symbol")
    json.dump(gsym, open(cache, "w"))

out, rej = [], []
for p in idx:
    g = p.get("gecko_id"); s = gsym.get(g) if g else None
    if not s:
        rej.append({"protocol": p.get("protocolSlug") or p["name"], "gecko_id": g, "why": "no symbol"}); continue
    s = s.upper()
    cands = [(f"{s}USDT", 1), (f"1000{s}USDT", 1000), (f"1000000{s}USDT", 1e6), (f"1M{s}USDT", 1e6)]
    cands = [(c, m) for c, m in cands if c in syms and (KL / f"{c}.parquet").exists()]
    if not cands:
        rej.append({"protocol": p.get("protocolSlug") or p["name"], "gecko_id": g, "symbol": s, "why": "no binance perp"}); continue
    ok = None
    for c, m in cands:
        k = pd.read_parquet(KL / f"{c}.parquet")
        if len(k) < 10: continue
        pos = [int(len(k) * q) for q in (0.2, 0.5, 0.9)]
        ts = [int(k.open_time.iloc[j] // 1000) + 86399 for j in pos]
        d = get("https://coins.llama.fi/batchHistorical?coins=" + urllib.parse.quote(json.dumps({f"coingecko:{g}": ts})))
        pr = d.get("coins", {}).get(f"coingecko:{g}", {}).get("prices", [])
        rat = []
        for j, t in zip(pos, ts):
            near = [x for x in pr if abs(x["timestamp"] - t) < 6 * 3600]
            if near:
                rat.append(k.close.iloc[j] / (near[0]["price"] * m))
        if len(rat) >= 2:
            med = sorted(rat)[len(rat) // 2]
            if 0.85 <= med <= 1.15:
                ok = {"protocol": p.get("protocolSlug") or p["name"], "name": p["name"], "gecko_id": g,
                      "symbol": s, "binance": c, "mult": m, "price_ratio_checks": [round(r, 3) for r in rat]}
                break
            else:
                rej.append({"protocol": p.get("protocolSlug") or p["name"], "gecko_id": g, "binance": c, "why": "price mismatch", "ratios": [round(r, 3) for r in rat]})
    if ok: out.append(ok)
    elif not any(r.get("protocol") == (p.get("protocolSlug") or p["name"]) for r in rej):
        rej.append({"protocol": p.get("protocolSlug") or p["name"], "gecko_id": g, "symbol": s, "why": "no price overlap"})
json.dump({"mapped": out, "rejected": rej}, open(U / "protocol_binance_map.json", "w"), indent=1)
print(len(out), "mapped;", len(rej), "rejected")
