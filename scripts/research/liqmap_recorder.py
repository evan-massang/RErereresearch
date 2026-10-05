"""Forward recorder for H-LIQMAP: public Hyperliquid positions (liquidation prices) of addresses trading meme perps.

Pre-registration (written before this recorder recorded anything): reports/hypotheses/liqmap_preregistration.json.
T0 = the 'start' line (start_ts_us) of data/raw/web/liqmap/recorder.log. Train = [T0+2h, T0+26h), validation =
[T0+26h, T0+50h), local clock.

Sources (public, unauthenticated, read-only; all HL access goes through pipeline/sources/hyperliquid_positions.py):
  * HL WS `trades` + `bbo` for the 13 meme coins. Every address in a trade's `users` ([buyer, seller]) is discovered.
  * HL info `clearinghouseState` per discovered address (weight 2), token bucket --poll-per-min (270/min = 540 weight)
    + `metaAndAssetCtxs` once a minute (20 weight) => <= 560 of HL's 1200 weight/min/IP (twap_recorder uses ~260).
    On 429: all polling pauses 60 s.
  * Poll schedule (priority = due time; near-liq and large tiers get a 60 s / 30 s priority bonus when backlogged):
      new address -> now; trades a meme coin again -> max(trade + 20 s, last poll + 60 s);
      after a poll: any meme liqPx within 300 bp of the HL mid -> 60 s; meme notional >= $100k -> 120 s;
      >= $10k -> 300 s; > 0 -> 900 s; none -> only when it trades a meme coin again.

Tables (zstd parquet, hourly by UTC hour of ts_us) in data/raw/web/liqmap/:
  hl_bbo_<H>      ts_us, coin, bid, ask, bid_sz, ask_sz, exch_ts_ms   (price change coalesced 50 ms; size-only <= 1/s)
  hl_trades_<H>   ts_us, coin, px, sz, side (+1 = HL side 'B', -1 = 'A'), exch_ts_ms, tid, buyer, seller
  positions_<H>   ts_us (response receive), address, coin, szi, entry_px, liq_px (null kept), position_value,
                  leverage, cross
  polls_<H>       ts_us, sent_us, address, ok, n_meme, meme_ntl, reason (0 new, 1 trade, 2 schedule, 3 resume), err
                  (every poll, also those with no meme position, so closed positions are visible)
  ctx_<H>         ts_us, coin, mark, mid, oracle, oi (base units), day_ntl_vlm, funding     (once a minute)
  coverage_<H>    ts_us, coin, n_addr, long_ntl, short_ntl, oi_ntl, liq10_ntl, med_age_s  (every 10 min, from the
                  latest poll of each address; oi_ntl = HL openInterest x mark, one side)
ts_us = OUR local receive time (container clock, ~2.8 s slow and drifting; reports/paper/hllag_forward_audit.md).
Score on ts_us only; never mix with exch_ts_ms.

Part files are written every 60 s in a worker thread; finished hours are merged. Disk guard: stop when free disk
< --min-free-gb (1.5).

    python scripts/research/liqmap_recorder.py --hours 0.05 --out <scratch dir>        # test
    nohup python scripts/research/liqmap_recorder.py --hours 50 >> data/raw/web/liqmap/recorder.log 2>&1 &
"""
import argparse
import asyncio
import heapq
import json
import os
import shutil
import signal
import ssl
import statistics
import sys
import time
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline.sources.base import SourceUnavailable  # noqa: E402
from pipeline.sources.hyperliquid_positions import (WS_URL, HyperliquidPositionsAdapter, RateLimited,  # noqa: E402
                                                    WeightBucket)

DEFAULT_OUT = ROOT / "data/raw/web/liqmap"
COINS = ["WIF", "kBONK", "FARTCOIN", "PUMP", "PENGU", "TRUMP", "SPX", "kPEPE", "kSHIB", "POPCAT", "USELESS", "kFLOKI",
         "DOGE"]
COINSET = set(COINS)

