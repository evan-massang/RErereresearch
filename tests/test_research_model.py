"""Decisions, readings, findings, hypotheses, candidates/leads, moments, windows, exports. All data SYNTHETIC."""

import csv
import json
import shutil

import pytest

from pipeline import (annotations, candidates, config, decisions, exports, findings, frames, moments,
                      observations)
from pipeline.ingest_transcript import ingest_caption_file
from pipeline.ingest_video import ingest_video
from pipeline.ingest_web import ingest_document, ingest_web
from pipeline.sources import get_video_adapter, get_web_adapter
from tests.conftest import FIXTURES


@pytest.fixture
def video(archive, synthetic_video):
    res = ingest_video(archive, str(synthetic_video), get_video_adapter("local"), media="video",
                       languages=["en"], is_synthetic=True)
    trader = annotations.add_trader(archive, "SYNTHETIC-TRADER-D", is_synthetic=True)
    return archive, res.source_id, res.transcript_ids[0], trader


# ------------------------------------------------------------------ parsing helpers

@pytest.mark.parametrize("text,value", [("$12.4K", 12400), ("1.2M", 1.2e6), ("45%", 45), ("1,234", 1234),
                                         ("0.5", 0.5), ("abc", None), ("12.4K holders", None)])
def test_parse_display_number(text, value):
    assert decisions.parse_display_number(text) == value


@pytest.mark.parametrize("text,value", [("12s", 12), ("3m", 180), ("1h 5m", 3900), ("2d", 172800),
                                         ("500ms", 0.5), ("soon", None)])
def test_parse_display_duration(text, value):
    assert decisions.parse_display_duration(text) == value


# ------------------------------------------------------------------ decisions & readings

def test_decision_with_readings_and_wide_view(video):
    con, sid, tid, trader = video
    tok = decisions.add_token(con, identification="ticker_visible", ticker="SYNA", is_synthetic=True)
    dec = decisions.add_decision(con, trader_id=trader, source_id=sid, decision="BUY", video_ts_s=4.0,
                                 token_id=tok, extraction_confidence=0.8, extractor="human",
                                 stated_reason="SYNTHETIC said reason", inferred_reason="SYNTHETIC inference",
                                 is_synthetic=True)
    f_before, f_close, f_after = frames.extract_frames(con, sid, timestamps=[1.0, 3.5, 5.0])
    decisions.add_reading(con, dec, "market_cap_usd", observed_via="screen", value_text="$10K", frame_id=f_before)
    decisions.add_reading(con, dec, "market_cap_usd", observed_via="screen", value_text="$12.4K", frame_id=f_close)
    decisions.add_reading(con, dec, "market_cap_usd", observed_via="screen", value_text="$15K", frame_id=f_after)
    decisions.add_reading(con, dec, "token_age_s", observed_via="screen", value_text="3m", frame_id=f_close)
    decisions.add_reading(con, dec, "x_axiom_example_field", observed_via="screen", value_text="SYN",
                          frame_id=f_close)
    offsets = sorted(r[0] for r in con.execute("SELECT as_of_offset_s FROM decision_metrics "
                                               "WHERE metric = 'market_cap_usd'").fetchall())
    assert offsets == [-3.0, -0.5, 1.0]
    row = con.execute("SELECT market_cap_usd, token_age_s, top10_pct, ticker, stated_reason, inferred_reason "
                      "FROM v_decisions_wide WHERE decision_id = ?", [dec]).fetchone()
    # closest reading at/before the decision; unseen metrics stay NULL
    assert row == (12400.0, 180.0, None, "SYNA", "SYNTHETIC said reason", "SYNTHETIC inference")


@pytest.mark.parametrize("kwargs,match", [
    ({"metric": "made_up_metric", "observed_via": "screen", "value_num": 1}, "unknown metric"),
    ({"metric": "holders", "observed_via": "screen", "value_num": 1}, "must cite the frame"),
    ({"metric": "holders", "observed_via": "said", "value_num": 1}, "must cite the observation"),
    ({"metric": "holders", "observed_via": "derived"}, "needs value_num or value_text"),
    ({"metric": "holders", "observed_via": "eyeballed", "value_num": 1}, "observed_via"),
])
def test_reading_validation(video, kwargs, match):
    con, sid, tid, trader = video
    dec = decisions.add_decision(con, trader_id=trader, source_id=sid, decision="SKIP", extraction_confidence=0.5,
                                 extractor="human", is_synthetic=True)
    with pytest.raises(ValueError, match=match):
        decisions.add_reading(con, dec, **kwargs)


