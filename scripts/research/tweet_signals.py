"""Point-in-time features of the X post linked from a launch, vs the launch's outcome.

Features that existed at launch: author followers / following / account age / verified, post age at launch
(launch time - post time), reply/quote/media flags, text length and keyword flags, whether the author or
this exact post was already linked by earlier launches (same-day record), rank of this launch among coins
for the same post. Like/view counts are NOT used (they accumulate after launch).

    python scripts/research/tweet_signals.py            # train stats (launches before 16:15 UTC)
    python scripts/research/tweet_signals.py --record   # + findings
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402

META = ROOT / "data/raw/web/token_metadata"
TW = ROOT / "data/raw/web/tweets"
RX = re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)/status/(\d+)")
TRAIN_END = 1790874900.0 - 3600


def build() -> pd.DataFrame:
    d = pd.read_parquet(config.path("data") / "processed" / "solo_signals.parquet")
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    uri = dict(con.execute("SELECT mint, uri FROM curve_creates").fetchall())
    rows = []
    for r in d.sort_values("created").itertuples():
        u = uri.get(r.mint) or ""
        f = META / (u.rstrip("/").split("/")[-1].replace(".json", "")[:80] + ".json")
        try:
            md = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        m = RX.search(md.get("twitter") or "")
        if not m:
            continue
        tf = TW / f"{m.group(2)}.json"
        if not tf.exists():
            continue
        t = json.loads(tf.read_text())
        if t.get("missing"):
            rows.append({"mint": r.mint, "created": r.created, "migrated": r.migrated, "peak_30m_x": r.peak_30m_x,
                         "status": m.group(2), "post_missing": True})
            continue
        a = t.get("author") or {}
        ts = t.get("created_timestamp")
        joined = a.get("joined")
        try:
            joined_ts = datetime.strptime(joined, "%a %b %d %H:%M:%S %z %Y").timestamp() if joined else None
        except ValueError:
            joined_ts = None
        text = (t.get("text") or "")
        rows.append({
            "mint": r.mint, "created": r.created, "migrated": r.migrated, "peak_30m_x": r.peak_30m_x,
            "status": m.group(2), "post_missing": False, "author": (a.get("screen_name") or m.group(1)).lower(),
            "followers": a.get("followers"), "following": a.get("following"), "author_posts": a.get("tweets"),
            "verified": bool(a.get("verified")), "account_age_d": (r.created - joined_ts) / 86400 if joined_ts else None,
            "post_age_min": (r.created - ts) / 60 if ts else None, "is_reply": t.get("is_reply"),
            "is_quote": bool(t.get("quote_of")), "has_media": t.get("has_media"), "text_len": len(text),
            "mentions_ca": bool(re.search(r"[1-9A-HJ-NP-Za-km-z]{32,44}", text)), "lang": t.get("lang"),
            "text": text[:280], "vamp": r.vamp, "dev_prior_migrations": r.dev_prior_migrations,
        })
    df = pd.DataFrame(rows)
    # same-day records, point in time
    df = df.sort_values("created")
    df["rank_for_post"] = df.groupby("status").cumcount() + 1
    seen_auth, seen_auth_mig, out_prev, out_prev_mig = [], [], {}, {}
    for r in df.itertuples():
        a = getattr(r, "author", None)
        seen_auth.append(out_prev.get(a, 0))
        seen_auth_mig.append(out_prev_mig.get(a, 0))
        if a:
            out_prev[a] = out_prev.get(a, 0) + 1
    df["author_prior_coins"] = seen_auth
    return df


def stats(df: pd.DataFrame) -> dict:
    t = df[(df.created < TRAIN_END) & (~df.post_missing)]
    base = float(t.migrated.mean())
    g = {
        "post age < 5 min": t.post_age_min < 5, "post age 5-60 min": (t.post_age_min >= 5) & (t.post_age_min < 60),
        "post age 1-24 h": (t.post_age_min >= 60) & (t.post_age_min < 1440), "post age > 1 day": t.post_age_min >= 1440,
        "followers < 1k": t.followers < 1000, "followers 1k-10k": (t.followers >= 1000) & (t.followers < 10000),
        "followers 10k-100k": (t.followers >= 10000) & (t.followers < 100000), "followers 100k-1M": (t.followers >= 100000) & (t.followers < 1e6),
        "followers > 1M": t.followers >= 1e6, "verified": t.verified, "account < 30 d old": t.account_age_d < 30,
        "reply": t.is_reply == True, "quote": t.is_quote, "has media": t.has_media == True,  # noqa: E712
        "text mentions a CA": t.mentions_ca, "first coin for this post": t.rank_for_post == 1,
        "2nd+ coin for this post": t.rank_for_post >= 2, "author linked by 3+ earlier coins": t.author_prior_coins >= 3,
        "post missing (deleted) at fetch": df[df.created < TRAIN_END].post_missing,
    }
    out = {"n": len(t), "base_migration_rate": round(base, 4), "groups": {}}
    for k, m in g.items():
        src = df[df.created < TRAIN_END] if k.startswith("post missing") else t
        x = src[m.reindex(src.index).fillna(False).astype(bool)]
        if len(x):
            out["groups"][k] = {"n": int(len(x)), "migration_rate": round(float(x.migrated.mean()), 4),
                                "lift": round(float(x.migrated.mean()) / base, 2) if base else None,
                                "share_peak_30m_ge_3x": round(float((x.peak_30m_x >= 3).mean()), 3)}
    return out


if __name__ == "__main__":
    df = build()
    df.to_parquet(config.path("data") / "processed" / "tweet_signals.parquet")
    s = stats(df)
    print(f"{len(df)} launches with a fetched post; train n={s['n']} base={s['base_migration_rate']}")
    for k, v in s["groups"].items():
        print(f"{k:36} n={v['n']:5} migr={v['migration_rate']:.4f} lift={v['lift']:5.2f} peak>=3x={v['share_peak_30m_ge_3x']:.3f}")
    if "--record" in sys.argv:
        from pipeline import db, findings, observations
        from pipeline.ingest_web import ingest_document
        ex = "claude:tweet-signals-2026-10-02"
        p = ROOT / "research/observations/evidence_tweet_signals_2026-10-02.json"
        p.write_text(json.dumps(s, indent=1))
        con = db.connect()
        kept = findings.clear_previous(con, ex, ex)
        sid, snap = ingest_document(con, str(p), title="Linked X post features vs migration (train)",
                                    canonical_url="stream://pump_curve/2026-10-02/tweet-signals")
        obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="document", kind="signal_study",
                                           extractor=ex, status="reviewed", value=s,
                                           content="Point-in-time features of linked X posts (fxtwitter) vs migration.")
        g = s["groups"]
        f = lambda k: f"{g[k]['migration_rate']:.1%} ({g[k]['lift']}x, n={g[k]['n']})"
        new = findings.add_finding(
            con, trader_id=None, funnel_stage="narrative", evidence_type="observed",
            statement=f"For launches linking an X post (train, base {s['base_migration_rate']:.2%}): post under 5 min old "
                      f"at launch {f('post age < 5 min')}; 5-60 min {f('post age 5-60 min')}; over a day old "
                      f"{f('post age > 1 day')}. Author under 1k followers {f('followers < 1k')}; 10k-100k "
                      f"{f('followers 10k-100k')}; over 1M {f('followers > 1M')}. First coin for the post "
                      f"{f('first coin for this post')} vs later coins {f('2nd+ coin for this post')}.",
            evidence=[("observation", obs, "supports")], n_supporting=g["first coin for this post"]["n"],
            n_observable=s["n"], confidence=0.6, notes=f"{ex}; like/view counts excluded (not point-in-time)")
        for k in kept:
            findings.set_finding_status(con, k, "superseded", "Rebuilt.", superseded_by=new)
        print("recorded")
