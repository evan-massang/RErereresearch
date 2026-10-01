"""Webpage / document ingestion: raw snapshot + extracted main text + outbound links."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urldefrag, urljoin

import duckdb
import trafilatura
from bs4 import BeautifulSoup, UnicodeDammit

from . import config, db
from .ids import stable_id
from .provenance import SourceUnavailable, register_artifact, sha256_bytes, tracked
from .sources.base import WebAdapter, WebPage

_EXT = {"text/html": ".html", "application/xhtml+xml": ".html", "application/json": ".json",
        "application/pdf": ".pdf", "text/plain": ".txt", "text/csv": ".csv"}


@dataclass
class Extracted:
    text: str | None
    extractor: str | None
    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    language: str | None = None
    sitename: str | None = None
    links: list[str] | None = None


def _mime(content_type: str | None) -> str:
    return (content_type or "text/html").split(";")[0].strip().lower()


def extract_html(content: bytes, url: str | None = None) -> Extracted:
    """Main-text extraction with trafilatura, BeautifulSoup as fallback."""
    markup = UnicodeDammit(content, is_html=True).unicode_markup or ""
    soup = BeautifulSoup(markup, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        href = urldefrag(urljoin(url or "", a["href"].strip()))[0]
        if href.startswith(("http://", "https://")) and href not in links:
            links.append(href)
    lang = soup.html.get("lang") if soup.html else None

    text = trafilatura.extract(markup, url=url, output_format="txt", include_comments=False,
                               include_tables=True, favor_recall=True)
    extractor = "trafilatura"
    if not text:
        for tag in soup(["script", "style", "noscript", "template"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True) or None
        extractor = "bs4_fallback" if text else None

    meta = trafilatura.extract_metadata(markup, default_url=url)
    published = None
    if meta and meta.date:
        try:
            published = datetime.fromisoformat(meta.date).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    title = (meta.title if meta else None) or (soup.title.string.strip() if soup.title and soup.title.string else None)
    return Extracted(text=text, extractor=extractor, title=title,
                     author=meta.author if meta else None, published_at=published,
                     language=lang, sitename=meta.sitename if meta else None, links=links[:5000])


def _extract(page: WebPage) -> Extracted:
    mime = _mime(page.content_type)
    if mime in ("text/html", "application/xhtml+xml"):
        return extract_html(page.content, page.final_url if page.final_url.startswith("http") else None)
    if mime == "application/json":
        try:
            return Extracted(text=json.dumps(json.loads(page.content), indent=1, ensure_ascii=False),
                             extractor="json")
        except ValueError:
            pass
    if mime.startswith("text/"):
        return Extracted(text=page.content.decode("utf-8", errors="replace"), extractor="plain")
    return Extracted(text=None, extractor=None)   # e.g. PDF: archived raw, no extractor yet


def ingest_web(
    con: duckdb.DuckDBPyConnection,
    uri: str,
    adapter: WebAdapter,
    *,
    canonical_url: str | None = None,
    is_synthetic: bool = False,
    notes: str | None = None,
) -> tuple[str, str]:
    """Fetch a page, archive the raw bytes, extract text. Returns (source_id, snapshot_id).

    ``canonical_url`` lets a locally saved copy be filed under the URL it came from.
    """
    with tracked(con, stage="web", adapter=adapter.name, uri=uri) as ev:
        page = adapter.fetch(uri)
        key_url = canonical_url or page.final_url
        source_id = stable_id("src", "web", key_url)
        ev.source_id = source_id
        digest = sha256_bytes(page.content)
        mime = _mime(page.content_type)
        raw_path = config.path("raw_web", source_id) / f"{digest[:16]}{_EXT.get(mime, '.bin')}"
        raw_path.write_bytes(page.content)
        artifact_id = register_artifact(con, source_id, "html" if "html" in mime else "document", raw_path,
                                        details={"headers": page.headers} if page.headers else None)
        ex = _extract(page)

        prev = con.execute("SELECT first_seen_at FROM sources WHERE source_id = ?", [source_id]).fetchone()
        now = db.now()
        db.upsert(con, "sources", {
            "source_id": source_id, "source_kind": "webpage" if "html" in mime else "document",
            "platform": "web", "external_id": None, "uri": uri, "canonical_url": key_url,
            "title": ex.title, "author": ex.author, "published_at": ex.published_at,
            "first_seen_at": prev[0] if prev else now, "last_fetched_at": now,
            "adapter": adapter.name, "metadata": {"sitename": ex.sitename, "content_type": page.content_type},
            "is_synthetic": is_synthetic, "notes": notes,
        })
        snapshot_id = stable_id("snap", source_id, digest)
        db.upsert(con, "web_snapshots", {
            "snapshot_id": snapshot_id, "source_id": source_id, "fetched_at": now,
            "http_status": page.status_code, "final_url": page.final_url,
            "content_type": page.content_type, "html_artifact_id": artifact_id,
            "content_sha256": digest, "text": ex.text, "extractor": ex.extractor,
            "word_count": len(ex.text.split()) if ex.text else 0, "language": ex.language,
            "links": ex.links, "page_metadata": {"title": ex.title, "author": ex.author,
                                                 "sitename": ex.sitename},
        })
        ev.details = {"snapshot_id": snapshot_id, "extractor": ex.extractor}
    return source_id, snapshot_id


def ingest_document(con: duckdb.DuckDBPyConnection, path: str, *, title: str | None = None,
                    canonical_url: str | None = None, is_synthetic: bool = False,
                    notes: str | None = None) -> tuple[str, str]:
    """Any local file (PDF, CSV, TXT, HTML) through the same snapshot path."""
    from .sources.local_adapter import FileWebAdapter

    source_id, snapshot_id = ingest_web(con, path, FileWebAdapter(), canonical_url=canonical_url,
                                        is_synthetic=is_synthetic, notes=notes)
    if title:
        con.execute("UPDATE sources SET title = ? WHERE source_id = ?", [title, source_id])
    return source_id, snapshot_id


__all__ = ["ingest_web", "ingest_document", "extract_html", "SourceUnavailable"]