S = pa.string()
SCHEMAS = {
    "hl_bbo": pa.schema([("ts_us", pa.int64()), ("coin", S), ("bid", pa.float64()), ("ask", pa.float64()),
                         ("bid_sz", pa.float32()), ("ask_sz", pa.float32()), ("exch_ts_ms", pa.int64())]),
    "hl_trades": pa.schema([("ts_us", pa.int64()), ("coin", S), ("px", pa.float64()), ("sz", pa.float64()),
                            ("side", pa.int8()), ("exch_ts_ms", pa.int64()), ("tid", pa.int64()), ("buyer", S),
                            ("seller", S)]),
    "positions": pa.schema([("ts_us", pa.int64()), ("address", S), ("coin", S), ("szi", pa.float64()),
                            ("entry_px", pa.float64()), ("liq_px", pa.float64()), ("position_value", pa.float64()),
                            ("leverage", pa.int16()), ("cross", pa.bool_())]),
    "polls": pa.schema([("ts_us", pa.int64()), ("sent_us", pa.int64()), ("address", S), ("ok", pa.int8()),
                        ("n_meme", pa.int16()), ("meme_ntl", pa.float64()), ("reason", pa.int8()), ("err", S)]),
    "ctx": pa.schema([("ts_us", pa.int64()), ("coin", S), ("mark", pa.float64()), ("mid", pa.float64()),
                      ("oracle", pa.float64()), ("oi", pa.float64()), ("day_ntl_vlm", pa.float64()),
                      ("funding", pa.float64())]),
    "coverage": pa.schema([("ts_us", pa.int64()), ("coin", S), ("n_addr", pa.int32()), ("long_ntl", pa.float64()),
                           ("short_ntl", pa.float64()), ("oi_ntl", pa.float64()), ("liq10_ntl", pa.float64()),
                           ("med_age_s", pa.float64())]),
}
R_NEW, R_TRADE, R_SCHED, R_RESUME = 0, 1, 2, 3


def now_us() -> int:
    return time.time_ns() // 1000


