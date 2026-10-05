"""Small top-of-book recorder for H-BETALAG (BTC leads crypto-beta equity perps).

Pre-registration: reports/hypotheses/betalag_preregistration.json (written before this script existed).
Standalone on purpose: it copies patterns from multivenue_recorder.py but imports nothing from it, so the running
multivenue recorder cannot be affected by edits here. Public, unauthenticated websockets only (no accounts, no orders).
`websockets` picks up HTTPS_PROXY; TLS is verified against SSL_CERT_FILE.

Streams
  binance  wss://fstream.binance.com/stream?streams=btcusdt@bookTicker   (falls back to the /market route if the
           legacy route delivers nothing for 60 s)                                       -> binance_bbo  coin BTC
  lighter  wss://mainnet.zklighter.elliot.ai/stream?readonly=true  ticker/<id>  MSTR COIN HOOD CRCL -> lighter_bbo
  xyz      wss://api.hyperliquid.xyz/ws  bbo  xyz:COIN xyz:HOOD xyz:CRCL xyz:MSTR (MSTR = unscored diagnostic) -> xyz_bbo
  meta     hourly REST: xyz metaAndAssetCtxs (growthMode, deployerFeeScale, funding) and Lighter orderBooks fees
  events   events.jsonl: one line per connect / disconnect with local ts_us (the prereg's gap rule uses it)

Table (hourly parquet, zstd) data/raw/web/betalag/<venue>_bbo_<YYYY-MM-DD-HH>.parquet, hour = UTC hour of ts_us:
  ts_us, coin, bid, ask, bid_sz, ask_sz, exch_ts_ms
  ts_us = local receive time (microseconds, container clock, ~2.8 s behind venue clocks); decisions use ts_us only.
  exch_ts_ms = venue time (binance T, lighter last_updated_at truncated to ms, hl time), for diagnostics.

Compaction (same rule as multivenue_recorder.py), per venue x coin, relative to the last WRITTEN row:
  unchanged repeats dropped; a price change is written if >= 50 ms after the last written row, else held and the
  latest state written once 50 ms have passed (prices at most ~60 ms stale); size-only changes at most every 500 ms
  (recorded top size up to ~0.5 s stale).
Disk guard: stops when free disk < --min-free-gb (default 1.5).

    python scripts/research/betalag_recorder.py --hours 0.03 --out <scratch dir>     # test
    nohup python scripts/research/betalag_recorder.py --hours 48 >> data/raw/web/betalag/recorder.log 2>&1 &
"""
import argparse
import asyncio
import json
import os
import shutil
import signal
import ssl
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "data/raw/web/betalag"

BIN_SYM = {"BTC": "BTCUSDT"}
LIGHTER_SYMBOLS = ["MSTR", "COIN", "HOOD", "CRCL"]
LIGHTER_IDS_FALLBACK = {"MSTR": 122, "COIN": 109, "HOOD": 108, "CRCL": 121}   # orderBooks 2026-10-05 07:42Z
XYZ = {"COIN": "xyz:COIN", "HOOD": "xyz:HOOD", "CRCL": "xyz:CRCL", "MSTR": "xyz:MSTR"}
LIGHTER_REST = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
HL_INFO = "https://api.hyperliquid.xyz/info"
BIN_URLS = ["wss://fstream.binance.com/stream?streams=btcusdt@bookTicker",
            "wss://fstream.binance.com/market/stream?streams=btcusdt@bookTicker"]

SCHEMA = pa.schema([("ts_us", pa.int64()), ("coin", pa.string()), ("bid", pa.float64()), ("ask", pa.float64()),
                    ("bid_sz", pa.float32()), ("ask_sz", pa.float32()), ("exch_ts_ms", pa.int64())])


def _ssl():
    return ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))


def now_us() -> int:
    return time.time_ns() // 1000


