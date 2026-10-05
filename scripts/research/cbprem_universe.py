"""H-CBPREM universe check: Coinbase product existence + first candle date (timestamps only), Binance kline existence."""
import json, datetime as dt
from pipeline.sources.coinbase import CoinbaseExchangeAdapter
from pipeline.sources.binance_vision import BinanceVisionAdapter
from pipeline.sources.base import SourceUnavailable

PRE = json.load(open("reports/hypotheses/cbprem_preregistration.json"))
CB = PRE["universe"]["coinbase_products"]
cb, bv = CoinbaseExchangeAdapter(), BinanceVisionAdapter()
ts = lambda d: int(dt.datetime(*d, tzinfo=dt.timezone.utc).timestamp())
out = {}
for coin, prod in list(CB.items()) + [("USDT", "USDT-USD")]:
    rec = {"product": prod}
    try:
        meta = cb.product(prod); rec["status"] = meta.get("status")
    except SourceUnavailable as e:
        rec["exists"] = False; rec["err"] = str(e); out[coin] = rec; continue
    rec["exists"] = True
    first = None; s = ts((2021, 1, 1))
    while s < ts((2026, 4, 1)) and first is None:
        e = s + 300 * 86400
        rows = cb.candles(prod, s, e, 86400)
        if rows: first = rows[0][0]
        s = e
    rec["first_daily_candle_utc"] = dt.datetime.utcfromtimestamp(first).isoformat() if first else None
    if first:  # refine to 1m: first 1m candle within that day
        r1 = []; s1 = first
        while not r1 and s1 < first + 86400:
            r1 = cb.candles_1m(prod, s1, s1 + 300 * 60); s1 += 300 * 60
        rec["first_1m_candle_utc"] = dt.datetime.utcfromtimestamp(r1[0][0]).isoformat() if r1 else None
    if coin != "USDT":
        sym = coin + "USDT"; rec["binance_symbol"] = sym
        rec["binance_monthly_2025_05_exists"] = bv.client.head(f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/1m/{sym}-1m-2025-05.zip").status_code == 200
    out[coin] = rec; print(coin, rec, flush=True)
json.dump(out, open("data/raw/web/cbprem/universe_check.json", "w"), indent=1)
