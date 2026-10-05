"""Forward paper test of the frozen H-HLLAG candidate (reports/candidates/hlanchor.md).

collect  Records live public feeds into the same schema as the Tardis parquet used in the backtest:
         Binance USDⓈ-M bookTicker (wss://fstream.binance.com) -> book_ticker (local_timestamp, bid/ask px+qty)
         Hyperliquid bbo + trades (wss://api.hyperliquid.xyz/ws) -> quotes (timestamp = HL exchange time,
         local_timestamp, bid/ask px+qty) and trades (timestamp, local_timestamp, side, price, amount).
         All timestamps are microseconds; local = this container's receive time. Hourly chunk files go to
         data/raw/web/hllag_forward/chunks/<kind>_<YYYY-MM-DD-HH>_<COIN>.parquet.
         Differences from the backtest data: HL quotes here are event-driven bbo updates (Tardis sampled ~0.5 s).
freeze   Writes reports/paper/hllag_theta40.json: frozen parameters, sha256 of hlanchor_lib.py, frozen_at.
         Refuses to overwrite.
score    Merges chunks into per-day files, runs hlanchor_lib.sim_lag with the frozen parameters on data
         received AFTER frozen_at only, and applies the bar. Refuses if hlanchor_lib.py changed.

    python scripts/research/hllag_forward.py collect --hours 1.9
    python scripts/research/hllag_forward.py freeze
    python scripts/research/hllag_forward.py score
"""
import argparse
import asyncio
import hashlib
import json
import os
import ssl
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/research"))
import pandas as pd  # noqa: E402

OUT = ROOT / "data/raw/web/hllag_forward"
CHUNKS, DAYS = OUT / "chunks", OUT / "days"
LIB = ROOT / "scripts/research/hlanchor_lib.py"
# Hyperliquid coin -> Binance futures symbol (same pairs as the backtest)
COINS = {"WIF": "WIFUSDT", "kBONK": "1000BONKUSDT", "FARTCOIN": "FARTCOINUSDT", "PUMP": "PUMPUSDT"}
# Second frozen record (reports/candidates/hllag_newcoins.md): same rule, coins it was not developed on.
NEW_COINS = {"TRUMP": "TRUMPUSDT", "SPX": "SPXUSDT"}
# Third record: the pre-registered addendum pair (reports/hypotheses/hllag_newcoins_addendum.json), pooled.
ADD_COINS = {"PENGU": "PENGUUSDT", "kSHIB": "1000SHIBUSDT"}
RECORDS = {"hllag_theta40": COINS, "hllag_theta40_newcoins": NEW_COINS, "hllag_theta40_addendum": ADD_COINS}
ALL_COINS = {**COINS, **NEW_COINS, **ADD_COINS}
PARAMS = dict(theta_bp=40.0, L_ms=300, H_s=30.0, cooldown_s=10.0, close_bp=None, info_lat_ms=300)
HL_RESTAMP_US = 175_000
# Known-bad local-clock windows dropped from every stream at scoring (gaps, never fills). See the amendment file.
#   2026-10-05 07:25:40-07:26:45 local: a 72 s test run of the collector appended a second copy of all streams.
EXCLUDE_WINDOWS_US = [(1791185140_000000, 1791185205_000000)]
BAR = dict(min_trades=50, net_gt=0.0, pf_gt=1.2, net_ex_top3_gt=0.0)


def _ssl():
    return ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))


def _now_us() -> int:
    return int(time.time() * 1_000_000)


import threading  # noqa: E402

_WRITE_LOCK = threading.Lock()