def utc(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(*a):
    print(utc(), *a, flush=True)


def hour_of(ts_us: int) -> str:
    return datetime.fromtimestamp(ts_us / 1e6, timezone.utc).strftime("%Y-%m-%d-%H")


class Store:
    def __init__(self, out: Path, throttle_ms: int, coalesce_ms: int):
        self.out, self.parts = out, out / "parts"
        self.parts.mkdir(parents=True, exist_ok=True)
        self.rows = defaultdict(list)
        self.thr, self.pc = throttle_ms * 1000, coalesce_ms * 1000
        self.last, self.pending = {}, {}
        self.recv, self.written = defaultdict(int), defaultdict(int)
        self.seq = 0

    def _due(self, key, row, t):
        last = self.last[key]
        if row[2] != last[2] or row[3] != last[3]:
            return t - last[0] >= self.pc
        return t - last[0] >= self.thr

    def bbo(self, table, coin, ts, bid, ask, bsz, asz, exch_ms):
        self.recv[table] += 1
        key, row = (table, coin), (ts, coin, bid, ask, bsz, asz, exch_ms)
        last = self.last.get(key)
        if last is None:
            self._write(key, row)
        elif row[2:6] == last[2:6]:
            self.pending.pop(key, None)
        elif self._due(key, row, ts):
            self._write(key, row)
        else:
            self.pending[key] = row

    def reset(self, table):
        """After a reconnect the first state is always written (so the gap rule sees a fresh row)."""
        for key in [k for k in self.last if k[0] == table]:
            self.last.pop(key)
            self.pending.pop(key, None)

    def _write(self, key, row):
        self.pending.pop(key, None)
        self.last[key] = row
        self.rows[key[0]].append(row)

    def sweep(self):
        t = now_us()
        for key, row in list(self.pending.items()):
            if self._due(key, row, t):
                self._write(key, row)

    def flush(self):
        for table, rows in self.rows.items():
            by_hour = defaultdict(list)
            for r in rows:
                by_hour[hour_of(r[0])].append(r)
            for h, rr in by_hour.items():
                cols = list(zip(*rr))
                t = pa.Table.from_arrays([pa.array(c, type=f.type) for c, f in zip(cols, SCHEMA)], schema=SCHEMA)
                self.seq += 1
                pq.write_table(t, self.parts / f"{table}_{h}_p{self.seq:07d}.parquet", compression="zstd")
                self.written[table] += len(rr)
        self.rows = defaultdict(list)
        self.merge(final=False)

    def merge(self, final: bool):
        cur = hour_of(now_us())
        groups = defaultdict(list)
        for p in self.parts.glob("*_p*.parquet"):
            table, h = p.name.rsplit("_p", 1)[0].rsplit("_", 1)
            groups[(table, h)].append(p)
        for (table, h), ps in groups.items():
            if h >= cur and not final:
                continue
            dst = self.out / f"{table}_{h}.parquet"
            srcs = ([dst] if dst.exists() else []) + sorted(ps)
            t = pa.concat_tables([pq.read_table(s) for s in srcs]).sort_by([("coin", "ascending"),
                                                                            ("ts_us", "ascending")])
            tmp = dst.with_suffix(".tmp")
            pq.write_table(t, tmp, compression="zstd", compression_level=9, row_group_size=1_000_000,
                           use_dictionary=["coin", "bid", "ask"],
                           column_encoding={"ts_us": "DELTA_BINARY_PACKED", "exch_ts_ms": "DELTA_BINARY_PACKED",
                                            "bid_sz": "BYTE_STREAM_SPLIT", "ask_sz": "BYTE_STREAM_SPLIT"})
            tmp.replace(dst)
            for p in ps:
                p.unlink()


def event(out: Path, venue: str, kind: str, detail: str = ""):
    with open(out / "events.jsonl", "a") as f:
        f.write(json.dumps({"ts_us": now_us(), "utc": utc(), "venue": venue, "event": kind, "detail": detail}) + "\n")


async def ws_loop(name, urls, table, on_open, on_msg, stop, stats, store, out):
    import websockets
    k = 0
    while not stop.is_set():
        url = urls[k % len(urls)]
        got = False
        try:
            async with websockets.connect(url, ssl=_ssl(), open_timeout=20, ping_interval=20, ping_timeout=20,
                                          max_size=2 ** 24) as ws:
                stats["connects"][name] += 1
                store.reset(table)
                event(out, name, "connect", url)
                await on_open(ws)
                while not stop.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    except asyncio.TimeoutError:
                        raise RuntimeError("no message for 60 s")
                    got = True
                    on_msg(raw)
        except Exception as e:  # noqa: BLE001
            if stop.is_set():
                break
            event(out, name, "disconnect", f"{type(e).__name__} {str(e)[:120]}")
            log(name, "reconnect", type(e).__name__, str(e)[:160])
            if not got:
                k += 1           # nothing ever arrived on this url: try the next route
            await asyncio.sleep(3)


def binance_handler(store):
    rev = {v: k for k, v in BIN_SYM.items()}

    def on_msg(raw):
        ts = now_us()
        m = json.loads(raw)
        d = m.get("data") or m
        coin = rev.get(d.get("s"))
        if coin and d.get("b") is not None:
            store.bbo("binance_bbo", coin, ts, float(d["b"]), float(d["a"]), float(d["B"]), float(d["A"]),
                      int(d.get("T") or d.get("E") or 0))
    return on_msg


def lighter_handlers(store, ids):
    rev = {v: k for k, v in ids.items()}

    async def on_open(ws):
        for i in ids.values():
            await ws.send(json.dumps({"type": "subscribe", "channel": f"ticker/{i}"}))

    def on_msg(raw):
        ts = now_us()
        m = json.loads(raw)
        typ, ch = m.get("type", ""), m.get("channel", "")
        if typ.endswith("/ticker"):
            tk = m.get("ticker") or {}
            coin = rev.get(int(ch.split(":")[1])) if ":" in ch else None
            a, b = tk.get("a") or {}, tk.get("b") or {}
            if coin and a.get("price") and b.get("price"):
                store.bbo("lighter_bbo", coin, ts, float(b["price"]), float(a["price"]), float(b["size"]),
                          float(a["size"]), int(tk.get("last_updated_at") or m.get("last_updated_at") or 0) // 1000)
    return on_open, on_msg


def xyz_handlers(store):
    rev = {v: k for k, v in XYZ.items()}

    async def on_open(ws):
        for c in XYZ.values():
            await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "bbo", "coin": c}}))

    def on_msg(raw):
        ts = now_us()
        m = json.loads(raw)
        ch, d = m.get("channel"), m.get("data")
        if ch == "bbo" and d and d.get("coin") in rev and all(d.get("bbo") or [None]):
            b, a = d["bbo"]
            store.bbo("xyz_bbo", rev[d["coin"]], ts, float(b["px"]), float(a["px"]), float(b["sz"]), float(a["sz"]),
                      int(d["time"]))
    return on_open, on_msg


