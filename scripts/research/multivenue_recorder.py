"""Multi-venue top-of-book + trades recorder for H-LIGHTLAG, H-EQLAG, H-LIGHTFADE and H-T2LAG.

Public, unauthenticated websockets only (no accounts, no orders). Connection pattern as in hllag_forward.py
(`websockets` picks up HTTPS_PROXY; TLS verified against SSL_CERT_FILE).

Streams
  binance  wss://fstream.binance.com  <sym>@bookTicker   crypto leaders + equity/metal perps
  aster    wss://fstream.asterdex.com <sym>@bookTicker   crypto (control venue)
  lighter  wss://mainnet.zklighter.elliot.ai/stream?readonly=true   ticker/<id> (best bid/ask) + trade/<id>
  hl       wss://api.hyperliquid.xyz/ws  bbo + trades for HIP-3 trade[XYZ] coins (xyz:TSLA ...)
  meta     hourly REST snapshots: xyz metaAndAssetCtxs (growthMode, deployerFeeScale) and Lighter orderBooks fees

Tables (hourly parquet, zstd) data/raw/web/multivenue/<table>_<YYYY-MM-DD-HH>.parquet, hour = UTC hour of ts_us:
  <venue>_bbo     ts_us, coin, bid, ask, bid_sz, ask_sz, exch_ts_ms
  <venue>_trades  ts_us, coin, px, sz, side (+1 taker buy / -1 taker sell), exch_ts_ms [, liq, trade_id for lighter]
  ts_us = our receive time (microseconds, this container's clock); exch_ts_ms = venue time where given
  (binance/aster: T transaction time; lighter ticker: last_updated_at; lighter trade: transaction_time; hl: time). Coin keys are the hypothesis names (SOL, TSLA, XAU ...), not venue symbols.

Compaction rule (to stay < 300 MB/day), per venue x coin, relative to the last WRITTEN row:
  - unchanged repeats are dropped;
  - a best bid/ask PRICE change is written if >= --price-coalesce-ms (default 50) after the last written row,
    otherwise it is held and the latest state is written (with its own receive time) once the window has passed:
    sub-50-ms flickers are coalesced, and a recorded price is at most ~60 ms stale;
  - a size-only change is written at most once per --size-throttle-ms (default 500), same holding rule, so a
    recorded top-of-book SIZE can be up to ~0.5 s stale.
  Trades are written in full. exch_ts is stored in ms (venue clocks are ms except Lighter's, which is truncated).
Every 60 s rows go to part files; parts of finished hours are merged into the hourly file, sorted by (coin, ts_us),
with delta encoding for timestamps.

    python scripts/research/multivenue_recorder.py --hours 0.05 --out <scratch dir>   # test
    nohup python scripts/research/multivenue_recorder.py --hours 48 >> data/raw/web/multivenue/recorder.log 2>&1 &
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
DEFAULT_OUT = ROOT / "data/raw/web/multivenue"

CRYPTO = ["SOL", "XRP", "HYPE", "ENA", "PUMP", "DOGE", "SUI"]
EQUITY = ["TSLA", "NVDA", "MU", "INTC", "COIN", "MSTR", "XAU", "XAG"]
BINANCE = {c: f"{c}USDT" for c in CRYPTO + EQUITY}            # all 15 verified live on fstream 2026-10-05
ASTER = {c: f"{c}USDT" for c in CRYPTO}
XYZ = {"TSLA": "xyz:TSLA", "NVDA": "xyz:NVDA", "MU": "xyz:MU", "INTC": "xyz:INTC", "COIN": "xyz:COIN",
       "MSTR": "xyz:MSTR", "XAU": "xyz:GOLD", "XAG": "xyz:SILVER"}
LIGHTER_SYMBOLS = CRYPTO + EQUITY                               # Lighter symbol == coin key
LIGHTER_IDS_FALLBACK = {"SOL": 2, "XRP": 7, "HYPE": 24, "ENA": 29, "PUMP": 45, "DOGE": 3, "SUI": 16, "TSLA": 112,
                        "NVDA": 110, "MU": 164, "INTC": 137, "COIN": 109, "MSTR": 122, "XAU": 92, "XAG": 93}
LIGHTER_REST = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
HL_INFO = "https://api.hyperliquid.xyz/info"

BBO_SCHEMA = pa.schema([("ts_us", pa.int64()), ("coin", pa.string()), ("bid", pa.float64()), ("ask", pa.float64()),
                        ("bid_sz", pa.float32()), ("ask_sz", pa.float32()), ("exch_ts_ms", pa.int64())])
TRD_SCHEMA = pa.schema([("ts_us", pa.int64()), ("coin", pa.string()), ("px", pa.float64()), ("sz", pa.float32()),
                        ("side", pa.int8()), ("exch_ts_ms", pa.int64())])
LTRD_SCHEMA = TRD_SCHEMA.append(pa.field("liq", pa.int8())).append(pa.field("trade_id", pa.int64()))
SCHEMAS = {"binance_bbo": BBO_SCHEMA, "aster_bbo": BBO_SCHEMA, "lighter_bbo": BBO_SCHEMA, "hl_bbo": BBO_SCHEMA,
           "lighter_trades": LTRD_SCHEMA, "hl_trades": TRD_SCHEMA}


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
    """Row buffers per table, BBO compaction, part files, hourly merge."""

    def __init__(self, out: Path, throttle_ms: int, coalesce_ms: int):
        self.out, self.parts = out, out / "parts"
        self.parts.mkdir(parents=True, exist_ok=True)
        self.rows = defaultdict(list)
        self.thr, self.pc = throttle_ms * 1000, coalesce_ms * 1000
        self.last = {}        # (table, coin) -> last WRITTEN row
        self.pending = {}     # (table, coin) -> latest unwritten state
        self.recv = defaultdict(int)
        self.written = defaultdict(int)
        self.seq = 0

    def _due(self, key, row, t):
        last = self.last[key]
        if row[2] != last[2] or row[3] != last[3]:
            return t - last[0] >= self.pc
        return t - last[0] >= self.thr

    def bbo(self, table, coin, ts, bid, ask, bsz, asz, exch_ms):
        self.recv[table] += 1
        key = (table, coin)
        row = (ts, coin, bid, ask, bsz, asz, exch_ms)
        last = self.last.get(key)
        if last is None:
            self._write_bbo(key, row)
        elif row[2:6] == last[2:6]:
            self.pending.pop(key, None)          # back to the written state: flicker coalesced
        elif self._due(key, row, ts):
            self._write_bbo(key, row)
        else:
            self.pending[key] = row

    def _write_bbo(self, key, row):
        self.pending.pop(key, None)
        self.last[key] = row
        self.rows[key[0]].append(row)

    def sweep(self):
        t = now_us()
        for key, row in list(self.pending.items()):
            if self._due(key, row, t):
                self._write_bbo(key, row)

    def trade(self, table, row):
        self.recv[table] += 1
        self.rows[table].append(row)

    def flush(self):
        for table, rows in self.rows.items():
            if not rows:
                continue
            by_hour = defaultdict(list)
            for r in rows:
                by_hour[hour_of(r[0])].append(r)
            schema = SCHEMAS[table]
            for h, rr in by_hour.items():
                cols = list(zip(*rr))
                t = pa.Table.from_arrays([pa.array(c, type=f.type) for c, f in zip(cols, schema)], schema=schema)
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
            ints = [f.name for f in t.schema if pa.types.is_integer(f.type) and f.type.bit_width == 64]
            flts = [f.name for f in t.schema if f.type == pa.float32()]
            pq.write_table(t, tmp, compression="zstd", compression_level=9, row_group_size=1_000_000,
                           use_dictionary=[f.name for f in t.schema if f.name not in ints + flts],
                           column_encoding={**{c: "DELTA_BINARY_PACKED" for c in ints},
                                            **{c: "BYTE_STREAM_SPLIT" for c in flts}})
            tmp.replace(dst)
            for p in ps:
                p.unlink()


async def ws_loop(name, url, on_open, on_msg, stop: asyncio.Event, stats):
    import websockets
    while not stop.is_set():
        try:
            async with websockets.connect(url, ssl=_ssl(), open_timeout=20, ping_interval=20, ping_timeout=20,
                                          max_size=2 ** 24) as ws:
                stats["connects"][name] += 1
                await on_open(ws)
                while not stop.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    except asyncio.TimeoutError:
                        raise RuntimeError("no message for 60 s")
                    on_msg(raw)
        except Exception as e:  # noqa: BLE001
            if stop.is_set():
                return
            log(name, "reconnect", type(e).__name__, str(e)[:160])
            await asyncio.sleep(3)


def book_ticker_handler(store, table, symmap):
    rev = {v: k for k, v in symmap.items()}

    def on_msg(raw):
        ts = now_us()
        d = json.loads(raw).get("data") or {}
        coin = rev.get(d.get("s"))
        if coin and d.get("b") is not None:
            store.bbo(table, coin, ts, float(d["b"]), float(d["a"]), float(d["B"]), float(d["A"]),
                      int(d.get("T") or d.get("E") or 0))
    return on_msg


def lighter_handlers(store, ids):
    rev = {v: k for k, v in ids.items()}

    async def on_open(ws):
        for i in ids.values():
            await ws.send(json.dumps({"type": "subscribe", "channel": f"ticker/{i}"}))
            await ws.send(json.dumps({"type": "subscribe", "channel": f"trade/{i}"}))

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
        elif typ == "update/trade":          # 'subscribed/trade' carries history: skipped
            for liq, key in ((0, "trades"), (1, "liquidation_trades")):
                for t in m.get(key) or []:
                    coin = rev.get(int(t.get("market_id", -1)))
                    if coin:
                        store.trade("lighter_trades", (ts, coin, float(t["price"]), float(t["size"]),
                                                       1 if t.get("is_maker_ask") else -1,
                                                       int(t.get("transaction_time") or 0) // 1000 or int(t.get("timestamp", 0)),
                                                       liq, int(t.get("trade_id") or 0)))
        elif typ == "ping":
            pass
    return on_open, on_msg


def hl_handlers(store):
    rev = {v: k for k, v in XYZ.items()}
    snap_seen = set()     # the first trades message per coin after (re)subscribing is a history snapshot: skipped

    async def on_open(ws):
        snap_seen.clear()
        for c in XYZ.values():
            await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "bbo", "coin": c}}))
            await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "trades", "coin": c}}))

    def on_msg(raw):
        ts = now_us()
        m = json.loads(raw)
        ch, d = m.get("channel"), m.get("data")
        if ch == "bbo" and d and d.get("coin") in rev and all(d.get("bbo") or [None]):
            b, a = d["bbo"]
            store.bbo("hl_bbo", rev[d["coin"]], ts, float(b["px"]), float(a["px"]), float(b["sz"]), float(a["sz"]),
                      int(d["time"]))
        elif ch == "trades" and isinstance(d, list) and d:
            if d[0].get("coin") not in snap_seen:
                snap_seen.add(d[0].get("coin"))
                return
            for t in d:
                if t.get("coin") in rev:
                    store.trade("hl_trades", (ts, rev[t["coin"]], float(t["px"]), float(t["sz"]),
                                              1 if t.get("side") == "B" else -1, int(t["time"])))
    return on_open, on_msg


def _http(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30, context=_ssl()) as r:
        return json.loads(r.read())


def lighter_ids() -> dict:
    try:
        obs = _http(LIGHTER_REST)["order_books"]
        got = {o["symbol"]: int(o["market_id"]) for o in obs if o["symbol"] in LIGHTER_SYMBOLS and o.get("market_type") == "perp"}
        if len(got) == len(LIGHTER_SYMBOLS):
            return got
        log("lighter ids incomplete from REST, using fallback for", sorted(set(LIGHTER_SYMBOLS) - set(got)))
        return {**LIGHTER_IDS_FALLBACK, **got}
    except Exception as e:  # noqa: BLE001
        log("lighter ids REST failed, fallback", type(e).__name__, str(e)[:120])
        return dict(LIGHTER_IDS_FALLBACK)


def meta_snapshot(out: Path):
    ts = utc()
    try:
        meta, ctxs = _http(HL_INFO, {"type": "metaAndAssetCtxs", "dex": "xyz"})
        rows = []
        for u, c in zip(meta["universe"], ctxs):
            if u["name"] in XYZ.values():
                rows.append({k: u.get(k) for k in ("name", "growthMode", "deployerFeeScale", "lastFeeScaleChangeTime",
                                                   "onlyIsolated")} |
                            {k: c.get(k) for k in ("dayNtlVlm", "funding", "markPx", "oraclePx", "openInterest")})
        with open(out / "meta_xyz.jsonl", "a") as f:
            f.write(json.dumps({"snapshot_utc": ts, "source": HL_INFO + " metaAndAssetCtxs dex=xyz", "rows": rows}) + "\n")
    except Exception as e:  # noqa: BLE001
        log("meta xyz failed", type(e).__name__, str(e)[:120])
    try:
        obs = _http(LIGHTER_REST)["order_books"]
        rows = [{k: o.get(k) for k in ("symbol", "market_id", "status", "taker_fee", "maker_fee",
                                       "is_taker_fee_enabled", "is_maker_fee_enabled")}
                for o in obs if o["symbol"] in LIGHTER_SYMBOLS]
        with open(out / "meta_lighter.jsonl", "a") as f:
            f.write(json.dumps({"snapshot_utc": ts, "source": LIGHTER_REST, "rows": rows}) + "\n")
    except Exception as e:  # noqa: BLE001
        log("meta lighter failed", type(e).__name__, str(e)[:120])


async def housekeeping(store: Store, out: Path, stop: asyncio.Event, stats, min_free_gb: float):
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
                f"dir_MB {size / 1e6:.1f} free_GB {free:.2f}")
            if free < min_free_gb:
                log(f"free disk {free:.2f} GB < {min_free_gb} GB: stopping")
                stop.set()


async def run(hours: float, out: Path, throttle_ms: int, coalesce_ms: int, min_free_gb: float):
    out.mkdir(parents=True, exist_ok=True)
    store, stop = Store(out, throttle_ms, coalesce_ms), asyncio.Event()
    stats = {"connects": defaultdict(int)}
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    ids = lighter_ids()
    log("start", json.dumps({"pid": os.getpid(), "hours": hours, "out": str(out), "size_throttle_ms": throttle_ms, "price_coalesce_ms": coalesce_ms,
                             "start_ts_us": now_us(), "end_utc": utc(time.time() + hours * 3600),
                             "binance": BINANCE, "aster": ASTER, "hl_xyz": XYZ, "lighter_ids": ids}))
    bin_url = "wss://fstream.binance.com/stream?streams=" + "/".join(f"{s.lower()}@bookTicker" for s in BINANCE.values())
    ast_url = "wss://fstream.asterdex.com/stream?streams=" + "/".join(f"{s.lower()}@bookTicker" for s in ASTER.values())

    async def nothing(ws):
        return None

    l_open, l_msg = lighter_handlers(store, ids)
    h_open, h_msg = hl_handlers(store)

    async def timer():
        try:
            await asyncio.wait_for(stop.wait(), timeout=hours * 3600)
        except asyncio.TimeoutError:
            stop.set()

    tasks = [ws_loop("binance", bin_url, nothing, book_ticker_handler(store, "binance_bbo", BINANCE), stop, stats),
             ws_loop("aster", ast_url, nothing, book_ticker_handler(store, "aster_bbo", ASTER), stop, stats),
             ws_loop("lighter", "wss://mainnet.zklighter.elliot.ai/stream?readonly=true", l_open, l_msg, stop, stats),
             ws_loop("hl", "wss://api.hyperliquid.xyz/ws", h_open, h_msg, stop, stats),
             housekeeping(store, out, stop, stats, min_free_gb), timer()]
    running = [asyncio.create_task(t) for t in tasks]
    await stop.wait()
    await asyncio.sleep(1)
    for t in running:
        t.cancel()
    await asyncio.gather(*running, return_exceptions=True)
    store.sweep()
    for k, row in list(store.pending.items()):
        store._write_bbo(k, row)
    store.flush()
    store.merge(final=True)
    log("stop", json.dumps({"written": dict(store.written), "recv": dict(store.recv)}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=48.0)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--size-throttle-ms", type=int, default=500)
    ap.add_argument("--price-coalesce-ms", type=int, default=50)
    ap.add_argument("--min-free-gb", type=float, default=1.0)
    a = ap.parse_args()
    asyncio.run(run(a.hours, a.out, a.size_throttle_ms, a.price_coalesce_ms, a.min_free_gb))
