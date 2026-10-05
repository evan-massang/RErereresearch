"""H-LSRATIO-LC forward paper test: the H-LSRATIO contrarian oi_crowd L4/H8 signal, executed on Lighter.

POST-HOC CAVEAT (stated in the freeze record): this config and this venue were chosen AFTER the train and
validation gross of H-LSRATIO were seen (reports/failures/agent_lsratio.md: oi_crowd L4 H8 grossed +13.3 bp/trade
on train, +10.5 bp on validation, and failed at 13 bp taker cost). The historical splits therefore cannot validate
it. Only trades whose decision time is after ``frozen_at`` count.

Signal (unchanged from reports/hypotheses/lsratio_preregistration.json, code reused from lsratio_sim.py and
lsratio_fetch.metrics_day): hourly decision t uses the Binance metrics row stamped <= t - 5 min; zO = z(dlnOI_4h),
zC = z(dln crowd account ratio_4h), trailing 168 h z (>= 120 values). Short if zO >= 1.5 and zC >= 1.5; long if
zO >= 1.5 and zC <= -1.5. Enter at the open of the 1h bar at t, exit at the open of bar t + 8 h, 5% stop, one
position per symbol. Prices are Binance USD-M 1h klines (proxy for Lighter prices; basis not modelled).

Cost model (Lighter, standard account): taker fee as published by Lighter's orderBookDetails at scoring time
(0 at freeze), plus a round-trip spread cost = (VWAP to buy $1,000 - VWAP to sell $1,000) / mid from Lighter
order books, plus Lighter hourly funding. Per trade the spread cost is the median of recorded samples for that
coin within [t - 6 h, exit + 6 h] when >= 3 exist (from ``spreads`` runs), else the per-coin median frozen at
freeze time.

Data: data.binance.vision daily metrics and daily 1h klines (archive lags ~1 day; fapi is 451-blocked and is
not used), Lighter public REST (unauthenticated). Cache: data/raw/web/lsratio_forward/.

    python scripts/research/lsratio_forward.py markets           # Lighter market list -> lighter_markets.json
    python scripts/research/lsratio_forward.py universe          # forward universe candidates -> universe.json
    python scripts/research/lsratio_forward.py spreads --minutes 10 --interval 60 [--set all|universe]
    python scripts/research/lsratio_forward.py posthoc           # informational historical recompute (post-hoc)
    python scripts/research/lsratio_forward.py freeze            # once; refuses to overwrite
    python scripts/research/lsratio_forward.py score
"""
import argparse
import hashlib
import io
import json
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
import lsratio_fetch as lf  # noqa: E402
import lsratio_sim as ls  # noqa: E402

OUT = ROOT / "data/raw/web/lsratio_forward"
FREEZE = ROOT / "reports/paper/lsratio_lc.json"
LEDGER = ROOT / "reports/paper/lsratio_lc_ledger.json"
POSTHOC = ROOT / "research/observations/evidence_lsratio_lc_posthoc_20261005.json"
MODULES = ["scripts/research/lsratio_sim.py", "scripts/research/lsratio_fetch.py", "scripts/research/lsratio_forward.py"]
LIGHTER = "https://mainnet.zklighter.elliot.ai/api/v1"
BV = "https://data.binance.vision/data/futures/um"
PARAMS = dict(signal="oi_crowd", L_hours=4, H_hours=8, z_open_interest_min=1.5, z_crowd_abs_min=1.5,
              z_window_hours=ls.ZWIN, z_min_values=ls.ZMIN, stop=ls.STOP, notional_usd=1000)
BAR = dict(min_trades=50, net_sum_gt=0.0, profit_factor_gt=1.2, net_sum_ex_top3_gt=0.0)
UNIVERSE_MONTH = "2026-09"           # 30 daily bars used to rank the forward universe (latest complete month)
PRICE_TOL = 0.15                      # Lighter mark vs latest archived Binance daily close: name-collision guard
NOTIONAL = 1000.0
sess = requests.Session()


