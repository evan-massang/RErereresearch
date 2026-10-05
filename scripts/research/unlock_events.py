"""H-UNLOCK step 2: build the cliff-unlock event table from DefiLlama emissions schedules.

No prices are used except the Binance daily archive's bar *existence* and quote volume
(universe filter). Output: data/raw/web/unlock/events.parquet
"""
import json, pathlib, collections
import pandas as pd, numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
U = ROOT / "data/raw/web/unlock"
VEST = {"insiders", "privateSale", "publicSale", "airdrop"}
DAY = 86400

mp = json.load(open(U / "protocol_binance_map.json"))["mapped"]
rows = []
for m in mp:
    f = U / "emissions" / f"{m['protocol']}.json"
    if not f.exists():
        continue
    a = json.load(open(f))
    md = a.get("metadata") or {}
    ue = md.get("unlockEvents") or []
    # recipient label -> category, from events (cliff + linear)
    lab2cat = {}
    for e in ue:
        for al in (e.get("cliffAllocations") or []) + (e.get("linearAllocations") or []):
            lab2cat[al["recipient"]] = al["category"]
    # schedule-unlocked supply per day, excluding noncirculating labels
    series = {}
    for s in (a.get("documentedData") or {}).get("data") or []:
        cat = lab2cat.get(s["label"])
        if cat in ("noncirculating", "burned"):
            continue
        for p in s["data"]:
            d = int(p["timestamp"]) // DAY
            series[d] = series.get(d, 0.0) + float(p.get("unlocked") or 0)
    if not series:
        continue
    sd = pd.Series(series).sort_index()
    byday = collections.defaultdict(lambda: collections.Counter())
    for e in ue:
        d = int(e["timestamp"]) // DAY
        for al in e.get("cliffAllocations") or []:
            amt = float(al.get("amount") or 0)
            if amt <= 0:
                continue
            c = al["category"]
            byday[d]["all_cliff"] += amt
            if c in VEST:
                byday[d]["vest"] += amt
                byday[d]["team" if c == "insiders" else "investor" if c in ("privateSale", "publicSale") else "airdrop"] += amt
    for d, c in byday.items():
        if c["vest"] <= 0:
            continue
        prev = sd[sd.index <= d - 1]
        circ = float(prev.iloc[-1]) if len(prev) else 0.0
        rows.append(dict(protocol=m["protocol"], symbol=m["binance"], mult=m["mult"], day=d,
                         date=pd.Timestamp(d * DAY, unit="s").date().isoformat(),
                         tok_vest=c["vest"], tok_team=c["team"], tok_investor=c["investor"],
                         tok_airdrop=c["airdrop"], tok_all_cliff=c["all_cliff"], circ_prev=circ,
                         size_pct=100 * c["vest"] / circ if circ > 0 else np.nan))
ev = pd.DataFrame(rows).sort_values(["day", "symbol"]).reset_index(drop=True)
ev.to_parquet(U / "events.parquet")
print(len(ev), "vesting-cliff event-days on", ev.symbol.nunique(), "symbols")