@pytest.mark.parametrize("kwargs,match", [
    ({"decision": "YOLO"}, "decision must be"),
    ({"extraction_confidence": 2}, "extraction_confidence"),
    ({"position_size": 1.0}, "position_size_unit"),
    ({"result_pct": 50.0}, "result_basis"),
    ({"video_ts_s": 999.0}, "outside the video"),
])
def test_decision_validation(video, kwargs, match):
    con, sid, tid, trader = video
    base = dict(trader_id=trader, source_id=sid, decision="BUY", extraction_confidence=0.5, extractor="human",
                is_synthetic=True)
    with pytest.raises(ValueError, match=match):
        decisions.add_decision(con, **{**base, **kwargs})


def test_tokens_dedupe_by_mint_and_mint_conflicts(archive):
    a = decisions.add_token(archive, identification="ca_visible", mint="SYNTHMINT1", ticker="A", is_synthetic=True)
    assert decisions.add_token(archive, identification="ca_visible", mint="SYNTHMINT1", is_synthetic=True) == a
    b = decisions.add_token(archive, identification="spoken", ticker="B", is_synthetic=True)
    with pytest.raises(ValueError, match="merge"):
        decisions.set_token_mint(archive, b, "SYNTHMINT1")
    decisions.set_token_mint(archive, b, "SYNTHMINT2", confidence=0.9, note="SYNTHETIC wallet match")
    assert archive.execute("SELECT mint, identification FROM tokens WHERE token_id = ?", [b]).fetchone() == \
        ("SYNTHMINT2", "onchain_match")


def test_import_decisions_is_atomic(video, tmp_path):
    con, sid, tid, trader = video
    good = {"decision": {"trader_id": trader, "source_id": sid, "decision": "SKIP", "extraction_confidence": 0.6,
                         "extractor": "claude"},
            "readings": [{"metric": "holders", "observed_via": "derived", "value_num": 12}]}
    bad = {"decision": {"trader_id": trader, "source_id": sid, "decision": "SKIP", "extraction_confidence": 0.6,
                        "extractor": "claude"},
           "readings": [{"metric": "holders", "observed_via": "screen", "value_num": 12}]}   # no frame
    f = tmp_path / "d.jsonl"
    f.write_text(json.dumps(good) + "\n" + json.dumps(bad) + "\n")
    with pytest.raises(ValueError, match="line 2"):
        decisions.import_decisions_jsonl(con, f, is_synthetic=True)
    assert con.execute("SELECT count(*) FROM decisions").fetchone()[0] == 0
    f.write_text(json.dumps(good) + "\n")
    assert len(decisions.import_decisions_jsonl(con, f, is_synthetic=True)) == 1


# ------------------------------------------------------------------ findings & hypotheses

def _said(con, sid, trader, text="SYNTHETIC: I never chase green candles"):
    return observations.add_observation(con, source_id=sid, modality="said", kind="quote", content=text,
                                        trader_id=trader, extractor="human", is_synthetic=True)


