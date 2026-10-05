"""Binance public data archive adapter (data.binance.vision), USD-M futures.

Used because fapi.binance.com returns HTTP 451 from this container. Files are zipped CSVs:
futures/um/{monthly,daily}/klines/<SYM>/1m/<SYM>-1m-<period>.zip and
futures/um/monthly/fundingRate/<SYM>/<SYM>-fundingRate-<YYYY-MM>.zip.
"""

from __future__ import annotations

import io
import zipfile

import httpx
import pandas as pd

from .base import SourceUnavailable
from .http_adapter import DEFAULT_UA, _verify

BASE = "https://data.binance.vision/data/futures/um"


class BinanceVisionAdapter:
    name = "binance_vision"

    def __init__(self, timeout: float = 120.0, transport: httpx.BaseTransport | None = None):
        self.client = httpx.Client(timeout=timeout, headers={"User-Agent": DEFAULT_UA}, verify=_verify(),
                                   transport=transport, follow_redirects=True)
        self.bytes_downloaded = 0

    def _zip_csv(self, url: str) -> pd.DataFrame | None:
        try:
            r = self.client.get(url)
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"{type(e).__name__}: {e}") from e
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            raise SourceUnavailable(f"HTTP {r.status_code} for {url}")
        self.bytes_downloaded += len(r.content)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            raw = z.read(z.namelist()[0])
        first = raw.split(b"\n", 1)[0]
        header = 0 if first[:1].isalpha() else None
        return pd.read_csv(io.BytesIO(raw), header=header)

    def klines_1m(self, symbol: str, period: str, freq: str = "monthly") -> pd.DataFrame | None:
        """period 'YYYY-MM' (monthly) or 'YYYY-MM-DD' (daily). Returns open_time_ms, close or None if absent."""
        df = self._zip_csv(f"{BASE}/{freq}/klines/{symbol}/1m/{symbol}-1m-{period}.zip")
        if df is None:
            return None
        df = df.iloc[:, [0, 4]]
        df.columns = ["open_time_ms", "close"]
        return df.astype({"open_time_ms": "int64", "close": "float64"})

    def funding_monthly(self, symbol: str, month: str) -> pd.DataFrame | None:
        df = self._zip_csv(f"{BASE}/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{month}.zip")
        if df is None:
            return None
        df = df.iloc[:, [0, 2]] if df.shape[1] >= 3 else df
        df.columns = ["calc_time_ms", "funding_rate"]
        return df.astype({"calc_time_ms": "int64", "funding_rate": "float64"})