def _get(url, **kw):
    for a in range(4):
        try:
            r = sess.get(url, timeout=30, **kw)
            if r.status_code in (403, 404, 451):
                return r
            r.raise_for_status()
            return r
        except Exception:  # noqa: BLE001
            time.sleep(2 * (a + 1))
    return None


def _zip_csv(url):
    r = _get(url)
    if r is None or r.status_code != 200:
        return None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    return z.read(z.namelist()[0]).decode()


def _klines(txt):
    lines = [ln for ln in txt.strip().splitlines() if ln]
    if lines and not lines[0][0].isdigit():
        lines = lines[1:]
    d = pd.read_csv(io.StringIO("\n".join(lines)), header=None, usecols=range(8))
    d.columns = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume"]
    return d[["open_time", "open", "high", "low", "close", "quote_volume"]].apply(pd.to_numeric, errors="coerce")


# ---------------------------------------------------------------- Lighter
def markets(path=None):
    r = _get(f"{LIGHTER}/orderBookDetails")
    keep = ["symbol", "market_id", "market_type", "status", "taker_fee", "maker_fee", "mark_price",
            "last_trade_price", "daily_quote_token_volume", "created_at"]
    rows = [{k: x.get(k) for k in keep} for x in r.json()["order_book_details"]]
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"fetched_at_utc": datetime.now(timezone.utc).isoformat(), "source": f"{LIGHTER}/orderBookDetails",
           "markets": rows}
    (path or OUT / "lighter_markets.json").write_text(json.dumps(rec, indent=0))
    print(len(rows), "markets;", sum(r["taker_fee"] != "0.0000" for r in rows), "with nonzero taker fee")
    return rec


def lighter_perps(rec=None):
    rec = rec or json.loads((OUT / "lighter_markets.json").read_text())
    return {m["symbol"]: m for m in rec["markets"] if m["market_type"] == "perp" and m["status"] == "active"}


def book_cost(asks, bids):
    """Touch spread and round-trip cost of a $1,000 taker buy + $1,000 taker sell, in bp of mid."""
    a = [(float(x["price"]), float(x["remaining_base_amount"])) for x in asks]
    b = [(float(x["price"]), float(x["remaining_base_amount"])) for x in bids]
    if not a or not b:
        return None
    a.sort(), b.sort(reverse=True)
    mid = (a[0][0] + b[0][0]) / 2

    def vwap(levels):
        need, cost, qty = NOTIONAL, 0.0, 0.0
        for p, q in levels:
            take = min(q, need / p)
            cost, qty, need = cost + take * p, qty + take, need - take * p
            if need <= 1e-9:
                return cost / qty
        return None
    va, vb = vwap(a), vwap(b)
    return dict(mid=mid, touch_bp=(a[0][0] - b[0][0]) / mid * 1e4,
                rt1k_bp=(va - vb) / mid * 1e4 if va and vb else np.nan,
                top_ask_usd=a[0][0] * a[0][1], top_bid_usd=b[0][0] * b[0][1])


def spreads(minutes, interval, which):
    perps = lighter_perps()
    if which == "universe":
        syms = json.loads((OUT / "universe.json").read_text())["forward_universe"]
    else:
        syms = sorted(set(json.loads((OUT / "universe.json").read_text())["forward_universe"])
                      | set(json.loads((OUT / "universe.json").read_text())["historical_lighter_subset"]))
    ids = {s: perps[s[:-4]]["market_id"] for s in syms}
    rows, stop = [], time.time() + minutes * 60
    while True:
        t0 = time.time()
        for s, mid in ids.items():
            r = _get(f"{LIGHTER}/orderBookOrders", params={"market_id": mid, "limit": 50})
            if r is None or r.status_code != 200:
                continue
            d = r.json()
            c = book_cost(d.get("asks") or [], d.get("bids") or [])
            if c:
                rows.append(dict(t=pd.Timestamp.now(tz="UTC").tz_localize(None), symbol=s, market_id=mid, **c))
        if time.time() + interval > stop:
            break
        time.sleep(max(0.0, interval - (time.time() - t0)))
    df = pd.DataFrame(rows)
    p = OUT / "lighter_spreads.parquet"
    if p.exists():
        df = pd.concat([pd.read_parquet(p), df], ignore_index=True)
    df.to_parquet(p)
    print(len(rows), "samples;", df.groupby("symbol").rt1k_bp.median().describe().round(2).to_dict())


