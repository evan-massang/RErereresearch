"""Small forward recorder of trade[XYZ] (HL HIP-3 dex "xyz") top of book, for H-TWAPXYZ.

README
------
Why: scripts/research/twap_recorder.py (pid 25141, not modified) stores 1-minute `metaAndAssetCtxs` mids for the
xyz dex whenever an xyz TWAP is tracked, but no bid/ask, no top-of-book size and no per-minute growth-mode /
deployerFeeScale. multivenue_recorder.py records xyz bbo for only 8 names. H-TWAPXYZ
(reports/hypotheses/twapxyz_preregistration.json) uses this recorder for an INFORMATIONAL secondary cost/fill arm
(measured spread, entry at first sight + 300 ms) and to check the frozen per-side slippage table during US cash hours.
It is never used to choose a config.

Sources (public, unauthenticated, read-only):
  * HL websocket `bbo` channel for every non-delisted xyz coin (one subscription per coin, ~120 of HL's per-IP cap).
    Sampled every 2 s: a row is written for a coin only if its bid or ask PRICE changed since its last row (sizes are
    the sizes at that moment; pure size changes are not written). A state at time t = last row with ts_us <= t.
    Note: HL `time` (exch_ts_ms) ran ~2.6 s ahead of the container clock in a test on 2026-10-05; use ts_us.
  * HL info `metaAndAssetCtxs` dex "xyz" every 5 min: growthMode, deployerFeeScale, lastFeeScaleChangeTime,
    isDelisted, mark, mid, oracle, impact prices, 24h notional volume, funding.

Output (hourly parquet chunks, UTC hour of receive time), data/raw/web/twapxyz/ (gitignored, data/raw/):
  bbo_<YYYY-MM-DD-HH>.parquet   ts_us, coin, bid, ask, bid_sz, ask_sz, exch_ts_ms
  meta_<YYYY-MM-DD-HH>.parquet  ts_ms, coin, growth_mode, fee_scale, fee_change_time, delisted, mark, mid, oracle,
                                impact_bid, impact_ask, day_ntl_vlm, funding
  recorder.log

Usage:
  nohup python scripts/research/twapxyz_bbo_recorder.py --hours 75 >> data/raw/web/twapxyz/recorder.log 2>&1 &
"""
import argparse
import asyncio
import json
import os
import ssl
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("RR_TWAPXYZ_OUT", ROOT / "data/raw/web/twapxyz"))
INFO = "https://api.hyperliquid.xyz/info"
WS = "wss://api.hyperliquid.xyz/ws"
SAMPLE_S = 2.0   # one row per coin per 2 s at most, only when bid or ask price changed (size kept on that row)
META_S = 300     # xyz metaAndAssetCtxs every 5 min (1-min mids are already in twap_recorder ctx)


def log(*a):
    print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), *a, flush=True)


def _ssl():
    return ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))


def info(body):
    req = urllib.request.Request(INFO, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30, context=_ssl()) as r:
        return json.loads(r.read())


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


class Store:
    def __init__(self):
        self.rows = defaultdict(list)
        self.latest = {}       # coin -> (ts_us, bid, ask, bsz, asz, exch_ms)
        self.written = {}      # coin -> (bid, ask) last written

    def add(self, table, row, ts_ms):
        h = datetime.fromtimestamp(ts_ms / 1000, timezone.utc).strftime("%Y-%m-%d-%H")
        self.rows[(table, h)].append(row)

    def sample(self):
        for coin, (ts, b, a, bs, az, ex) in list(self.latest.items()):
            if self.written.get(coin) != (b, a):
                self.written[coin] = (b, a)
                self.add("bbo", dict(ts_us=ts, coin=coin, bid=b, ask=a, bid_sz=bs, ask_sz=az, exch_ts_ms=ex), ts // 1000)

    def flush(self):
        OUT.mkdir(parents=True, exist_ok=True)
        for (table, h), rows in list(self.rows.items()):
            p = OUT / f"{table}_{h}.parquet"
            df = pd.DataFrame(rows)
            if p.exists():
                df = pd.concat([pd.read_parquet(p), df], ignore_index=True)
            tmp = p.with_suffix(".tmp")
            df.to_parquet(tmp, index=False, compression="zstd")
            os.replace(tmp, p)
        self.rows.clear()


def meta_poll(store):
    meta, ctxs = info({"type": "metaAndAssetCtxs", "dex": "xyz"})
    ts = int(time.time() * 1000)
    for u, c in zip(meta["universe"], ctxs):
        imp = c.get("impactPxs") or [None, None]
        store.add("meta", dict(ts_ms=ts, coin=u["name"], growth_mode=u.get("growthMode"),
                               fee_scale=f(u.get("deployerFeeScale")), fee_change_time=u.get("lastFeeScaleChangeTime"),
                               delisted=bool(u.get("isDelisted")), mark=f(c.get("markPx")), mid=f(c.get("midPx")),
                               oracle=f(c.get("oraclePx")), impact_bid=f(imp[0]), impact_ask=f(imp[1]),
                               day_ntl_vlm=f(c.get("dayNtlVlm")), funding=f(c.get("funding"))), ts)
    return [u["name"] for u in meta["universe"] if not u.get("isDelisted")]


async def ws_loop(coins, store, stop):
    import websockets
    while not stop.is_set():
        try:
            async with websockets.connect(WS, ssl=_ssl(), open_timeout=20, ping_interval=20, ping_timeout=20,
                                          max_size=2 ** 24) as ws:
                for c in coins:
                    await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "bbo", "coin": c}}))
                log(f"ws connected, subscribed bbo for {len(coins)} coins")
                while not stop.is_set():
                    raw = await asyncio.wait_for(ws.recv(), timeout=120)
                    m = json.loads(raw)
                    if m.get("channel") != "bbo":
                        continue
                    d = m["data"]
                    b, a = d.get("bbo") or [None, None]
                    store.latest[d["coin"]] = (time.time_ns() // 1000, f(b and b["px"]), f(a and a["px"]),
                                               f(b and b["sz"]), f(a and a["sz"]), int(d.get("time") or 0))
        except Exception as e:  # noqa: BLE001
            if stop.is_set():
                return
            log("ws reconnect", type(e).__name__, str(e)[:160])
            await asyncio.sleep(3)


async def main(hours):
    store, stop = Store(), asyncio.Event()
    coins = await asyncio.to_thread(meta_poll, store)
    log(f"start: {len(coins)} xyz coins, hours={hours}")
    task = asyncio.create_task(ws_loop(coins, store, stop))
    end = time.monotonic() + hours * 3600
    last_meta, last_flush = time.monotonic(), time.monotonic()
    while time.monotonic() < end:
        await asyncio.sleep(SAMPLE_S)
        store.sample()
        if time.monotonic() - last_meta >= META_S:
            last_meta = time.monotonic()
            try:
                await asyncio.to_thread(meta_poll, store)
            except Exception as e:  # noqa: BLE001
                log("meta failed", type(e).__name__, str(e)[:160])
        if time.monotonic() - last_flush >= 300:
            last_flush = time.monotonic()
            await asyncio.to_thread(store.flush)
    stop.set()
    task.cancel()
    store.flush()
    log("stopped: --hours reached")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=75)
    asyncio.run(main(ap.parse_args().hours))