def utc(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(*a):
    print(utc(), *a, flush=True)


def hour_of(ts_us: int) -> str:
    return datetime.fromtimestamp(ts_us / 1e6, timezone.utc).strftime("%Y-%m-%d-%H")


class Store:
    def __init__(self, out: Path, coalesce_ms=50, size_ms=1000):
        self.out, self.parts = out, out / "parts"
        self.parts.mkdir(parents=True, exist_ok=True)
        self.rows = defaultdict(list)
        self.pc, self.thr = coalesce_ms * 1000, size_ms * 1000
        self.last, self.pending = {}, {}
        self.written = defaultdict(int)
        self.seq = 0

    def add(self, table, row):
        self.rows[table].append(row)

    def bbo(self, row):
        coin, ts = row[1], row[0]
        last = self.last.get(coin)
        if last is None:
            return self._wb(row)
        if row[2:6] == last[2:6]:
            self.pending.pop(coin, None)
            return
        lim = self.pc if (row[2] != last[2] or row[3] != last[3]) else self.thr
        if ts - last[0] >= lim:
            self._wb(row)
        else:
            self.pending[coin] = row

    def _wb(self, row):
        self.pending.pop(row[1], None)
        self.last[row[1]] = row
        self.rows["hl_bbo"].append(row)

    def sweep(self):
        t = now_us()
        for coin, row in list(self.pending.items()):
            last = self.last[coin]
            lim = self.pc if (row[2] != last[2] or row[3] != last[3]) else self.thr
            if t - last[0] >= lim:
                self._wb(row)

    def take(self):
        rows, self.rows = self.rows, defaultdict(list)
        return rows

    def write_parts(self, rows):
        for table, rr in rows.items():
            if not rr:
                continue
            schema = SCHEMAS[table]
            by_hour = defaultdict(list)
            for r in rr:
                by_hour[hour_of(r[0])].append(r)
            for h, hr in by_hour.items():
                cols = list(zip(*hr))
                t = pa.Table.from_arrays([pa.array(c, type=f.type) for c, f in zip(cols, schema)], schema=schema)
                self.seq += 1
                pq.write_table(t, self.parts / f"{table}_{h}_p{self.seq:07d}.parquet", compression="zstd")
                self.written[table] += len(hr)

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
            t = pa.concat_tables([pq.read_table(s) for s in srcs]).sort_by([("ts_us", "ascending")])
            ints = [f.name for f in t.schema if pa.types.is_integer(f.type) and f.type.bit_width == 64]
            flts = [f.name for f in t.schema if f.type == pa.float32()]
            tmp = dst.with_suffix(".tmp")
            pq.write_table(t, tmp, compression="zstd", compression_level=9, row_group_size=1_000_000,
                           use_dictionary=[f.name for f in t.schema if f.name not in ints + flts],
                           column_encoding={**{c: "DELTA_BINARY_PACKED" for c in ints},
                                            **{c: "BYTE_STREAM_SPLIT" for c in flts}})
            tmp.replace(dst)
            for p in ps:
                p.unlink()


class Scheduler:
    """Due-time priority queue of addresses (monotonic seconds), lazy deletion."""

    def __init__(self):
        self.heap, self.key, self.reason = [], {}, {}
        self.info = {}          # addr -> dict(last_poll, ntl, near, positions(list), poll_ts_us)
        self.seq = 0
        self.wakeup = asyncio.Event()

    def schedule(self, addr, due, reason, bonus=0.0):
        k = due - bonus
        if addr in self.key and self.key[addr] <= k:
            return
        self.key[addr], self.reason[addr] = k, reason
        self.seq += 1
        heapq.heappush(self.heap, (k, self.seq, addr))
        self.wakeup.set()

    def on_trade_addr(self, addr):
        if not addr:
            return
        t = time.monotonic()
        inf = self.info.get(addr)
        if inf is None:
            self.info[addr] = dict(last_poll=None, ntl=0.0, near=False, positions=[], poll_ts_us=None)
            self.schedule(addr, t, R_NEW)
        else:
            lp = inf["last_poll"]
            self.schedule(addr, max(t + 20, (lp + 60) if lp else t), R_TRADE)

    def backlog(self):
        t = time.monotonic()
        return sum(1 for a, k in self.key.items() if k <= t)

    async def next(self, stop):
        while not stop.is_set():
            t = time.monotonic()
            while self.heap and self.key.get(self.heap[0][2]) != self.heap[0][0]:
                heapq.heappop(self.heap)
            if self.heap and self.heap[0][0] <= t:
                k, _, addr = heapq.heappop(self.heap)
                del self.key[addr]
                return addr, self.reason.pop(addr, R_SCHED), t - k
            wait = (self.heap[0][0] - t) if self.heap else 5.0
            self.wakeup.clear()
            try:
                await asyncio.wait_for(self.wakeup.wait(), timeout=min(max(wait, 0.01), 5.0))
            except asyncio.TimeoutError:
                pass
        return None, None, None


class Recorder:
    def __init__(self, a, out: Path):
        self.a, self.out = a, out
        self.store = Store(out)
        self.sched = Scheduler()
        self.bucket = WeightBucket(per_min=a.poll_per_min * 2 + 20, burst=40)
        self.hl = HyperliquidPositionsAdapter(self.bucket)
        self.stop = asyncio.Event()
        self.mid = {}
        self.ctx = {}
        self.stats = defaultdict(int)
        self.lat = []
        self.lags = []
        self.pause_until = 0.0
        self.tids = OrderedDict()
        self.t_start = time.monotonic()

    # ---------- resume ----------
    def resume(self):
        n = 0
        for p in sorted(self.out.glob("polls_*.parquet"))[-6:]:
            df = pq.read_table(p, columns=["address", "n_meme"]).to_pydict()
            for addr, nm in zip(df["address"], df["n_meme"]):
                if addr not in self.sched.info:
                    self.sched.info[addr] = dict(last_poll=None, ntl=0.0, near=False, positions=[], poll_ts_us=None)
                    if nm:
                        self.sched.schedule(addr, time.monotonic(), R_RESUME)
                        n += 1
        if self.sched.info:
            log(f"resume: {len(self.sched.info)} known addresses, {n} with meme positions re-queued")

    # ---------- websocket ----------
    async def ws_loop(self):
        import websockets
        ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))
        while not self.stop.is_set():
            try:
                async with websockets.connect(WS_URL, ssl=ctx, open_timeout=20, ping_interval=20, ping_timeout=20,
                                              max_size=2 ** 24) as ws:
                    self.stats["ws_connects"] += 1
                    for s in HyperliquidPositionsAdapter.ws_subscriptions(COINS):
                        await ws.send(s)
                    while not self.stop.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        except asyncio.TimeoutError:
                            raise RuntimeError("no message for 60 s")
                        self.on_ws(raw)
            except Exception as e:  # noqa: BLE001
                if self.stop.is_set():
                    return
                log("ws reconnect", type(e).__name__, str(e)[:160])
                await asyncio.sleep(3)

    def on_ws(self, raw):
        ts = now_us()
        for kind, d in HyperliquidPositionsAdapter.parse_ws(raw):
            if d["coin"] not in COINSET:
                continue
            if kind == "bbo":
                self.mid[d["coin"]] = (d["bid"] + d["ask"]) / 2
                self.stats["bbo_recv"] += 1
                self.store.bbo((ts, d["coin"], d["bid"], d["ask"], d["bid_sz"], d["ask_sz"], d["exch_ms"]))
            else:
                key = (d["coin"], d["tid"], d["exch_ms"])
                if key in self.tids:
                    self.stats["trade_dupes"] += 1
                    continue
                self.tids[key] = None
                if len(self.tids) > 50000:
                    self.tids.popitem(last=False)
                self.stats["trades"] += 1
                self.store.add("hl_trades", (ts, d["coin"], d["px"], d["sz"], d["side"], d["exch_ms"], d["tid"],
                                             d["buyer"], d["seller"]))
                self.sched.on_trade_addr(d["buyer"])
                self.sched.on_trade_addr(d["seller"])

    # ---------- polling ----------
    async def poll_worker(self):
        while not self.stop.is_set():
            addr, reason, lag = await self.sched.next(self.stop)
            if addr is None:
                return
            wait = self.pause_until - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            sent = now_us()
            t0 = time.monotonic()
            try:
                st = await self.hl.clearinghouse_state(addr)
            except RateLimited:
                self.stats["http_429"] += 1
                self.pause_until = time.monotonic() + 60
                log("HL 429: pausing polls 60 s")
                self.sched.schedule(addr, time.monotonic() + 61, reason)
                continue
            except (SourceUnavailable, Exception) as e:  # noqa: BLE001
                ts = now_us()
                self.stats["poll_err"] += 1
                self.store.add("polls", (ts, sent, addr, 0, 0, 0.0, reason, f"{type(e).__name__}: {e}"[:200]))
                self.sched.schedule(addr, time.monotonic() + 120, R_SCHED)
                continue
            ts = now_us()
            self.lat.append(time.monotonic() - t0)
            self.lags.append(lag)
            self.stats["polls"] += 1
            pos = HyperliquidPositionsAdapter.meme_positions(st, COINSET)
            ntl, near = 0.0, False
            for p in pos:
                self.store.add("positions", (ts, addr, p.coin, p.szi, p.entry_px, p.liq_px, p.position_value,
                                             p.leverage, p.cross))
                ntl += abs(p.position_value or 0.0)
                m = self.mid.get(p.coin)
                if p.liq_px and m and abs(p.liq_px / m - 1) <= 0.03:
                    near = True
            self.store.add("polls", (ts, sent, addr, 1, len(pos), ntl, reason, None))
            inf = self.sched.info.setdefault(addr, {})
            inf.update(last_poll=time.monotonic(), ntl=ntl, near=near, positions=pos, poll_ts_us=ts)
            t = time.monotonic()
            if near:
                self.sched.schedule(addr, t + 60, R_SCHED, bonus=60)
            elif ntl >= 100_000:
                self.sched.schedule(addr, t + 120, R_SCHED, bonus=30)
            elif ntl >= 10_000:
                self.sched.schedule(addr, t + 300, R_SCHED)
            elif ntl > 0:
                self.sched.schedule(addr, t + 900, R_SCHED)
            # no meme position: re-polled only when it trades a meme coin again (on_trade_addr)

    async def ctx_loop(self):
        while not self.stop.is_set():
            try:
                rows = await self.hl.meta_and_ctxs()
                ts = now_us()
                for r in rows:
                    if r["coin"] in COINSET:
                        self.ctx[r["coin"]] = r
                        self.store.add("ctx", (ts, r["coin"], r["mark"], r["mid"], r["oracle"], r["oi"],
                                               r["day_ntl_vlm"], r["funding"]))
            except RateLimited:
                self.pause_until = time.monotonic() + 60
                log("HL 429 on ctx")
            except Exception as e:  # noqa: BLE001
                log("ctx error", type(e).__name__, str(e)[:160])
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=60 - (time.time() % 60) + 0.5)
            except asyncio.TimeoutError:
                pass

    # ---------- coverage ----------
    def coverage(self):
        ts = now_us()
        agg = {c: dict(n=0, long=0.0, short=0.0, liq10=0.0, ages=[]) for c in COINS}
        for addr, inf in self.sched.info.items():
            if not inf.get("positions"):
                continue
            age = (ts - inf["poll_ts_us"]) / 1e6
            for p in inf["positions"]:
                g = agg[p.coin]
                g["n"] += 1
                v = abs(p.position_value or 0.0)
                g["long" if p.szi > 0 else "short"] += v
                m = self.mid.get(p.coin)
                if p.liq_px and m and abs(p.liq_px / m - 1) <= 0.10:
                    g["liq10"] += v
                g["ages"].append(age)
        summ = {}
        for c, g in agg.items():
            cx = self.ctx.get(c) or {}
            oi_ntl = (cx.get("oi") or 0) * (cx.get("mark") or 0)
            med = statistics.median(g["ages"]) if g["ages"] else None
            self.store.add("coverage", (ts, c, g["n"], g["long"], g["short"], oi_ntl, g["liq10"], med))
            summ[c] = dict(n=g["n"], cov_long=round(g["long"] / oi_ntl, 3) if oi_ntl else None,
                           cov_short=round(g["short"] / oi_ntl, 3) if oi_ntl else None,
                           liq10_M=round(g["liq10"] / 1e6, 2), med_age_s=round(med) if med else None)
        tracked = sum(1 for i in self.sched.info.values() if i.get("positions"))
        log("coverage", json.dumps({"known_addr": len(self.sched.info), "addr_with_meme_pos": tracked,
                                    "per_coin": summ}))

    # ---------- housekeeping ----------
    def dir_bytes(self):
        return sum(p.stat().st_size for p in self.out.glob("*.parquet")) + \
            sum(p.stat().st_size for p in self.store.parts.glob("*.parquet"))

    async def housekeeping(self):
        last_flush, last_cov = time.monotonic(), time.monotonic() - 480
        while not self.stop.is_set():
            await asyncio.sleep(0.02)
            self.store.sweep()
            t = time.monotonic()
            if t - last_cov >= 600:
                last_cov = t
                self.coverage()
            if t - last_flush >= 60:
                last_flush = t
                rows = self.store.take()
                await asyncio.to_thread(self.store.write_parts, rows)
                await asyncio.to_thread(self.store.merge, False)
                size = self.dir_bytes()
                free = shutil.disk_usage(self.out).free / 1e9
                el_h = max((t - self.t_start) / 3600, 1e-9)
                lat = sorted(self.lat)
                lags = sorted(self.lags)
                self.lat, self.lags = [], []
                log("stats", json.dumps({**self.stats, "known_addr": len(self.sched.info),
                                         "queued": len(self.sched.key), "backlog_due": self.sched.backlog(),
                                         "weight_spent": round(self.bucket.spent),
                                         "polls_last_min": len(lat),
                                         "poll_lat_med_s": round(lat[len(lat) // 2], 3) if lat else None,
                                         "sched_lag_med_s": round(lags[len(lags) // 2], 1) if lags else None,
                                         "sched_lag_p90_s": round(lags[int(len(lags) * .9)], 1) if lags else None,
                                         "written": dict(self.store.written), "dir_MB": round(size / 1e6, 1),
                                         "MB_per_day": round(size / 1e6 / el_h * 24),
                                         "free_GB": round(free, 2)}))
                if free < self.a.min_free_gb:
                    log(f"free disk {free:.2f} GB < {self.a.min_free_gb} GB: stopping")
                    self.stop.set()

    async def timer(self):
        try:
            await asyncio.wait_for(self.stop.wait(), timeout=self.a.hours * 3600)
        except asyncio.TimeoutError:
            self.stop.set()

    async def run(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.stop.set)
        self.resume()
        log("start", json.dumps({"pid": os.getpid(), "hours": self.a.hours, "out": str(self.out),
                                 "start_ts_us": now_us(), "end_utc": utc(time.time() + self.a.hours * 3600),
                                 "coins": COINS, "poll_per_min": self.a.poll_per_min, "workers": self.a.workers,
                                 "weight_budget_per_min": self.a.poll_per_min * 2 + 20,
                                 "min_free_gb": self.a.min_free_gb,
                                 "prereg": "reports/hypotheses/liqmap_preregistration.json",
                                 "clock": "ts_us = local receive time (container clock)"}))
        tasks = [self.ws_loop(), self.ctx_loop(), self.housekeeping(), self.timer()] + \
                [self.poll_worker() for _ in range(self.a.workers)]
        running = [asyncio.create_task(t) for t in tasks]
        await self.stop.wait()
        await asyncio.sleep(1)
        for t in running:
            t.cancel()
        await asyncio.gather(*running, return_exceptions=True)
        for coin, row in list(self.store.pending.items()):
            self.store._wb(row)
        self.store.write_parts(self.store.take())
        self.store.merge(final=True)
        await self.hl.aclose()
        log("stop", json.dumps({**self.stats, "written": dict(self.store.written), "known_addr": len(self.sched.info),
                                "dir_MB": round(self.dir_bytes() / 1e6, 1)}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, default=50)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--poll-per-min", type=int, default=270, help="clearinghouseState calls per minute (weight 2 each)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--min-free-gb", type=float, default=1.5)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(a.out).free / 1e9
    if free < a.min_free_gb:
        log(f"free disk {free:.2f} GB < {a.min_free_gb} GB at start: not starting")
        return
    asyncio.run(Recorder(a, a.out).run())


if __name__ == "__main__":
    main()