def spread_table(df=None):
    df = pd.read_parquet(OUT / "lighter_spreads.parquet") if df is None else df
    g = df.groupby("symbol")
    return pd.DataFrame(dict(n=g.size(), touch_med_bp=g.touch_bp.median(), rt1k_med_bp=g.rt1k_bp.median(),
                             rt1k_p90_bp=g.rt1k_bp.quantile(0.9), top_usd_med=g[["top_ask_usd", "top_bid_usd"]]
                             .median().min(axis=1), first=g.t.min(), last=g.t.max()))


# ---------------------------------------------------------------- universe
def hl_candidates():
    out = {}
    for x in json.load(open(lf.HLMETA))["meta"]["universe"]:
        n = x["name"]
        c = [("1000" + n[1:] + "USDT"), n[1:] + "USDT"] if (n.startswith("k") and n[1:].isupper()) else [n + "USDT"]
        out[n] = c
    return out


def universe():
    """Forward universe rule (declared before any forward scoring):
    HL-listed names (data/raw/web/hyperliquid/meta.json, fetched 2026-10) mapped to Binance USDT perps as in
    H-LSRATIO (kNAME -> 1000NAMEUSDT, else NAMEUSDT; same exclusions); ranked by the sum of Binance quote volume
    over the 30 daily bars of UNIVERSE_MONTH (>= 25 bars); top 30; keep those whose Binance base (symbol minus
    USDT) is an active Lighter perp of the same name whose mark price is within 15% of the latest archived
    Binance daily close (name-collision guard).
    Fixed for the whole forward test."""
    perps = lighter_perps()
    vol, last = {}, {}
    for n, cands in hl_candidates().items():
        for s in cands:
            if s in lf.EXCL or s[:-4] in lf.STABLE or "_" in s:
                break
            txt = _zip_csv(f"{BV}/monthly/klines/{s}/1d/{s}-1d-{UNIVERSE_MONTH}.zip")
            if txt is None:
                continue
            k = _klines(txt)
            if len(k) >= 25:
                vol[s], last[s] = float(k.quote_volume.sum()), float(k.close.iloc[-1])
            break
    top = sorted(vol, key=vol.get, reverse=True)[:30]
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()

    def latest_close(s):          # latest archived Binance daily close (archive lags 1-2 days)
        for k in range(1, 5):
            d = (today - pd.Timedelta(days=k)).strftime("%Y-%m-%d")
            txt = _zip_csv(f"{BV}/daily/klines/{s}/1d/{s}-1d-{d}.zip")
            if txt:
                return float(_klines(txt).close.iloc[-1]), d
        return None, None

    def on_lighter(s, _px):
        m = perps.get(s[:-4])
        if not m:
            return False, None, None
        px, _ = latest_close(s)
        if px is None:
            return False, None, None
        lp = float(m["mark_price"] or m["last_trade_price"] or "nan")
        return bool(abs(lp / px - 1) <= PRICE_TOL), lp, px
    rows = []
    for i, s in enumerate(top):
        ok, lp, px = on_lighter(s, None)
        rows.append(dict(rank=i + 1, symbol=s, quote_volume_30d=vol[s], binance_latest_close=px,
                         lighter_mark=lp, on_lighter=ok))
    fwd = [r["symbol"] for r in rows if r["on_lighter"]]
    # historical H-LSRATIO symbols on Lighter today (same name + price check where Binance still trades it)
    U = pd.read_parquet(ROOT / "data/raw/web/lsratio/universe.parquet")
    hist = []
    for s in sorted(U.symbol.unique()):
        if s[:-4] not in perps:
            continue
        ok, lp, px = on_lighter(s, None)
        hist.append(dict(symbol=s, binance_latest_close=px, lighter_mark=lp, on_lighter=ok,
                         lighter_created_at=pd.Timestamp(int(perps[s[:-4]]["created_at"]), unit="ms").isoformat()))
    rec = dict(built_at_utc=datetime.now(timezone.utc).isoformat(), rule=universe.__doc__.strip(),
               universe_month=UNIVERSE_MONTH, top30=rows, forward_universe=fwd,
               historical_checks=hist, historical_lighter_subset=[h["symbol"] for h in hist if h["on_lighter"]])
    (OUT / "universe.json").write_text(json.dumps(rec, indent=1))
    print("top30:", [r["symbol"] for r in rows])
    print("forward universe (%d):" % len(fwd), fwd)
    print("historical subset (%d):" % len(rec["historical_lighter_subset"]), rec["historical_lighter_subset"])
    print("historical name match rejected by price:", [h for h in hist if not h["on_lighter"]])


