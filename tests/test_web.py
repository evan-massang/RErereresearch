import json

from pipeline import config
from pipeline.ingest_web import extract_html, ingest_document, ingest_web
from pipeline.sources import get_web_adapter
from tests.conftest import FIXTURES

PAGE = FIXTURES / "synthetic_page.html"


def test_extract_html_main_text_and_metadata():
    ex = extract_html(PAGE.read_bytes(), "https://synthetic.invalid/page")
    assert "alpha bravo charlie delta echo" in ex.text
    assert "script text should not be extracted" not in ex.text
    assert ex.title.startswith("SYNTHETIC")
    assert ex.author == "Synthetic Author"
    assert ex.language == "en"
    assert "https://synthetic.invalid/relative/page.html" in ex.links
    assert "https://example.invalid/about" in ex.links            # fragment stripped


def test_file_adapter_with_canonical_url(archive):
    sid, snap = ingest_web(archive, str(PAGE), get_web_adapter("file"),
                           canonical_url="https://synthetic.invalid/page", is_synthetic=True)
    src = archive.execute("SELECT source_kind, canonical_url, adapter, is_synthetic FROM sources").fetchone()
    assert src == ("webpage", "https://synthetic.invalid/page", "file", True)
    text, extractor, wc, html_art = archive.execute(
        "SELECT text, extractor, word_count, html_artifact_id FROM web_snapshots").fetchone()
    assert extractor == "trafilatura" and wc > 20
    raw = archive.execute("SELECT local_path, sha256 FROM artifacts WHERE artifact_id=?", [html_art]).fetchone()
    assert config.resolve(raw[0]).read_bytes() == PAGE.read_bytes()


def test_same_content_same_snapshot_changed_content_new_snapshot(archive, tmp_path):
    p = tmp_path / "page.html"
    p.write_text("<html><body><p>SYNTHETIC version one of a page with enough words to extract.</p></body></html>")
    a = ingest_web(archive, str(p), get_web_adapter("file"), canonical_url="https://synthetic.invalid/p", is_synthetic=True)
    b = ingest_web(archive, str(p), get_web_adapter("file"), canonical_url="https://synthetic.invalid/p", is_synthetic=True)
    assert a == b
    p.write_text("<html><body><p>SYNTHETIC version two of a page with enough words to extract.</p></body></html>")
    c = ingest_web(archive, str(p), get_web_adapter("file"), canonical_url="https://synthetic.invalid/p", is_synthetic=True)
    assert c[0] == a[0] and c[1] != a[1]
    assert archive.execute("SELECT count(*) FROM web_snapshots").fetchone()[0] == 2
    assert archive.execute("SELECT count(*) FROM sources").fetchone()[0] == 1


def test_non_html_documents(archive, tmp_path):
    j = tmp_path / "synthetic.json"
    j.write_text(json.dumps({"synthetic": True, "values": [1, 2]}))
    sid, _ = ingest_document(archive, str(j), title="SYNTHETIC json doc", is_synthetic=True)
    kind, title = archive.execute("SELECT source_kind, title FROM sources").fetchone()
    assert (kind, title) == ("document", "SYNTHETIC json doc")
    assert '"synthetic": true' in archive.execute("SELECT text FROM web_snapshots").fetchone()[0]

    pdf = tmp_path / "synthetic.pdf"
    pdf.write_bytes(b"%PDF-1.4 synthetic placeholder bytes")
    ingest_document(archive, str(pdf), is_synthetic=True)
    row = archive.execute("SELECT text, extractor FROM web_snapshots WHERE content_type='application/pdf'").fetchone()
    assert row == (None, None)                    # archived raw; no extractor yet