def _http(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30, context=_ssl()) as r:
        return json.loads(r.read())


def lighter_ids() -> dict:
    try:
        obs = _http(LIGHTER_REST)["order_books"]
        got = {o["symbol"]: int(o["market_id"]) for o in obs
               if o["symbol"] in LIGHTER_SYMBOLS and o.get("market_type") == "perp"}
        if len(got) != len(LIGHTER_SYMBOLS):
            log("lighter ids incomplete from REST, fallback for", sorted(set(LIGHTER_SYMBOLS) - set(got)))
        return {**LIGHTER_IDS_FALLBACK, **got}
    except Exception as e:  # noqa: BLE001
        log("lighter ids REST failed, fallback", type(e).__name__, str(e)[:120])
        return dict(LIGHTER_IDS_FALLBACK)


def meta_snapshot(out: Path):
    ts, tus = utc(), now_us()
    try:
        meta, ctxs = _http(HL_INFO, {"type": "metaAndAssetCtxs", "dex": "xyz"})
        rows = [{k: u.get(k) for k in ("name", "growthMode", "deployerFeeScale", "lastFeeScaleChangeTime",
                                       "onlyIsolated")} |
                {k: c.get(k) for k in ("dayNtlVlm", "funding", "markPx", "oraclePx", "openInterest")}
                for u, c in zip(meta["universe"], ctxs) if u["name"] in XYZ.values()]
        with open(out / "meta_xyz.jsonl", "a") as f:
            f.write(json.dumps({"snapshot_utc": ts, "ts_us": tus, "source": HL_INFO + " metaAndAssetCtxs dex=xyz",
                                "rows": rows}) + "\n")
    except Exception as e:  # noqa: BLE001
        log("meta xyz failed", type(e).__name__, str(e)[:120])
    try:
        obs = _http(LIGHTER_REST)["order_books"]
        rows = [{k: o.get(k) for k in ("symbol", "market_id", "status", "taker_fee", "maker_fee",
                                       "is_taker_fee_enabled", "is_maker_fee_enabled")}
                for o in obs if o["symbol"] in LIGHTER_SYMBOLS]
        with open(out / "meta_lighter.jsonl", "a") as f:
            f.write(json.dumps({"snapshot_utc": ts, "ts_us": tus, "source": LIGHTER_REST, "rows": rows}) + "\n")
    except Exception as e:  # noqa: BLE001
        log("meta lighter failed", type(e).__name__, str(e)[:120])