# ---------------------------------------------------------------- post-hoc historical (informational)
def posthoc():
    u = json.loads((OUT / "universe.json").read_text())
    sub = set(u["historical_lighter_subset"])
    sp = spread_table()
    cost = (sp.rt1k_med_bp / 1e4).to_dict()
    out = dict(hypothesis="H-LSRATIO-LC", kind="POST-HOC, informational only", is_synthetic=False,
               caveat=("Config (oi_crowd L4 H8) and venue (Lighter) were chosen after seeing H-LSRATIO train and "
                       "validation gross; this recompute cannot validate anything. Lighter listing and spreads are "
                       "as of 2026-10-05 (not point-in-time; Lighter did not exist for most of train). Prices are "
                       "Binance 1h klines; funding is the Binance fundingRate proxy used in H-LSRATIO."),
               cost_model="per-coin median round-trip cost of a $1k taker buy+sell on Lighter, sampled 2026-10-05, + Binance funding",
               lighter_subset=sorted(sub), views={
                   "name_match_all_dates": "every H-LSRATIO trade on a symbol whose name is an active Lighter perp today",
                   "after_lighter_market_created": "only trades decided after the Lighter market's created_at "
                                                   "(also removes LITUSDT's Litentry era)"}, splits={})
    created = {h["symbol"]: pd.Timestamp(h["lighter_created_at"]) for h in u["historical_checks"]}
    U = pd.read_parquet(ROOT / "data/raw/web/lsratio/universe.parquet")
    for split in ("train", "validation"):
        lo_, hi_ = map(pd.Timestamp, ls.SPLITS[split])
        t0 = pd.read_parquet(ROOT / f"data/raw/web/lsratio/trades_{split}_oi_crowd_L4_H8.parquet")
        allstats = ls.stats(t0)
        res = dict(all_symbols_at_13bp_for_reference=dict(n=allstats["n"], mean_bp=allstats["mean_bp"],
                                                           gross_mean_bp=allstats["gross_mean_bp"]))
        Us = U[(U.day >= lo_) & (U.day < hi_) & U.symbol.isin(sub)]
        for view in ("name_match_all_dates", "after_lighter_market_created"):
            t = t0[t0.symbol.isin(sub)].copy()
            cd = Us
            if view == "after_lighter_market_created":
                t = t[t.t > t.symbol.map(created)]
                cd = Us[Us.day > Us.symbol.map(created)]
            t["cost"] = t.symbol.map(cost)
            t["net"] = t.gross - t.funding - t.cost
            s_ = ls.stats(t)
            if s_.get("n"):
                s_["cost_mean_bp"] = float(t.cost.mean() * 1e4)
                s_["by_symbol_n"] = t.symbol.value_counts().to_dict()
                s_["universe_coin_days"] = int(len(cd))
                s_["trades_per_coin_day"] = float(len(t) / len(cd)) if len(cd) else None
            res[view] = s_
            print(split, view, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in s_.items()
                                if k not in ("by_year", "by_symbol_n")})
        out["splits"][split] = res
    POSTHOC.write_text(json.dumps(out, indent=1))


