"""Hyperliquid public positions adapter (unauthenticated, read-only) for H-LIQMAP.

Endpoints (no keys, no orders):
  POST https://api.hyperliquid.xyz/info  {"type": "clearinghouseState", "user": <0x..>}   weight 2 (HL docs)
  POST https://api.hyperliquid.xyz/info  {"type": "metaAndAssetCtxs"}                    weight 20 (HL docs)
  wss://api.hyperliquid.xyz/ws  subscriptions {"type": "trades", "coin": c} and {"type": "bbo", "coin": c}

HL REST limit: 1200 weight per minute per IP, shared by every process on this container. Callers budget it with
``WeightBucket``. Trades messages carry ``users`` = [buyer, seller] (HL docs), which is how addresses are discovered.
Position objects carry ``liquidationPx`` (null when the account has no liquidation price), checked live 2026-10-05.

Only the fields H-LIQMAP needs are kept (``meme_positions``): coin, szi, entryPx, liquidationPx, positionValue,
leverage value and cross flag. Everything else in the account state is dropped.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass

import httpx

from .base import SourceUnavailable
from .http_adapter import _verify

INFO = "https://api.hyperliquid.xyz/info"
WS_URL = "wss://api.hyperliquid.xyz/ws"
WEIGHT = {"clearinghouseState": 2, "metaAndAssetCtxs": 20}
UA = "RErereresearch-liqmap/1.0 (research; budgeted polling)"


def _f(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


class RateLimited(SourceUnavailable):
    """HTTP 429 from HL."""


class WeightBucket:
    """Token bucket in HL weight units: at most ``per_min`` weight per rolling minute (refilled continuously)."""

    def __init__(self, per_min: float, burst: float | None = None):
        self.rate = per_min / 60.0
        self.cap = burst if burst is not None else max(per_min / 20.0, 20.0)
        self.tokens = self.cap
        self.t = time.monotonic()
        self.spent = 0.0
        self._lock = asyncio.Lock()

    async def take(self, w: float):
        async with self._lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.cap, self.tokens + (now - self.t) * self.rate)
                self.t = now
                if self.tokens >= w:
                    self.tokens -= w
                    self.spent += w
                    return
                await asyncio.sleep((w - self.tokens) / self.rate)


@dataclass
class Position:
    coin: str
    szi: float
    entry_px: float | None
    liq_px: float | None
    position_value: float | None
    leverage: int | None
    cross: bool | None


class HyperliquidPositionsAdapter:
    name = "hyperliquid_positions"

    def __init__(self, bucket: WeightBucket, timeout: float = 20.0, client: httpx.AsyncClient | None = None):
        self.bucket = bucket
        self.client = client or httpx.AsyncClient(timeout=timeout, verify=_verify(), headers={"User-Agent": UA},
                                                  http2=False, limits=httpx.Limits(max_connections=8))

    async def info(self, body: dict):
        await self.bucket.take(WEIGHT.get(body["type"], 20))
        try:
            r = await self.client.post(INFO, json=body)
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"{type(e).__name__}: {e}") from e
        if r.status_code == 429:
            raise RateLimited("HTTP 429 from HL info")
        if r.status_code >= 400:
            raise SourceUnavailable(f"HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    async def clearinghouse_state(self, user: str) -> dict:
        return await self.info({"type": "clearinghouseState", "user": user})

    async def meta_and_ctxs(self) -> list[dict]:
        meta, ctxs = await self.info({"type": "metaAndAssetCtxs"})
        out = []
        for u, c in zip(meta["universe"], ctxs):
            out.append(dict(coin=u["name"], mark=_f(c.get("markPx")), mid=_f(c.get("midPx")),
                            oracle=_f(c.get("oraclePx")), oi=_f(c.get("openInterest")),
                            day_ntl_vlm=_f(c.get("dayNtlVlm")), funding=_f(c.get("funding"))))
        return out

    async def aclose(self):
        await self.client.aclose()

    # ---------- parsing (pure) ----------
    @staticmethod
    def meme_positions(state: dict, coins: set[str]) -> list[Position]:
        out = []
        for ap in state.get("assetPositions") or []:
            p = ap.get("position") or {}
            if p.get("coin") not in coins:
                continue
            szi = _f(p.get("szi"))
            if not szi:
                continue
            lev = p.get("leverage") or {}
            out.append(Position(coin=p["coin"], szi=szi, entry_px=_f(p.get("entryPx")), liq_px=_f(p.get("liquidationPx")),
                                position_value=_f(p.get("positionValue")),
                                leverage=int(lev["value"]) if lev.get("value") is not None else None,
                                cross=(lev.get("type") == "cross") if lev.get("type") else None))
        return out

    @staticmethod
    def ws_subscriptions(coins) -> list[str]:
        subs = []
        for c in coins:
            subs.append(json.dumps({"method": "subscribe", "subscription": {"type": "trades", "coin": c}}))
            subs.append(json.dumps({"method": "subscribe", "subscription": {"type": "bbo", "coin": c}}))
        return subs

    @staticmethod
    def parse_ws(raw: str | bytes):
        """Yield ('trade', dict) / ('bbo', dict) events from one WS message."""
        m = json.loads(raw)
        ch, d = m.get("channel"), m.get("data")
        if ch == "trades" and isinstance(d, list):
            for t in d:
                users = t.get("users") or [None, None]
                yield "trade", dict(coin=t["coin"], px=float(t["px"]), sz=float(t["sz"]),
                                    side=1 if t.get("side") == "B" else -1, exch_ms=int(t["time"]),
                                    tid=int(t.get("tid") or 0), buyer=users[0], seller=users[1])
        elif ch == "bbo" and d and all(d.get("bbo") or [None]):
            b, a = d["bbo"]
            yield "bbo", dict(coin=d["coin"], bid=float(b["px"]), ask=float(a["px"]), bid_sz=float(b["sz"]),
                              ask_sz=float(a["sz"]), exch_ms=int(d["time"]))
