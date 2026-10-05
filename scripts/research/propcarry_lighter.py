"""Lighter public hourly funding history for H-PROPCARRY (descriptive only). < 2026-04-01 only.
Units (docs.lighter.xyz/trading/funding): floor fundingRate = InterestRate/8 = 0.01%/8 per hour; API `rate`
is a PERCENT per hour rounded to 4 dp (0.0012 = 0.12 bp/h); `direction` gives which side pays."""
import json, time, urllib.request, datetime as dt
MK = {"PENGU": 47, "PUMP": 45, "FARTCOIN": 21, "USELESS": 66, "BONK": 18, "TRUMP": 15}
END = int(dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc).timestamp())
out = {"source": "https://mainnet.zklighter.elliot.ai/api/v1/fundings", "units": __doc__, "data": {}}
for c, mid in MK.items():
    rows, t0 = {}, int(dt.datetime(2024, 12, 1, tzinfo=dt.timezone.utc).timestamp())
    while t0 < END:
        t1 = min(t0 + 500 * 3600, END)
        u = f"{out['source']}?market_id={mid}&resolution=1h&start_timestamp={t0}&end_timestamp={t1}&count_back=500"
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
        for f in d.get("fundings", []):
            if f["timestamp"] < END:
                rows[f["timestamp"]] = [f["timestamp"], f["rate"], f["direction"], f["value"]]
        t0 = t1; time.sleep(0.25)
    out["data"][c] = sorted(rows.values())
    r = out["data"][c]
    print(c, len(r), r[0] if r else None, r[-1] if r else None)
json.dump(out, open("data/raw/web/propcarry/lighter_funding.json", "w"))