def test_evidence_type_rules(video):
    con, sid, tid, trader = video
    other = annotations.add_trader(con, "SYNTHETIC-OTHER-TRADER", is_synthetic=True)
    said = _said(con, sid, trader)
    screen = observations.add_observation(con, source_id=sid, modality="screen", kind="setup",
                                          content="SYNTHETIC pullback visible", trader_id=trader,
                                          extractor="human", is_synthetic=True)
    common = dict(trader_id=trader, funnel_stage="entry", is_synthetic=True)

    stated = findings.add_finding(con, evidence_type="stated", statement="SYNTHETIC stated",
                                  evidence=[("observation", said, "supports")], **common)
    with pytest.raises(ValueError, match="'said'"):
        findings.add_finding(con, evidence_type="stated", statement="x",
                             evidence=[("observation", screen, "supports")], **common)
    with pytest.raises(ValueError, match="different trader"):
        findings.add_finding(con, evidence_type="stated", statement="x", trader_id=other, funnel_stage="entry",
                             evidence=[("observation", said, "supports")], is_synthetic=True)

    with pytest.raises(ValueError, match="n_supporting"):
        findings.add_finding(con, evidence_type="observed", statement="x",
                             evidence=[("observation", screen, "supports")], **common)
    observed = findings.add_finding(con, evidence_type="observed", statement="SYNTHETIC 1 of 1 entries after pullback",
                                    evidence=[("observation", screen, "supports")], n_supporting=1,
                                    n_observable=1, **common)

    with pytest.raises(ValueError, match="derived_from"):
        findings.add_finding(con, evidence_type="inferred", statement="x", evidence=[], **common)
    inferred = findings.add_finding(con, evidence_type="inferred", statement="SYNTHETIC inferred rule",
                                    evidence=[("finding", observed, "derived_from"), ("finding", stated, "derived_from")],
                                    **common)

    with pytest.raises(ValueError, match="validation or holdout"):
        findings.add_finding(con, evidence_type="validated", statement="x",
                             evidence=[("finding", inferred, "derived_from")], **common)
    # nothing half-written after refusals
    assert con.execute("SELECT count(*) FROM findings").fetchone()[0] == 3
    assert findings.check_integrity(con) == {}
    # an out-of-band "upgrade" is caught
    con.execute("UPDATE findings SET evidence_type = 'validated' WHERE finding_id = ?", [inferred])
    assert inferred in findings.check_integrity(con)


def test_hypothesis_iterations_need_reasons(video):
    con, sid, tid, trader = video
    f1 = findings.add_finding(con, trader_id=trader, funnel_stage="entry", evidence_type="stated",
                              statement="SYNTHETIC", evidence=[("observation", _said(con, sid, trader), "supports")],
                              is_synthetic=True)
    with pytest.raises(ValueError, match="at least one finding"):
        findings.add_hypothesis(con, statement="s", measurable_definition="d", rationale="r", is_synthetic=True)
    h1 = findings.add_hypothesis(con, statement="SYNTHETIC h1", measurable_definition="d1", rationale="r1",
                                 basis_finding_ids=[f1], is_synthetic=True)
    with pytest.raises(ValueError, match="refinement"):
        findings.add_hypothesis(con, statement="h2", measurable_definition="d2", rationale="threshold tweak",
                                parent_id=h1, basis_finding_ids=[f1], is_synthetic=True)
    f2 = findings.add_finding(con, trader_id=trader, funnel_stage="entry", evidence_type="stated",
                              statement="SYNTHETIC new evidence",
                              evidence=[("observation", _said(con, sid, trader, "SYNTHETIC: wait for buyers"), "supports")],
                              is_synthetic=True)
    h2 = findings.add_hypothesis(con, statement="SYNTHETIC h2", measurable_definition="d2", rationale="new evidence",
                                 parent_id=h1, basis_finding_ids=[f2], is_synthetic=True)
    assert [x["hypothesis_id"] for x in findings.hypothesis_lineage(con, h2)] == [h1, h2]


# ------------------------------------------------------------------ candidates & leads

def test_candidates_merge_and_status(archive):
    a = candidates.add_candidate(archive, "https://www.synthetic.invalid/v/1/", discovered_via="manual",
                                 priority="low", discovery_evidence={"n": 1}, is_synthetic=True)
    b = candidates.add_candidate(archive, "https://synthetic.invalid/v/1", discovered_via="manual",
                                 priority="high", discovery_evidence={"n": 2}, is_synthetic=True)
    assert a == b
    pri, ev = archive.execute("SELECT priority, discovery_evidence FROM source_candidates").fetchone()
    assert pri == "high" and len(json.loads(ev)) == 2
    with pytest.raises(ValueError, match="source_id"):
        candidates.set_candidate_status(archive, a, "ingested", "x")