# ---------------------------------------------------------------- forward data
def _cache_day(sym, day):
    d = day.strftime("%Y-%m-%d")
    mp, kp = OUT / "metrics" / sym / f"{d}.parquet", OUT / "k1h" / sym / f"{d}.parquet"
    for p in (mp, kp):
        p.parent.mkdir(parents=True, exist_ok=True)
    if not mp.exists():
        h = lf.metrics_day(sym, day)
        if h is not None and len(h):
            h.to_parquet(mp)
    if not kp.exists():
        txt = _zip_csv(f"{BV}/daily/klines/{sym}/1h/{sym}-1h-{d}.zip")
        if txt:
            _klines(txt).to_parquet(kp)


def load_symbol_fwd(sym):
    """Same construction as lsratio_sim.load_symbol, from the forward cache, no holdout cut."""
    mf, kf = sorted((OUT / "metrics" / sym).glob("*.parquet")), sorted((OUT / "k1h" / sym).glob("*.parquet"))
    if not mf or not kf:
        return None
    m = pd.concat([pd.read_parquet(p) for p in mf]).drop_duplicates("t", keep="last").set_index("t").sort_index()
    k = pd.concat([pd.read_parquet(p) for p in kf]).drop_duplicates("open_time")
    k["t"] = pd.to_datetime(k.open_time, unit="ms")
    k = k.set_index("t").sort_index()
    last_open = k.open.dropna().index.max()
    grid = pd.date_range(min(m.index.min(), k.index.min()), max(m.index.max(), k.index.max()), freq="h")
    m, k = m.reindex(grid), k.reindex(grid)
    f = pd.DataFrame(index=grid)
    f["open"], f["high"], f["low"], f["close"] = k.open, k.high, k.low, k.close
    L = PARAMS["L_hours"]
    lnC = np.log(m.count_long_short_ratio.where(m.count_long_short_ratio > 0))
    lnO = np.log(m.sum_open_interest.where(m.sum_open_interest > 0))
    f[f"zC{L}"] = ls.tz(lnC - lnC.shift(L))
    f[f"zO{L}"] = ls.tz(lnO - lnO.shift(L))
    f["in_u"] = True
    return f, last_open


def lighter_funding(sym, market_id, start, end):
    """Signed hourly funding fraction (+ = longs pay). Lighter 'rate' is in percent; 'direction' long = longs pay."""
    rows, a = [], start
    while a < end:                                   # windows of 500 h (endpoint returns at most count_back rows)
        b = min(end, a + pd.Timedelta(hours=500))
        r = _get(f"{LIGHTER}/fundings", params=dict(market_id=market_id, resolution="1h",
                                                    start_timestamp=int(a.timestamp()),
                                                    end_timestamp=int(b.timestamp()),
                                                    count_back=int((b - a) / pd.Timedelta(hours=1)) + 2))
        if r is None or r.status_code != 200:
            return None
        rows += r.json().get("fundings") or []
        a = b
    if not rows:
        return None
    s = pd.Series({pd.Timestamp(x["timestamp"], unit="s"): (1 if x["direction"] == "long" else -1)
                   * float(x["rate"]) / 100 for x in rows})
    return s[~s.index.duplicated()].sort_index()


# ---------------------------------------------------------------- freeze / score
def _shas():
    return {m: hashlib.sha256((ROOT / m).read_bytes()).hexdigest() for m in MODULES}


