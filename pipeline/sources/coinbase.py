"""Coinbase Exchange public market-data adapter (unauthenticated).

Endpoints: GET https://api.exchange.coinbase.com/products/<id> and
/products/<id>/candles?granularity=60&start=..&end=.. (max 300 candles per call).
Candle rows are [time, low, high, open, close, volume]; minutes without trades are absent.
Rate limit: public endpoints allow ~10 req/s per IP; callers should stay well below.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from .base import SourceUnavailable
from .http_adapter import DEFAULT_UA, _verify

BASE = "https://api.exchange.coinbase.com"


class CoinbaseExchangeAdapter:
    name = "coinbase"

    def __init__(self, timeout: float = 30.0, min_interval_s: float = 0.15, transport: httpx.BaseTransport | None = None):
        self.min_interval_s = min_interval_s
        self._last = 0.0
        self.client = httpx.Client(timeout=timeout, headers={"User-Agent": DEFAULT_UA}, verify=_verify(),
                                   transport=transport, follow_redirects=True)

    def _get(self, path: str, params: dict | None = None, retries: int = 6):
        for attempt in range(retries):
            wait = self.min_interval_s - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.client.get(BASE + path, params=params)
            except httpx.HTTPError as e:
                if attempt == retries - 1:
                    raise SourceUnavailable(f"{type(e).__name__}: {e}") from e
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(min(30, 2 ** attempt))
                continue
            if r.status_code == 404:
                raise SourceUnavailable(f"HTTP 404 for {path}", status="error")
            if r.status_code >= 400:
                raise SourceUnavailable(f"HTTP {r.status_code} for {path}: {r.text[:200]}",
                                        status="blocked" if r.status_code in (401, 403, 407, 451) else "error")
            return r.json()
        raise SourceUnavailable(f"retries exhausted for {path}")

    def product(self, product_id: str) -> dict:
        return self._get(f"/products/{product_id}")

    def candles_1m(self, product_id: str, start: int, end: int) -> list[list]:
        """1-minute candles with open time in [start, end) (unix s); end - start <= 300*60."""
        assert end - start <= 300 * 60
        iso = lambda s: datetime.fromtimestamp(s, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self._get(f"/products/{product_id}/candles",
                         {"granularity": 60, "start": iso(start), "end": iso(end - 60)})
        return sorted((r for r in rows if start <= r[0] < end), key=lambda r: r[0])

    def candles(self, product_id: str, start: int, end: int, granularity: int) -> list[list]:
        """Candles of any supported granularity with open time in [start, end); <= 300 per call."""
        assert (end - start) // granularity <= 300
        iso = lambda s: datetime.fromtimestamp(s, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self._get(f"/products/{product_id}/candles",
                         {"granularity": granularity, "start": iso(start), "end": iso(end - granularity)})
        return sorted((r for r in rows if start <= r[0] < end), key=lambda r: r[0])
