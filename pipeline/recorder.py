"""Live recorder: tracked traders' trades + every trade on the tokens they touch.

Two public, unauthenticated feeds:

* kolscan SSE stream  (https://kolscan-api.pump.fun/api/v1/stream)
  every swap by the wallets kolscan tracks, as they happen.
* Solana RPC websocket ``logsSubscribe``: every pump.fun bonding-curve
  TradeEvent / CreateEvent / CompleteEvent (decoded, with reserves) and the raw
  events of the PumpSwap AMM (where tokens trade after graduating). This is the
  whole market tape, so tokens traders *skipped* are recorded too.
* PumpPortal websocket (free part): new-token and migration events.
  (Per-token trade subscriptions there need a funded API key.)

* X-post snapshots (``tweet_snaps`` feed): for each new launch whose metadata links an X post, the post's
  public counters (views, likes, reposts, replies, quotes, bookmarks) via the fxtwitter mirror, fetched as soon
  as the metadata is readable and again ~60 s later, each stamped with its own fetch time. These are the
  numbers a trader watching the post sees at that moment, so they are point-in-time by construction.

Raw messages are appended as JSON lines with our own receive time, so the
feed latency itself is measurable. Files rotate hourly under
data/raw/streams/<feed>/YYYYMMDD_HH_<pid>.jsonl.gz. Run:

    python -m pipeline.recorder --hours 8
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import gzip
import hashlib
import json
import os
import re
import ssl
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

import base58
import httpx
import websockets

from . import config

KOLSCAN_STREAM = "https://kolscan-api.pump.fun/api/v1/stream"
PUMPPORTAL_WS = "wss://pumpportal.fun/api/data"
WSOL = "So11111111111111111111111111111111111111112"
PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMPSWAP_PROGRAM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"


def _disc(name: str) -> bytes:
    return hashlib.sha256(f"event:{name}".encode()).digest()[:8]


_TRADE, _CREATE, _COMPLETE = _disc("TradeEvent"), _disc("CreateEvent"), _disc("CompleteEvent")


def _pk(b: bytes, o: int) -> tuple[str, int]:
    return base58.b58encode(b[o:o + 32]).decode(), o + 32


def _str(b: bytes, o: int) -> tuple[str, int]:
    (n,) = struct.unpack_from("<I", b, o)
    return b[o + 4:o + 4 + n].decode("utf-8", "replace"), o + 4 + n


def decode_pump_event(data_b64: str) -> dict | None:
    """Decode a pump.fun bonding-curve Anchor event from a 'Program data:' log line.

    Token amounts use pump.fun's 6 decimals; SOL amounts are converted from lamports.
    Returns None for events we don't use or can't parse.
    """
    try:
        b = base64.b64decode(data_b64)
    except ValueError:
        return None
    d = b[:8]
    try:
        if d == _TRADE:
            mint, o = _pk(b, 8)
            sol, tok = struct.unpack_from("<QQ", b, o)
            is_buy = b[o + 16]
            user, o = _pk(b, o + 17)
            ts, vs, vt, rs, rt = struct.unpack_from("<qQQQQ", b, o)
            o += 40 + 32                                      # skip reserves + fee_recipient
            fee_bps = cfee_bps = None
            if len(b) >= o + 16 + 32 + 16:
                fee_bps, _fee = struct.unpack_from("<QQ", b, o)
                cfee_bps, _cfee = struct.unpack_from("<QQ", b, o + 48)
            row = {"e": "trade", "mint": mint, "user": user, "buy": bool(is_buy), "sol": sol / 1e9,
                   "tok": tok / 1e6, "ts": ts, "vsol": vs / 1e9, "vtok": vt / 1e6, "rsol": rs / 1e9,
                   "rtok": rt / 1e6, "fee_bps": fee_bps, "cfee_bps": cfee_bps}
            if vs == 0:      # non-SOL quote (e.g. USDC-paired curve): keep raw bytes, decode later
                row["raw"] = data_b64
            return row
        if d == _CREATE:
            name, o = _str(b, 8)
            symbol, o = _str(b, o)
            uri, o = _str(b, o)
            mint, o = _pk(b, o)
            curve, o = _pk(b, o)
            user, o = _pk(b, o)
            return {"e": "create", "mint": mint, "name": name, "symbol": symbol, "uri": uri, "curve": curve,
                    "user": user, "raw": data_b64}
        if d == _COMPLETE:
            user, o = _pk(b, 8)
            mint, o = _pk(b, o)
            return {"e": "complete", "mint": mint, "user": user}
    except (struct.error, IndexError, UnicodeDecodeError):
        return None
    return None


class Sink:
    def __init__(self, feed: str):
        self.name = feed
        self.dir = config.path("raw_streams", feed)
        self._hour = None
        self._fh = None
        self.count = 0

    def write(self, obj: dict) -> None:
        hour = datetime.now(timezone.utc).strftime("%Y%m%d_%H")
        if hour != self._hour:
            if self._fh:
                self._fh.close()
            # one file per process and hour: a killed process can leave a truncated gzip member,
            # and nothing must ever be appended after one.
            self._fh = gzip.open(self.dir / f"{hour}_{os.getpid()}.jsonl.gz", "at", compresslevel=3)
            self._hour = hour
        self._fh.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self.count += 1
        if self.count % 200 == 0:
            self._fh.flush()

    def close(self) -> None:
        if self._fh:
            self._fh.close()


def _ssl() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))


class Recorder:
    def __init__(self, token_watch_s: float = 3600.0, max_tokens: int = 400):
        self.kol = Sink("kolscan")
        self.pp = Sink("pumpportal")
        self.tw = Sink("tweet_snaps")
        self.new_tokens: asyncio.Queue[dict] = asyncio.Queue(maxsize=2000)
        self.pump = Sink("pump_curve")
        self.amm = Sink("pumpswap_raw")
        self.token_watch_s = token_watch_s
        self.max_tokens = max_tokens
        self.watched: dict[str, float] = {}         # mint -> watch until (monotonic)
        self.pending_subs: asyncio.Queue[str] = asyncio.Queue()
        self.stop_at = 0.0
        self.status = {"kolscan_msgs": 0, "pumpportal_msgs": 0, "reconnects_kolscan": 0, "reconnects_pp": 0,
                       "tweet_snaps": 0, "tweet_snap_errors": 0}

    def _watch(self, mint: str) -> None:
        if not mint or mint == WSOL:
            return
        now = time.monotonic()
        if mint not in self.watched:
            self.pending_subs.put_nowait(mint)
        self.watched[mint] = now + self.token_watch_s

    async def kolscan(self) -> None:
        verify = os.environ.get("SSL_CERT_FILE") or True
        while time.monotonic() < self.stop_at:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=120), verify=verify) as client:
                    async with client.stream("GET", KOLSCAN_STREAM, headers={"accept": "text/event-stream"}) as r:
                        async for line in r.aiter_lines():
                            if time.monotonic() >= self.stop_at:
                                return
                            if not line.startswith("data:"):
                                continue
                            try:
                                msg = json.loads(line[5:].strip())
                            except ValueError:
                                continue
                            self.kol.write({"recv": time.time(), "msg": msg})
                            self.status["kolscan_msgs"] += 1
                            for k in ("in_token_address", "out_token_address"):
                                self._watch(msg.get(k) or "")
            except Exception as e:  # noqa: BLE001 — keep recording through network hiccups
                self.status["reconnects_kolscan"] += 1
                self.kol.write({"recv": time.time(), "error": f"{type(e).__name__}: {e}"[:300]})
                await asyncio.sleep(3)

    async def pumpportal(self) -> None:
        while time.monotonic() < self.stop_at:
            try:
                async with websockets.connect(PUMPPORTAL_WS, ssl=_ssl(), open_timeout=20, ping_interval=20,
                                              max_size=2 ** 22) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    await ws.send(json.dumps({"method": "subscribeMigration"}))
                    async for raw in ws:
                        if time.monotonic() >= self.stop_at:
                            return
                        msg, now = json.loads(raw), time.time()
                        self.pp.write({"recv": now, "msg": msg})
                        self.status["pumpportal_msgs"] += 1
                        if msg.get("txType") == "create" and msg.get("uri") and not self.new_tokens.full():
                            self.new_tokens.put_nowait({"mint": msg.get("mint"), "uri": msg["uri"], "recv": now})
            except Exception as e:  # noqa: BLE001
                self.status["reconnects_pp"] += 1
                self.pp.write({"recv": time.time(), "error": f"{type(e).__name__}: {e}"[:300]})
                await asyncio.sleep(3)

    async def chain_logs(self, program: str, sink: "Sink", decode: bool) -> None:
        url = os.environ.get("SOLANA_WS_URL", "wss://api.mainnet-beta.solana.com")
        key = f"chain_{sink.name}"
        while time.monotonic() < self.stop_at:
            try:
                async with websockets.connect(url, ssl=_ssl(), open_timeout=20, ping_interval=20,
                                              max_size=2 ** 24) as ws:
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
                                              "params": [{"mentions": [program]}, {"commitment": "confirmed"}]}))
                    async for raw in ws:
                        if time.monotonic() >= self.stop_at:
                            return
                        m = json.loads(raw)
                        res = (m.get("params") or {}).get("result") or {}
                        v = res.get("value") or {}
                        if not v or v.get("err") is not None:
                            continue
                        recv = time.time()
                        slot = (res.get("context") or {}).get("slot")
                        for line in v.get("logs") or []:
                            if not line.startswith("Program data: "):
                                continue
                            data = line[14:]
                            row = {"recv": recv, "slot": slot, "sig": v["signature"]}
                            ev = decode_pump_event(data) if decode else None
                            if ev is not None:
                                row.update(ev)
                            elif decode:
                                continue                      # other pump events we don't use
                            else:
                                row["data"] = data
                            sink.write(row)
                            self.status[key] = self.status.get(key, 0) + 1
                            if ev and ev.get("e") == "trade" and ev["mint"] in self.watched:
                                self.status["watched_trades"] = self.status.get("watched_trades", 0) + 1
            except Exception as e:  # noqa: BLE001
                self.status[f"reconnects_{sink.name}"] = self.status.get(f"reconnects_{sink.name}", 0) + 1
                sink.write({"recv": time.time(), "error": f"{type(e).__name__}: {e}"[:300]})
                await asyncio.sleep(3)

    async def new_token_feed(self) -> None:
        """PumpPortal create events into the snapshot queue only (``--tweets-only``; no raw sink)."""
        while time.monotonic() < self.stop_at:
            try:
                async with websockets.connect(PUMPPORTAL_WS, ssl=_ssl(), open_timeout=20, ping_interval=20) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    async for raw in ws:
                        if time.monotonic() >= self.stop_at:
                            return
                        msg = json.loads(raw)
                        if msg.get("txType") == "create" and msg.get("uri") and not self.new_tokens.full():
                            self.new_tokens.put_nowait({"mint": msg.get("mint"), "uri": msg["uri"], "recv": time.time()})
            except Exception:  # noqa: BLE001
                self.status["reconnects_pp"] += 1
                await asyncio.sleep(3)

    async def run_tweets_only(self, hours: float) -> None:
        self.stop_at = time.monotonic() + hours * 3600
        await asyncio.gather(self.new_token_feed(), self.tweet_snaps())
        self.tw.close()

    async def tweet_snaps(self, workers: int = 12, second_after_s: float = 60.0) -> None:
        """Snapshot the X post linked by each new launch: at once, and again ~second_after_s later."""
        import httpx
        rx = re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/status/(\d+)")

        def meta_urls(uri: str) -> list[str]:
            if "/ipfs/" in uri:
                cid = uri.split("/ipfs/")[1]
                return [f"https://pump.mypinata.cloud/ipfs/{cid}", f"https://gateway.pinata.cloud/ipfs/{cid}"]
            return [uri]

        async def snap(client, tok: dict, handle: str, sid: str, k: int) -> None:
            t0 = time.time()
            try:
                r = await client.get(f"https://api.fxtwitter.com/{handle}/status/{sid}", timeout=10)
                t = (r.json().get("tweet") or {}) if r.status_code == 200 else {}
                a = t.get("author") or {}
                self.tw.write({"recv": time.time(), "fetch_start": t0, "mint": tok["mint"], "launch_recv": tok["recv"],
                               "snap": k, "status": sid, "handle": handle, "http": r.status_code,
                               "created_timestamp": t.get("created_timestamp"), "views": t.get("views"),
                               "likes": t.get("likes"), "retweets": t.get("retweets"), "replies": t.get("replies"),
                               "quotes": t.get("quotes"), "bookmarks": t.get("bookmarks"),
                               "followers": a.get("followers"), "text": (t.get("text") or "")[:280] if k == 0 else None})
                self.status["tweet_snaps"] += 1
            except Exception as e:  # noqa: BLE001
                self.status["tweet_snap_errors"] += 1
                self.tw.write({"recv": time.time(), "mint": tok["mint"], "snap": k, "error": f"{type(e).__name__}: {e}"[:200]})

        async def worker(client) -> None:
            while time.monotonic() < self.stop_at:
                try:
                    tok = await asyncio.wait_for(self.new_tokens.get(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                md = None
                for u in meta_urls(tok["uri"]):
                    try:
                        r = await client.get(u, timeout=8, follow_redirects=True)
                        if r.status_code == 200:
                            md = r.json()
                            break
                    except Exception:  # noqa: BLE001
                        continue
                m = rx.search(str((md or {}).get("twitter") or "")) if isinstance(md, dict) else None
                if not m:
                    continue
                await snap(client, tok, m.group(1), m.group(2), 0)
                delay = tok["recv"] + second_after_s - time.time()
                asyncio.get_running_loop().call_later(max(delay, 0), lambda tk=tok, h=m.group(1), sd=m.group(2):
                                                      asyncio.ensure_future(snap(client, tk, h, sd, 1)))

        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
            await asyncio.gather(*(worker(client) for _ in range(workers)))

    async def heartbeat(self) -> None:
        path = config.path("data") / "recorder_status.json"
        while time.monotonic() < self.stop_at:
            path.write_text(json.dumps({**self.status, "watched_tokens": len(self.watched),
                                        "at": datetime.now(timezone.utc).isoformat()}))
            for sink in (self.kol, self.pp, self.pump, self.amm, self.tw):
                sink._fh and sink._fh.flush()
            await asyncio.sleep(30)

    async def run(self, hours: float) -> None:
        self.stop_at = time.monotonic() + hours * 3600
        await asyncio.gather(self.kolscan(), self.pumpportal(), self.heartbeat(), self.tweet_snaps(),
                             self.chain_logs(PUMP_PROGRAM, self.pump, decode=True),
                             self.chain_logs(PUMPSWAP_PROGRAM, self.amm, decode=False))
        await asyncio.sleep(0)
        for sink in (self.kol, self.pp, self.pump, self.amm, self.tw):
            sink.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=8.0)
    ap.add_argument("--token-watch-min", type=float, default=60.0)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--tweets-only", action="store_true", help="only the X-post snapshot collector")
    a = ap.parse_args()
    r = Recorder(a.token_watch_min * 60, a.max_tokens)
    asyncio.run(r.run_tweets_only(a.hours) if a.tweets_only else r.run(a.hours))


if __name__ == "__main__":
    main()