def freeze():
    if FREEZE.exists():
        raise SystemExit(f"{FREEZE} exists; frozen strategies are never changed.")
    u = json.loads((OUT / "universe.json").read_text())
    mk = json.loads((OUT / "lighter_markets.json").read_text())
    sp = spread_table()
    sp = sp[sp.index.isin(u["forward_universe"])]
    short = sorted(set(u["forward_universe"]) - set(sp[sp.n >= 5].index[sp[sp.n >= 5].rt1k_med_bp.notna()]))
    if short:
        raise SystemExit(f"fewer than 5 Lighter spread samples for {short}; run spreads first.")
    perps = lighter_perps(mk)
    rec = {
        "name": "lsratio_lc", "hypothesis": "H-LSRATIO-LC",
        "statement": ("The frozen H-LSRATIO contrarian oi_crowd signal (L = 4 h, H = 8 h) executed on Lighter "
                      "(0 bp taker for standard accounts) earns more than its Lighter spread + funding costs."),
        "post_hoc_caveat": ("SELECTED POST-HOC. This config and venue were chosen after seeing H-LSRATIO's train "
                            "(+13.3 bp/trade gross, n = 5,463) and validation (+10.5 bp gross, n = 1,625) results, "
                            "where it failed at 13 bp taker cost. The historical splits cannot validate it; any "
                            "historical recompute (evidence_lsratio_lc_posthoc_20261005.json) is informational. "
                            "Only this forward test, on decisions after frozen_at, can."),
        "parent": "H-LSRATIO (reports/failures/agent_lsratio.md, reports/hypotheses/lsratio_preregistration.json)",
        "params": PARAMS, "trade_rules": ls.PRE["trade_rules"], "signal_definition": ls.PRE["signals"],
        "point_in_time": ls.PRE["point_in_time"],
        "universe_rule": u["rule"], "universe_month": u["universe_month"], "universe": u["forward_universe"],
        "lighter_market_ids": {s: perps[s[:-4]]["market_id"] for s in u["forward_universe"]},
        "universe_top30_ranked": u["top30"],
        "cost_model": {
            "fee": "Lighter taker fee from orderBookDetails at scoring time, charged on both sides (0.0000 for "
                   "every market at freeze; standard account, 300 ms taker speed bump, irrelevant at 1 h scale)",
            "spread": "round-trip cost of a $1,000 taker buy + taker sell walked through the Lighter order book, "
                      "bp of mid. Per trade: median of recorded samples (lighter_spreads.parquet) for the coin in "
                      "[t - 6 h, exit + 6 h] if >= 3 samples, else the per-coin median frozen below",
            "frozen_rt_cost_bp": sp.rt1k_med_bp.round(3).to_dict(),
            "frozen_touch_spread_bp": sp.touch_med_bp.round(3).to_dict(),
            "spread_sample": {"n": int(sp.n.sum()), "first": str(sp["first"].min()), "last": str(sp["last"].max())},
            "funding": "Lighter hourly funding from /api/v1/fundings (rate in percent, direction long = longs pay), "
                       "prints with timestamp in (entry, exit]",
            "price_proxy": "Binance USD-M 1h kline opens (Lighter-vs-Binance basis not modelled)",
        },
        "data": "data.binance.vision futures/um daily metrics + daily 1h klines (lag ~1 day; fapi 451, not used); "
                "Lighter public REST. Pre-freeze days are fetched only as z-score warm-up and never scored.",
        "bar": BAR, "module_sha256": _shas(), "frozen_at": time.time(),
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lighter_markets_fetched_at_utc": mk["fetched_at_utc"],
        "expected_trade_rate": None,
    }
    est = json.loads(POSTHOC.read_text()) if POSTHOC.exists() else None
    if est:   # historical trade frequency only (no P&L used): trades per universe coin-day on Lighter-listed coins
        r = {k: v["name_match_all_dates"]["trades_per_coin_day"] for k, v in est["splits"].items()}
        per_day = float(np.mean(list(r.values()))) * len(u["forward_universe"])
        rec["expected_trade_rate"] = dict(trades_per_coin_day_hist=r, coins=len(u["forward_universe"]),
                                          trades_per_day=round(per_day, 2),
                                          days_to_50_trades=round(50 / per_day, 1) if per_day else None,
                                          note="plus ~1-2 days archive lag before the trades can be scored")
    FREEZE.parent.mkdir(parents=True, exist_ok=True)
    FREEZE.write_text(json.dumps(rec, indent=1, default=str))
    print(json.dumps({k: rec[k] for k in ("frozen_at_utc", "universe", "module_sha256")}, indent=1))