class Buffer:
    def __init__(self):
        self.rows = defaultdict(list)   # (kind, coin) -> rows
        self.hour = None

    def add(self, kind, coin, row):
        h = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
        if self.hour and h != self.hour:
            self.flush()
        self.hour = h
        self.rows[(kind, coin)].append(row)

    def flush(self):
        rows_by_key, hour = self.take()
        self.write(rows_by_key, hour)

    def take(self):
        """Detach the buffered rows (cheap, in the event loop) so writing can run in a worker thread."""
        out, self.rows = self.rows, defaultdict(list)
        return out, self.hour

    @staticmethod
    def write(rows_by_key, hour):
        with _WRITE_LOCK:                                   # hour-change flush and the worker never interleave
            Buffer._write(rows_by_key, hour)

    @staticmethod
    def _write(rows_by_key, hour):
        CHUNKS.mkdir(parents=True, exist_ok=True)
        for (kind, coin), rows in rows_by_key.items():
            if not rows:
                continue
            p = CHUNKS / f"{kind}_{hour}_{coin}.parquet"
            df = pd.DataFrame(rows)
            if p.exists():                                  # restart within the same hour: append
                df = pd.concat([pd.read_parquet(p), df], ignore_index=True)
            df.to_parquet(p)


async def binance(buf: Buffer, stop: float):
    import websockets
    rev = {v.lower(): k for k, v in ALL_COINS.items()}
    url = "wss://fstream.binance.com/stream?streams=" + "/".join(f"{s.lower()}@bookTicker" for s in ALL_COINS.values())
    while time.monotonic() < stop:
        try:
            async with websockets.connect(url, ssl=_ssl(), open_timeout=20, ping_interval=20) as ws:
                async for raw in ws:
                    if time.monotonic() >= stop:
                        return
                    d = json.loads(raw).get("data") or {}
                    coin = rev.get((d.get("s") or "").lower())
                    if coin:
                        buf.add("book_ticker", coin, dict(local_timestamp=_now_us(), bid_price=float(d["b"]),
                                                          ask_price=float(d["a"]), bid_amount=float(d["B"]),
                                                          ask_amount=float(d["A"]),
                                                          event_time_ms=int(d.get("E") or 0)))
        except Exception as e:  # noqa: BLE001
            print("binance reconnect", type(e).__name__, str(e)[:120], flush=True)
            await asyncio.sleep(3)


async def hyperliquid(buf: Buffer, stop: float):
    import websockets
    while time.monotonic() < stop:
        try:
            async with websockets.connect("wss://api.hyperliquid.xyz/ws", ssl=_ssl(), open_timeout=20,
                                          ping_interval=20) as ws:
                for c in ALL_COINS:
                    await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "bbo", "coin": c}}))
                    await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "trades", "coin": c}}))
                async for raw in ws:
                    if time.monotonic() >= stop:
                        return
                    m = json.loads(raw)
                    ch, d, now = m.get("channel"), m.get("data"), _now_us()
                    if ch == "bbo" and d and d.get("coin") in ALL_COINS and all(d.get("bbo") or [None]):
                        b, a = d["bbo"]
                        buf.add("quotes", d["coin"], dict(timestamp=int(d["time"]) * 1000, local_timestamp=now,
                                                          bid_price=float(b["px"]), ask_price=float(a["px"]),
                                                          bid_amount=float(b["sz"]), ask_amount=float(a["sz"])))
                    elif ch == "trades" and isinstance(d, list):
                        for t in d:
                            if t.get("coin") in ALL_COINS:
                                buf.add("trades", t["coin"], dict(timestamp=int(t["time"]) * 1000, local_timestamp=now,
                                                                  side="buy" if t.get("side") == "B" else "sell",
                                                                  price=float(t["px"]), amount=float(t["sz"])))
        except Exception as e:  # noqa: BLE001
            print("hyperliquid reconnect", type(e).__name__, str(e)[:120], flush=True)
            await asyncio.sleep(3)


async def flusher(buf: Buffer, stop: float):
    while time.monotonic() < stop:
        await asyncio.sleep(60)
        rows, hour = buf.take()
        await asyncio.to_thread(Buffer.write, rows, hour)   # off the event loop: no once-a-minute recording stall


async def collect(hours: float):
    buf, stop = Buffer(), time.monotonic() + hours * 3600
    await asyncio.gather(binance(buf, stop), hyperliquid(buf, stop), flusher(buf, stop))
    buf.flush()


def _sha() -> str:
    return hashlib.sha256(LIB.read_bytes()).hexdigest()


def _freeze_path(name: str) -> Path:
    return ROOT / f"reports/paper/{name}.json"