def test_import_leads_then_fetching_the_page_verifies_quotes(archive, tmp_path):
    counts = candidates.import_leads(archive, FIXTURES / "synthetic_leads.json", is_synthetic=True)
    assert counts["identities"] == 2 and counts["candidates"] == 2 and counts["open_questions"] == 1
    statuses = dict(archive.execute("SELECT platform, verification_status FROM trader_identities").fetchall())
    assert statuses == {"x": "probable", "wallet": "lead"}          # never 'verified' from search alone
    cited = archive.execute("SELECT count(*) FROM sources WHERE source_kind = 'search_citation' "
                            "AND last_fetched_at IS NULL").fetchone()[0]
    assert cited >= 3
    assert archive.execute("SELECT count(*) FROM observations WHERE quote_verified IS NOT NULL").fetchone()[0] == 0

    page = tmp_path / "profile.html"
    page.write_text("<html><body><article><p>SYNTHETIC page. The synthetic seed posts as @synthetic_seed "
                    "and nothing else of note is written here for the extractor to keep.</p></article></body></html>")
    ingest_web(archive, str(page), get_web_adapter("file"), canonical_url="https://synthetic-a.invalid/profile",
               is_synthetic=True)
    res = observations.reverify_quotes(archive)
    assert res["now_verified"] >= 1
    verified = archive.execute("SELECT quote FROM observations WHERE quote_verified").fetchall()
    assert ("synthetic seed posts as @synthetic_seed",) in verified

    trader = annotations.trader_by_slug(archive, "synthetic-seed")
    page_md = exports.render_identity(archive, trader).read_text()
    assert "probable" in page_md and "SYNTHETIC token ticker" in page_md


def test_ledger_excludes_synthetic_unless_asked(archive):
    candidates.import_leads(archive, FIXTURES / "synthetic_leads.json", is_synthetic=True)
    assert candidates.ledger_rows(archive) == []
    rows = candidates.ledger_rows(archive, include_synthetic=True)
    kinds = {r["ledger_kind"] for r in rows}
    assert kinds == {"source", "candidate"}
    path = candidates.export_ledger(archive)
    with open(path) as f:
        assert next(csv.reader(f)) == candidates.LEDGER_COLUMNS


# ------------------------------------------------------------------ moments, windows, exports

def test_moments_and_review(video, tmp_path):
    con, sid, tid, trader = video
    vtt = tmp_path / "decisions.vtt"
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nSYNTHETIC ok i'm in on this one\n\n"
                   "00:00:02.000 --> 00:00:03.000\nSYNTHETIC skip that, too bundled\n\n"
                   "00:00:03.000 --> 00:00:04.000\nSYNTHETIC dev is selling, i'm out\n\n"
                   "00:00:04.000 --> 00:00:05.000\nSYNTHETIC nothing here\n")
    t2 = ingest_caption_file(con, sid, vtt, language="en")
    found = moments.find_moments(con, t2)
    cats = {(m["seq"], m["category"]) for m in found}
    assert {(0, "entry"), (1, "skip"), (2, "exit"), (2, "rug")} <= cats
    assert not any(m["seq"] == 3 for m in found)
    mid = next(m["moment_id"] for m in found if m["category"] == "skip")
    moments.review_moment(con, mid, "confirmed")
    moments.find_moments(con, t2)                       # re-scan keeps the review
    assert con.execute("SELECT review_status FROM candidate_moments WHERE moment_id = ?", [mid]).fetchone()[0] == "confirmed"
    top = moments.busiest_windows(con, t2, window_s=2.0)
    assert top[0]["n"] >= 2


def test_decision_window_frames(video):
    con, sid, tid, trader = video
    ids = frames.extract_decision_window(con, sid, 3.0, before=2.0, after=2.0, step=1.0, dense_radius=0.5,
                                         dense_step=0.25, adaptive=True, change_threshold=0.2)
    rows = con.execute(f"SELECT timestamp_s, anchor_s, scene_score FROM frames WHERE frame_id IN "
                       f"({', '.join('?' for _ in ids)}) ORDER BY 1", ids).fetchall()
    times = [r[0] for r in rows]
    assert times[0] == 1.0 and times[-1] == 5.0
    assert {2.5, 2.75, 3.0, 3.25, 3.5} <= set(times)            # dense around the anchor
    assert all(r[1] == 3.0 for r in rows)
    assert any(r[2] is not None and r[2] >= 0.2 for r in rows)  # the cut at 3.0 s was flagged
    assert frames.window_timestamps(0.5, before=5, after=1, step=1, dense_radius=0, dense_step=1,
                                    duration=1.0) == [0.5]       # clipped to the video