def score():
    rec = json.loads(FREEZE.read_text())
    if _shas() != rec["module_sha256"]:
        raise SystemExit("a frozen module changed since freezing; scoring refused: "
                         + str([m for m, h in _shas().items() if rec["module_sha256"].get(m) != h]))
    t_freeze = pd.Timestamp(rec["frozen_at"], unit="s")
    lo = t_freeze.ceil("h") if t_freeze != t_freeze.ceil("h") else t_freeze + pd.Timedelta(hours=1)
    H = rec["params"]["H_hours"]
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    days = pd.date_range(t_freeze.normalize() - pd.Timedelta(days=9), today - pd.Timedelta(days=1))
    fees = {m["symbol"]: float(m["taker_fee"]) / 100 for m in lighter_perps(markets(OUT / "lighter_markets_at_score.json")).values()}  # percent
    rec_sp = pd.read_parquet(OUT / "lighter_spreads.parquet") if (OUT / "lighter_spreads.parquet").exists() else None
    ls.HOLDOUT = pd.Timestamp("2100-01-01")    # forward data lies after the H-LSRATIO holdout start by design
    trades, coverage = [], {}
    for sym in rec["universe"]:
        for d in days:
            _cache_day(sym, d)
        x = load_symbol_fwd(sym)
        if x is None:
            coverage[sym] = "no data"
            continue
        f, last_open = x
        hi = last_open - pd.Timedelta(hours=H) + pd.Timedelta(hours=1)
        coverage[sym] = dict(last_kline=str(last_open), decisions_scored_until=str(hi))
        if hi <= lo:
            continue
        fr = lighter_funding(sym, rec["lighter_market_ids"][sym], lo - pd.Timedelta(hours=1),
                             hi + pd.Timedelta(hours=H + 1))
        tr = ls.simulate(f, fr, sym, "oi_crowd", rec["params"]["L_hours"], H, lo, hi)
        for t in tr:
            assert t["t"] > t_freeze
            sp = None
            if rec_sp is not None:
                w = rec_sp[(rec_sp.symbol == sym) & (rec_sp.t >= t["t"] - pd.Timedelta(hours=6))
                           & (rec_sp.t <= t["exit_t"] + pd.Timedelta(hours=6))].rt1k_bp.dropna()
                if len(w) >= 3:
                    sp = float(w.median()) / 1e4
            t["spread_cost"] = sp if sp is not None else rec["cost_model"]["frozen_rt_cost_bp"][sym] / 1e4
            t["spread_source"] = "recorded" if sp is not None else "frozen_median"
            t["fee_cost"] = 2 * fees.get(sym[:-4], 0.0)
            t["funding_source"] = "missing" if fr is None else "lighter"
            t["net"] = t["gross"] - t["funding"] - t["spread_cost"] - t["fee_cost"]
            for k in ("net_bn",):
                t.pop(k, None)
        trades += tr
    df = pd.DataFrame(trades)
    st = ls.stats(df) if len(df) else dict(n=0, passes_bar=False)
    out = {"name": rec["name"], "frozen_at_utc": rec["frozen_at_utc"],
           "scored_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "decisions_from": str(lo), "post_hoc_caveat": rec["post_hoc_caveat"], "bar": rec["bar"],
           "verdict": ("PASS" if st.get("passes_bar") else ("PENDING (n < 50)" if st.get("n", 0) < 50 else "FAIL")),
           "stats": st, "coverage": coverage, "is_synthetic": False,
           "trades": df.assign(t=df.t.astype(str), exit_t=df.exit_t.astype(str)).to_dict("records") if len(df) else []}
    LEDGER.write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["markets", "universe", "spreads", "posthoc", "freeze", "score"])
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--interval", type=float, default=60)
    ap.add_argument("--set", default="all", choices=["all", "universe"])
    a = ap.parse_args()
    if a.cmd == "markets":
        markets()
    elif a.cmd == "universe":
        universe()
    elif a.cmd == "spreads":
        spreads(a.minutes, a.interval, a.set)
    elif a.cmd == "posthoc":
        posthoc()
    elif a.cmd == "freeze":
        freeze()
    else:
        print(json.dumps({k: v for k, v in score().items() if k != "trades"}, indent=1, default=str))
