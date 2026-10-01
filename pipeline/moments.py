"""Transcript triage: find candidate decision moments worth inspecting.

This is a recall-oriented keyword pass over transcript segments. It produces
*pointers* (candidate_moments), not evidence. Every pointer is reviewed by
reading the surrounding transcript and the frames before/after it; only then
is a decision or observation recorded. Patterns are deliberately broad;
traders' slang varies, so extend PATTERNS as real transcripts show new phrasing.
"""

from __future__ import annotations

import re
from collections import Counter

import duckdb

from . import db
from .ids import stable_id

PATTERNS: dict[str, list[str]] = {
    "entry": [
        r"\b(i'?m|we'?re|i am|we are|got|getting) in\b",
        r"\b(bought|aped|aping|ape in|sniped|sniping|entered|entering|scooped|send(ing)? it|sent it|bidding)\b",
        r"\bbuy(ing)? (it|this|that|some|here|now)\b",
        r"\btook a (position|bag)\b",
    ],
    "add": [r"\b(add(ing|ed)? (more|to it|to this|here)|buy(ing)? more|doubl(e|ing) (down|up)|top(ping)? up|reload(ing|ed)?)\b"],
    "partial": [
        r"\b(took|taking|take|taken) (initials?|my initials?|half|some( profit)?|a little( off)?|profits?)\b",
        r"\bsold (half|some|a bit|a portion|initials?)\b",
        r"\b(initials|partials?)\b",
    ],
    "exit": [r"\b(sold|selling|sell (it|all|everything|the rest)|i'?m out|got out|exit(ed|ing)?|closed (it|the position)|dumped (it|my bag)|out of (it|this))\b"],
    "stop": [r"\b(stop(ped)? out|stop ?loss|cut (it|losses|the loss)|cutting (it|losses))\b"],
    "rug": [r"\b(rug(ged|pull|pulled)?|rugs|dev (sold|dumped|is selling|selling|dumping)|honeypot|rekt)\b"],
    "skip": [
        r"\b(skip(ping)?|i'?ll pass|passing( on (it|this|that))?|not touching|no thanks|not (buying|aping)|not for me)\b",
        r"\b(avoid(ing)?|stay(ing)? away|too (late|high|risky|early|bundled))\b",
        r"\b(looks (bad|weird|sketchy|rugged|botted)|don'?t like (it|this|that|the))\b",
    ],
    "missed": [r"\b(missed|should (have|'ve) (bought|aped|held|sold)|fomo|ran without me|sold too early|paper ?hand(s|ed)?)\b"],
    "discovery": [r"\b(new pairs?|just (launched|migrated|bonded)|migrat(ed|ing|ion)|final stretch|bond(ed|ing)|pulse|trending|alerts?|j7|tracker|tweet(ed)?|kols?|just came out|fresh (launch|coin|pair))\b"],
    "analysis": [r"\b(devs?|holders|top ?10|top ten|bundle(d|s)?|snipers?|insiders?|liquidity|market ?cap|mcap|volume|chart|candles?|narrative|ticker|cto|fresh wallets?|socials?)\b"],
    "strategy": [r"\b(i (always|never|only|usually)|my (strategy|rules?|setup)|what i look for|the key is|the trick is|you (always|never) want|rule of thumb)\b"],
}
DECISION_CATEGORIES = ("entry", "add", "partial", "exit", "stop", "rug", "skip", "missed")
_COMPILED = {cat: [re.compile(p, re.IGNORECASE) for p in pats] for cat, pats in PATTERNS.items()}


def classify_text(text: str) -> list[tuple[str, str]]:
    """[(category, matched_text), ...] for one piece of text (first match per category)."""
    hits = []
    for cat, regs in _COMPILED.items():
        for r in regs:
            m = r.search(text)
            if m:
                hits.append((cat, m.group(0)))
                break
    return hits


def find_moments(con: duckdb.DuckDBPyConnection, transcript_id: str) -> list[dict]:
    """Scan a transcript and store candidate moments (idempotent; keeps prior review status)."""
    db.require(con, "transcripts", "transcript_id", transcript_id)
    segs = con.execute("SELECT seq, start_s, text FROM transcript_segments WHERE transcript_id = ? ORDER BY seq",
                       [transcript_id]).fetchall()
    found = []
    for seq, start_s, text in segs:
        for cat, matched in classify_text(text):
            moment_id = stable_id("mom", transcript_id, seq, cat)
            prev = con.execute("SELECT review_status, decision_id, created_at FROM candidate_moments "
                               "WHERE moment_id = ?", [moment_id]).fetchone()
            db.upsert(con, "candidate_moments", {
                "moment_id": moment_id, "transcript_id": transcript_id, "seq": seq, "start_s": start_s,
                "category": cat, "matched_text": matched,
                "review_status": prev[0] if prev else "unreviewed",
                "decision_id": prev[1] if prev else None,
                "created_at": prev[2] if prev else db.now(),
            })
            found.append({"moment_id": moment_id, "seq": seq, "start_s": start_s, "category": cat,
                          "matched_text": matched, "text": text})
    return found


def busiest_windows(con: duckdb.DuckDBPyConnection, transcript_id: str, window_s: float = 120.0,
                    categories: tuple[str, ...] = DECISION_CATEGORIES, top: int = 20) -> list[dict]:
    """Rank fixed windows of the video by how many decision-language moments they contain.

    Useful for long streams: review the densest stretches first, then sweep the rest.
    """
    rows = con.execute(
        f"SELECT start_s, category FROM candidate_moments WHERE transcript_id = ? AND start_s IS NOT NULL "
        f"AND category IN ({', '.join('?' for _ in categories)})", [transcript_id, *categories]).fetchall()
    buckets: dict[int, Counter] = {}
    for start_s, cat in rows:
        buckets.setdefault(int(start_s // window_s), Counter())[cat] += 1
    ranked = sorted(buckets.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:top]
    return [{"start_s": b * window_s, "end_s": (b + 1) * window_s, "n": sum(c.values()), "by_category": dict(c)}
            for b, c in ranked]


def review_moment(con: duckdb.DuckDBPyConnection, moment_id: str, status: str,
                  decision_id: str | None = None) -> None:
    if status not in {"unreviewed", "confirmed", "false_positive"}:
        raise ValueError("status must be unreviewed | confirmed | false_positive")
    db.require(con, "candidate_moments", "moment_id", moment_id)
    db.require(con, "decisions", "decision_id", decision_id)
    con.execute("UPDATE candidate_moments SET review_status = ?, decision_id = coalesce(?, decision_id) "
                "WHERE moment_id = ?", [status, decision_id, moment_id])