def freeze(name: str = "hllag_theta40"):
    FREEZE = _freeze_path(name)
    if FREEZE.exists():
        raise SystemExit(f"{FREEZE} exists; frozen strategies are never changed.")
    FREEZE.parent.mkdir(parents=True, exist_ok=True)
    rec = {"name": name, "module": "scripts/research/hlanchor_lib.py", "function": "sim_lag",
           "params": PARAMS, "coins": RECORDS[name], "module_sha256": _sha(), "frozen_at": time.time(),
           "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "bar": BAR,
           "unit": "round trip of $1,000 notional; pnl in USD after 4.5 bp taker fees each side",
           "source": "reports/candidates/hllag_newcoins.md (TRUMP+SPX: train PF 1.74 n=329, validation PF 1.39 n=243; only 2 coins)"
           if name.endswith("newcoins") else
           "reports/candidates/hllag_newcoins.md addendum (PENGU+kSHIB pooled: train PF 1.30 n=218, validation PF 1.40 n=90; PENGU carries it, kSHIB thin)"
           if name.endswith("addendum") else "reports/candidates/hlanchor.md (passed train PF 1.204 n=721, validation PF 1.358 n=721; fragile)",
           "caveats": ["config added after the pre-registered grid failed", "validation profit concentrated on 2025-08-01",
                       "fails at +0.5 bp cost or 800 ms latency", "forward HL quotes are event-driven bbo, not 0.5 s snapshots"]}
    FREEZE.write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec, indent=1))


def score(name: str = "hllag_theta40") -> dict:
    import hlanchor_lib as hl
    rec = json.loads(_freeze_path(name).read_text())
    if _sha() != rec["module_sha256"]:
        raise SystemExit("hlanchor_lib.py changed since freezing; scoring refused.")
    t0 = int(rec["frozen_at"] * 1_000_000)
    DAYS.mkdir(parents=True, exist_ok=True)
    import re
    days = sorted({m.group(1) for p in CHUNKS.glob("*.parquet")
                   if (m := re.search(r"_(\d{4}-\d{2}-\d{2})-\d{2}_", p.name))})
    for day in days:                                           # merge hour chunks -> day files, post-freeze only
        for kind in ("quotes", "trades", "book_ticker"):
            for coin in rec["coins"]:
                parts = sorted(CHUNKS.glob(f"{kind}_{day}-??_{coin}.parquet"))
                if not parts:
                    continue
                df = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
                df = df[df.local_timestamp >= t0]
                for a, b in EXCLUDE_WINDOWS_US:
                    df = df[(df.local_timestamp < a) | (df.local_timestamp >= b)]
                if kind in ("quotes", "trades") and len(df):
                    # Scoring amendment 1 (reports/paper/hllag_scoring_amendment.json): this container's clock is
                    # ~2.8 s behind real time, so HL exchange times cannot be compared with our local times. Re-stamp
                    # HL rows onto the local clock with the backtest's relation (Tardis receive - exchange ~ +175 ms).
                    df = df.assign(timestamp=df.local_timestamp - HL_RESTAMP_US)
                if len(df):
                    df.to_parquet(DAYS / f"{kind}_{day}_{coin}.parquet")   # all coins share the same post-freeze cut
    hl.PQ = DAYS
    trades = []
    for day in days:
        for coin in rec["coins"]:
            d = hl.load_day(coin, day)
            if d is not None:
                trades += hl.sim_lag(d, **rec["params"])
    stats = hl.bar_stats([t["pnl"] for t in trades])
    out = {"name": rec["name"], "frozen_at_utc": rec["frozen_at_utc"],
           "scored_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "days": days, **stats,
           "trades": trades}
    (ROOT / f"reports/paper/{name}_ledger.json").write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "freeze", "score"])
    ap.add_argument("--hours", type=float, default=1.9)
    ap.add_argument("--name", default="hllag_theta40", choices=sorted(RECORDS))
    a = ap.parse_args()
    if a.cmd == "collect":
        asyncio.run(collect(a.hours))
    elif a.cmd == "freeze":
        freeze(a.name)
    else:
        print(json.dumps({k: v for k, v in score(a.name).items() if k != "trades"}, indent=1))
