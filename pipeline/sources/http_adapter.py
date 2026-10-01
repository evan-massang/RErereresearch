"""HTTP adapter for web pages and plain JSON/HTML APIs (httpx)."""

from __future__ import annotations

import os

import httpx

from .base import SourceUnavailable, WebPage

DEFAULT_UA = "Mozilla/5.0 (X11; Linux x86_64) research-archive/0.1 (+https://github.com/)"


def _verify() -> str | bool:
    # Respect the container's proxy CA bundle when one is configured.
    return os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE") or True


class HttpWebAdapter:
    name = "http"

    def __init__(self, timeout: float = 30.0, user_agent: str = DEFAULT_UA, headers: dict | None = None,
                 transport: httpx.BaseTransport | None = None):
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent, **(headers or {})}
        self.transport = transport  # injectable for offline tests

    def fetch(self, uri: str) -> WebPage:
        try:
            with httpx.Client(follow_redirects=True, timeout=self.timeout,
                              headers=self.headers, verify=_verify(), transport=self.transport) as client:
                r = client.get(uri)
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"{type(e).__name__}: {e}") from e
        if r.status_code in (401, 403, 407, 429, 451):
            raise SourceUnavailable(f"HTTP {r.status_code} for {uri}", status="blocked")
        if r.status_code >= 400:
            raise SourceUnavailable(f"HTTP {r.status_code} for {uri}", status="error")
        return WebPage(
            uri=uri, final_url=str(r.url), status_code=r.status_code, content=r.content,
            content_type=r.headers.get("content-type"), headers=dict(r.headers),
        )