async def housekeeping(store, out, stop, stats, min_free_gb):
    last_flush, last_meta = time.monotonic(), 0.0
    while not stop.is_set():
        await asyncio.sleep(0.01)
        store.sweep()
        if time.monotonic() - last_meta >= 3600:
            last_meta = time.monotonic()
            await asyncio.to_thread(meta_snapshot, out)
        if time.monotonic() - last_flush >= 60:
            last_flush = time.monotonic()
            await asyncio.to_thread(store.flush)
            size = sum(p.stat().st_size for p in out.glob("*.parquet")) + \
                sum(p.stat().st_size for p in store.parts.glob("*.parquet"))
            free = shutil.disk_usage(out).free / 1e9
            log("stats recv", dict(store.recv), "written", dict(store.written), "connects", dict(stats["connects"]),
                f"dir_MB {size / 1e6:.2f} free_GB {free:.2f}")
            if free < min_free_gb:
                log(f"free disk {free:.2f} GB < {min_free_gb} GB: stopping")
                stop.set()


async def run(hours, out, throttle_ms, coalesce_ms, min_free_gb):
    out.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(out).free / 1e9
    if free < min_free_gb:
        log(f"free disk {free:.2f} GB < {min_free_gb} GB: not starting")
        return
    store, stop = Store(out, throttle_ms, coalesce_ms), asyncio.Event()
    stats = {"connects": defaultdict(int)}
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    ids = lighter_ids()
    log("start", json.dumps({"pid": os.getpid(), "hours": hours, "out": str(out), "size_throttle_ms": throttle_ms,
                             "price_coalesce_ms": coalesce_ms, "min_free_gb": min_free_gb, "start_ts_us": now_us(),
                             "end_utc": utc(time.time() + hours * 3600), "binance": BIN_SYM, "xyz": XYZ,
                             "lighter_ids": ids, "free_gb": round(free, 2)}))
    l_open, l_msg = lighter_handlers(store, ids)
    x_open, x_msg = xyz_handlers(store)

    async def nothing(ws):
        return None

    async def timer():
        try:
            await asyncio.wait_for(stop.wait(), timeout=hours * 3600)
        except asyncio.TimeoutError:
            stop.set()

    tasks = [ws_loop("binance", BIN_URLS, "binance_bbo", nothing, binance_handler(store), stop, stats, store, out),
             ws_loop("lighter", ["wss://mainnet.zklighter.elliot.ai/stream?readonly=true"], "lighter_bbo",
                     l_open, l_msg, stop, stats, store, out),
             ws_loop("xyz", ["wss://api.hyperliquid.xyz/ws"], "xyz_bbo", x_open, x_msg, stop, stats, store, out),
             housekeeping(store, out, stop, stats, min_free_gb), timer()]
    running = [asyncio.create_task(t) for t in tasks]
    await stop.wait()
    await asyncio.sleep(1)
    for t in running:
        t.cancel()
    await asyncio.gather(*running, return_exceptions=True)
    for venue in ("binance", "lighter", "xyz"):
        event(out, venue, "disconnect", "stop")
    store.sweep()
    for k, row in list(store.pending.items()):
        store._write(k, row)
    store.flush()
    store.merge(final=True)
    log("stop", json.dumps({"written": dict(store.written), "recv": dict(store.recv)}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=48.0)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--size-throttle-ms", type=int, default=500)
    ap.add_argument("--price-coalesce-ms", type=int, default=50)
    ap.add_argument("--min-free-gb", type=float, default=1.5)
    a = ap.parse_args()
    asyncio.run(run(a.hours, a.out, a.size_throttle_ms, a.price_coalesce_ms, a.min_free_gb))
