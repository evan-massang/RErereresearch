"""Lean forward recorder for pump.fun: decoded bonding-curve + PumpSwap events only, compact zstd parquet.

Why: pump.fun strategy tests are starved of clean tape (reports/failures/agent_cleanmig.md: recorder gaps, train
~14.6 covered hours) and the full recorder (pipeline/recorder.py: raw JSON lines, ~250 MB/h of PumpSwap alone) plus
its DuckDB load cost ~2 GB/day. This one keeps only the fields the pump.fun tests use, target <= 250 MB/day.

Public, unauthenticated Solana RPC websocket only (``logsSubscribe`` mentions program, commitment confirmed), one
connection per program; plus ``getMultipleAccounts`` on the public HTTP RPC to resolve PumpSwap pools created before
the recording started (pool -> base mint). No trading, no keys, no tweets / kolscan / launchlab / pumpportal.

Decoders are imported, not copied: ``pipeline.recorder.decode_pump_event`` (curve Trade/Create/Complete) and
``pipeline.market.decode_amm`` (PumpSwap Buy/Sell/CreatePool). The few fields those decoders drop (curve trade fee
amounts + creator, create-event reserves/creator/mayhem flag, PumpSwap fee amounts) are read here from the same bytes
at the IDL offsets the decoders already use (see the layout notes in pipeline/market.py).

Tables, data/raw/web/pumplean/<table>_<YYYY-MM-DD-HH>.parquet (UTC hour of recv_us), all amounts RAW integers
(SOL in lamports = 1e-9 SOL, pump tokens in base units = 1e-6 token):
  curve_trades     recv_us slot tx_seq ts mint user creator is_buy sol tok vsol vtok rsol rtok fee_bps fee cfee_bps cfee
  curve_creates    recv_us slot tx_seq ts mint curve user creator name symbol uri vtok vsol rtok supply is_mayhem
  curve_completes  recv_us slot tx_seq mint user
  amm_pools        recv_us slot tx_seq ts pool mint quote_mint creator coin_creator base_dec quote_dec base_in quote_in
  amm_swaps        recv_us slot tx_seq ts pool user is_buy base quote user_quote pool_base pool_quote
                   lp_bps lp_fee proto_bps proto_fee cc_bps cc_fee
  pool_map         pool mint quote_mint coin_creator resolved_us src      (pools seen in swaps, resolved via RPC)
recv_us = our receive time (container clock, microseconds). ts = on-chain unix time from the event. tx_seq = per-process
counter of log notifications (one per transaction): rows with equal (file pid, tx_seq) come from the same transaction.
Signatures are NOT kept (incompressible, ~60 B/row). pool_base/pool_quote are the PumpSwap reserves AS LOGGED (pre-trade;
see pipeline/market.py note) - post-trade reserves are derived in the loader note.

Gaps are declared, never silent: data/raw/web/pumplean/events.jsonl gets 'start', 'connect', 'disconnect' (with the
error and the reconnect backoff), 'minute' (per-stream notification + decoded row counts, last slot, and silent=true
when a stream got nothing that minute), 'chunk', 'disk_guard', 'stop'. A stream with no message for 45 s is treated as
dead and reconnected; backoff 1, 2, 4 ... 60 s, reset after a connection that lived >= 120 s.
Disk guard: stop when free disk < --min-free-gb (1.5).

    python scripts/research/pumplean_recorder.py --hours 0.08 --out <scratch dir>          # test
    nohup python scripts/research/pumplean_recorder.py --hours 72 >> data/raw/web/pumplean/recorder.log 2>&1 &
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import signal
import struct
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import base58  # noqa: E402
import httpx  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import websockets  # noqa: E402

from pipeline.market import _EV as AMM_EV, decode_amm  # noqa: E402
from pipeline.recorder import (PUMP_PROGRAM, PUMPSWAP_PROGRAM, _COMPLETE, _CREATE, _TRADE, _ssl,  # noqa: E402
                               decode_pump_event)

WS_URL = os.environ.get("SOLANA_WS_URL", "wss://api.mainnet-beta.solana.com")
HTTP_URL = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
OUT = ROOT / "data/raw/web/pumplean"
_PUMP_DISCS = {_TRADE, _CREATE, _COMPLETE}
_AMM_DISCS = set(AMM_EV)
_POOL_DISC = next(k for k, v in AMM_EV.items() if v == "CreatePoolEvent")

I64, U64, U16, U8, S, B = pa.int64(), pa.uint64(), pa.uint16(), pa.uint8(), pa.string(), pa.bool_()
HEAD = [("recv_us", I64), ("slot", I64), ("tx_seq", I64)]
SCHEMAS = {
    "curve_trades": pa.schema(HEAD + [("ts", I64), ("mint", S), ("user", S), ("creator", S), ("is_buy", B),
                                      ("sol", U64), ("tok", U64), ("vsol", U64), ("vtok", U64), ("rsol", U64),
                                      ("rtok", U64), ("fee_bps", U16), ("fee", U64), ("cfee_bps", U16),
                                      ("cfee", U64)]),
    "curve_creates": pa.schema(HEAD + [("ts", I64), ("mint", S), ("curve", S), ("user", S), ("creator", S),
                                       ("name", S), ("symbol", S), ("uri", S), ("vtok", U64), ("vsol", U64),
                                       ("rtok", U64), ("supply", U64), ("is_mayhem", B)]),
    "curve_completes": pa.schema(HEAD + [("mint", S), ("user", S)]),
    "amm_pools": pa.schema(HEAD + [("ts", I64), ("pool", S), ("mint", S), ("quote_mint", S), ("creator", S),
                                   ("coin_creator", S), ("base_dec", U8), ("quote_dec", U8), ("base_in", U64),
                                   ("quote_in", U64)]),
    "amm_swaps": pa.schema(HEAD + [("ts", I64), ("pool", S), ("user", S), ("is_buy", B), ("base", U64),
                                   ("quote", U64), ("user_quote", U64), ("pool_base", U64), ("pool_quote", U64),
                                   ("lp_bps", U16), ("lp_fee", U64), ("proto_bps", U16), ("proto_fee", U64),
                                   ("cc_bps", U16), ("cc_fee", U64)]),
    "amm_bars": pa.schema([("recv_us", I64), ("pool", S), ("n", pa.uint32()), ("n_buy", pa.uint32()),
                           ("n_users", pa.uint32()), ("base_buy", U64), ("base_sell", U64), ("quote_buy", U64),
                           ("quote_sell", U64), ("first_slot", I64), ("last_slot", I64),
                           ("open_pool_base", U64), ("open_pool_quote", U64), ("last_pool_base", U64),
                           ("last_pool_quote", U64), ("last_is_buy", B), ("last_base", U64), ("last_quote", U64)]),
    "pool_map": pa.schema([("pool", S), ("mint", S), ("quote_mint", S), ("coin_creator", S), ("resolved_us", I64),
                           ("src", S), ("created_us", I64)]),
}
SORT = {"curve_trades": "mint", "curve_creates": "mint", "curve_completes": "mint", "amm_pools": "pool",
        "amm_swaps": "pool", "amm_bars": "pool", "pool_map": "pool"}


def now_us() -> int:
    return time.time_ns() // 1000


def utc(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(*a) -> None:
    print(utc(), *a, flush=True)


def hour_of(ts_us: int) -> str:
    return datetime.fromtimestamp(ts_us / 1e6, timezone.utc).strftime("%Y-%m-%d-%H")


def _pkb(b: bytes, o: int) -> str:
    return base58.b58encode(b[o:o + 32]).decode()


# ------------------------------------------------------------------------------------------------ decoding
def curve_rows(data: str, head: tuple) -> tuple[str, tuple] | None:
    """One curve 'Program data:' line -> (table, row) or None. Core fields from decode_pump_event."""
    ev = decode_pump_event(data)
    if ev is None:
        return None
    b = base64.b64decode(data)
    if ev["e"] == "trade":
        if ev.get("raw"):                       # non-SOL quoted curve (vsol == 0): not a pump.fun SOL curve, skip
            return None
        # raw integers read from the same offsets decode_pump_event uses (no float round trip): sol, tok @40;
        # is_buy @56; user @57; ts, vsol, vtok, rsol, rtok @89; fee_recipient @129; fee_bps @161, fee @169,
        # creator @177, creator_fee_bps @209, creator_fee @217
        sol, tok = struct.unpack_from("<QQ", b, 40)
        vs, vt, rs, rt = struct.unpack_from("<QQQQ", b, 97)
        fee = cfee = creator = None
        if len(b) >= 225:
            fee = struct.unpack_from("<Q", b, 169)[0]
            creator = _pkb(b, 177)
            cfee = struct.unpack_from("<Q", b, 217)[0]
        return "curve_trades", head + (ev["ts"], ev["mint"], ev["user"], creator, ev["buy"], sol, tok, vs, vt, rs, rt,
                                       ev["fee_bps"], fee, ev["cfee_bps"], cfee)
    if ev["e"] == "create":
        # after name/symbol/uri/mint/curve/user: creator pk, timestamp i64, virtual token/sol, real token, supply
        # u64, token_program pk, is_mayhem_mode bool (IDL order). Offsets found by walking the strings again.
        o = 8
        for _ in range(3):
            (n,) = struct.unpack_from("<I", b, o)
            o += 4 + n
        o += 96                                                   # mint, curve, user
        creator = ts = vtok = vsol = rtok = supply = mayhem = None
        if len(b) >= o + 72:
            creator = _pkb(b, o)
            ts, vtok, vsol, rtok, supply = struct.unpack_from("<qQQQQ", b, o + 32)
            if len(b) >= o + 72 + 32 + 1:
                mayhem = bool(b[o + 104])
        return "curve_creates", head + (ts, ev["mint"], ev["curve"], ev["user"], creator, ev["name"][:64],
                                        ev["symbol"][:32], ev["uri"][:200], vtok, vsol, rtok, supply, mayhem)
    if ev["e"] == "complete":
        return "curve_completes", head + (ev["mint"], ev["user"])
    return None


def amm_rows(data: str, head: tuple) -> tuple[str, tuple] | None:
    """One PumpSwap 'Program data:' line -> (table, row) or None. Core fields from pipeline.market.decode_amm."""
    try:
        if base64.b64decode(data[:12])[:8] not in _AMM_DISCS:
            return None
    except ValueError:
        return None
    ev = decode_amm({"data": data})
    if ev is None:
        return None
    b = base64.b64decode(data)
    if ev["e"] == "pool":
        coin_creator = _pkb(b, 301) if len(b) >= 333 else None   # after pool@173, lp_mint, user base/quote atas
        return "amm_pools", head + (ev["ts"], ev["pool"], ev["mint"], ev["quote_mint"], ev["creator"], coin_creator,
                                    ev["base_dec"], ev["quote_dec"], ev["base_in"], ev["quote_in"])
    u = struct.unpack_from("<14Q", b, 8)
    return "amm_swaps", head + (ev["ts"], ev["pool"], ev["user"], ev["buy"], ev["base"], ev["quote"],
                                ev["user_quote"], ev["pool_base"], ev["pool_quote"], ev["lp_bps"], u[9],
                                ev["protocol_bps"], u[11], ev["creator_bps"], struct.unpack_from("<Q", b, 352)[0])


# ------------------------------------------------------------------------------------------------ storage
class Store:
    def __init__(self, out: Path):
        self.out, self.parts = out, out / "parts"
        self.parts.mkdir(parents=True, exist_ok=True)
        self.rows: dict[str, list] = defaultdict(list)
        self.written: dict[str, int] = defaultdict(int)
        self.dropped: dict[str, int] = defaultdict(int)
        self.seq = 0
        self.pid = os.getpid()

    def add(self, table: str, row: tuple) -> None:
        self.rows[table].append(row)

    def take(self) -> dict:
        """Swap the buffers (call on the event-loop thread, so no row is appended to a list being written)."""
        rows, self.rows = self.rows, defaultdict(list)
        return rows

    def flush(self, rows: dict | None = None) -> None:
        rows = self.take() if rows is None else rows
        for table, rr in rows.items():
            if not rr:
                continue
            by_hour = defaultdict(list)
            for r in rr:
                by_hour[hour_of(r[0] if table != "pool_map" else r[4])].append(r)
            schema = SCHEMAS[table]
            for h, part in by_hour.items():
                cols = list(zip(*part))
                try:
                    t = pa.Table.from_arrays([pa.array(c, type=f.type) for c, f in zip(cols, schema)], schema=schema)
                except (pa.ArrowException, OverflowError, TypeError) as e:   # never lose the whole part to one row
                    good = []
                    for r in part:
                        try:
                            pa.Table.from_arrays([pa.array([v], type=f.type) for v, f in zip(r, schema)], schema=schema)
                            good.append(r)
                        except (pa.ArrowException, OverflowError, TypeError):
                            self.dropped[table] += 1
                    log("flush", table, "dropped bad rows", len(part) - len(good), type(e).__name__)
                    if not good:
                        continue
                    cols = list(zip(*good))
                    t = pa.Table.from_arrays([pa.array(c, type=f.type) for c, f in zip(cols, schema)], schema=schema)
                self.seq += 1
                pq.write_table(t, self.parts / f"{table}_{h}_p{self.pid}x{self.seq:07d}.parquet", compression="zstd")
                self.written[table] += len(part)

    def merge(self, final: bool) -> list[dict]:
        cur, done = hour_of(now_us()), []
        groups = defaultdict(list)
        for p in self.parts.glob("*_p*.parquet"):
            table, h = p.name.rsplit("_p", 1)[0].rsplit("_", 1)
            groups[(table, h)].append(p)
        for (table, h), ps in groups.items():
            if h >= cur and not final:
                continue
            dst = self.out / f"{table}_{h}.parquet"
            srcs = ([dst] if dst.exists() else []) + sorted(ps)
            t = pa.concat_tables([pq.read_table(s) for s in srcs])
            keys = [(SORT[table], "ascending")] + {"pool_map": [], "amm_bars": [("recv_us", "ascending")]}.get(
                table, [("slot", "ascending"), ("tx_seq", "ascending")])
            t = t.sort_by(keys)
            ints = [f.name for f in t.schema if pa.types.is_integer(f.type) and f.type.bit_width == 64]

            tmp = dst.with_suffix(".tmp")
            pq.write_table(t, tmp, compression="zstd", compression_level=15, row_group_size=2_000_000,
                           use_dictionary=[f.name for f in t.schema if f.name not in ints],
                           column_encoding={c: "DELTA_BINARY_PACKED" for c in ints})
            tmp.replace(dst)
            for p in ps:
                p.unlink()
            done.append({"table": table, "hour": h, "rows": t.num_rows, "bytes": dst.stat().st_size})
        return done


def dir_bytes(out: Path) -> int:
    return sum(p.stat().st_size for p in out.glob("*.parquet")) + sum(p.stat().st_size for p in
                                                                      (out / "parts").glob("*.parquet"))


class Events:
    def __init__(self, path: Path):
        self.fh = open(path, "a")

    def __call__(self, kind: str, **kw) -> None:
        self.fh.write(json.dumps({"t": utc(), "recv_us": now_us(), "pid": os.getpid(), "ev": kind, **kw},
                                 separators=(",", ":")) + "\n")
        self.fh.flush()


# ------------------------------------------------------------------------------------------------ streams
class Recorder:
    def __init__(self, out: Path, min_free_gb: float, young_days: float):
        self.out, self.min_free_gb, self.young_days = out, min_free_gb, young_days
        self.store = Store(out)
        self.ev = Events(out / "events.jsonl")
        self.stop = asyncio.Event()
        self.tx_seq = 0
        self.minute: dict[str, dict] = {n: defaultdict(int) for n in ("curve", "amm")}
        self.last_slot: dict[str, int] = {}
        self.connected: dict[str, bool] = {"curve": False, "amm": False}
        self.known_pools: set[str] = set()
        self.unresolved: dict[str, None] = {}        # insertion-ordered set
        self.young: set[str] = set()                 # pools created < young_days ago: every swap kept
        self.bar_minute = 0
        self.bars: dict[str, list] = {}              # other pools: 1-minute aggregates

    def seed_young(self) -> dict:
        """Pools whose CreatePoolEvent is already on file (old recorder's market.duckdb amm_pools, earlier pumplean
        amm_pools chunks) and younger than young_days. Pools created in old-recorder gaps are NOT known: their
        swaps only reach amm_bars (declared in the start event)."""
        import duckdb
        cut = time.time() - self.young_days * 86400
        n = {}
        try:
            con = duckdb.connect(str(ROOT / "data/market.duckdb"), read_only=True)
            rows = con.execute("SELECT pool, mint, creator, recv FROM amm_pools WHERE recv >= ?", [cut]).fetchall()
            con.close()
            for pool, mint, creator, recv in rows:
                self.young.add(pool)
                self.store.add("pool_map", (pool, mint, None, None, now_us(), "seed_market_duckdb", int(recv * 1e6)))
            n["market_duckdb"] = len(rows)
        except Exception as e:  # noqa: BLE001
            n["market_duckdb_error"] = f"{type(e).__name__}: {e}"[:200]
        try:
            files = sorted(self.out.glob("amm_pools_*.parquet"))
            if files:
                import duckdb as _d
                rows = _d.sql(f"SELECT pool, recv_us FROM read_parquet({[str(f) for f in files]}) "
                              f"WHERE recv_us >= {int(cut * 1e6)}").fetchall()
                self.young.update(r[0] for r in rows)
                n["pumplean_chunks"] = len(rows)
        except Exception as e:  # noqa: BLE001
            n["pumplean_error"] = f"{type(e).__name__}: {e}"[:200]
        self.known_pools.update(self.young)
        n["young_pools"] = len(self.young)
        return n

    def flush_bars(self) -> None:
        m = self.bar_minute * 60_000_000
        for pool, b in self.bars.items():
            self.store.add("amm_bars", (m, pool, b[0], b[1], len(b[2]), b[3], b[4], b[5], b[6], b[7], b[8], b[9],
                                        b[10], b[11], b[12], b[13], b[14], b[15]))
        self.minute["amm"]["bar_rows"] += len(self.bars)
        self.bars = {}

    def bar(self, row: tuple) -> None:
        # row = amm_swaps layout: recv_us slot tx_seq ts pool user is_buy base quote user_quote pool_base pool_quote ..
        minute = row[0] // 60_000_000
        if minute != self.bar_minute:
            if self.bars:
                self.flush_bars()
            self.bar_minute = minute
        b = self.bars.get(row[4])
        if b is None:
            b = self.bars[row[4]] = [0, 0, set(), 0, 0, 0, 0, row[1], row[1], row[10], row[11], 0, 0, False, 0, 0]
        b[0] += 1
        b[2].add(row[5])
        if row[6]:
            b[1] += 1
            b[3] += row[7]
            b[5] += row[8]
        else:
            b[4] += row[7]
            b[6] += row[8]
        b[8] = row[1]
        b[11], b[12], b[13], b[14], b[15] = row[10], row[11], row[6], row[7], row[8]

    def on_msg(self, name: str, raw: str | bytes) -> None:
        m = json.loads(raw)
        res = (m.get("params") or {}).get("result") or {}
        v = res.get("value") or {}
        c = self.minute[name]
        c["msgs"] += 1
        if not v:
            return
        if v.get("err") is not None:
            c["failed_tx"] += 1
            return
        slot = (res.get("context") or {}).get("slot")
        self.last_slot[name] = slot
        self.tx_seq += 1
        head = (now_us(), slot, self.tx_seq)
        dec = curve_rows if name == "curve" else amm_rows
        for line in v.get("logs") or ():
            if not line.startswith("Program data: "):
                continue
            out = dec(line[14:], head)
            if out is None:
                continue
            table, row = out
            if table == "amm_swaps":
                p = row[4]
                if p not in self.young:
                    self.bar(row)
                    c["swaps_to_bars"] += 1
                    if p not in self.known_pools:
                        self.known_pools.add(p)
                        self.unresolved[p] = None
                    continue
            elif table == "amm_pools":
                self.young.add(row[4])
                self.known_pools.add(row[4])
                self.store.add("pool_map", (row[4], row[5], row[6], row[8], head[0], "create_event", head[0]))
            self.store.add(table, row)
            c[table] += 1

    async def stream(self, name: str, program: str) -> None:
        backoff = 1.0
        while not self.stop.is_set():
            t_conn = time.monotonic()
            try:
                async with websockets.connect(WS_URL, ssl=_ssl(), open_timeout=20, ping_interval=20, ping_timeout=30,
                                              max_size=2 ** 24) as ws:
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
                                              "params": [{"mentions": [program]}, {"commitment": "confirmed"}]}))
                    self.connected[name] = True
                    self.ev("connect", stream=name, program=program, url=WS_URL)
                    log(name, "connected")
                    while not self.stop.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=45)
                        except asyncio.TimeoutError:
                            raise RuntimeError("no message for 45 s")
                        self.on_msg(name, raw)
            except Exception as e:  # noqa: BLE001 - keep recording through network hiccups, but declare the gap
                self.connected[name] = False
                if self.stop.is_set():
                    break
                lived = time.monotonic() - t_conn
                if lived >= 120:
                    backoff = 1.0
                self.ev("disconnect", stream=name, error=f"{type(e).__name__}: {e}"[:300], lived_s=round(lived, 1),
                        last_slot=self.last_slot.get(name), backoff_s=backoff)
                log(name, "disconnect", type(e).__name__, str(e)[:160], f"backoff {backoff}s")
                try:
                    await asyncio.wait_for(self.stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 60.0)
        self.connected[name] = False

    async def resolver(self) -> None:
        """pool -> base mint for PumpSwap pools first seen in a swap (created before we started), via public RPC
        getMultipleAccounts (Pool account: disc 8, bump u8, index u16, creator@11, base_mint@43, quote_mint@75,
        lp_mint@107, base/quote token accounts, lp_supply u64@203, coin_creator@211). Rate: <= 1 call / 2 s."""
        verify = os.environ.get("SSL_CERT_FILE") or True
        async with httpx.AsyncClient(timeout=20, verify=verify) as client:
            while not self.stop.is_set():
                try:
                    await asyncio.wait_for(self.stop.wait(), timeout=2)
                    break
                except asyncio.TimeoutError:
                    pass
                batch = list(self.unresolved)[:100]
                if not batch:
                    continue
                try:
                    r = await client.post(HTTP_URL, json={"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts",
                                                          "params": [batch, {"encoding": "base64"}]})
                    if r.status_code == 429:
                        await asyncio.sleep(10)
                        continue
                    vals = r.json()["result"]["value"]
                except Exception as e:  # noqa: BLE001
                    self.minute["amm"]["resolver_errors"] += 1
                    log("resolver", type(e).__name__, str(e)[:120])
                    await asyncio.sleep(5)
                    continue
                t = now_us()
                for p, acc in zip(batch, vals):
                    self.unresolved.pop(p, None)
                    if not acc:
                        self.store.add("pool_map", (p, None, None, None, t, "rpc_missing", None))
                        continue
                    b = base64.b64decode(acc["data"][0])
                    if len(b) < 243 or acc.get("owner") != PUMPSWAP_PROGRAM:
                        self.store.add("pool_map", (p, None, None, None, t, "rpc_unparsed", None))
                        continue
                    self.store.add("pool_map", (p, _pkb(b, 43), _pkb(b, 75), _pkb(b, 211), t, "rpc_account", None))
                    self.minute["amm"]["pools_resolved"] += 1

    async def housekeeping(self, t_start: float) -> None:
        next_min = (int(time.time()) // 60 + 1) * 60
        last_flush = time.monotonic()
        while not self.stop.is_set():
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=max(next_min - time.time(), 0.1))
                break
            except asyncio.TimeoutError:
                pass
            minute_start = next_min - 60
            next_min += 60
            snap = {n: dict(c) for n, c in self.minute.items()}
            for c in self.minute.values():
                c.clear()
            silent = [n for n, c in snap.items() if not c.get("msgs")]
            self.ev("minute", minute=utc(minute_start), counts=snap, last_slot=dict(self.last_slot),
                    connected=dict(self.connected), silent=silent or None, unresolved_pools=len(self.unresolved))
            if time.monotonic() - last_flush >= 120:
                last_flush = time.monotonic()
                await asyncio.to_thread(self.store.flush, self.store.take())
                for d in await asyncio.to_thread(self.store.merge, False):
                    self.ev("chunk", **d)
                size = dir_bytes(self.out)
                free = shutil.disk_usage(self.out).free / 1e9
                el_h = max((time.monotonic() - t_start) / 3600, 1e-9)
                log("stats written", dict(self.store.written), f"dir_MB {size / 1e6:.1f}",
                    f"MB_per_h_since_start {size / 1e6 / el_h:.1f} free_GB {free:.2f}",
                    f"unresolved_pools {len(self.unresolved)}")
                if free < self.min_free_gb:
                    self.ev("disk_guard", free_gb=round(free, 2), min_free_gb=self.min_free_gb)
                    log(f"free disk {free:.2f} GB < {self.min_free_gb} GB: stopping")
                    self.stop.set()

    async def run(self, hours: float) -> None:
        free = shutil.disk_usage(self.out).free / 1e9
        if free < self.min_free_gb:
            self.ev("disk_guard", free_gb=round(free, 2), min_free_gb=self.min_free_gb, at="start")
            log(f"free disk {free:.2f} GB < {self.min_free_gb} GB at start: not starting")
            return
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.stop.set)
        t_start = time.monotonic()
        seed = self.seed_young()
        meta = {"pid": os.getpid(), "hours": hours, "out": str(self.out), "ws": WS_URL, "http": HTTP_URL,
                "min_free_gb": self.min_free_gb, "young_days": self.young_days, "seed": seed,
                "start_ts_us": now_us(), "end_utc": utc(time.time() + hours * 3600)}
        self.ev("start", **meta)
        log("start", json.dumps(meta))

        async def timer():
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=hours * 3600)
            except asyncio.TimeoutError:
                self.stop.set()

        tasks = [asyncio.create_task(t) for t in (self.stream("curve", PUMP_PROGRAM),
                                                   self.stream("amm", PUMPSWAP_PROGRAM),
                                                   self.resolver(), self.housekeeping(t_start), timer())]
        await self.stop.wait()
        await asyncio.sleep(1)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.bars:
            self.flush_bars()
        self.store.flush()
        for d in self.store.merge(final=True):
            self.ev("chunk", **d)
        self.ev("stop", written=dict(self.store.written), dir_bytes=dir_bytes(self.out),
                hours=round((time.monotonic() - t_start) / 3600, 4))
        log("stop", json.dumps({"written": dict(self.store.written)}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=72.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--min-free-gb", type=float, default=1.5)
    ap.add_argument("--young-days", type=float, default=7.0, help="keep every swap of pools created < this ago")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    asyncio.run(Recorder(a.out, a.min_free_gb, a.young_days).run(a.hours))


if __name__ == "__main__":
    main()