def test_exports(video):
    con, sid, tid, trader = video
    moments.find_moments(con, tid)
    out = exports.export_all(con)
    assert out["transcripts"] == 0 and out["worksheets"] == 0       # synthetic excluded
    written = exports.export_transcripts(con, include_synthetic=True)
    assert written and "[00:00:00]" in written[0].read_text()
    ws = exports.render_worksheet(con, sid).read_text()
    assert "Candidate decision moments" in ws and "SYNTHETIC test clip" in ws
    for f in config.path("observations").glob("*.csv"):
        assert f.read_text().count("\n") == 1                       # header only: nothing real yet


def test_reregister_keeps_identity_and_refuses_changed_definition(video):
    con, sid, tid, trader = video
    f1 = findings.add_finding(con, trader_id=trader, funnel_stage="entry", evidence_type="stated",
                              statement="SYNTHETIC", evidence=[("observation", _said(con, sid, trader), "supports")],
                              is_synthetic=True)
    kw = dict(statement="HX: SYNTHETIC", measurable_definition="d1", rationale="r", basis_finding_ids=[f1],
              is_synthetic=True)
    h = findings.reregister_hypothesis(con, "HX:", **kw)
    created = con.execute("SELECT created_at FROM hypotheses WHERE hypothesis_id = ?", [h]).fetchone()[0]
    assert findings.reregister_hypothesis(con, "HX:", **kw) == h
    assert con.execute("SELECT created_at FROM hypotheses WHERE hypothesis_id = ?", [h]).fetchone()[0] == created
    assert con.execute("SELECT count(*) FROM hypothesis_basis WHERE hypothesis_id = ?", [h]).fetchone()[0] == 1
    with pytest.raises(ValueError, match="different measurable definition"):
        findings.reregister_hypothesis(con, "HX:", **{**kw, "measurable_definition": "d2"})


def test_integrity_flags_hypothesis_whose_basis_was_deleted(video):
    con, sid, tid, trader = video
    f1 = findings.add_finding(con, trader_id=trader, funnel_stage="entry", evidence_type="stated",
                              statement="SYNTHETIC", evidence=[("observation", _said(con, sid, trader), "supports")],
                              is_synthetic=True)
    h = findings.add_hypothesis(con, statement="SYNTHETIC h", measurable_definition="d", rationale="r",
                                basis_finding_ids=[f1], is_synthetic=True)
    assert h not in findings.check_integrity(con)
    con.execute("DELETE FROM finding_evidence WHERE finding_id = ?", [f1])
    con.execute("DELETE FROM findings WHERE finding_id = ?", [f1])
    assert "no longer exist" in findings.check_integrity(con)[h][0]


def test_clear_previous_keeps_findings_a_hypothesis_rests_on(video):
    con, sid, tid, trader = video
    f1 = findings.add_finding(con, trader_id=trader, funnel_stage="entry", evidence_type="stated", statement="SYNTHETIC a",
                              evidence=[("observation", _said(con, sid, trader), "supports")], notes="SYNTHETIC-TAG",
                              is_synthetic=True)
    f2 = findings.add_finding(con, trader_id=trader, funnel_stage="entry", evidence_type="stated", statement="SYNTHETIC b",
                              evidence=[("observation", _said(con, sid, trader), "supports")], notes="SYNTHETIC-TAG",
                              is_synthetic=True)
    findings.add_hypothesis(con, statement="SYNTHETIC h", measurable_definition="d", rationale="r",
                            basis_finding_ids=[f1], is_synthetic=True)
    assert findings.clear_previous(con, "SYNTHETIC-TAG", "none") == [f1]
    left = {r[0] for r in con.execute("SELECT finding_id FROM findings WHERE notes = 'SYNTHETIC-TAG'").fetchall()}
    assert left == {f1} and f2 not in left
    assert findings.check_integrity(con) == {}
